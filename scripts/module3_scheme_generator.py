#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
模块三：场景组合方案生成

根据narrative_function_tag组合规则，从场景库中匹配场景，生成N个组合方案。
"""

import json
import random
from pathlib import Path
from typing import Dict, List, Any
import argparse
from copy import deepcopy


def load_config(config_path: str = "./config/config.json") -> Dict[str, Any]:
    """加载配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_scenes_data(scenes_data_path: str) -> Dict[str, Any]:
    """加载场景数据"""
    with open(scenes_data_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_scene_index(scenes_data: Dict[str, Any]) -> Dict[str, List[Dict]]:
    """
    构建场景索引，按标签分类

    Args:
        scenes_data: 场景数据

    Returns:
        {narrative_function_tag: [scene_list]} 的索引字典
    """
    scene_index = {}

    for material_id, material_data in scenes_data.items():
        video_url = material_data.get("video_url")
        scenes = material_data.get("scenes", [])

        for scene in scenes:
            tag = scene.get("narrative_function_tag")

            if not tag:
                continue

            # 构建场景信息（包含素材ID）
            scene_with_source = deepcopy(scene)
            scene_with_source["material_id"] = material_id
            scene_with_source["video_url"] = video_url

            if tag not in scene_index:
                scene_index[tag] = []

            scene_index[tag].append(scene_with_source)

    return scene_index


def generate_single_scheme(
    tag_sequence: List[str],
    scene_index: Dict[str, List[Dict]],
    scheme_id: int
) -> Dict[str, Any]:
    """
    生成单个组合方案

    Args:
        tag_sequence: 标签序列（如 ["F01", "F02", "F03"]）
        scene_index: 场景索引
        scheme_id: 方案ID

    Returns:
        组合方案字典
    """
    scenes = []
    total_duration = 0

    for scene_index_pos, tag in enumerate(tag_sequence):
        # 获取该标签下的所有场景
        available_scenes = scene_index.get(tag, [])

        if not available_scenes:
            print(f"⚠️  警告: 未找到标签 '{tag}' 对应的场景")
            continue

        # 随机选择一个场景
        selected_scene = random.choice(available_scenes)

        # 添加场景序号信息
        scene_entry = {
            "scene_index": scene_index_pos + 1,
            "material_id": selected_scene.get("material_id"),
            "segment_id": selected_scene.get("segment_id"),
            "start_time": selected_scene.get("start_time"),
            "end_time": selected_scene.get("end_time"),
            "duration": selected_scene.get("duration"),
            "narrative_function_tag": tag,
            "plot_summary": selected_scene.get("plot_summary"),
            "main_location": selected_scene.get("main_location")
        }

        scenes.append(scene_entry)
        total_duration += selected_scene.get("duration", 0)

    return {
        "scheme_id": scheme_id,
        "scenes": scenes,
        "total_duration": total_duration,
        "num_scenes": len(scenes)
    }


def generate_schemes(
    tag_sequence: List[str],
    scene_index: Dict[str, List[Dict]],
    num_schemes: int
) -> List[Dict[str, Any]]:
    """
    生成多个组合方案

    Args:
        tag_sequence: 标签序列
        scene_index: 场景索引
        num_schemes: 方案数量

    Returns:
        方案列表
    """
    schemes = []

    # 检查是否有足够的场景
    for tag in tag_sequence:
        available_count = len(scene_index.get(tag, []))
        if available_count == 0:
            print(f"❌ 错误: 标签 '{tag}' 没有可用场景")
            return []
        if available_count < num_schemes:
            print(f"⚠️  警告: 标签 '{tag}' 只有 {available_count} 个场景，将产生重复方案")

    for i in range(num_schemes):
        scheme = generate_single_scheme(tag_sequence, scene_index, i + 1)
        schemes.append(scheme)
        print(f"✅ 生成方案 {i + 1}/{num_schemes}: {len(scheme['scenes'])} 个场景，总时长 {scheme['total_duration']} 秒")

    return schemes


def save_schemes(schemes: List[Dict[str, Any]], output_file: str):
    """保存方案到JSON文件"""
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(schemes, f, ensure_ascii=False, indent=2)

    print(f"✅ 方案已保存到: {output_path}")


def print_scheme_summary(schemes: List[Dict[str, Any]]):
    """打印方案摘要"""
    print("\n" + "=" * 60)
    print("📋 方案摘要")
    print("=" * 60)

    for scheme in schemes:
        print(f"\n方案 {scheme['scheme_id']}:")
        print(f"  场景数量: {scheme['num_scenes']}")
        print(f"  总时长: {scheme['total_duration']} 秒 ({scheme['total_duration'] // 60} 分 {scheme['total_duration'] % 60} 秒)")
        print(f"  场景序列:")
        for scene in scheme['scenes']:
            print(f"    {scene['scene_index']}. [{scene['narrative_function_tag']}] 素材 {scene['material_id']} - {scene['segment_id']} ({scene['duration']}s)")

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description='模块三：场景组合方案生成')
    parser.add_argument('--config', default='./config/config.json', help='配置文件路径')
    parser.add_argument('--scenes-data', default='./data/output/scenes_data.json', help='场景数据文件路径')
    parser.add_argument('--output', default='./data/output/scene_combination_schemes.json', help='输出文件路径')
    parser.add_argument('--tags', nargs='+', help='标签组合（覆盖配置文件）')
    parser.add_argument('--num-schemes', type=int, help='生成方案数量（覆盖配置文件）')
    parser.add_argument('--seed', type=int, help='随机种子（用于可复现结果）')

    args = parser.parse_args()

    # 加载配置
    config = load_config(args.config)

    # 命令行参数覆盖配置文件
    tag_sequence = args.tags if args.tags else config.get("narrative_function_tags", [])
    num_schemes = args.num_schemes if args.num_schemes else config.get("num_schemes", 10)

    if not tag_sequence:
        print("❌ 错误: 未指定标签组合")
        print("   请通过 --tags 参数或在配置文件中设置 narrative_function_tags")
        return 1

    # 设置随机种子
    if args.seed is not None:
        random.seed(args.seed)
        print(f"🎲 随机种子: {args.seed}")

    print(f"🎬 开始生成场景组合方案")
    print(f"📋 标签序列: {' + '.join(tag_sequence)}")
    print(f"🔢 方案数量: {num_schemes}")
    print("-" * 60)

    try:
        # 加载场景数据
        print(f"📖 正在加载场景数据: {args.scenes_data}")
        scenes_data = load_scenes_data(args.scenes_data)

        # 构建场景索引
        print("🔍 正在构建场景索引...")
        scene_index = build_scene_index(scenes_data)

        # 打印索引统计
        print("\n📊 场景索引统计:")
        for tag in tag_sequence:
            count = len(scene_index.get(tag, []))
            print(f"  {tag}: {count} 个场景")

        print("-" * 60)

        # 生成方案
        print(f"🎯 开始生成 {num_schemes} 个方案...\n")
        schemes = generate_schemes(tag_sequence, scene_index, num_schemes)

        if not schemes:
            print("❌ 生成方案失败")
            return 1

        # 保存方案
        save_schemes(schemes, args.output)

        # 打印摘要
        print_scheme_summary(schemes)

        print(f"\n✅ 模块三执行完成！共生成 {len(schemes)} 个方案")

        return 0

    except Exception as e:
        print(f"❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
