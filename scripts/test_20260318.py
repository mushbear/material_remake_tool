#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
20260318测试主脚本

这是最新版本，包含所有剪辑规则：
- F06-悬念结尾/付费卡点可以复用
- 连续相同打标的片段自动合并
- 除F01/F06外，其他片段时长必须>15秒
- 每个素材的每个场景只能使用一次
- 同一方案避免重复使用同一素材
- 最后非F06场景去掉1秒

使用方法：
    python3 scripts/test_20260318.py

作者: Claude Code
日期: 2026-03-18
版本: v3
"""

from test_20260318_v3 import Test20260318V2


def main():
    """主函数"""
    tester = Test20260318V2(
        json_dir='/Users/wangchenyi/video_ad_analyzer/test_20260311/output',
        output_dir='/Users/wangchenyi/material_remake_tool/20260318v3',
        material_csv='/Users/wangchenyi/material_remake_tool/material_list.csv'
    )

    tester.process_all()


if __name__ == '__main__':
    main()
