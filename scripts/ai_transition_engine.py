#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI驱动的转场推荐引擎
使用千问多模态API分析场景特征并推荐最佳转场效果
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
import dashscope
from dashscope import MultiModalConversation, Generation

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SceneFeatures:
    """场景特征"""
    main_scene: str  # 主要场景
    emotion: str  # 情感氛围
    color_tone: str  # 画面色调
    action_type: str  # 动作类型
    lighting: str  # 光照条件
    camera_angle: str  # 拍摄角度
    character_presence: bool  # 是否有角色
    confidence: float  # 分析置信度


@dataclass
class TransitionRecommendation:
    """转场推荐结果"""
    transition_type: str  # 转场类型：fade, dissolve, cut, flash, wipe
    duration: float  # 转场时长（秒）
    confidence: float  # 推荐置信度
    reason: str  # 推荐理由
    scene_jump_level: str  # 场景跳跃程度：小/中/大
    emotion_change: str  # 情感变化：柔和/渐进/突变
    coherence_score: float  # 连贯性得分 (0-100)


@dataclass
class CoherenceAnalysis:
    """连贯性分析结果"""
    scene_similarity: float  # 场景相似度 (0-1)
    emotion_flow: str  # 情感流动：natural/abrupt
    character_continuity: bool  # 角色连续性
    narrative_logic: str  # 叙事逻辑：logical/illogical
    overall_score: float  # 总体得分 (0-100)
    suggestions: List[str]  # 改进建议


