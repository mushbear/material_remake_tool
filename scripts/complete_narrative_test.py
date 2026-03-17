#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整叙事方案测试 - 基于已有JSON数据
直接读取已有分析结果进行叙事方案匹配测试
"""

import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Tuple
import sys


class CompleteNarrativeTester:
    """完整叙事方案测试器"""

    def __init__(self, json_dir: str):
        self.json_dir = Path(json_dir)
        self.schemes = {
            "方案1": ["F01-强开局/吸睛钩子", "F04-金手指觉醒/身份曝光", "F02-背景速递/设定交代", "F06-悬念结尾/付费卡点"],
            "方案2": ["F02-背景速递/设定交代", "F02-背景速递/设定交代", "F03-极限施压/受辱", "F04-金手指觉醒/身份曝光", "F06-悬念结尾/付费卡点"]
        }
        self.material_ids = ['1337589', '1330603', '1330602', '1329504', '1330869', '1327758', '1327761']

    def load_material(self, material_id: str) -> Dict[str, Any]:
        """加载指定素材的 JSON 数据"""
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
            print(f"❌ 读取文件 {json_file} 失败: {e}")
            return None

    def extract_narrative_tags(self, data: Dict[str, Any]) -> List[str]:
        """提取素材的叙事功能标签序列"""
        if not data or 'result' not in data or 'segments' not in data['result']:
            return []

        segments = data['result']['segments']
        tags = [segment.get('narrative_function_tag', 'Unknown') for segment in segments]

        return tags

    def extract_segments_info(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """提取片段详细信息"""
        if not data or 'result' not in data or 'segments' not in data['result']:
            return []

        segments = data['result']['segments']
        segment_info = []

        for seg in segments:
            info = {
                'segment_id': seg.get('segment_id'),
                'start_time': seg.get('start_time'),
                'end_time': seg.get('end_time'),
                'duration': seg.get('duration'),
                'narrative_function_tag': seg.get('narrative_function_tag'),
                'plot_summary': seg.get('plot_summary'),
                'main_location': seg.get('main_location'),
                'emotion_trope_tags': ', '.join(seg.get('emotion_trope_tags', [])),
                'character_count': len(seg.get('characters', []))
            }
            segment_info.append(info)

        return segment_info

    def extract_basic_info(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """提取基本信息"""
        if not data or 'result' not in data:
            return {}

        result = data['result']
        basic_info = {}

        # 基本信息
        if 'basic_info' in result:
            basic_info.update(result['basic_info'])

        # 剧情类型
        if 'drama_type' in result:
            basic_info.update(result['drama_type'])

        # 应用内容
        if 'app_content' in result:
            basic_info.update(result['app_content'])

        # 目标受众
        if 'target_audience' in result:
            basic_info.update(result['target_audience'])

        return basic_info

    def calculate_match_score(self, actual_tags: List[str], scheme_tags: List[str]) -> Tuple[float, Dict]:
        """计算实际标签序列与方案的匹配分数"""
        if not actual_tags or not scheme_tags:
            return 0.0, {"reason": "Empty tags"}

        # 位置和标签都匹配
        exact_matches = 0
        for i in range(min(len(actual_tags), len(scheme_tags))):
            if actual_tags[i] == scheme_tags[i]:
                exact_matches += 1

        # 标签出现（不考虑位置）
        tag_matches = 0
        for tag in scheme_tags:
            if tag in actual_tags:
                tag_matches += 1

        # 计算分数
        position_score = exact_matches / max(len(scheme_tags), 1)
        tag_score = tag_matches / max(len(scheme_tags), 1)

        # 综合分数
        overall_score = (position_score * 0.6 + tag_score * 0.4)

        details = {
            "exact_matches": exact_matches,
            "tag_matches": tag_matches,
            "position_score": position_score,
            "tag_score": tag_score,
            "overall_score": overall_score,
            "actual_length": len(actual_tags),
            "scheme_length": len(scheme_tags)
        }

        return overall_score, details

    def test_material(self, material_id: str) -> Dict[str, Any]:
        """测试单个素材"""
        print(f"\n{'='*80}")
        print(f"📹 测试素材: {material_id}")
        print('='*80)

        # 加载数据
        data = self.load_material(material_id)
        if not data:
            print(f"⚠️  素材 {material_id} 数据不可用")
            return None

        # 提取基本信息
        basic_info = self.extract_basic_info(data)
        print(f"\n📋 基本信息:")
        print(f"  题材: {basic_info.get('drama_genre', 'N/A')}")
        print(f"  主题: {basic_info.get('drama_theme', 'N/A')}")
        print(f"  应用: {basic_info.get('app_name', 'N/A')}")
        print(f"  剧集名: {basic_info.get('drama_name', 'N/A')}")

        # 提取叙事标签
        actual_tags = self.extract_narrative_tags(data)

        print(f"\n🎬 实际叙事序列 ({len(actual_tags)} 个片段):")
        for i, tag in enumerate(actual_tags, 1):
            print(f"  片段 {i}: {tag}")

        # 提取片段信息
        segments_info = self.extract_segments_info(data)

        # 测试各个方案
        results = {}

        for scheme_name, scheme_tags in self.schemes.items():
            print(f"\n📊 {scheme_name}:")
            print(f"  预设序列: {' → '.join(scheme_tags)}")

            score, details = self.calculate_match_score(actual_tags, scheme_tags)

            print(f"  匹配分数: {score:.2%}")
            print(f"  - 位置匹配: {details['exact_matches']}/{details['scheme_length']} ({details['position_score']:.2%})")
            print(f"  - 标签匹配: {details['tag_matches']}/{details['scheme_length']} ({details['tag_score']:.2%})")

            results[scheme_name] = {
                'score': score,
                'details': details,
                'scheme_tags': scheme_tags
            }

        # 找出最佳匹配方案
        best_scheme = max(results.keys(), key=lambda k: results[k]['score'])

        return {
            'material_id': material_id,
            'basic_info': basic_info,
            'actual_tags': actual_tags,
            'segments_info': segments_info,
            'results': results,
            'best_scheme': best_scheme,
            'best_score': results[best_scheme]['score']
        }

    def test_all(self) -> pd.DataFrame:
        """测试所有素材"""
        all_results = []
        detailed_results = []

        print("\n" + "="*80)
        print("🚀 开始完整叙事方案测试")
        print("="*80)
        print(f"📂 JSON数据目录: {self.json_dir}")
        print(f"📋 测试素材数量: {len(self.material_ids)}")
        print(f"📝 对比方案数量: {len(self.schemes)}")

        for material_id in self.material_ids:
            result = self.test_material(material_id)

            if result:
                # 为每个方案创建一行记录
                for scheme_name, scheme_data in result['results'].items():
                    row = {
                        'material_id': material_id,
                        'drama_genre': result['basic_info'].get('drama_genre', 'N/A'),
                        'drama_theme': result['basic_info'].get('drama_theme', 'N/A'),
                        'app_name': result['basic_info'].get('app_name', 'N/A'),
                        'scheme': scheme_name,
                        'is_best': (scheme_name == result['best_scheme']),
                        'score': scheme_data['score'],
                        'position_score': scheme_data['details']['position_score'],
                        'tag_score': scheme_data['details']['tag_score'],
                        'exact_matches': scheme_data['details']['exact_matches'],
                        'tag_matches': scheme_data['details']['tag_matches'],
                        'actual_length': scheme_data['details']['actual_length'],
                        'scheme_length': scheme_data['details']['scheme_length'],
                        'actual_tags': ' → '.join(result['actual_tags']),
                        'scheme_tags': ' → '.join(scheme_data['scheme_tags'])
                    }
                    all_results.append(row)

                # 详细结果
                detailed_results.append(result)

        # 创建 DataFrame
        df = pd.DataFrame(all_results)
        df = df.sort_values(['material_id', 'score'], ascending=[True, False])

        return df, detailed_results

    def generate_summary_report(self, df: pd.DataFrame, detailed_results: List[Dict]):
        """生成汇总报告"""
        print(f"\n\n{'='*80}")
        print("📈 测试汇总报告")
        print('='*80)

        # 统计成功的素材
        successful_materials = df['material_id'].nunique()
        print(f"\n✅ 成功测试素材: {successful_materials}/{len(self.material_ids)}")

        # 统计每个方案的获胜次数
        best_matches = df[df['is_best'] == True]
        if len(best_matches) > 0:
            scheme_counts = best_matches['scheme'].value_counts()

            print("\n🏆 各方案最佳匹配次数:")
            for scheme, count in scheme_counts.items():
                print(f"  {scheme}: {count} 个素材")

        # 平均分数
        print("\n📊 各方案平均匹配分数:")
        for scheme in df['scheme'].unique():
            scheme_df = df[df['scheme'] == scheme]
            avg_score = scheme_df['score'].mean()
            print(f"  {scheme}: {avg_score:.2%}")

        # 最佳匹配素材
        print("\n🥇 最佳匹配素材:")
        for scheme in df['scheme'].unique():
            scheme_df = df[df['scheme'] == scheme]
            if len(scheme_df) > 0:
                best_match = scheme_df.loc[scheme_df['score'].idxmax()]
                print(f"\n  {scheme}:")
                print(f"    素材ID: {best_match['material_id']}")
                print(f"    匹配分数: {best_match['score']:.2%}")
                print(f"    题材: {best_match['drama_genre']}")
                print(f"    主题: {best_match['drama_theme']}")
                print(f"    实际序列: {best_match['actual_tags']}")

    def save_detailed_results(self, df: pd.DataFrame, detailed_results: List[Dict], output_dir: str = '.'):
        """保存详细结果"""
        output_path = Path(output_dir)

        # 保存汇总表
        summary_file = output_path / 'narrative_scheme_summary.csv'
        df.to_csv(summary_file, index=False, encoding='utf-8-sig')
        print(f"\n✓ 汇总表已保存: {summary_file}")

        # 保存详细片段表
        segments_data = []
        for result in detailed_results:
            material_id = result['material_id']
            best_scheme = result['best_scheme']
            best_score = result['best_score']

            for seg in result['segments_info']:
                seg_row = {
                    'material_id': material_id,
                    'best_scheme': best_scheme,
                    'best_score': best_score,
                    **seg
                }
                segments_data.append(seg_row)

        segments_df = pd.DataFrame(segments_data)
        segments_file = output_path / 'narrative_segments_detailed.csv'
        segments_df.to_csv(segments_file, index=False, encoding='utf-8-sig')
        print(f"✓ 片段详情表已保存: {segments_file}")

        # 保存JSON格式详细结果
        json_file = output_path / 'narrative_test_detailed.json'
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(detailed_results, f, ensure_ascii=False, indent=2)
        print(f"✓ 详细结果JSON已保存: {json_file}")


def main():
    """主函数"""
    # JSON 文件目录
    json_dir = '/Users/wangchenyi/video_ad_analyzer/test_20260311/output'

    # 创建测试器
    tester = CompleteNarrativeTester(json_dir)

    # 执行测试
    df, detailed_results = tester.test_all()

    # 保存结果
    tester.save_detailed_results(df, detailed_results, '.')

    # 显示详细结果表
    print(f"\n\n{'='*80}")
    print("📋 详细结果表")
    print('='*80)

    # 选择关键列显示
    display_columns = ['material_id', 'scheme', 'is_best', 'score', 'position_score', 'tag_score', 'exact_matches', 'tag_matches']
    display_df = df[display_columns].copy()
    display_df['score'] = display_df['score'].apply(lambda x: f"{x:.2%}")
    display_df['position_score'] = display_df['position_score'].apply(lambda x: f"{x:.2%}")
    display_df['tag_score'] = display_df['tag_score'].apply(lambda x: f"{x:.2%}")
    display_df['is_best'] = display_df['is_best'].apply(lambda x: '✓' if x else '')

    print(display_df.to_string(index=False))

    # 生成汇总报告
    tester.generate_summary_report(df, detailed_results)

    print("\n" + "="*80)
    print("✅ 测试完成！")
    print("="*80)


if __name__ == '__main__':
    main()
