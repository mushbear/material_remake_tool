#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
模块二：场景信息提取

根据素材ID列表，从JSON分析文件中提取场景信息。
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any
import argparse


def load_config(config_path: str = "./config/config.json") -> Dict[str, Any]:
    """加载配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def find_json_files(material_ids: List[str], json_dir: str) -> Dict[str, str]:
    """
    根据素材ID列表，查找对应的JSON文件

    Args:
        material_ids: 素材ID列表
        json_dir: JSON文件所在目录

    Returns:
        {material_id: json_file_path} 的字典
    """
    json_files = {}
    json_path = Path(json_dir)

    # 首先尝试直接按文件名查找：{material_id}.json
    for material_id in material_ids:
        direct_file = json_path / f"{material_id}.json"
        if direct_file.exists():
            json_files[material_id] = str(direct_file)
            continue

        # 如果直接文件不存在，扫描目录查找包含material_id的JSON文件
        found = False
        for json_file in json_path.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data.get("material_id") == material_id:
                        json_files[material_id] = str(json_file)
                        found = True
                        break
            except (json.JSONDecodeError, KeyError):
                continue

        if not found:
            print(f"⚠️  警告: 未找到素材ID {material_id} 对应的JSON文件")

    return json_files


def extract_scenes_from_json(json_file_path: str) -> List[Dict[str, Any]]:
    """
    从JSON文件中提取场景信息

    Args:
        json_file_path: JSON文件路径

    Returns:
        场景信息列表
    """
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    material_id = data.get("material_id")
    video_url = data.get("video_url")
    segments = data.get("result", {}).get("segments", [])

    scenes = []
    for segment in segments:
        scene = {
            "segment_id": segment.get("segment_id"),
            "start_time": segment.get("start_time"),
            "end_time": segment.get("end_time"),
            "duration": segment.get("duration"),
            "narrative_function_tag": segment.get("narrative_function_tag"),
            "plot_summary": segment.get("plot_summary"),
            "main_location": segment.get("main_location"),
            "emotion_trope_tags": segment.get("emotion_trope_tags", [])
        }
        scenes.append(scene)

    return {
        "material_id": material_id,
        "video_url": video_url,
        "scenes": scenes
    }


def extract_all_scenes(material_ids: List[str], json_dir: str) -> Dict[str, Any]:
    """
    提取所有素材的场景信息

    Args:
        material_ids: 素材ID列表
        json_dir: JSON文件所在目录

    Returns:
        所有场景信息的字典
    """
    json_files = find_json_files(material_ids, json_dir)

    if not json_files:
        raise ValueError("未找到任何JSON文件！请检查素材ID和JSON目录配置。")

    all_scenes = {}
    for material_id, json_file in json_files.items():
        print(f"📖 正在读取: {json_file}")
        try:
            scenes_data = extract_scenes_from_json(json_file)
            all_scenes[material_id] = scenes_data
            print(f"✅ 成功提取素材 {material_id} 的 {len(scenes_data['scenes'])} 个场景")
        except Exception as e:
            print(f"❌ 读取文件 {json_file} 时出错: {e}")

    return all_scenes


def save_scenes_data(scenes_data: Dict[str, Any], output_file: str):
    """
    保存场景数据到JSON文件

    Args:
        scenes_data: 场景数据
        output_file: 输出文件路径
    """
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(scenes_data, f, ensure_ascii=False, indent=2)

    print(f"✅ 场景数据已保存到: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='模块二：场景信息提取')
    parser.add_argument('--config', default='./config/config.json', help='配置文件路径')
    parser.add_argument('--material-ids', nargs='+', help='素材ID列表（覆盖配置文件）')
    parser.add_argument('--json-dir', help='JSON文件所在目录（覆盖配置文件）')
    parser.add_argument('--output', default='./data/output/scenes_data.json', help='输出文件路径')

    args = parser.parse_args()

    # 加载配置
    config = load_config(args.config)

    # 命令行参数覆盖配置文件
    material_ids = args.material_ids if args.material_ids else config.get("test_material_ids", [])
    json_dir = args.json_dir if args.json_dir else config.get("json_source_dir", "./")

    if not material_ids:
        print("❌ 错误: 未提供素材ID列表")
        print("   请通过 --material-ids 参数或在配置文件中设置 test_material_ids")
        sys.exit(1)

    print(f"🎬 开始提取场景信息")
    print(f"📋 素材ID列表: {material_ids}")
    print(f"📁 JSON目录: {json_dir}")
    print("-" * 50)

    try:
        # 提取场景信息
        scenes_data = extract_all_scenes(material_ids, json_dir)

        # 统计信息
        total_scenes = sum(len(data["scenes"]) for data in scenes_data.values())
        print("-" * 50)
        print(f"📊 统计: 共处理 {len(scenes_data)} 个素材，提取 {total_scenes} 个场景")

        # 保存结果
        save_scenes_data(scenes_data, args.output)

        print("✅ 模块二执行完成！")

    except Exception as e:
        print(f"❌ 执行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
