#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
模块四：素材下载与组合

根据组合方案下载素材、提取场景片段、去除BGM、拼接新素材。
"""

import json
import os
import sys
import subprocess
import requests
from pathlib import Path
from typing import Dict, List, Any
import argparse
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
import time


def load_config(config_path: str = "./config/config.json") -> Dict[str, Any]:
    """加载配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_schemes(schemes_path: str) -> List[Dict[str, Any]]:
    """加载组合方案"""
    with open(schemes_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_material_list(csv_path: str) -> Dict[str, str]:
    """
    加载素材列表CSV

    Returns:
        {material_id: video_url} 的字典
    """
    material_urls = {}

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            material_id = row.get('id')
            video_url = row.get('video_url')
            if material_id and video_url:
                material_urls[material_id] = video_url

    return material_urls


def download_video(url: str, output_path: str, timeout: int = 300) -> bool:
    """
    下载视频文件

    Args:
        url: 视频URL
        output_path: 输出文件路径
        timeout: 超时时间（秒）

    Returns:
        是否下载成功
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 如果文件已存在且大小大于0，跳过下载
    if output_path.exists() and output_path.stat().st_size > 0:
        print(f"✅ 文件已存在，跳过下载: {output_path}")
        return True

    try:
        print(f"📥 正在下载: {url}")
        print(f"   保存到: {output_path}")

        response = requests.get(url, stream=True, timeout=timeout)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        downloaded_size = 0

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded_size += len(chunk)

                    if total_size > 0:
                        progress = (downloaded_size / total_size) * 100
                        print(f"\r   进度: {progress:.1f}% ({downloaded_size}/{total_size} bytes)", end='')

        print(f"\n✅ 下载完成: {output_path}")
        return True

    except Exception as e:
        print(f"\n❌ 下载失败: {e}")
        # 删除部分下载的文件
        if output_path.exists():
            output_path.unlink()
        return False


def extract_scene(
    video_path: str,
    start_time: float,
    end_time: float,
    output_path: str
) -> bool:
    """
    使用ffmpeg提取场景片段

    Args:
        video_path: 源视频路径
        start_time: 起始时间（秒）
        end_time: 结束时间（秒）
        output_path: 输出文件路径

    Returns:
        是否提取成功
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    duration = end_time - start_time

    try:
        # ffmpeg命令：提取视频片段
        cmd = [
            'ffmpeg',
            '-y',  # 覆盖输出文件
            '-ss', str(start_time),  # 起始时间
            '-i', video_path,  # 输入文件
            '-t', str(duration),  # 持续时间
            '-c', 'copy',  # 直接复制流，不重新编码
            str(output_path)
        ]

        print(f"🎬 提取场景: {start_time}s - {end_time}s")

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60
        )

        if result.returncode == 0:
            print(f"✅ 场景已保存: {output_path}")
            return True
        else:
            print(f"❌ ffmpeg错误: {result.stderr.decode()}")
            return False

    except Exception as e:
        print(f"❌ 提取场景失败: {e}")
        return False


def remove_bgm_simple(audio_input: str, audio_output: str) -> bool:
    """
    简单的BGM去除：使用高通滤波器保留人声

    注意：这只是简单的频率过滤，不是真正的BGM分离。
    对于专业的BGM分离，建议使用Spleeter或Demucs等AI工具。

    Args:
        audio_input: 输入音频文件
        audio_output: 输出音频文件

    Returns:
        是否处理成功
    """
    try:
        # 使用ffmpeg的高通滤波器保留300Hz以上的人声频率
        cmd = [
            'ffmpeg',
            '-y',
            '-i', audio_input,
            '-af', 'highpass=f=300',  # 高通滤波器，保留300Hz以上频率
            audio_output
        ]

        print(f"🎵 处理音频（简单BGM去除）...")

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60
        )

        if result.returncode == 0:
            print(f"✅ 音频处理完成")
            return True
        else:
            print(f"⚠️  音频处理警告: {result.stderr.decode()}")
            return False

    except Exception as e:
        print(f"❌ 音频处理失败: {e}")
        return False


