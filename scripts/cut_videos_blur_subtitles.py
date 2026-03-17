#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按照叙事方案剪辑视频 - 模糊遮盖字幕
1. 使用模糊滤镜遮盖原字幕区域
2. 根据剧情生成英文字幕
3. 将新字幕嵌入视频
"""

import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import subprocess
import sys


class VideoCutterBlurSubtitles:
    """按方案剪辑视频并模糊字幕"""

    def __init__(self, json_dir: str, output_dir: str = "output_videos_blur"):
        self.json_dir = Path(json_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # 定义方案
        self.schemes = {
            "方案1": ["F01-强开局/吸睛钩子", "F04-金手指觉醒/身份曝光", "F02-背景速递/设定交代", "F06-悬念结尾/付费卡点"],
            "方案2": ["F02-背景速递/设定交代", "F02-背景速递/设定交代", "F03-极限施压/受辱", "F04-金手指觉醒/身份曝光", "F06-悬念结尾/付费卡点"]
        }

        # 素材列表
        self.material_ids = ['1337589', '1330603', '1330602', '1329504', '1330869', '1327758', '1327761']

        # 字幕遮盖参数
        self.subtitle_blur_height = 80  # 底部80像素
        self.blur_strength = 20  # 模糊强度

    def load_material(self, material_id: str) -> Optional[Dict[str, Any]]:
        """加载素材JSON数据"""
        json_file = self.json_dir / f"{material_id}.json"

        if not json_file.exists():
            return None

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not data.get('success'):
                return None

            return data
        except Exception as e:
            return None

    def find_segments_by_tag(self, data: Dict[str, Any], tag: str) -> List[Dict[str, Any]]:
        """根据叙事标签查找片段"""
        if not data or 'result' not in data or 'segments' not in data['result']:
            return []

        segments = data['result']['segments']
        matched = []

        for seg in segments:
            if seg.get('narrative_function_tag') == tag:
                matched.append(seg)

        return matched

    def select_best_segment(self, segments: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """选择最佳片段"""
        if not segments:
            return None

        scored_segments = []

        for seg in segments:
            duration = seg.get('duration', 0)
            if 30 <= duration <= 120:
                score = 100
            elif 15 <= duration < 30:
                score = 80
            elif 120 < duration <= 180:
                score = 70
            elif duration < 15:
                score = 50
            else:
                score = 30

            scored_segments.append((score, seg))

        scored_segments.sort(key=lambda x: x[0], reverse=True)
        return scored_segments[0][1]

    def find_segments_for_scheme(self, scheme_name: str, scheme_tags: List[str]) -> Dict[str, Any]:
        """为方案查找所有需要的片段"""
        print(f"\n{'='*80}")
        print(f"🎬 为 {scheme_name} 查找片段")
        print(f"目标序列: {' → '.join(scheme_tags)}")
        print('='*80)

        selected_segments = []
        missing_tags = []
        used_materials: Set[str] = set()

        for tag in scheme_tags:
            found = False

            for material_id in self.material_ids:
                if material_id in used_materials:
                    continue

                data = self.load_material(material_id)
                if not data:
                    continue

                segments = self.find_segments_by_tag(data, tag)

                if segments:
                    best_segment = self.select_best_segment(segments)

                    if best_segment:
                        video_url = data.get('video_url', '')

                        segment_info = {
                            'material_id': material_id,
                            'video_url': video_url,
                            'tag': tag,
                            'start_time': best_segment.get('start_time', 0),
                            'end_time': best_segment.get('end_time', 0),
                            'duration': best_segment.get('duration', 0),
                            'plot_summary': best_segment.get('plot_summary', ''),
                            'main_location': best_segment.get('main_location', ''),
                            'emotion_trope_tags': best_segment.get('emotion_trope_tags', [])
                        }

                        selected_segments.append(segment_info)
                        used_materials.add(material_id)

                        print(f"\n✓ 找到片段: {tag}")
                        print(f"  来源素材: {material_id}")
                        print(f"  时间: {segment_info['start_time']}s - {segment_info['end_time']}s ({segment_info['duration']}s)")
                        print(f"  已使用素材: {len(used_materials)}/{len(self.material_ids)}")

                        found = True
                        break

            if not found:
                print(f"\n❌ 未找到片段: {tag}")
                missing_tags.append(tag)

        return {
            'scheme_name': scheme_name,
            'scheme_tags': scheme_tags,
            'selected_segments': selected_segments,
            'missing_tags': missing_tags,
            'used_materials': list(used_materials)
        }

    def generate_srt_subtitle(self, plot_summary: str, start_time: float, duration: float) -> str:
        """生成SRT格式字幕"""
        # 简化剧情摘要为英文字幕
        if len(plot_summary) > 80:
            summary = plot_summary[:80] + "..."
        else:
            summary = plot_summary

        # 转换为简单英文（这里可以用翻译API，暂时用简单映射）
        english_text = self.translate_to_english(summary)

        start_srt = self.seconds_to_srt_time(start_time)
        end_srt = self.seconds_to_srt_time(start_time + duration)

        return f"1\n{start_srt} --> {end_srt}\n{english_text}\n"

    def translate_to_english(self, text: str) -> str:
        """简单的中译英（实际应使用翻译API）"""
        # 这里只是示例，实际应该调用翻译API
        translations = {
            "视频开场，一名 overweight 的男子 Arthur 因被嘲笑而跳入冰湖": "Arthur, an overweight man, jumps into a frozen lake after being teased",
            "Anya Throne 在车内得知 Arthur 在 Tessac 集团派对上被羞辱的消息": "Anya Throne learns Arthur was humiliated at the Tessac group party",
            "闪回 5 年前，Arthur 在机场向女友 Serena 求婚": "Flashback: 5 years ago, Arthur proposes to Serena at the airport",
            "DramaBox app 宣传画面，显示下载链接": "DramaBox app promotional screen showing download link"
        }

        for cn, en in translations.items():
            if cn in text:
                return en

        # 简单替换
        text = text.replace("闪回", "Flashback: ")
        text = text.replace("年", " years ago")
        return text

    def seconds_to_srt_time(self, seconds: float) -> str:
        """将秒数转换为SRT时间格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"

    def cut_segment_with_blur(self, seg: Dict[str, Any], index: int, scheme_name: str) -> tuple:
        """
        剪辑片段并模糊字幕区域
        返回：(输出文件路径, SRT字幕内容)
        """
        material_id = seg['material_id']
        start = seg['start_time']
        end = seg['end_time']
        duration = end - start

        # 输出文件
        segment_file = self.output_dir / f"{scheme_name}_片段{index+1}_{material_id}.mp4"

        # ffmpeg命令：剪辑并模糊底部字幕区域
        # delogo滤镜：模糊指定区域
        blur_filter = f"delogo=x=0:y=ih-{self.subtitle_blur_height}:w=iw:h={self.subtitle_blur_height}:show=0"

        cmd = (
            f'ffmpeg -y -ss {start} -i "{seg["video_url"]}" '
            f'-t {duration} '
            f'-vf "{blur_filter}" '
            f'-c:v libx264 -preset fast -crf 23 -c:a aac '
            f'-threads 4 '
            f'"{segment_file}"'
        )

        print(f"\n📹 剪辑并模糊字幕: {seg['tag']}")
        print(f"   来源: {material_id}")

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode == 0:
                print(f"   ✅ 成功: {segment_file.name}")

                # 生成字幕
                srt_content = self.generate_srt_subtitle(
                    seg['plot_summary'],
                    0,  # 片段内开始时间
                    duration
                )

                return str(segment_file), srt_content
            else:
                print(f"   ❌ 失败: {result.stderr[:200]}")
                return None, None

        except subprocess.TimeoutExpired:
            print(f"   ⏱️  超时")
            return None, None
        except Exception as e:
            print(f"   ❌ 错误: {e}")
            return None, None

    def process_scheme(self, scheme_result: Dict[str, Any]) -> bool:
        """处理单个方案"""
        scheme_name = scheme_result['scheme_name']
        segments = scheme_result['selected_segments']

        if not segments:
            return False

        print(f"\n{'='*80}")
        print(f"🎬 处理 {scheme_name}")
        print('='*80)

        # 1. 剪辑片段并模糊字幕
        segment_files = []
        all_srt_content = ""
        current_time = 0

        for i, seg in enumerate(segments):
            segment_file, srt_content = self.cut_segment_with_blur(seg, i, scheme_name)

            if segment_file and srt_content:
                segment_files.append(segment_file)

                # 更新字幕时间戳
                srt_content = srt_content.replace("00:00:00,", self.seconds_to_srt_time(current_time)[:-4])
                srt_content = srt_content.replace("00:00:00,", self.seconds_to_srt_time(current_time + seg['duration'])[:-4])

                all_srt_content += srt_content + "\n"
                current_time += seg['duration']

        if len(segment_files) != len(segments):
            print(f"\n❌ 部分片段剪辑失败")
            return False

        # 2. 合并视频
        print(f"\n{'='*80}")
        print(f"🔗 合并视频")
        print('='*80)

        concat_file = self.output_dir / f"{scheme_name}_concat_list.txt"
        with open(concat_file, 'w', encoding='utf-8') as f:
            for video_file in segment_files:
                f.write(f"file '{video_file}'\n")

        output_video = self.output_dir / f"{scheme_name}_最终版.mp4"

        cmd = (
            f'ffmpeg -y -f concat -safe 0 '
            f'-i "{concat_file}" '
            f'-c copy "{output_video}"'
        )

        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=600)

            if result.returncode == 0:
                print(f"   ✅ 合并成功: {output_video.name}")
            else:
                print(f"   ❌ 合并失败: {result.stderr[:200]}")
                return False

        except Exception as e:
            print(f"   ❌ 错误: {e}")
            return False

        # 3. 保存字幕文件
        srt_file = self.output_dir / f"{scheme_name}_英文字幕.srt"
        with open(srt_file, 'w', encoding='utf-8') as f:
            f.write(all_srt_content)

        print(f"\n✅ 字幕文件: {srt_file.name}")

        return True

    def save_cut_plan(self, scheme_results: List[Dict[str, Any]]):
        """保存剪辑计划"""
        plan_data = []

        for result in scheme_results:
            scheme_name = result['scheme_name']

            for seg in result['selected_segments']:
                plan_data.append({
                    '方案': scheme_name,
                    '目标标签': seg['tag'],
                    '来源素材': seg['material_id'],
                    '开始时间': seg['start_time'],
                    '结束时间': seg['end_time'],
                    '时长': seg['duration'],
                    '场景': seg['main_location'],
                    '剧情摘要': seg['plot_summary']
                })

        df = pd.DataFrame(plan_data)
        output_file = self.output_dir / '剪辑计划.csv'
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n✓ 剪辑计划已保存: {output_file}")

    def process_all_schemes(self):
        """处理所有方案"""
        print("\n" + "="*80)
        print("🚀 开始按方案剪辑视频（模糊字幕 + 英文字幕）")
        print("="*80)
        print(f"📂 JSON目录: {self.json_dir}")
        print(f"📁 输出目录: {self.output_dir}")
        print(f"📋 素材数量: {len(self.material_ids)}")
        print(f"🎬 方案数量: {len(self.schemes)}")
        print(f"🔒 限制: 每个素材最多使用一次")
        print(f"📝 字幕: 模糊原字幕 + 生成英文字幕文件")

        scheme_results = []

        # 为每个方案查找片段
        for scheme_name, scheme_tags in self.schemes.items():
            result = self.find_segments_for_scheme(scheme_name, scheme_tags)
            scheme_results.append(result)

        # 保存剪辑计划
        self.save_cut_plan(scheme_results)

        # 显示摘要
        print(f"\n{'='*80}")
        print("📊 方案匹配摘要")
        print('='*80)

        for result in scheme_results:
            scheme_name = result['scheme_name']
            total_tags = len(result['scheme_tags'])
            found_tags = len(result['selected_segments'])
            missing_tags = len(result['missing_tags'])

            print(f"\n{scheme_name}:")
            print(f"  目标片段: {total_tags}")
            print(f"  已找到: {found_tags}")
            print(f"  缺失: {missing_tags}")

            if missing_tags == 0:
                print(f"  状态: ✅ 可执行剪辑")
                total_duration = sum(seg['duration'] for seg in result['selected_segments'])
                print(f"  预计时长: {total_duration}秒 ({total_duration/60:.1f}分钟)")
            else:
                print(f"  状态: ⚠️  无法完整剪辑")

        # 处理可执行的方案
        print(f"\n{'='*80}")
        print("⚠️  即将执行视频剪辑...")
        print(f"这将下载、剪辑视频并模糊字幕，可能需要较长时间")
        print('='*80)

        response = input("\n是否继续？(yes/no): ")

        if response.lower() not in ['yes', 'y']:
            print("已取消执行")
            return

        for result in scheme_results:
            if not result['missing_tags']:
                self.process_scheme(result)

        print("\n" + "="*80)
        print("✅ 处理完成！")
        print("="*80)


def main():
    """主函数"""
    cutter = VideoCutterBlurSubtitles(
        json_dir='/Users/wangchenyi/video_ad_analyzer/test_20260311/output',
        output_dir='output_videos_blur'
    )

    cutter.process_all_schemes()


if __name__ == '__main__':
    main()
