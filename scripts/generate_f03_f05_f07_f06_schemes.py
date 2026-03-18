#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成尽可能多的 F03→F05→F07→F06 方案
"""

import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Set, Optional
import subprocess


class SchemeGeneratorF03F05F07F06:
    """F03→F05→F07→F06 方案生成器"""

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

        # 可用素材（排除3个分析失败的）
        self.material_ids = ['1337589', '1327761', '1337586', '1327760', '1327757']

        # 已使用的片段记录
        self.used_segments: Set[tuple] = set()  # (material_id, segment_id)

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

    def get_available_segments_by_tag(self, tag: str) -> List[Dict[str, Any]]:
        """获取指定标签的所有可用片段"""
        available = []

        for material_id in self.material_ids:
            data = self.load_material(material_id)
            if not data:
                continue

            segments = data.get('result', {}).get('segments', [])

            for seg in segments:
                if seg.get('narrative_function_tag') != tag:
                    continue

                seg_id = seg.get('segment_id')
                key = (material_id, seg_id)

                # 检查是否已使用
                if key in self.used_segments:
                    continue

                # 检查时长（除了F06，其他必须>15秒）
                duration = seg.get('duration', 0)
                if tag != 'F06-悬念结尾/付费卡点' and duration <= 15:
                    continue

                # 可用片段
                available.append({
                    'material_id': material_id,
                    'segment_id': seg_id,
                    'tag': tag,
                    'start_time': seg.get('start_time', 0),
                    'end_time': seg.get('end_time', 0),
                    'duration': duration,
                    'plot_summary': seg.get('plot_summary', ''),
                    'main_location': seg.get('main_location', ''),
                    'video_url': data.get('video_url', '')
                })

        return available

    def generate_schemes(self, max_schemes: int = 10) -> List[Dict[str, Any]]:
        """生成方案"""
        print("="*80)
        print("🎯 生成 F03→F05→F07→F06 方案")
        print("="*80)

        schemes = []
        scheme_number = 3  # 从方案3开始（方案1和2已存在）

        while len(schemes) < max_schemes:
            print(f"\n{'='*80}")
            print(f"🎬 生成 方案{scheme_number}")
            print('='*80)

            # 获取各标签的可用片段
            f03_segments = self.get_available_segments_by_tag('F03-极限施压/受辱')
            f05_segments = self.get_available_segments_by_tag('F05-高潮打脸/绝地反击')
            f07_segments = self.get_available_segments_by_tag('F07-情感拉扯/发糖')
            f06_segments = self.get_available_segments_by_tag('F06-悬念结尾/付费卡点')

            print(f"\n可用片段:")
            print(f"  F03: {len(f03_segments)}个")
            print(f"  F05: {len(f05_segments)}个")
            print(f"  F07: {len(f07_segments)}个")
            print(f"  F06: {len(f06_segments)}个")

            # 检查是否可以构建完整方案
            if not f03_segments or not f05_segments or not f07_segments or not f06_segments:
                print(f"\n❌ 资源不足，无法生成更多方案")
                break

            # 选择片段（优先选择时长合适的）
            # F03: 选择时长适中的（100-300秒）
            f03_candidates = [s for s in f03_segments if 100 <= s['duration'] <= 300]
            if not f03_candidates:
                f03_candidates = f03_segments
            selected_f03 = f03_candidates[0]

            # F05: 选择时长适中的（100-400秒）
            f05_candidates = [s for s in f05_segments if 100 <= s['duration'] <= 400]
            if not f05_candidates:
                f05_candidates = f05_segments
            # 尝试选择不同素材的F05
            for seg in f05_candidates:
                if seg['material_id'] != selected_f03['material_id']:
                    selected_f05 = seg
                    break
            else:
                selected_f05 = f05_candidates[0]

            # F07: 只有2个，直接用第一个
            selected_f07 = f07_segments[0]

            # F06: 可以复用，使用1327757的F06
            f06_from_1327757 = [s for s in f06_segments if s['material_id'] == '1327757']
            if f06_from_1327757:
                selected_f06 = f06_from_1327757[0]
            else:
                selected_f06 = f06_segments[0]

            # 标记这些片段为已使用
            self.used_segments.add((selected_f03['material_id'], selected_f03['segment_id']))
            self.used_segments.add((selected_f05['material_id'], selected_f05['segment_id']))
            self.used_segments.add((selected_f07['material_id'], selected_f07['segment_id']))
            # F06不需要标记，可以复用

            # 构建方案
            scheme = {
                'scheme_id': scheme_number,
                'scheme_name': f'方案{scheme_number}',
                'tags': ['F03-极限施压/受辱', 'F05-高潮打脸/绝地反击', 'F07-情感拉扯/发糖', 'F06-悬念结尾/付费卡点'],
                'segments': [
                    {**selected_f03, 'tag_index': 1},
                    {**selected_f05, 'tag_index': 2},
                    {**selected_f07, 'tag_index': 3},
                    {**selected_f06, 'tag_index': 4}
                ]
            }

            schemes.append(scheme)

            # 显示方案详情
            print(f"\n✅ 方案{scheme_number} 片段选择:")
            for seg in scheme['segments']:
                print(f"  {seg['tag']}:")
                print(f"    素材: {seg['material_id']}")
                print(f"    时间: {seg['start_time']}s - {seg['end_time']}s ({seg['duration']}s)")
                print(f"    场景: {seg['main_location']}")

            total_duration = sum(seg['duration'] for seg in scheme['segments'])
            print(f"\n  总时长: {total_duration}秒 ({total_duration/60:.1f}分钟)")

            scheme_number += 1

        return schemes

    def cut_segment(self, seg: Dict[str, Any], scheme_name: str, index: int) -> Optional[str]:
        """剪辑单个片段"""
        output_file = self.output_dir / f"{scheme_name}_片段{index+1}_{seg['material_id']}.mp4"

        start = seg['start_time']
        end = seg['end_time']
        duration = end - start

        cmd = (
            f'ffmpeg -y -ss {start} -i "{seg["video_url"]}" '
            f'-t {duration} '
            f'-c:v libx264 -preset fast -crf 23 -c:a aac '
            f'-threads 4 '
            f'"{output_file}"'
        )

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode == 0:
                return str(output_file)
            else:
                return None

        except Exception as e:
            return None

    def process_scheme(self, scheme: Dict[str, Any]) -> bool:
        """处理单个方案"""
        scheme_name = scheme['scheme_name']
        segments = scheme['segments']

        print(f"\n{'='*80}")
        print(f"🎬 剪辑 {scheme_name}")
        print('='*80)

        # 1. 剪辑片段
        segment_files = []
        for i, seg in enumerate(segments):
            print(f"\n📹 剪辑: {seg['tag']}")
            print(f"   来源: {seg['material_id']}")

            segment_file = self.cut_segment(seg, scheme_name, i)

            if segment_file:
                print(f"   ✅ 成功: {Path(segment_file).name}")
                segment_files.append(segment_file)
            else:
                print(f"   ❌ 失败")
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
                size_mb = output_video.stat().st_size / (1024 * 1024)
                print(f"   📦 大小: {size_mb:.1f}MB")

                total_duration = sum(seg['duration'] for seg in segments)
                print(f"   ⏱️  时长: {total_duration}秒 ({total_duration/60:.1f}分钟)")

                return True
            else:
                print(f"   ❌ 合并失败: {result.stderr[:200]}")
                return False

        except Exception as e:
            print(f"   ❌ 错误: {e}")
            return False

    def save_cut_plan(self, schemes: List[Dict[str, Any]]):
        """保存剪辑计划"""
        plan_data = []

        for scheme in schemes:
            for seg in scheme['segments']:
                plan_data.append({
                    '方案': scheme['scheme_name'],
                    '目标标签': seg['tag'],
                    '来源素材': seg['material_id'],
                    '片段ID': seg['segment_id'],
                    '开始时间': seg['start_time'],
                    '结束时间': seg['end_time'],
                    '时长': seg['duration'],
                    '场景': seg['main_location'],
                    '剧情摘要': seg['plot_summary']
                })

        df = pd.DataFrame(plan_data)
        output_file = self.output_dir / 'F03_F05_F07_F06_剪辑计划.csv'
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n✓ 剪辑计划已保存: {output_file}")

    def process_all(self):
        """生成并处理所有方案"""
        print("\n" + "="*80)
        print("🚀 开始生成 F03→F05→F07→F06 方案")
        print("="*80)

        # 生成方案
        schemes = self.generate_schemes(max_schemes=10)

        if not schemes:
            print("\n❌ 无法生成任何方案")
            return

        # 保存剪辑计划
        self.save_cut_plan(schemes)

        # 显示摘要
        print(f"\n{'='*80}")
        print("📊 方案生成摘要")
        print('='*80)

        print(f"\n✅ 成功生成 {len(schemes)} 个方案:")
        for scheme in schemes:
            total_duration = sum(seg['duration'] for seg in scheme['segments'])
            print(f"  {scheme['scheme_name']}: {total_duration}秒 ({total_duration/60:.1f}分钟)")

        # 处理方案
        print(f"\n{'='*80}")
        print("⚠️  即将执行视频剪辑...")
        print('='*80)

        for scheme in schemes:
            self.process_scheme(scheme)

        print("\n" + "="*80)
        print("✅ 处理完成！")
        print('='*80)


def main():
    generator = SchemeGeneratorF03F05F07F06(
        json_dir='/Users/wangchenyi/video_ad_analyzer/test_20260311/output',
        output_dir='/Users/wangchenyi/material_remake_tool/20260318v1',
        material_csv='/Users/wangchenyi/material_remake_tool/material_list.csv'
    )

    generator.process_all()


if __name__ == '__main__':
    main()