class AITransitionEngine:
    """AI驱动的转场推荐引擎"""

    def __init__(self, api_key: str, model: str = "qwen-vl-max-latest"):
        """
        初始化AI转场引擎

        Args:
            api_key: 千问API密钥
            model: 使用的模型名称
        """
        dashscope.api_key = api_key
        self.model = model
        self.text_model = "qwen-plus"  # 用于文本分析的模型

        # 缓存已分析的场景特征
        self.feature_cache: Dict[str, SceneFeatures] = {}

    def extract_scene_features(
        self,
        video_segment_path: str,
        segment_id: str,
        use_cache: bool = True
    ) -> Optional[SceneFeatures]:
        """
        使用千问多模态API提取场景特征

        Args:
            video_segment_path: 视频片段路径或关键帧图片路径
            segment_id: 片段ID（用于缓存）
            use_cache: 是否使用缓存

        Returns:
            SceneFeatures对象
        """
        # 检查缓存
        if use_cache and segment_id in self.feature_cache:
            logger.info(f"使用缓存的特征: {segment_id}")
            return self.feature_cache[segment_id]

        try:
            logger.info(f"提取场景特征: {segment_id}")

            # 构建分析提示词
            prompt = """
            请分析这个视频片段/图像的以下特征：
            1. 主要场景（室内/室外/具体地点）
            2. 情感氛围（紧张/轻松/浪漫/悲伤等）
            3. 画面色调（明亮/阴暗/冷色调/暖色调）
            4. 动作类型（静态/对话/动作/奔跑等）
            5. 光照条件（自然光/人工光/强光/弱光）
            6. 拍摄角度（平视/俯视/仰视）
            7. 是否有主要角色出现

            请以JSON格式返回，格式如下：
            {
                "main_scene": "场景描述",
                "emotion": "情感",
                "color_tone": "色调",
                "action_type": "动作类型",
                "lighting": "光照",
                "camera_angle": "拍摄角度",
                "character_presence": true/false,
                "confidence": 0.0-1.0
            }
            """

            # 调用千问多模态API
            # 注意：这里需要传入图像，实际使用时需要先从视频中提取关键帧
            # 这里展示如何调用，实际实现需要结合视频关键帧提取

            # 示例：如果有关键帧图片
            if Path(video_segment_path).suffix in ['.jpg', '.jpeg', '.png']:
                response = MultiModalConversation.call(
                    model=self.model,
                    messages=[{
                        'role': 'user',
                        'content': [
                            {'image': f'file://{video_segment_path}'},
                            {'text': prompt}
                        ]
                    }]
                )

                if response.status_code == 200:
                    # 解析返回的JSON
                    result_text = response.output.choices[0].message.content[0]['text']
                    features_data = json.loads(result_text)

                    features = SceneFeatures(**features_data)

                    # 缓存结果
                    self.feature_cache[segment_id] = features

                    return features

            # 如果没有图片，返回基于元数据的简单分析
            # 实际使用中应该先提取关键帧
            logger.warning(f"无法提取关键帧，返回默认特征: {segment_id}")
            return self._get_default_features(segment_id)

        except Exception as e:
            logger.error(f"提取场景特征失败: {e}")
            return None

    def _get_default_features(self, segment_id: str) -> SceneFeatures:
        """返回默认场景特征（当无法提取时）"""
        return SceneFeatures(
            main_scene="未知",
            emotion="中性",
            color_tone="中性",
            action_type="未知",
            lighting="未知",
            camera_angle="平视",
            character_presence=True,
            confidence=0.0
        )

    def analyze_transition(
        self,
        seg1_features: SceneFeatures,
        seg2_features: SceneFeatures,
        seg1_tag: str,
        seg2_tag: str
    ) -> TransitionRecommendation:
        """
        分析两个片段间的最佳转场

        Args:
            seg1_features: 片段1的特征
            seg2_features: 片段2的特征
            seg1_tag: 片段1的叙事标签
            seg2_tag: 片段2的叙事标签

        Returns:
            TransitionRecommendation对象
        """
        try:
            logger.info(f"分析转场: {seg1_tag} → {seg2_tag}")

            # 构建分析提示词
            prompt = f"""
            作为专业视频剪辑师，请分析以下两个场景之间应该使用什么转场效果：

            场景1：
            - 叙事标签: {seg1_tag}
            - 主要场景: {seg1_features.main_scene}
            - 情感氛围: {seg1_features.emotion}
            - 画面色调: {seg1_features.color_tone}
            - 动作类型: {seg1_features.action_type}
            - 光照: {seg1_features.lighting}
            - 拍摄角度: {seg1_features.camera_angle}

            场景2：
            - 叙事标签: {seg2_tag}
            - 主要场景: {seg2_features.main_scene}
            - 情感氛围: {seg2_features.emotion}
            - 画面色调: {seg2_features.color_tone}
            - 动作类型: {seg2_features.action_type}
            - 光照: {seg2_features.lighting}
            - 拍摄角度: {seg2_features.camera_angle}

            请分析并返回JSON格式：
            {{
                "scene_jump_level": "小/中/大",
                "emotion_change": "柔和/渐进/突变",
                "recommended_transition": "fade/dissolve/cut/flash/wipe",
                "transition_duration": 秒数(0.5-3.0),
                "confidence": 0.0-1.0,
                "reason": "推荐理由"
            }}

            转场类型说明：
            - fade: 淡入淡出（适合场景变化、时间跳跃）
            - dissolve: 溶解（适合同场景、情绪渐进）
            - cut: 直接切换（适合动作场景、情绪突变）
            - flash: 闪白（适合闪回、重大转折）
            - wipe: 擦除（适合并列场景、对比）
            """

            # 调用千问文本API
            response = Generation.call(
                model=self.text_model,
                prompt=prompt,
                result_format='message'
            )

            if response.status_code == 200:
                result_text = response.output.choices[0].message.content
                recommendation_data = json.loads(result_text)

                # 计算连贯性得分
                coherence_score = self._calculate_coherence_score(
                    seg1_features, seg2_features, recommendation_data
                )

                return TransitionRecommendation(
                    transition_type=recommendation_data.get("recommended_transition", "cut"),
                    duration=recommendation_data.get("transition_duration", 1.0),
                    confidence=recommendation_data.get("confidence", 0.7),
                    reason=recommendation_data.get("reason", ""),
                    scene_jump_level=recommendation_data.get("scene_jump_level", "中"),
                    emotion_change=recommendation_data.get("emotion_change", "渐进"),
                    coherence_score=coherence_score
                )
            else:
                logger.error(f"AI分析失败: {response.message}")
                return self._get_default_transition()

        except Exception as e:
            logger.error(f"转场分析失败: {e}")
            return self._get_default_transition()

    def _get_default_transition(self) -> TransitionRecommendation:
        """返回默认转场推荐"""
        return TransitionRecommendation(
            transition_type="cut",
            duration=0.0,
            confidence=0.0,
            reason="默认转场",
            scene_jump_level="未知",
            emotion_change="未知",
            coherence_score=50.0
        )

    def _calculate_coherence_score(
        self,
        seg1: SceneFeatures,
        seg2: SceneFeatures,
        analysis: Dict[str, Any]
    ) -> float:
        """
        基于AI分析计算连贯性得分

        Args:
            seg1: 片段1特征
            seg2: 片段2特征
            analysis: AI分析结果

        Returns:
            得分 (0-100)
        """
        score = 0.0

        # 1. 场景相似度 (30分)
        if seg1.main_scene == seg2.main_scene:
            score += 30
        elif seg1.main_scene in seg2.main_scene or seg2.main_scene in seg1.main_scene:
            score += 20
        else:
            # 场景跳跃程度
            jump_level = analysis.get("scene_jump_level", "中")
            if jump_level == "小":
                score += 25
            elif jump_level == "中":
                score += 15
            else:  # 大
                score += 5

        # 2. 情感连贯性 (25分)
        emotion_change = analysis.get("emotion_change", "渐进")
        if emotion_change == "柔和":
            score += 25
        elif emotion_change == "渐进":
            score += 20
        else:  # 突变
            score += 10

        # 3. 角色连续性 (25分)
        if seg1.character_presence and seg2.character_presence:
            score += 25
        elif not seg1.character_presence and not seg2.character_presence:
            score += 15
        else:
            score += 10

        # 4. 叙事逻辑 (20分)
        # AI置信度
        confidence = analysis.get("confidence", 0.5)
        score += confidence * 20

        return min(score, 100.0)

    def analyze_coherence(
        self,
        seg1_features: SceneFeatures,
        seg2_features: SceneFeatures,
        seg1_tag: str,
        seg2_tag: str
    ) -> CoherenceAnalysis:
        """
        深度连贯性分析

        Args:
            seg1_features: 片段1特征
            seg2_features: 片段2特征
            seg1_tag: 片段1叙事标签
            seg2_tag: 片段2叙事标签

        Returns:
            CoherenceAnalysis对象
        """
        try:
            logger.info(f"深度连贯性分析: {seg1_tag} → {seg2_tag}")

            prompt = f"""
            请深度分析以下两个视频片段之间的连贯性：

            片段1：
            - 标签: {seg1_tag}
            - 场景: {seg1_features.main_scene}
            - 情感: {seg1_features.emotion}
            - 角色: {'有' if seg1_features.character_presence else '无'}

            片段2：
            - 标签: {seg2_tag}
            - 场景: {seg2_features.main_scene}
            - 情感: {seg2_features.emotion}
            - 角色: {'有' if seg2_features.character_presence else '无'}

            请以JSON格式返回：
            {{
                "scene_similarity": 0.0-1.0,
                "emotion_flow": "natural/abrupt",
                "character_continuity": true/false,
                "narrative_logic": "logical/illogical",
                "overall_score": 0-100,
                "suggestions": ["建议1", "建议2"]
            }}
            """

            response = Generation.call(
                model=self.text_model,
                prompt=prompt,
                result_format='message'
            )

            if response.status_code == 200:
                result_text = response.output.choices[0].message.content
                analysis_data = json.loads(result_text)

                return CoherenceAnalysis(
                    scene_similarity=analysis_data.get("scene_similarity", 0.5),
                    emotion_flow=analysis_data.get("emotion_flow", "natural"),
                    character_continuity=analysis_data.get("character_continuity", False),
                    narrative_logic=analysis_data.get("narrative_logic", "logical"),
                    overall_score=analysis_data.get("overall_score", 50.0),
                    suggestions=analysis_data.get("suggestions", [])
                )
            else:
                logger.error(f"连贯性分析失败: {response.message}")
                return self._get_default_coherence()

        except Exception as e:
            logger.error(f"连贯性分析失败: {e}")
            return self._get_default_coherence()

    def _get_default_coherence(self) -> CoherenceAnalysis:
        """返回默认连贯性分析"""
        return CoherenceAnalysis(
            scene_similarity=0.5,
            emotion_flow="natural",
            character_continuity=False,
            narrative_logic="logical",
            overall_score=50.0,
            suggestions=[]
        )

    def recommend_transitions_for_scheme(
        self,
        segments: List[Dict[str, Any]],
        scene_features_dict: Dict[str, SceneFeatures]
    ) -> List[Tuple[int, int, TransitionRecommendation]]:
        """
        为整个方案推荐转场

        Args:
            segments: 片段列表 [{"segment_id": "...", "tag": "...", ...}, ...]
            scene_features_dict: 片段ID到场景特征的映射

        Returns:
            转场推荐列表 [(from_index, to_index, recommendation), ...]
        """
        recommendations = []

        for i in range(len(segments) - 1):
            seg1 = segments[i]
            seg2 = segments[i + 1]

            seg1_id = seg1.get("segment_id", f"seg_{i}")
            seg2_id = seg2.get("segment_id", f"seg_{i+1}")

            seg1_features = scene_features_dict.get(seg1_id)
            seg2_features = scene_features_dict.get(seg2_id)

            if seg1_features and seg2_features:
                recommendation = self.analyze_transition(
                    seg1_features,
                    seg2_features,
                    seg1.get("tag", ""),
                    seg2.get("tag", "")
                )

                recommendations.append((i, i + 1, recommendation))

                logger.info(f"\n转场 {i} → {i + 1}:")
                logger.info(f"  类型: {recommendation.transition_type}")
                logger.info(f"  时长: {recommendation.duration}秒")
                logger.info(f"  理由: {recommendation.reason}")
                logger.info(f"  得分: {recommendation.coherence_score:.1f}")

        return recommendations

    def extract_features_from_json(
        self,
        json_data: Dict[str, Any],
        segment_id: str
    ) -> SceneFeatures:
        """
        从JSON数据中提取场景特征（作为AI分析的补充或替代）

        Args:
            json_data: 视频分析JSON数据
            segment_id: 片段ID

        Returns:
            SceneFeatures对象
        """
        try:
            # 从JSON中提取信息
            result = json_data.get("result", {})
            segments = result.get("segments", [])

            # 找到对应片段
            segment_data = None
            for seg in segments:
                if seg.get("segment_id") == segment_id:
                    segment_data = seg
                    break

            if not segment_data:
                return self._get_default_features(segment_id)

            # 提取特征
            main_location = segment_data.get("main_location", "未知")
            plot_summary = segment_data.get("plot_summary", "")
            emotion_tags = segment_data.get("emotion_trope_tags", [])

            # 简单推断情感
            emotion = "中性"
            if any("甜蜜" in tag or "浪漫" in tag for tag in emotion_tags):
                emotion = "浪漫"
            elif any("紧张" in tag or "施压" in tag for tag in emotion_tags):
                emotion = "紧张"
            elif any("愤怒" in tag or "反击" in tag for tag in emotion_tags):
                emotion = "愤怒"

            return SceneFeatures(
                main_scene=main_location,
                emotion=emotion,
                color_tone="中性",  # JSON中通常没有
                action_type="对话",  # 简化处理
                lighting="未知",
                camera_angle="平视",
                character_presence=True,  # 假设都有角色
                confidence=0.7
            )

        except Exception as e:
            logger.error(f"从JSON提取特征失败: {e}")
            return self._get_default_features(segment_id)

    def clear_cache(self):
        """清空特征缓存"""
        self.feature_cache.clear()
        logger.info("特征缓存已清空")


