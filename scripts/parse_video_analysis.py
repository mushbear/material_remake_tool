#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频广告分析 JSON 解析脚本
将 JSON 数据解析为多个数据表格式（CSV）
"""

import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any
import glob


class VideoAnalysisParser:
    """视频广告分析数据解析器"""

    def __init__(self, json_dir: str):
        self.json_dir = Path(json_dir)
        self.data = []

    def load_json_files(self) -> List[Dict[str, Any]]:
        """加载目录下所有 JSON 文件"""
        json_files = list(self.json_dir.glob("*.json"))
        print(f"找到 {len(json_files)} 个 JSON 文件")

        all_data = []
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    all_data.append(data)
            except Exception as e:
                print(f"读取文件 {json_file} 失败: {e}")

        return all_data

    def parse_basic_info(self, data: List[Dict[str, Any]]) -> pd.DataFrame:
        """解析基本信息表"""
        records = []

        for item in data:
            if not item.get('success'):
                continue

            basic_record = {
                'material_id': item.get('material_id'),
                'video_url': item.get('video_url'),
                'analysis_time': item.get('analysis_time'),
                'model': item.get('model'),
                'elapsed_time': item.get('elapsed_time'),
                'success': item.get('success')
            }

            # 基本信息
            if 'result' in item and 'basic_info' in item['result']:
                basic_info = item['result']['basic_info']
                basic_record.update({
                    'aspect_ratio': basic_info.get('aspect_ratio'),
                    'video_style': basic_info.get('video_style'),
                    'color_tone': basic_info.get('color_tone'),
                    'scene_types': ', '.join(basic_info.get('scene_types', [])),
                    'total_duration': basic_info.get('total_duration')
                })

            # 剧情类型
            if 'result' in item and 'drama_type' in item['result']:
                drama_type = item['result']['drama_type']
                basic_record.update({
                    'drama_channel': drama_type.get('drama_channel'),
                    'drama_genre': drama_type.get('drama_genre'),
                    'drama_theme': drama_type.get('drama_theme'),
                    'drama_mainactor_male': drama_type.get('drama_mainactor_male'),
                    'drama_mainactor_female': drama_type.get('drama_mainactor_female')
                })

                # 内容分级
                if 'content_scale' in drama_type:
                    content_scale = drama_type['content_scale']
                    basic_record.update({
                        'sexual_level': content_scale.get('sexual'),
                        'nudity_level': content_scale.get('nudity'),
                        'violence_level': content_scale.get('violence'),
                        'prohibited_items': content_scale.get('prohibited_items'),
                        'children_related': content_scale.get('children_related')
                    })

            # 应用内容
            if 'result' in item and 'app_content' in item['result']:
                app_content = item['result']['app_content']
                basic_record.update({
                    'has_logo': app_content.get('has_logo'),
                    'logo_position': app_content.get('logo_position'),
                    'app_name': app_content.get('app_name'),
                    'drama_name': app_content.get('drama_name')
                })

            # 目标受众
            if 'result' in item and 'target_audience' in item['result']:
                target = item['result']['target_audience']
                basic_record.update({
                    'target_age_range': target.get('age_range'),
                    'target_gender': target.get('gender_target'),
                    'consumption_level': target.get('consumption_level')
                })

            # 片段摘要
            if 'result' in item and 'segment_summary' in item['result']:
                seg_summary = item['result']['segment_summary']
                basic_record.update({
                    'total_segments': seg_summary.get('total_segments'),
                    'segment_structure': seg_summary.get('segment_structure')
                })

            records.append(basic_record)

        return pd.DataFrame(records)

    def parse_segments(self, data: List[Dict[str, Any]]) -> pd.DataFrame:
        """解析片段信息表"""
        records = []

        for item in data:
            if not item.get('success'):
                continue

            material_id = item.get('material_id')

            if 'result' in item and 'segments' in item['result']:
                for segment in item['result']['segments']:
                    segment_record = {
                        'material_id': material_id,
                        'segment_id': segment.get('segment_id'),
                        'start_time': segment.get('start_time'),
                        'end_time': segment.get('end_time'),
                        'duration': segment.get('duration'),
                        'main_location': segment.get('main_location'),
                        'plot_summary': segment.get('plot_summary'),
                        'segment_transition': segment.get('segment_transition'),
                        'narrative_function_tag': segment.get('narrative_function_tag'),
                        'emotion_trope_tags': ', '.join(segment.get('emotion_trope_tags', [])),
                        'has_logo': segment.get('has_logo'),
                        'logo_position': segment.get('logo_position'),
                        'character_count': len(segment.get('characters', []))
                    }
                    records.append(segment_record)

        return pd.DataFrame(records)

    def parse_characters(self, data: List[Dict[str, Any]]) -> pd.DataFrame:
        """解析角色信息表"""
        records = []

        for item in data:
            if not item.get('success'):
                continue

            material_id = item.get('material_id')

            if 'result' in item and 'segments' in item['result']:
                for segment in item['result']['segments']:
                    segment_id = segment.get('segment_id')

                    for character in segment.get('characters', []):
                        character_record = {
                            'material_id': material_id,
                            'segment_id': segment_id,
                            'character_id': character.get('character_id'),
                            'identifying_features': character.get('identifying_features'),
                            'gender': character.get('gender'),
                            'age_group': character.get('age_group'),
                            'role_type': character.get('role_type'),
                            'screen_time': character.get('screen_time')
                        }
                        records.append(character_record)

        return pd.DataFrame(records)

    def save_to_csv(self, df: pd.DataFrame, output_path: str):
        """保存 DataFrame 到 CSV"""
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"✓ 已保存: {output_path} ({len(df)} 行)")

    def parse_all(self, output_dir: str = '.'):
        """解析所有数据并保存"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        # 加载数据
        data = self.load_json_files()
        if not data:
            print("没有找到有效数据")
            return

        # 解析并保存各个表
        print("\n解析数据表...")

        # 1. 基本信息表
        df_basic = self.parse_basic_info(data)
        self.save_to_csv(df_basic, output_path / 'video_basic_info.csv')

        # 2. 片段信息表
        df_segments = self.parse_segments(data)
        self.save_to_csv(df_segments, output_path / 'video_segments.csv')

        # 3. 角色信息表
        df_characters = self.parse_characters(data)
        self.save_to_csv(df_characters, output_path / 'video_characters.csv')

        print(f"\n完成！共生成 3 个数据表文件")
        print(f"- video_basic_info.csv: 基本信息 ({len(df_basic)} 条记录)")
        print(f"- video_segments.csv: 片段信息 ({len(df_segments)} 条记录)")
        print(f"- video_characters.csv: 角色信息 ({len(df_characters)} 条记录)")


def main():
    """主函数"""
    # JSON 文件目录
    json_dir = '/Users/wangchenyi/video_ad_analyzer/test_20260311/output'

    # 输出目录（当前目录）
    output_dir = '.'

    # 创建解析器并执行
    parser = VideoAnalysisParser(json_dir)
    parser.parse_all(output_dir)


if __name__ == '__main__':
    main()
