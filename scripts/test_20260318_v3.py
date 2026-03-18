#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
20260318测试 v2 - 新增规则：最后非F06场景去掉1秒
继承v1的素材分配逻辑（避免同一方案重复使用素材）
"""

import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple, Optional
import subprocess


class Test20260318V2:
    """20260318测试 v2"""

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

        # 完整的素材ID列表（与v1一致）
        self.material_ids = ['1327758', '1327761', '1328846', '1327760', '1327757', '1327756', '1337586', '1337589']

        # 场景使用记录 (material_id, tag) -> count
        self.scene_usage: Dict[Tuple[str, str], int] = {}

        # 缓存每个素材的segments
        self.material_cache: Dict[str, Tuple[Optional[str], List[Dict[str, Any]]]] = {}

    def load_and_merge_segments(self, material_id: str) -> Tuple[Optional[str], List[Dict[str, Any]]]:
        """加载素材并合并连续相同打标的片段（带缓存）"""
        if material_id in self.material_cache:
            return self.material_cache[material_id]

        json_file = self.json_dir / f"{material_id}.json"

        if not json_file.exists():
            self.material_cache[material_id] = (None, [])
            return None, []

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not data.get('success'):
                self.material_cache[material_id] = (None, [])
                return None, []

            video_url = data.get('video_url', '')
            segments = data.get('result', {}).get('segments', [])

            if not segments:
                self.material_cache[material_id] = (video_url, [])
                return video_url, []

            # 合并连续相同打标的片段
            merged_segments = []
            current_group = [segments[0]]

            for i in range(1, len(segments)):
                current_tag = segments[i].get('narrative_function_tag')
                prev_tag = current_group[-1].get('narrative_function_tag')

                if current_tag == prev_tag:
                    current_group.append(segments[i])
                else:
                    merged_segments.append(self._merge_segment_group(current_group, segments))
                    current_group = [segments[i]]

            # 最后一组
            merged_segments.append(self._merge_segment_group(current_group, segments))

            self.material_cache[material_id] = (video_url, merged_segments)
            return video_url, merged_segments

        except Exception as e:
            self.material_cache[material_id] = (None, [])
            return None, []

    def _merge_segment_group(self, group: List[Dict[str, Any]], all_segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """合并片段组，并标记是否是最后片段"""
        if len(group) == 1:
            seg = group[0]
            seg['is_last_segment'] = (seg == all_segments[-1])
            return seg

        first = group[0]
        last = group[-1]

        plot_summaries = [s.get('plot_summary', '') for s in group if s.get('plot_summary')]
        combined_summary = ' '.join(plot_summaries)

        merged = {
            'segment_id': first.get('segment_id'),
            'narrative_function_tag': first.get('narrative_function_tag'),
            'start_time': first.get('start_time', 0),
            'end_time': last.get('end_time', 0),
            'duration': last.get('end_time', 0) - first.get('start_time', 0),
            'plot_summary': combined_summary,
            'main_location': first.get('main_location', ''),
            'merged_from': len(group),
            'is_last_segment': (last == all_segments[-1])  # 检查最后片段是否是素材的最后片段
        }

        return merged

    def can_use_scene(self, material_id: str, tag: str) -> bool:
        """检查场景是否可以使用（F06可复用）"""
        if tag == 'F06-悬念结尾/付费卡点':
            return True

        key = (material_id, tag)
        current_usage = self.scene_usage.get(key, 0)
        return current_usage == 0

    def mark_scene_used(self, material_id: str, tag: str):
        """标记场景已使用"""
        if tag != 'F06-悬念结尾/付费卡点':
            key = (material_id, tag)
            self.scene_usage[key] = self.scene_usage.get(key, 0) + 1

    def find_segments_for_scheme(self, scheme_name: str, scheme_tags: List[str]) -> Dict[str, Any]:
        """为方案查找所有需要的片段（避免同一方案重复使用素材）"""
        print(f"\n{'='*80}")
        print(f"🎬 为 {scheme_name} 查找片段")
        print(f"目标序列: {' → '.join(scheme_tags)}")
        print('='*80)

        selected_segments = []
        missing_tags = []
        used_materials: Set[str] = set()  # 当前方案已使用的素材

        for tag in scheme_tags:
            found = False

            for material_id in self.material_ids:
                # 跳过当前方案已使用的素材
                if material_id in used_materials:
                    continue

                video_url, segments = self.load_and_merge_segments(material_id)
                if video_url is None:
                    continue

                # 查找匹配的片段
                for seg in segments:
                    if seg.get('narrative_function_tag') != tag:
                        continue

                    # 检查时长要求
                    duration = seg.get('duration', 0)
                    if tag not in ['F01-强开局/吸睛钩子', 'F06-悬念结尾/付费卡点'] and duration <= 15:
                        continue

                    # 检查场景是否可用
                    if not self.can_use_scene(material_id, tag):
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
                        'is_last_segment': seg.get('is_last_segment', False)
                    }

                    selected_segments.append(segment_info)
                    used_materials.add(material_id)
                    self.mark_scene_used(material_id, tag)

                    print(f"\n✓ 找到片段: {tag}")
                    print(f"  来源素材: {material_id}")
                    print(f"  时间: {segment_info['start_time']}s - {segment_info['end_time']}s ({duration}s)")
                    if seg.get('merged_from', 1) > 1:
                        print(f"  🔗 合并了 {seg['merged_from']} 个片段")
                    if seg.get('is_last_segment'):
                        print(f"  ⚠️  这是素材的最后片段")

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
        tag = seg['tag']

        # 新规则：如果是最后片段且不是F06，去掉最后1秒
        is_last = seg.get('is_last_segment', False)
        if is_last and tag != 'F06-悬念结尾/付费卡点':
            print(f"   ⚠️  最后片段，去掉最后1秒: {end}s -> {end-1}s")
            end = end - 1

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

        for i, seg in enumerate(segments):
            segment_file = self.cut_segment(seg, i, scheme_name)

            if segment_file:
                segment_files.append(segment_file)
            else:
                return False

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
                size_mb = output_video.stat().st_size / (1024 * 1024)
                total_duration = sum(seg['duration'] for seg in segments)
                print(f"   ✅ 合并成功: {output_video.name}")
                print(f"   📦 大小: {size_mb:.1f}MB")
                print(f"   ⏱️  时长: {total_duration}秒 ({total_duration/60:.1f}分钟)")
                return True
            else:
                print(f"   ❌ 合并失败: {result.stderr[:200]}")
                return False

        except Exception as e:
            print(f"   ❌ 错误: {e}")
            return False

    def process_all(self):
        """处理所有方案"""
        print("\n" + "="*80)
        print("🚀 开始 20260318测试 v2")
        print("📋 新规则: 最后非F06场景去掉1秒")
        print("="*80)

        # 定义4个方案
        schemes = [
            ("方案1", ["F01-强开局/吸睛钩子", "F04-金手指觉醒/身份曝光",
                      "F02-背景速递/设定交代", "F06-悬念结尾/付费卡点"]),
            ("方案2", ["F02-背景速递/设定交代", "F03-极限施压/受辱",
                      "F04-金手指觉醒/身份曝光", "F06-悬念结尾/付费卡点"]),
            ("方案3", ["F03-极限施压/受辱", "F05-高潮打脸/绝地反击",
                      "F07-情感拉扯/发糖", "F06-悬念结尾/付费卡点"]),
            ("方案4", ["F03-极限施压/受辱", "F05-高潮打脸/绝地反击",
                      "F07-情感拉扯/发糖", "F06-悬念结尾/付费卡点"]),
        ]

        # 为每个方案查找片段
        scheme_results = []
        for scheme_name, scheme_tags in schemes:
            result = self.find_segments_for_scheme(scheme_name, scheme_tags)
            scheme_results.append(result)

        # 保存剪辑计划
        self.save_cut_plan(scheme_results)

        # 处理方案
        results = []
        for result in scheme_results:
            if not result['missing_tags']:
                success = self.process_scheme(result)
                results.append((result['scheme_name'], success))
            else:
                results.append((result['scheme_name'], False))

        # 输出总结
        print("\n" + "="*80)
        print("📊 测试总结")
        print('='*80)

        for scheme_name, success in results:
            status = "✅ 成功" if success else "❌ 失败"
            print(f"  {scheme_name}: {status}")

        print("\n" + "="*80)
        print("✅ 处理完成！")
        print('='*80)

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
                    '是否最后片段': seg.get('is_last_segment', False)
                })

        df = pd.DataFrame(plan_data)
        output_file = self.output_dir / '剪辑计划.csv'
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n✓ 剪辑计划已保存: {output_file}")


def main():
    tester = Test20260318V2(
        json_dir='/Users/wangchenyi/video_ad_analyzer/test_20260311/output',
        output_dir='/Users/wangchenyi/material_remake_tool/20260318v3',
        material_csv='/Users/wangchenyi/material_remake_tool/material_list.csv'
    )

    tester.process_all()


if __name__ == '__main__':
    main()
