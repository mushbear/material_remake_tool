#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
规则引擎 - 基于规则的转场推荐系统
与AI驱动的引擎进行对比实验
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class RuleTransitionRecommendation:
    """规则引擎的转场推荐结果"""
    transition_type: str  # 转场类型
    duration: float  # 转场时长（秒）
    rule_applied: str  # 应用的规则名称
    confidence: float  # 规则置信度 (0-1)
    reason: str  # 推荐理由


@dataclass
class RuleCoherenceScore:
    """规则引擎的连贯性评分"""
    scene_similarity_score: float  # 场景相似度得分 (0-30)
    emotion_score: float  # 情感连贯性得分 (0-25)
    character_score: float  # 角色连续性得分 (0-25)
    narrative_score: float  # 叙事逻辑得分 (0-20)
    overall_score: float  # 总得分 (0-100)


class RuleBasedTransitionEngine:
    """基于规则的转场引擎"""

    def __init__(self, rules_config_path: Optional[str] = None):
        """
        初始化规则引擎

        Args:
            rules_config_path: 规则配置文件路径，不指定则使用默认规则
        """
        if rules_config_path and Path(rules_config_path).exists():
            with open(rules_config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.transition_rules = config.get("transition_rules", {})
        else:
            self.transition_rules = self._get_default_rules()

        logger.info(f"规则引擎已加载，共 {len(self.transition_rules)} 条规则")

    def _get_default_rules(self) -> Dict[str, Any]:
        """获取默认转场规则"""
        return {
            # 场景跳转规则
            "场景跳转": {
                "condition": lambda seg1, seg2: self._is_scene_jump(seg1, seg2),
                "transition": "fade",
                "duration": 1.0,
                "description": "场景跳转时使用淡入淡出"
            },

            # 时间跳跃规则（闪回）
            "时间跳跃": {
                "condition": lambda seg1, seg2: self._is_time_jump(seg1, seg2),
                "transition": "flash",
                "duration": 0.5,
                "description": "时间跳跃（闪回）时使用闪白转场"
            },

            # 情绪突变规则
            "emotion_sudden_change": {
                "conditions": {
                    "E07-高甜 → E03-施压": {
                        "transition": "cut",
                        "duration": 0.0
                    },
                    "E03-施压 → E05-反击": {
                        "transition": "cut",
                        "duration": 0.0
                    },
                    "E01-轻松 → E03-紧张": {
                        "transition": "cut",
                        "duration": 0.0
                    }
                },
                "description": "情绪突变时使用快速切换"
            },

            # 同场景规则
            "same_scene": {
                "condition": lambda seg1, seg2: not self._is_scene_jump(seg1, seg2),
                "transition": "dissolve",
                "duration": 1.5,
                "description": "同场景使用溶解过渡"
            },

            # 情绪渐进规则
            "emotion_gradual": {
                "condition": lambda seg1, seg2: self._is_emotion_gradual(seg1, seg2),
                "transition": "fade",
                "duration": 2.0,
                "description": "情绪渐进使用淡入淡出"
            },

            # 叙事功能标签规则
            "narrative_tags": {
                "F01 → F02": {
                    "transition": "dissolve",
                    "duration": 1.5,
                    "description": "强开局到背景交代，平滑过渡"
                },
                "F02 → F03": {
                    "transition": "fade",
                    "duration": 1.0,
                    "description": "背景交代到施压，逐渐紧张"
                },
                "F03 → F04": {
                    "transition": "flash",
                    "duration": 0.5,
                    "description": "施压到觉醒，闪白突出转折"
                },
                "F04 → F05": {
                    "transition": "cut",
                    "duration": 0.0,
                    "description": "觉醒到反击，快速切换"
                },
                "F05 → F06": {
                    "transition": "fade",
                    "duration": 2.0,
                    "description": "反击到悬念结尾，缓慢淡出"
                }
            }
        }

    def _is_scene_jump(self, seg1: Dict[str, Any], seg2: Dict[str, Any]) -> bool:
        """判断是否为场景跳转"""
        scene1 = seg1.get("main_location", "").lower()
        scene2 = seg2.get("main_location", "").lower()

        # 场景完全不同
        indoor_keywords = ["室内", "房间", "客厅", "卧室", "办公室"]
        outdoor_keywords = ["室外", "街道", "公园", "湖边", "广场"]

        seg1_indoor = any(kw in scene1 for kw in indoor_keywords)
        seg2_indoor = any(kw in scene2 for kw in indoor_keywords)
        seg1_outdoor = any(kw in scene1 for kw in outdoor_keywords)
        seg2_outdoor = any(kw in scene2 for kw in outdoor_keywords)

        # 从室内到室外或反之
        if (seg1_indoor and seg2_outdoor) or (seg1_outdoor and seg2_indoor):
            return True

        # 场景名称完全不相关
        if scene1 and scene2 and not any(word in scene2 for word in scene1.split()):
            return True

        return False

    def _is_time_jump(self, seg1: Dict[str, Any], seg2: Dict[str, Any]) -> bool:
        """判断是否为时间跳跃（闪回）"""
        plot1 = seg1.get("plot_summary", "").lower()
        plot2 = seg2.get("plot_summary", "").lower()

        # 检查是否有闪回关键词
        flashback_keywords = ["闪回", "回忆", "年前", "之前", "过去"]

        has_flashback1 = any(kw in plot1 for kw in flashback_keywords)
        has_flashback2 = any(kw in plot2 for kw in flashback_keywords)

        # 其中一个是闪回，另一个不是
        return has_flashback1 != has_flashback2

    def _is_emotion_gradual(self, seg1: Dict[str, Any], seg2: Dict[str, Any]) -> bool:
        """判断情绪变化是否渐进"""
        emotion1 = self._extract_emotion(seg1)
        emotion2 = self._extract_emotion(seg2)

        # 定义情绪强度等级
        emotion_levels = {
            "平静": 1,
            "轻松": 2,
            "温馨": 2,
            "紧张": 3,
            "愤怒": 4,
            "激动": 4,
            "悲伤": 3
        }

        level1 = emotion_levels.get(emotion1, 2)
        level2 = emotion_levels.get(emotion2, 2)

        # 强度差值<=1为渐进
        return abs(level2 - level1) <= 1

    def _extract_emotion(self, segment: Dict[str, Any]) -> str:
        """从片段中提取情绪"""
        emotion_tags = segment.get("emotion_trope_tags", [])

        if not emotion_tags:
            return "平静"

        # 从标签中提取情绪关键词
        for tag in emotion_tags:
            if "甜蜜" in tag or "浪漫" in tag:
                return "温馨"
            elif "紧张" in tag or "施压" in tag:
                return "紧张"
            elif "愤怒" in tag or "反击" in tag:
                return "愤怒"
            elif "轻松" in tag:
                return "轻松"
            elif "悲伤" in tag:
                return "悲伤"

        return "平静"

    def recommend_transition(
        self,
        seg1: Dict[str, Any],
        seg2: Dict[str, Any],
        seg1_tag: str = "",
        seg2_tag: str = ""
    ) -> RuleTransitionRecommendation:
        """
        基于规则推荐转场

        Args:
            seg1: 片段1数据
            seg2: 片段2数据
            seg1_tag: 片段1叙事标签
            seg2_tag: 片段2叙事标签

        Returns:
            RuleTransitionRecommendation对象
        """
        logger.info(f"规则引擎分析转场: {seg1_tag} → {seg2_tag}")

        # 按优先级检查规则

        # 1. 检查叙事功能标签规则
        narrative_key = f"{seg1_tag.split('-')[0]} → {seg2_tag.split('-')[0]}"
        if "narrative_tags" in self.transition_rules:
            narrative_rules = self.transition_rules["narrative_tags"]
            if narrative_key in narrative_rules:
                rule = narrative_rules[narrative_key]
                return RuleTransitionRecommendation(
                    transition_type=rule["transition"],
                    duration=rule["duration"],
                    rule_applied=f"叙事标签: {narrative_key}",
                    confidence=0.9,
                    reason=rule["description"]
                )

        # 2. 检查时间跳跃规则
        time_jump_rule = self.transition_rules.get("时间跳跃", {})
        if "condition" in time_jump_rule and time_jump_rule["condition"](seg1, seg2):
            return RuleTransitionRecommendation(
                transition_type=time_jump_rule["transition"],
                duration=time_jump_rule["duration"],
                rule_applied="时间跳跃",
                confidence=0.85,
                reason=time_jump_rule["description"]
            )

        # 3. 检查情绪突变规则
        emotion_rules = self.transition_rules.get("emotion_sudden_change", {})
        if "conditions" in emotion_rules:
            emotion1 = self._extract_emotion(seg1)
            emotion2 = self._extract_emotion(seg2)
            emotion_key = f"{emotion1} → {emotion2}"

            if emotion_key in emotion_rules["conditions"]:
                rule = emotion_rules["conditions"][emotion_key]
                return RuleTransitionRecommendation(
                    transition_type=rule["transition"],
                    duration=rule["duration"],
                    rule_applied=f"情绪突变: {emotion_key}",
                    confidence=0.8,
                    reason=emotion_rules["description"]
                )

        # 4. 检查场景跳转规则
        scene_jump_rule = self.transition_rules.get("场景跳转", {})
        same_scene_rule = self.transition_rules.get("same_scene", {})

        is_jump = self._is_scene_jump(seg1, seg2)

        if is_jump and "condition" in scene_jump_rule:
            return RuleTransitionRecommendation(
                transition_type=scene_jump_rule["transition"],
                duration=scene_jump_rule["duration"],
                rule_applied="场景跳转",
                confidence=0.75,
                reason=scene_jump_rule["description"]
            )
        elif not is_jump and "condition" in same_scene_rule:
            return RuleTransitionRecommendation(
                transition_type=same_scene_rule["transition"],
                duration=same_scene_rule["duration"],
                rule_applied="同场景",
                confidence=0.7,
                reason=same_scene_rule["description"]
            )

        # 5. 检查情绪渐进规则
        emotion_gradual_rule = self.transition_rules.get("emotion_gradual", {})
        if "condition" in emotion_gradual_rule and emotion_gradual_rule["condition"](seg1, seg2):
            return RuleTransitionRecommendation(
                transition_type=emotion_gradual_rule["transition"],
                duration=emotion_gradual_rule["duration"],
                rule_applied="情绪渐进",
                confidence=0.65,
                reason=emotion_gradual_rule["description"]
            )

        # 默认转场
        return RuleTransitionRecommendation(
            transition_type="cut",
            duration=0.0,
            rule_applied="默认规则",
            confidence=0.5,
            reason="无匹配规则，使用直接切换"
        )

    def calculate_coherence_score(
        self,
        seg1: Dict[str, Any],
        seg2: Dict[str, Any]
    ) -> RuleCoherenceScore:
        """
        基于规则计算连贯性得分

        Args:
            seg1: 片段1数据
            seg2: 片段2数据

        Returns:
            RuleCoherenceScore对象
        """
        # 1. 场景相似度得分 (0-30)
        scene_score = self._calculate_scene_score(seg1, seg2)

        # 2. 情感连贯性得分 (0-25)
        emotion_score = self._calculate_emotion_score(seg1, seg2)

        # 3. 角色连续性得分 (0-25)
        character_score = self._calculate_character_score(seg1, seg2)

        # 4. 叙事逻辑得分 (0-20)
        narrative_score = self._calculate_narrative_score(seg1, seg2)

        overall_score = scene_score + emotion_score + character_score + narrative_score

        return RuleCoherenceScore(
            scene_similarity_score=scene_score,
            emotion_score=emotion_score,
            character_score=character_score,
            narrative_score=narrative_score,
            overall_score=overall_score
        )

    def _calculate_scene_score(self, seg1: Dict[str, Any], seg2: Dict[str, Any]) -> float:
        """计算场景相似度得分"""
        scene1 = seg1.get("main_location", "")
        scene2 = seg2.get("main_location", "")

        if not scene1 or not scene2:
            return 15.0  # 默认中等到分

        # 完全相同
        if scene1 == scene2:
            return 30.0

        # 包含关系
        if scene1 in scene2 or scene2 in scene1:
            return 25.0

        # 场景跳转
        if self._is_scene_jump(seg1, seg2):
            return 5.0

        # 部分相似
        words1 = set(scene1.split())
        words2 = set(scene2.split())
        similarity = len(words1 & words2) / max(len(words1 | words2), 1)

        return 10.0 + similarity * 10.0

    def _calculate_emotion_score(self, seg1: Dict[str, Any], seg2: Dict[str, Any]) -> float:
        """计算情感连贯性得分"""
        emotion1 = self._extract_emotion(seg1)
        emotion2 = self._extract_emotion(seg2)

        # 相同情绪
        if emotion1 == emotion2:
            return 25.0

        # 情绪渐进
        if self._is_emotion_gradual(seg1, seg2):
            return 20.0

        # 情绪突变
        return 10.0

    def _calculate_character_score(self, seg1: Dict[str, Any], seg2: Dict[str, Any]) -> float:
        """计算角色连续性得分"""
        # 这里简化处理，实际应该分析角色列表
        # 假设都有角色出现
        has_char1 = True  # seg1.get("has_characters", True)
        has_char2 = True  # seg2.get("has_characters", True)

        if has_char1 and has_char2:
            return 25.0
        elif not has_char1 and not has_char2:
            return 15.0
        else:
            return 10.0

    def _calculate_narrative_score(self, seg1: Dict[str, Any], seg2: Dict[str, Any]) -> float:
        """计算叙事逻辑得分"""
        # 基于叙事标签
        tag1 = seg1.get("narrative_function_tag", "")
        tag2 = seg2.get("narrative_function_tag", "")

        # 定义合理的叙事顺序
        logical_sequences = [
            ("F01", "F02"),  # 强开局 -> 背景交代
            ("F01", "F04"),  # 强开局 -> 觉醒
            ("F02", "F03"),  # 背景交代 -> 施压
            ("F02", "F04"),  # 背景交代 -> 觉醒
            ("F03", "F04"),  # 施压 -> 觉醒
            ("F03", "F05"),  # 施压 -> 反击
            ("F04", "F05"),  # 觉醒 -> 反击
            ("F05", "F06"),  # 反击 -> 悬念结尾
        ]

        prefix1 = tag1.split("-")[0] if tag1 else ""
        prefix2 = tag2.split("-")[0] if tag2 else ""

        if (prefix1, prefix2) in logical_sequences:
            return 20.0
        elif prefix1 == prefix2:
            return 15.0
        else:
            return 10.0

    def recommend_transitions_for_scheme(
        self,
        segments: List[Dict[str, Any]]
    ) -> List[Tuple[int, int, RuleTransitionRecommendation]]:
        """
        为整个方案推荐转场

        Args:
            segments: 片段列表

        Returns:
            转场推荐列表 [(from_index, to_index, recommendation), ...]
        """
        recommendations = []

        for i in range(len(segments) - 1):
            seg1 = segments[i]
            seg2 = segments[i + 1]

            seg1_tag = seg1.get("narrative_function_tag", "")
            seg2_tag = seg2.get("narrative_function_tag", "")

            recommendation = self.recommend_transition(seg1, seg2, seg1_tag, seg2_tag)
            recommendations.append((i, i + 1, recommendation))

            logger.info(f"\n转场 {i} → {i + 1}:")
            logger.info(f"  类型: {recommendation.transition_type}")
            logger.info(f"  时长: {recommendation.duration}秒")
            logger.info(f"  规则: {recommendation.rule_applied}")
            logger.info(f"  理由: {recommendation.reason}")

        return recommendations

    def export_rules(self, output_path: str):
        """导出当前规则到文件"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.transition_rules, f, ensure_ascii=False, indent=2)
        logger.info(f"规则已导出到: {output_path}")


def main():
    """测试函数"""
    engine = RuleBasedTransitionEngine()

    # 测试转场推荐
    print("="*80)
    print("测试规则引擎转场推荐")
    print("="*80)

    seg1 = {
        "segment_id": "seg_1",
        "narrative_function_tag": "F01-强开局/吸睛钩子",
        "main_location": "室外-雪地湖边",
        "plot_summary": "Arthur跳入冰湖",
        "emotion_trope_tags": ["E01-紧张"]
    }

    seg2 = {
        "segment_id": "seg_2",
        "narrative_function_tag": "F04-金手指觉醒/身份曝光",
        "main_location": "室内-客厅",
        "plot_summary": "Anya得知消息",
        "emotion_trope_tags": ["E03-愤怒"]
    }

    recommendation = engine.recommend_transition(seg1, seg2, seg1["narrative_function_tag"], seg2["narrative_function_tag"])

    print(f"\n转场推荐:")
    print(f"  类型: {recommendation.transition_type}")
    print(f"  时长: {recommendation.duration}秒")
    print(f"  规则: {recommendation.rule_applied}")
    print(f"  置信度: {recommendation.confidence}")
    print(f"  理由: {recommendation.reason}")

    # 测试连贯性评分
    print("\n" + "="*80)
    print("测试连贯性评分")
    print("="*80)

    coherence = engine.calculate_coherence_score(seg1, seg2)
    print(f"\n连贯性得分:")
    print(f"  场景相似度: {coherence.scene_similarity_score:.1f}/30")
    print(f"  情感连贯性: {coherence.emotion_score:.1f}/25")
    print(f"  角色连续性: {coherence.character_score:.1f}/25")
    print(f"  叙事逻辑: {coherence.narrative_score:.1f}/20")
    print(f"  总分: {coherence.overall_score:.1f}/100")


if __name__ == "__main__":
    main()
