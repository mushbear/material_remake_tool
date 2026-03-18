#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
专门剪辑方案2（即使不完整）
"""

import json
import subprocess
from pathlib import Path


def cut_segment(video_url: str, start: float, end: float, output_path: str) -> bool:
    """剪辑单个片段"""
    duration = end - start

    cmd = (
        f'ffmpeg -y -ss {start} -i "{video_url}" '
        f'-t {duration} '
        f'-c:v libx264 -preset fast -crf 23 -c:a aac '
        f'-threads 4 '
        f'"{output_path}"'
    )

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300
        )
        return result.returncode == 0
    except:
        return False


def main():
    output_dir = Path('/Users/wangchenyi/material_remake_tool/20260318v1')

    print("🎬 剪辑方案2（3个片段，缺少F06）")
    print("="*80)

    # 方案2的3个片段（从之前的输出中获取）
    segments = [
        {
            'name': 'F02-背景速递/设定交代',
            'url': 'https://hwmat-enc.ikyuedu.com/encode/onl/market/material/video/20260311/oss_web/1773199618443_wily2y.mp4',
            'start': 23,
            'end': 262,
            'material_id': '1337589'
        },
        {
            'name': 'F03-极限施压/受辱',
            'url': 'https://hwmat-enc.ikyuedu.com/encode/onl/market/material/video/20260302/oss_web/1772448259834_04yy62.mp4',
            'start': 0,
            'end': 160,
            'material_id': '1327761'
        },
        {
            'name': 'F04-金手指觉醒/身份曝光',
            'url': 'https://hwmat-enc.ikyuedu.com/encode/onl/market/material/video/20260302/oss_web/1772448259835_pq23qc.mp4',
            'start': 550,
            'end': 998,
            'material_id': '1327760'
        }
    ]

    # 1. 剪辑片段
    segment_files = []
    for i, seg in enumerate(segments):
        output_file = output_dir / f"方案2_片段{i+1}_{seg['material_id']}.mp4"

        print(f"\n📹 剪辑: {seg['name']}")
        print(f"   来源: {seg['material_id']}")
        print(f"   时间: {seg['start']}s - {seg['end']}s ({seg['end']-seg['start']}s)")

        if cut_segment(seg['url'], seg['start'], seg['end'], str(output_file)):
            print(f"   ✅ 成功: {output_file.name}")
            segment_files.append(str(output_file))
        else:
            print(f"   ❌ 失败")
            return

    # 2. 合并视频
    print(f"\n{'='*80}")
    print(f"🔗 合并视频")
    print('='*80)

    concat_file = output_dir / "方案2_concat_list.txt"
    with open(concat_file, 'w', encoding='utf-8') as f:
        for video_file in segment_files:
            f.write(f"file '{video_file}'\n")

    output_video = output_dir / "方案2_最终版_3片段.mp4"

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

            # 显示文件大小
            size_mb = output_video.stat().st_size / (1024 * 1024)
            print(f"   📦 大小: {size_mb:.1f}MB")

            # 计算总时长
            total_duration = sum(seg['end'] - seg['start'] for seg in segments)
            print(f"   ⏱️  时长: {total_duration}秒 ({total_duration/60:.1f}分钟)")

        else:
            print(f"   ❌ 合并失败: {result.stderr[:200]}")

    except Exception as e:
        print(f"   ❌ 错误: {e}")

    print("\n" + "="*80)
    print("✅ 方案2剪辑完成！")
    print("="*80)


if __name__ == '__main__':
    main()