def main():
    """测试函数"""
    # 需要配置千问API密钥
    import os
    api_key = os.getenv("DASHSCOPE_API_KEY", "your-api-key-here")

    engine = AITransitionEngine(api_key=api_key)

    # 测试场景特征提取
    print("="*80)
    print("测试场景特征提取")
    print("="*80)

    # 这里需要实际的图片路径
    # features = engine.extract_scene_features("test_frame.jpg", "seg_1")
    # print(features)

    # 测试转场分析
    print("\n" + "="*80)
    print("测试转场分析")
    print("="*80)

    # 创建测试特征
    seg1_features = SceneFeatures(
        main_scene="室外-雪地湖边",
        emotion="紧张",
        color_tone="冷色调",
        action_type="奔跑",
        lighting="自然光",
        camera_angle="平视",
        character_presence=True,
        confidence=0.9
    )

    seg2_features = SceneFeatures(
        main_scene="室内-客厅",
        emotion="温馨",
        color_tone="暖色调",
        action_type="对话",
        lighting="人工光",
        camera_angle="平视",
        character_presence=True,
        confidence=0.85
    )

    recommendation = engine.analyze_transition(
        seg1_features,
        seg2_features,
        "F01-强开局/吸睛钩子",
        "F02-背景速递/设定交代"
    )

    print(f"\n转场推荐:")
    print(f"  类型: {recommendation.transition_type}")
    print(f"  时长: {recommendation.duration}秒")
    print(f"  置信度: {recommendation.confidence}")
    print(f"  理由: {recommendation.reason}")
    print(f"  连贯性得分: {recommendation.coherence_score:.1f}")


if __name__ == "__main__":
    main()
