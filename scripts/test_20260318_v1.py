#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
20260318测试脚本 v1
新功能：
1. 合并连续相同打标的片段
2. 除F01和F06外，其他片段时长必须>15秒
3. 每个素材的每个场景只能使用一次
"""

import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
import subprocess


class VideoCutter20260318:
    """20260318版本视频剪辑器"""

    def __init__(self, json_dir: str, output_dir: str, material_csv: str):
        self.json_dir = Path(json_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # 加载素材URL
        self.material_df = pd.read_csv(material_csv)
        self.material_urls = dict(zip(
            self.material_df['id'].astype(str),
            self.material_df['video_url']
        ))

        # 测试素材ID（排除不存在的1337588）
        self.material_ids = ['1327758', '1327761', '1328846', '1327760', '1327757', '1327756', '1337586', '1337589']

        # 剪辑方案
        self.schemes = {
            "方案1": ["F01-强开局/吸睛钩子", "F04-金手指觉醒/身份曝光", "F02-背景速递/设定交代", "F06-悬念结尾/付费卡点"],
            "方案2": ["F02-背景速递/设定交代", "F03-极限施压/受辱", "F04-金手指觉醒/身份曝光", "F06-悬念结尾/付费卡点"]
        }

        # 场景使用记录：{(material_id, tag): used_count}
        self.scene_usage: Dict[Tuple[str, str], int] = {}

    def load_and_merge_segments(self, material_id: str) -> Tuple[Optional[str], List[Dict[str, Any]]]:
        """
        加载素材并合并连续相同打标的片段
        返回：(video_url, merged_segments_list)
        """
        json_file = self.json_dir / f"{material_id}.json"

        if not json_file.exists():
            return None, []

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not data.get('success'):
                return None, []

            video_url = data.get('video_url', '')
            segments = data.get('result', {}).get('segments', [])

            if not segments:
                return video_url, []

            # 合并连续相同打标的片段
            merged_segments = []
            current_group = [segments[0]]

            for i in range(1, len(segments)):
                current_tag = segments[i].get('narrative_function_tag')
                prev_tag = current_group[-1].get('narrative_function_tag')

                if current_tag == prev_tag:
                    # 相同打标，加入当前组
                    current_group.append(segments[i])
                else:
                    # 不同打标，保存当前组并开始新组
                    merged_segments.append(self._merge_segment_group(current_group))
                    current_group = [segments[i]]

            # 最后一组
            merged_segments.append(self._merge_segment_group(current_group))

            return video_url, merged_segments

        except Exception as e:
            print(f"  ⚠️  加载{material_id}失败: {e}")
            return None, []

    def _merge_segment_group(self, group: List[Dict[str, Any]]) -> Dict[str, Any]:
        """将连续相同打标的片段合并为一个"""
        if len(group) == 1:
            return group[0]

        # 合并信息
        first_seg = group[0]
        last_seg = group[-1]

        merged = {
            'segment_id': f"{first_seg['segment_id']}-{last_seg['segment_id']}",
            'start_time': first_seg['start_time'],
            'end_time': last_seg['end_time'],
            'duration': last_seg['end_time'] - first_seg['start_time'],
            'main_location': f"{first_seg.get('main_location', '')} → {last_seg.get('main_location', '')}",
            'plot_summary': ' | '.join([seg.get('plot_summary', '') for seg in group]),
            'narrative_function_tag': first_seg.get('narrative_function_tag'),
            'emotion_trope_tags': list(set([
                tag for seg in group
                for tag in seg.get('emotion_trope_tags', [])
            ])),
            'merged_from': len(group),  # 记录合并了几个片段
            'original_segments': [seg['segment_id'] for seg in group]
        }

        return merged

    def check_duration_requirement(self, tag: str, duration: float) -> bool:
        """
        检查时长要求
        F01和F06不限制时长，其他必须>15秒
        """
        if tag in ['F01-强开局/吸睛钩子', 'F06-悬念结尾/付费卡点']:
            return True
        return duration > 15

    def can_use_scene(self, material_id: str, tag: str) -> bool:
        """
        检查场景是否可以使用
        - 每个素材的每个场景只能使用一次
        - 但F06-悬念结尾/付费卡点可以复用
        """
        # F06可以复用，直接返回True
        if tag == 'F06-悬念结尾/付费卡点':
            return True

        key = (material_id, tag)
        current_usage = self.scene_usage.get(key, 0)

        # 如果合并场景，merged_from > 1，说明是组合场景，也只能使用一次
        return current_usage == 0

    def mark_scene_used(self, material_id: str, tag: str):
        """标记场景已使用"""
        key = (material_id, tag)
        self.scene_usage[key] = self.scene_usage.get(key, 0) + 1

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

                video_url, segments = self.load_and_merge_segments(material_id)
                if video_url is None:
                    continue

                # 查找匹配的片段
                for seg in segments:
                    seg_tag = seg.get('narrative_function_tag')

                    if seg_tag != tag:
                        continue

                    # 检查时长要求
                    duration = seg.get('duration', 0)
                    if not self.check_duration_requirement(tag, duration):
                        print(f"\n⚠️  {material_id} 有 {tag} 片段但时长不符: {duration}秒")
                        continue

                    # 检查场景是否可用
                    if not self.can_use_scene(material_id, tag):
                        print(f"\n⚠️  {material_id} 的 {tag} 场景已使用")
                        continue

                    # 找到可用片段
                    segment_info = {
                        'material_id': material_id,
                        'video_url': video_url,
                        'tag': tag,
                        'start_time': seg.get('start_time', 0),
                        'end_time': seg.get('end_time', 0),
                        'duration': duration,
                        'plot_summary': seg.get('plot_summary', ''),
                        'main_location': seg.get('main_location', ''),
                        'merged_from': seg.get('merged_from', 1),
                        'original_segments': seg.get('original_segments', [seg.get('segment_id')])
                    }

                    selected_segments.append(segment_info)
                    used_materials.add(material_id)
                    self.mark_scene_used(material_id, tag)

                    print(f"\n✓ 找到片段: {tag}")
                    print(f"  来源素材: {material_id}")
                    print(f"  时间: {segment_info['start_time']}s - {segment_info['end_time']}s ({duration}s)")
                    print(f"  场景: {segment_info['main_location']}")
                    if seg.get('merged_from', 1) > 1:
                        print(f"  🔗 合并了 {seg['merged_from']} 个片段: {seg['original_segments']}")
                    print(f"  已使用素材: {len(used_materials)}/{len(self.material_ids)}")

                    found = True
                    break

                if found:
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

    def cut_segment(self, seg: Dict[str, Any], index: int, scheme_name: str) -> Optional[str]:
        """剪辑单个片段"""
        material_id = seg['material_id']
        start = seg['start_time']
        end = seg['end_time']
        duration = end - start

        segment_file = self.output_dir / f"{scheme_name}_片段{index+1}_{material_id}.mp4"

        cmd = (
            f'ffmpeg -y -ss {start} -i "{seg["video_url"]}" '
            f'-t {duration} '
            f'-c:v libx264 -preset fast -crf 23 -c:a aac '
            f'-threads 4 '
            f'"{segment_file}"'
        )

        print(f"\n📹 剪辑: {seg['tag']}")
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
                return str(segment_file)
            else:
                print(f"   ❌ 失败: {result.stderr[:200]}")
                return None

        except subprocess.TimeoutExpired:
            print(f"   ⏱️  超时")
            return None
        except Exception as e:
            print(f"   ❌ 错误: {e}")
            return None

    def process_scheme(self, scheme_result: Dict[str, Any]) -> bool:
        """处理单个方案"""
        scheme_name = scheme_result['scheme_name']
        segments = scheme_result['selected_segments']

        if not segments:
            return False

        print(f"\n{'='*80}")
        print(f"🎬 处理 {scheme_name}")
        print('='*80)

        # 1. 剪辑片段
        segment_files = []
        current_time = 0

        for i, seg in enumerate(segments):
            segment_file = self.cut_segment(seg, i, scheme_name)

            if segment_file:
                segment_files.append(segment_file)
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
                print(f"   📁 路径: {output_video}")
            else:
                print(f"   ❌ 合并失败: {result.stderr[:200]}")
                return False

        except Exception as e:
            print(f"   ❌ 错误: {e}")
            return False

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
                    '剧情摘要': seg['plot_summary'],
                    '合并片段数': seg.get('merged_from', 1),
                    '原始片段ID': str(seg.get('original_segments', []))
                })

        df = pd.DataFrame(plan_data)
        output_file = self.output_dir / '剪辑计划.csv'
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n✓ 剪辑计划已保存: {output_file}")

    def process_all_schemes(self, auto_confirm: bool = False):
        """处理所有方案"""
        print("\n" + "="*80)
        print("🚀 20260318测试 v1 - 开始")
        print("="*80)
        print(f"📂 JSON目录: {self.json_dir}")
        print(f"📁 输出目录: {self.output_dir}")
        print(f"📋 素材数量: {len(self.material_ids)}")
        print(f"🎬 方案数量: {len(self.schemes)}")
        print(f"🔒 限制: 每个素材的每个场景只能使用一次（F06除外）")
        print(f"♻️  F06可以复用")
        print(f"📏 时长: 除F01/F06外必须>15秒")
        print(f"🔗 新功能: 连续相同打标自动合并")

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
        print(f"这将下载、剪辑并合并视频，可能需要较长时间")
        print('='*80)

        should_continue = True
        if not auto_confirm:
            try:
                response = input("\n是否继续？(yes/no): ")
                should_continue = response.lower() in ['yes', 'y']
            except EOFError:
                # 非交互模式，自动继续
                print("\n非交互模式，自动继续...")
                should_continue = True

        if not should_continue:
            print("已取消执行")
            return

        for result in scheme_results:
            if not result['missing_tags']:
                self.process_scheme(result)

        print("\n" + "="*80)
        print("✅ 处理完成！")
        print("="*80)

        # 显示输出文件
        print(f"\n📁 输出文件:")
        for file in self.output_dir.glob("*.mp4"):
            size_mb = file.stat().st_size / (1024 * 1024)
            print(f"  - {file.name} ({size_mb:.1f}MB)")

        print(f"\n📋 剪辑计划: {self.output_dir / '剪辑计划.csv'}")


def main():
    """主函数"""
    import sys

    # 支持命令行参数 --auto 自动确认
    auto_confirm = '--auto' in sys.argv or '-y' in sys.argv

    cutter = VideoCutter20260318(
        json_dir='/Users/wangchenyi/video_ad_analyzer/test_20260311/output',
        output_dir='/Users/wangchenyi/material_remake_tool/20260318v1',
        material_csv='/Users/wangchenyi/material_remake_tool/material_list.csv'
    )

    cutter.process_all_schemes(auto_confirm=auto_confirm)


if __name__ == '__main__':
    main()
