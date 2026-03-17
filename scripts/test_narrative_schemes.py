#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
叙事方案测试脚本
对比素材的实际叙事结构与预定义方案的匹配度
"""

import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Tuple
import glob


class NarrativeSchemeTester:
    """叙事方案测试器"""

    def __init__(self, json_dir: str):
        self.json_dir = Path(json_dir)
        self.schemes = {
            "方案1": ["F01-强开局/吸睛钩子", "F04-金手指觉醒/身份曝光", "F02-背景速递/设定交代", "F06-悬念结尾/付费卡点"],
            "方案2": ["F02-背景速递/设定交代", "F02-背景速递/设定交代", "F03-极限施压/受辱", "F04-金手指觉醒/身份曝光", "F06-悬念结尾/付费卡点"]
        }

    def load_material(self, material_id: str) -> Dict[str, Any]:
        """加载指定素材的 JSON 数据"""
        json_file = self.json_dir / f"{material_id}.json"

        if not json_file.exists():
            print(f"⚠ 文件不存在: {json_file}")
            return None

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not data.get('success'):
                print(f"⚠ 素材 {material_id} 分析失败")
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

    def calculate_match_score(self, actual_tags: List[str], scheme_tags: List[str]) -> Tuple[float, Dict]:
        """计算实际标签序列与方案的匹配分数"""
        if not actual_tags or not scheme_tags:
            return 0.0, {"reason": "Empty tags"}

        # 简单匹配：计算位置和标签都匹配的数量
        exact_matches = 0
        tag_matches = 0

        # 位置和标签都匹配
        for i in range(min(len(actual_tags), len(scheme_tags))):
            if actual_tags[i] == scheme_tags[i]:
                exact_matches += 1

        # 标签出现（不考虑位置）
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
        print(f"测试素材: {material_id}")
        print('='*80)

        # 加载数据
        data = self.load_material(material_id)
        if not data:
            return None

        # 提取叙事标签
        actual_tags = self.extract_narrative_tags(data)

        print(f"\n实际叙事序列 ({len(actual_tags)} 个片段):")
        for i, tag in enumerate(actual_tags, 1):
            print(f"  片段 {i}: {tag}")

        # 测试各个方案
        results = {}

        for scheme_name, scheme_tags in self.schemes.items():
            print(f"\n{scheme_name}: {' → '.join(scheme_tags)}")

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
            'actual_tags': actual_tags,
            'results': results,
            'best_scheme': best_scheme,
            'best_score': results[best_scheme]['score']
        }

    def test_batch(self, material_ids: List[str]) -> pd.DataFrame:
        """批量测试素材"""
        all_results = []

        for material_id in material_ids:
            result = self.test_material(material_id)
            if result:
                # 为每个方案创建一行记录
                for scheme_name, scheme_data in result['results'].items():
                    row = {
                        'material_id': material_id,
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

        # 创建 DataFrame
        df = pd.DataFrame(all_results)

        # 按素材ID和分数排序
        df = df.sort_values(['material_id', 'score'], ascending=[True, False])

        return df

    def generate_summary(self, df: pd.DataFrame):
        """生成测试汇总报告"""
        print(f"\n\n{'='*80}")
        print("测试汇总报告")
        print('='*80)

        # 统计每个方案的获胜次数
        best_matches = df[df['is_best'] == True]
        scheme_counts = best_matches['scheme'].value_counts()

        print("\n各方案最佳匹配次数:")
        for scheme, count in scheme_counts.items():
            print(f"  {scheme}: {count} 个素材")

        # 平均分数
        print("\n各方案平均匹配分数:")
        for scheme in df['scheme'].unique():
            scheme_df = df[df['scheme'] == scheme]
            avg_score = scheme_df['score'].mean()
            print(f"  {scheme}: {avg_score:.2%}")

        # 最佳匹配素材
        print("\n最佳匹配素材:")
        for scheme in df['scheme'].unique():
            scheme_df = df[df['scheme'] == scheme]
            if len(scheme_df) > 0:
                best_match = scheme_df.loc[scheme_df['score'].idxmax()]
                print(f"\n  {scheme}:")
                print(f"    素材: {best_match['material_id']}")
                print(f"    分数: {best_match['score']:.2%}")
                print(f"    实际序列: {best_match['actual_tags']}")


def main():
    """主函数"""
    # JSON 文件目录
    json_dir = '/Users/wangchenyi/video_ad_analyzer/test_20260311/output'

    # 测试素材列表
    material_ids = ['1337589', '1330603', '1330602', '1329504', '1330869', '1327758', '1327761']

    # 创建测试器
    tester = NarrativeSchemeTester(json_dir)

    # 执行测试
    df = tester.test_batch(material_ids)

    # 保存结果
    output_file = 'narrative_scheme_test_results.csv'
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\n✓ 测试结果已保存到: {output_file}")

    # 显示详细结果表
    print(f"\n\n{'='*80}")
    print("详细结果表")
    print('='*80)

    # 选择关键列显示
    display_columns = ['material_id', 'scheme', 'is_best', 'score', 'position_score', 'tag_score', 'exact_matches', 'tag_matches']
    display_df = df[display_columns].copy()
    display_df['score'] = display_df['score'].apply(lambda x: f"{x:.2%}")
    display_df['position_score'] = display_df['position_score'].apply(lambda x: f"{x:.2%}")
    display_df['tag_score'] = display_df['tag_score'].apply(lambda x: f"{x:.2%}")
    display_df['is_best'] = display_df['is_best'].apply(lambda x: '✓' if x else '')

    print(display_df.to_string(index=False))

    # 生成汇总
    tester.generate_summary(df)


if __name__ == '__main__':
    main()