def concat_videos(
    video_files: List[str],
    output_path: str,
    remove_bgm: bool = False
) -> bool:
    """
    拼接多个视频文件

    Args:
        video_files: 视频文件列表
        output_path: 输出文件路径
        remove_bgm: 是否去除BGM

    Returns:
        是否拼接成功
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 创建临时文件列表
    concat_list_path = output_path.parent / "concat_list.txt"

    try:
        # 如果需要去除BGM，先处理每个视频的音频
        if remove_bgm:
            print("🎵 正在处理视频音频...")
            processed_videos = []

            for i, video_file in enumerate(video_files):
                temp_video = output_path.parent / f"temp_{i}_{Path(video_file).name}"

                # 提取音频
                temp_audio = output_path.parent / f"temp_{i}_audio.m4a"

                # 提取音频命令
                extract_audio_cmd = [
                    'ffmpeg', '-y', '-i', video_file,
                    '-vn', '-acodec', 'copy',
                    str(temp_audio)
                ]

                subprocess.run(extract_audio_cmd, capture_output=True)

                # 处理音频
                processed_audio = output_path.parent / f"temp_{i}_audio_processed.m4a"
                remove_bgm_simple(str(temp_audio), str(processed_audio))

                # 将处理后的音频合并回视频
                merge_cmd = [
                    'ffmpeg', '-y',
                    '-i', video_file,
                    '-i', str(processed_audio),
                    '-c:v', 'copy',
                    '-c:a', 'aac',
                    '-map', '0:v:0',
                    '-map', '1:a:0',
                    '-shortest',
                    str(temp_video)
                ]

                subprocess.run(merge_cmd, capture_output=True)
                processed_videos.append(str(temp_video))

                # 清理临时文件
                temp_audio.unlink(missing_ok=True)
                processed_audio.unlink(missing_ok=True)

            video_files = processed_videos

        # 创建concat文件列表
        with open(concat_list_path, 'w') as f:
            for video_file in video_files:
                # 使用绝对路径
                abs_path = Path(video_file).resolve()
                f.write(f"file '{abs_path}'\n")

        # ffmpeg concat命令
        cmd = [
            'ffmpeg',
            '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', str(concat_list_path),
            '-c', 'copy',
            str(output_path)
        ]

        print(f"🎞️  正在拼接 {len(video_files)} 个视频片段...")

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=300
        )

        # 清理临时文件
        concat_list_path.unlink(missing_ok=True)

        if remove_bgm:
            for temp_video in video_files:
                Path(temp_video).unlink(missing_ok=True)

        if result.returncode == 0:
            print(f"✅ 视频拼接完成: {output_path}")
            return True
        else:
            print(f"❌ 拼接失败: {result.stderr.decode()}")
            return False

    except Exception as e:
        print(f"❌ 拼接视频失败: {e}")
        return False


def process_scheme(
    scheme: Dict[str, Any],
    material_urls: Dict[str, str],
    temp_dir: str,
    output_dir: str,
    remove_bgm: bool
) -> Dict[str, Any]:
    """
    处理单个组合方案

    Args:
        scheme: 组合方案
        material_urls: 素材URL字典
        temp_dir: 临时目录
        output_dir: 输出目录
        remove_bgm: 是否去除BGM

    Returns:
        处理结果
    """
    scheme_id = scheme['scheme_id']
    scenes = scheme['scenes']

    print(f"\n{'='*60}")
    print(f"🎯 处理方案 {scheme_id}")
    print(f"{'='*60}")

    temp_path = Path(temp_dir)
    temp_path.mkdir(parents=True, exist_ok=True)

    # 用于存储需要拼接的视频片段
    scene_videos = []

    # 用于记录处理日志
    log_entries = []

    try:
        for scene in scenes:
            material_id = scene['material_id']
            segment_id = scene['segment_id']
            start_time = scene['start_time']
            end_time = scene['end_time']

            # 获取视频URL
            video_url = material_urls.get(material_id)

            if not video_url:
                # 尝试从场景数据中获取
                video_url = scene.get('video_url')

            if not video_url:
                print(f"❌ 未找到素材 {material_id} 的下载链接")
                return {
                    'scheme_id': scheme_id,
                    'success': False,
                    'error': f'未找到素材 {material_id} 的下载链接'
                }

            # 下载完整视频
            video_filename = f"{material_id}.mp4"
            video_path = temp_path / video_filename

            if not download_video(video_url, str(video_path)):
                return {
                    'scheme_id': scheme_id,
                    'success': False,
                    'error': f'下载素材 {material_id} 失败'
                }

            # 提取场景片段
            scene_filename = f"scheme_{scheme_id}_scene_{scene['scene_index']}_{material_id}_{segment_id}.mp4"
            scene_output_path = temp_path / scene_filename

            if not extract_scene(str(video_path), start_time, end_time, str(scene_output_path)):
                return {
                    'scheme_id': scheme_id,
                    'success': False,
                    'error': f'提取场景片段失败'
                }

            scene_videos.append(str(scene_output_path))

            log_entries.append({
                'material_id': material_id,
                'segment_id': segment_id,
                'scene_file': scene_filename,
                'duration': end_time - start_time
            })

        # 拼接视频
        output_filename = f"remix_material_{scheme_id}.mp4"
        output_path = Path(output_dir) / output_filename

        if not concat_videos(scene_videos, str(output_path), remove_bgm):
            return {
                'scheme_id': scheme_id,
                'success': False,
                'error': '拼接视频失败'
            }

        # 获取输出文件大小
        file_size = output_path.stat().st_size if output_path.exists() else 0

        print(f"\n✅ 方案 {scheme_id} 处理完成！")
        print(f"   输出文件: {output_path}")
        print(f"   文件大小: {file_size / (1024*1024):.2f} MB")

        return {
            'scheme_id': scheme_id,
            'success': True,
            'output_file': str(output_path),
            'file_size': file_size,
            'num_scenes': len(scenes),
            'scenes': log_entries
        }

    except Exception as e:
        print(f"❌ 处理方案 {scheme_id} 时出错: {e}")
        return {
            'scheme_id': scheme_id,
            'success': False,
            'error': str(e)
        }


def main():
    parser = argparse.ArgumentParser(description='模块四：素材下载与组合')
    parser.add_argument('--config', default='./config/config.json', help='配置文件路径')
    parser.add_argument('--schemes', default='./data/output/scene_combination_schemes.json', help='组合方案文件')
    parser.add_argument('--material-csv', default='./material_list.csv', help='素材列表CSV文件')
    parser.add_argument('--output-dir', default='./output', help='输出目录')
    parser.add_argument('--temp-dir', default='./data/temp', help='临时文件目录')
    parser.add_argument('--no-bgm-removal', action='store_true', help='不去除BGM')
    parser.add_argument('--scheme-id', type=int, help='只处理指定方案')

    args = parser.parse_args()

    # 加载配置
    config = load_config(args.config)

    # 命令行参数覆盖配置
    remove_bgm = not args.no_bgm_removal and config.get('remove_bgm', True)
    output_dir = args.output_dir
    temp_dir = args.temp_dir

    print(f"🎬 开始处理素材组合")
    print(f"📋 组合方案: {args.schemes}")
    print(f"📦 素材列表: {args.material_csv}")
    print(f"🎵 BGM处理: {'启用' if remove_bgm else '禁用'}")
    print(f"{'='*60}")

    try:
        # 加载组合方案
        print(f"📖 正在加载组合方案...")
        schemes = load_schemes(args.schemes)

        # 过滤方案
        if args.scheme_id:
            schemes = [s for s in schemes if s['scheme_id'] == args.scheme_id]
            if not schemes:
                print(f"❌ 未找到方案ID {args.scheme_id}")
                return 1

        # 加载素材URL
        print(f"📖 正在加载素材列表...")
        material_urls = load_material_list(args.material_csv)

        if not material_urls:
            print(f"⚠️  警告: 素材列表为空")

        # 处理每个方案
        results = []
        for scheme in schemes:
            result = process_scheme(
                scheme,
                material_urls,
                temp_dir,
                output_dir,
                remove_bgm
            )
            results.append(result)

        # 保存处理日志
        log_file = Path('./data/output/processing_log.json')
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        # 打印总结
        print(f"\n{'='*60}")
        print("📊 处理总结")
        print(f"{'='*60}")

        success_count = sum(1 for r in results if r['success'])
        fail_count = len(results) - success_count

        print(f"✅ 成功: {success_count} 个")
        print(f"❌ 失败: {fail_count} 个")

        for result in results:
            if result['success']:
                size_mb = result['file_size'] / (1024*1024)
                print(f"  方案 {result['scheme_id']}: ✅ {size_mb:.2f} MB")
            else:
                print(f"  方案 {result['scheme_id']}: ❌ {result['error']}")

        print(f"\n✅ 处理日志已保存: {log_file}")

        return 0

    except Exception as e:
        print(f"❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
