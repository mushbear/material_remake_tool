#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
20260319 素材剪辑测试方案
将41个素材视频按照指定规则剪辑成4个新视频
"""

import os
import sys
import json
import csv
import shutil
import subprocess
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field, asdict
from collections import defaultdict
import hashlib

# 添加父目录到路径以导入通用模块
sys.path.insert(0, str(Path(__file__).parent.parent))

# ============================================================
# 配置
# ============================================================
MATERIAL_LIST_PATH = "/Users/wangchenyi/video_ad_analyzer/test_20260319/material_list.csv"
MATERIAL_JSON_DIR = "/Users/wangchenyi/video_ad_analyzer/test_20260319/material"
ORIGIN_JSON_PATH = "/Users/wangchenyi/video_ad_analyzer/test_20260319/origin_json/all.json"
OUTPUT_DIR = "/Users/wangchenyi/material_remake_tool/20260319v1"

# 方案定义
SCHEME_1 = ["F01", "F04", "F02", "F06"]  # 方案1
SCHEME_2 = ["F02", "F03", "F04", "F06"]  # 方案2

# 时长限制（秒）
MIN_DURATION_NON_SPECIAL = 15  # 非F01/F06场景最小时长

# AI模型
AI_MODEL = "qwen3.5-plus"

# ============================================================
# 数据类
# ============================================================
@dataclass
class SceneInfo:
    """场景信息"""
    material_id: str
    material_name: str
    video_url: str
    segment_id: int
    start_time: float
    end_time: float
    duration: float
    plot_summary: str
    narrative_function_tag: str
    characters: List[Dict]
    main_location: str = ""
    emotion_level: int = 0
    emotion_polarity: int = 0
    is_highlight: bool = False
    has_logo: bool = False  # 新增：是否有logo
    logo_position: str = ""  # 新增：logo位置

    # 匹配信息（由SceneTagger填充）
    origin_episode: Optional[int] = None
    origin_segment_index: Optional[int] = None
    match_score: float = 0.0
    is_matched: bool = False
    is_usable: bool = True  # 新增：是否可用（未匹配的非F06场景不可用）
    match_note: str = ""


@dataclass
class OriginScene:
    """原片场景信息"""
    episode: int
    segment_id: int
    segment_index: int  # 该集中的第几个场景
    start_time: float
    end_time: float
    duration: float
    plot_summary: str
    narrative_function_tag: str
    characters: List[Dict]


@dataclass
class MergedScene:
    """合并后的场景"""
    scenes: List[SceneInfo]
    tag: str
    start_time: float
    end_time: float
    total_duration: float
    merged_count: int
    origin_episode: Optional[int] = None
    origin_segment_index: Optional[int] = None
    match_score: float = 0.0
    is_matched: bool = False
    has_logo: bool = False  # 新增：是否有logo
    is_usable: bool = True  # 新增：是否可用


@dataclass
class EditingPlan:
    """剪辑计划"""
    scheme_id: int
    scheme_name: str
    scenes: List[MergedScene]
    total_duration: float
    is_valid: bool
    invalid_reason: str = ""


# ============================================================
# 场景匹配器
# ============================================================
class SceneMatcher:
    """场景匹配器 - 为素材场景找到原片中对应的场景"""

    def __init__(self, origin_scenes: List[OriginScene]):
        self.origin_scenes = origin_scenes
        # 构建索引：集数 -> 场景列表
        self.episode_index = defaultdict(list)
        for scene in origin_scenes:
            self.episode_index[scene.episode].append(scene)

    def _normalize_tag(self, tag: str) -> str:
        """提取标签前缀（F01, F02等）"""
        if not tag:
            return ""
        match = re.match(r'(F\d+)', tag)
        return match.group(1) if match else tag

    def _compute_text_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度（基于关键词重叠）"""
        if not text1 or not text2:
            return 0.0

        # 简单的关键词匹配（实际应用中可以用向量相似度）
        words1 = set(re.findall(r'\w+', text1.lower()))
        words2 = set(re.findall(r'\w+', text2.lower()))

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def _compute_character_similarity(self, chars1: List[Dict], chars2: List[Dict]) -> float:
        """计算人物相似度"""
        if not chars1 or not chars2:
            return 0.0

        # 提取人物名称
        names1 = {c.get('character_id', '').lower() for c in chars1}
        names2 = {c.get('character_id', '').lower() for c in chars2}

        # 过滤空名称
        names1 = {n for n in names1 if n}
        names2 = {n for n in names2 if n}

        if not names1 or not names2:
            return 0.0

        intersection = len(names1 & names2)
        union = len(names1 | names2)

        return intersection / union if union > 0 else 0.0

    def _compute_duration_similarity(self, dur1: float, dur2: float) -> float:
        """计算时长相似度"""
        if dur1 <= 0 or dur2 <= 0:
            return 0.0

        # 时长差异越小，相似度越高
        ratio = min(dur1, dur2) / max(dur1, dur2)
        return ratio

    def compute_similarity(self, material_scene: SceneInfo, origin_scene: OriginScene) -> float:
        """计算综合相似度"""
        # 权重设置
        W_PLOT = 0.5      # 剧情摘要权重
        W_CHAR = 0.35     # 人物权重
        W_DURATION = 0.15 # 时长权重

        plot_sim = self._compute_text_similarity(
            material_scene.plot_summary,
            origin_scene.plot_summary
        )

        char_sim = self._compute_character_similarity(
            material_scene.characters,
            origin_scene.characters
        )

        dur_sim = self._compute_duration_similarity(
            material_scene.duration,
            origin_scene.duration
        )

        total = W_PLOT * plot_sim + W_CHAR * char_sim + W_DURATION * dur_sim
        return total

    def match_scene(self, material_scene: SceneInfo) -> Tuple[Optional[OriginScene], float]:
        """匹配单个场景到原片"""
        best_match = None
        best_score = 0.0

        for origin_scene in self.origin_scenes:
            score = self.compute_similarity(material_scene, origin_scene)
            if score > best_score:
                best_score = score
                best_match = origin_scene

        return best_match, best_score

    def match_all_scenes(self, material_scenes: List[SceneInfo]) -> Dict[str, Tuple[Optional[OriginScene], float]]:
        """批量匹配所有场景"""
        results = {}
        for scene in material_scenes:
            key = f"{scene.material_id}_{scene.segment_id}"
            results[key] = self.match_scene(scene)
        return results


# ============================================================
# 场景打标器
# ============================================================
class SceneTagger:
    """场景打标器"""

    def __init__(self, matcher: SceneMatcher, min_match_score: float = 0.2):
        self.matcher = matcher
        self.min_match_score = min_match_score

    def tag_scene(self, scene: SceneInfo) -> SceneInfo:
        """打标单个场景"""
        match, score = self.matcher.match_scene(scene)

        if match and score >= self.min_match_score:
            scene.origin_episode = match.episode
            scene.origin_segment_index = match.segment_index
            scene.match_score = score
            scene.is_matched = True
            scene.is_usable = True
            scene.match_note = f"匹配到第{match.episode}集第{match.segment_index}个场景"
        else:
            scene.is_matched = False
            scene.match_score = score if score else 0.0

            # 特殊处理：F06类型
            tag_prefix = self.matcher._normalize_tag(scene.narrative_function_tag)
            if tag_prefix == "F06":
                scene.is_usable = True
                scene.match_note = "F06类型，无需匹配原片"
            else:
                # V2修改：未匹配的非F06场景不使用
                scene.is_usable = False
                scene.match_note = f"未找到匹配（相似度: {score:.2f}），该场景不使用"

        return scene

    def tag_all_scenes(self, scenes: List[SceneInfo]) -> List[SceneInfo]:
        """打标所有场景"""
        return [self.tag_scene(scene) for scene in scenes]


# ============================================================
# 场景合并器
# ============================================================
class SceneMerger:
    """合并连续相同打标的场景"""

    def merge_consecutive(self, scenes: List[SceneInfo]) -> List[MergedScene]:
        """合并连续相同tag的场景"""
        if not scenes:
            return []

        merged = []
        current_group = [scenes[0]]
        current_tag = self._get_tag_prefix(scenes[0].narrative_function_tag)

        for scene in scenes[1:]:
            tag = self._get_tag_prefix(scene.narrative_function_tag)

            if tag == current_tag:
                current_group.append(scene)
            else:
                # 保存当前组
                merged.append(self._create_merged_scene(current_group))
                # 开始新组
                current_group = [scene]
                current_tag = tag

        # 保存最后一组
        merged.append(self._create_merged_scene(current_group))

        return merged

    def _get_tag_prefix(self, tag: str) -> str:
        """获取标签前缀"""
        if not tag:
            return ""
        match = re.match(r'(F\d+)', tag)
        return match.group(1) if match else tag

    def _create_merged_scene(self, scenes: List[SceneInfo]) -> MergedScene:
        """创建合并后的场景"""
        if not scenes:
            return None

        tag = self._get_tag_prefix(scenes[0].narrative_function_tag)
        start_time = scenes[0].start_time
        end_time = scenes[-1].end_time
        total_duration = sum(s.duration for s in scenes)

        # 使用第一个场景的匹配信息
        first_scene = scenes[0]

        # 检查是否有logo（任一场景有logo则合并后的场景有logo）
        has_logo = any(s.has_logo for s in scenes)

        # 检查是否可用（所有场景都可用则合并后的场景可用）
        is_usable = all(s.is_usable for s in scenes)

        return MergedScene(
            scenes=scenes,
            tag=tag,
            start_time=start_time,
            end_time=end_time,
            total_duration=total_duration,
            merged_count=len(scenes),
            origin_episode=first_scene.origin_episode,
            origin_segment_index=first_scene.origin_segment_index,
            match_score=first_scene.match_score,
            is_matched=first_scene.is_matched,
            has_logo=has_logo,
            is_usable=is_usable
        )


# ============================================================
# 方案生成器
# ============================================================
class SchemeGenerator:
    """方案生成器"""

    def __init__(self, all_merged_scenes: Dict[str, List[MergedScene]]):
        """
        all_merged_scenes: {material_id: [MergedScene, ...]}
        """
        self.all_merged_scenes = all_merged_scenes
        # 按tag索引所有场景
        self.tag_index = defaultdict(list)
        for material_id, scenes in all_merged_scenes.items():
            for scene in scenes:
                self.tag_index[scene.tag].append((material_id, scene))

        # 记录场景使用情况：{(material_id, tag): used_count}
        self.usage_tracker = defaultdict(int)

    def reset_usage(self):
        """重置使用记录"""
        self.usage_tracker = defaultdict(int)

    def generate_fixed_scheme(self, scheme_tags: List[str], scheme_id: int, excluded_material_ids: Set[str] = None) -> EditingPlan:
        """生成固定方案

        Args:
            scheme_tags: 方案标签列表
            scheme_id: 方案ID
            excluded_material_ids: 需要排除的素材ID集合（用于避免相似度过高）
        """
        self.reset_usage()
        if excluded_material_ids is None:
            excluded_material_ids = set()

        selected_scenes = []
        is_valid = True
        invalid_reason = ""

        # V4新增：跟踪每个素材在当前方案中已使用的场景数（每个素材最多2个场景）
        material_scene_count = defaultdict(int)

        # V4新增：跟踪当前方案的最大集数（用于确保集数递增）
        last_episode = 0

        for tag in scheme_tags:
            available_scenes = []

            # 收集可用场景
            for material_id, scene in self.tag_index.get(tag, []):
                # V2新增：过滤不可用的场景
                if not scene.is_usable:
                    continue

                # V2新增：排除指定的素材ID
                if material_id in excluded_material_ids:
                    continue

                # V4新增：每个素材最多使用2个场景
                if material_scene_count[material_id] >= 2:
                    continue

                # V4新增：集数顺序检查（场景集数必须大于等于当前最大集数）
                if scene.origin_episode is not None and scene.origin_episode < last_episode:
                    continue

                # F06可以重复使用
                if tag == "F06":
                    available_scenes.append((material_id, scene))
                else:
                    # 非F06检查使用记录
                    usage_key = (material_id, tag)
                    if self.usage_tracker[usage_key] == 0:
                        available_scenes.append((material_id, scene))

            if not available_scenes:
                is_valid = False
                invalid_reason = f"找不到类型为 {tag} 的可用场景（集数需>={last_episode}）"
                break

            # 选择场景（优先选择匹配的且集数最小的）
            selected = None
            matched_scenes = [(mid, s) for mid, s in available_scenes if s.is_matched]
            if matched_scenes:
                # 按集数排序，选择集数最小的
                matched_scenes.sort(key=lambda x: x[1].origin_episode or 999)
                selected = matched_scenes[0]

            if not selected:
                # 如果没有匹配的，选择集数最小的
                available_scenes.sort(key=lambda x: x[1].origin_episode or 999)
                selected = available_scenes[0]

            material_id, scene = selected
            selected_scenes.append(scene)

            # 更新使用记录
            if tag != "F06":
                self.usage_tracker[(material_id, tag)] += 1

            # V4新增：更新素材场景使用计数
            material_scene_count[material_id] += 1

            # V4新增：更新最大集数
            if scene.origin_episode is not None:
                last_episode = scene.origin_episode

        # 验证时长
        if is_valid:
            for i, scene in enumerate(selected_scenes):
                tag = scene.tag
                # F01和F06不限制时长
                if tag not in ["F01", "F06"]:
                    if scene.total_duration < MIN_DURATION_NON_SPECIAL:
                        is_valid = False
                        invalid_reason = f"场景 {tag} 时长不足 {MIN_DURATION_NON_SPECIAL} 秒（实际: {scene.total_duration:.1f}秒）"
                        break

        # 验证顺序
        if is_valid and len(selected_scenes) > 1:
            order_valid, order_reason = self._validate_order(selected_scenes)
            if not order_valid:
                is_valid = False
                invalid_reason = order_reason

        total_duration = sum(s.total_duration for s in selected_scenes) if selected_scenes else 0

        scheme_name = f"方案{scheme_id}: {' → '.join(scheme_tags)}"

        return EditingPlan(
            scheme_id=scheme_id,
            scheme_name=scheme_name,
            scenes=selected_scenes,
            total_duration=total_duration,
            is_valid=is_valid,
            invalid_reason=invalid_reason
        )

    def _validate_order(self, scenes: List[MergedScene]) -> Tuple[bool, str]:
        """验证场景顺序是否与原片一致

        V4修改：
        1. 首先判定集数顺序（集数应递增）
        2. 同一集中则按该集的场景顺序判定
        """
        # 只验证有匹配信息的场景
        matched_scenes = [(i, s) for i, s in enumerate(scenes) if s.is_matched]

        if len(matched_scenes) < 2:
            return True, ""

        # V4新增：检查集数顺序是否递增
        for i in range(len(matched_scenes) - 1):
            _, scene1 = matched_scenes[i]
            _, scene2 = matched_scenes[i + 1]

            if scene1.origin_episode is not None and scene2.origin_episode is not None:
                if scene1.origin_episode > scene2.origin_episode:
                    return False, f"集数顺序错误：第{scene1.origin_episode}集在第{scene2.origin_episode}集之后"

        # 按集数分组，检查同一集内场景顺序
        episodes_scenes = defaultdict(list)
        for idx, scene in matched_scenes:
            episodes_scenes[scene.origin_episode].append((idx, scene))

        # 检查每个集内的场景顺序
        for episode, scene_list in episodes_scenes.items():
            if len(scene_list) < 2:
                continue

            # 按在方案中的出现顺序排序
            scene_list.sort(key=lambda x: x[0])

            # 检查原片中的场景序号是否递增
            for i in range(len(scene_list) - 1):
                _, scene1 = scene_list[i]
                _, scene2 = scene_list[i + 1]

                if scene1.origin_segment_index > scene2.origin_segment_index:
                    return False, f"第{episode}集内场景顺序错误：场景{scene1.origin_segment_index}应在场景{scene2.origin_segment_index}之后"

        return True, ""

    def get_scene_distribution(self) -> Dict[str, int]:
        """获取各类型场景的分布"""
        distribution = defaultdict(int)
        for tag, scenes in self.tag_index.items():
            distribution[tag] = len(scenes)
        return dict(distribution)

    def get_available_scenes_by_tag(self, tag: str) -> List[Tuple[str, MergedScene]]:
        """获取指定tag的所有可用场景"""
        return self.tag_index.get(tag, [])


# ============================================================
# AI方案生成器
# ============================================================
class AISchemeGenerator:
    """使用AI生成方案3和方案4"""

    def __init__(self, generator: SchemeGenerator):
        self.generator = generator
        self.distribution = generator.get_scene_distribution()

    def generate_ai_schemes(self, excluded_material_ids: Set[str] = None) -> List[EditingPlan]:
        """使用AI生成两个最优方案

        Args:
            excluded_material_ids: 需要排除的素材ID集合
        """
        if excluded_material_ids is None:
            excluded_material_ids = set()

        # 获取场景分布信息
        distribution = self.distribution

        # 构建提示词
        prompt = self._build_prompt(distribution)

        # 调用AI - 使用dashscope
        try:
            import dashscope
            from dashscope import Generation

            # 检查API密钥
            api_key = os.environ.get('DASHSCOPE_API_KEY')
            if not api_key:
                print("未设置DASHSCOPE_API_KEY环境变量，使用默认方案")
                return self._get_default_schemes(excluded_material_ids)

            dashscope.api_key = api_key

            # 调用通义千问
            response = Generation.call(
                model='qwen-plus',
                prompt=prompt,
                max_tokens=2000,
                temperature=0.7,
                result_format='message'
            )

            if response.status_code == 200:
                ai_response = response.output.choices[0].message.content
                # 解析AI响应
                schemes = self._parse_ai_response(ai_response, excluded_material_ids)
                return schemes
            else:
                print(f"AI调用失败: {response.code} - {response.message}")
                return self._get_default_schemes(excluded_material_ids)

        except Exception as e:
            print(f"AI生成方案失败: {e}")
            # 返回默认方案
            return self._get_default_schemes(excluded_material_ids)

    def _build_prompt(self, distribution: Dict[str, int]) -> str:
        """构建AI提示词"""
        available_tags = [tag for tag, count in distribution.items() if count > 0]

        prompt = f"""你是一个专业的短视频剪辑师。我有一些已分类的视频场景素材，需要你帮我设计两个最优的剪辑方案。

可用场景类型及数量：
{json.dumps(distribution, ensure_ascii=False, indent=2)}

场景类型说明：
- F01: 开场钩子/悬念引入
- F02: 背景速递/设定交代
- F03: 极限施压/受辱
- F04: 金手指觉醒/身份曝光
- F05: 高潮打脸/绝地反击
- F06: 结尾悬念/下集预告

要求：
1. 每个方案必须是4-6个场景类型组合
2. 每个方案必须以F06结尾
3. 场景类型可以重复使用（如F03-F03-F05-F06）
4. 方案应该符合短剧的叙事逻辑
5. 两个方案应该有不同的侧重点

请直接输出两个方案的JSON数组格式：
[
  {{"scheme_id": 3, "scheme_name": "方案3描述", "tags": ["F01", "F03", "F05", "F06"], "reason": "选择理由"}},
  {{"scheme_id": 4, "scheme_name": "方案4描述", "tags": ["F02", "F03", "F03", "F05", "F06"], "reason": "选择理由"}}
]
"""
        return prompt

    def _parse_ai_response(self, response: str, excluded_material_ids: Set[str] = None) -> List[EditingPlan]:
        """解析AI响应"""
        try:
            # 提取JSON部分
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                schemes_data = json.loads(json_match.group())
            else:
                raise ValueError("无法从响应中提取JSON")

            plans = []
            for scheme in schemes_data:
                tags = scheme.get('tags', [])
                scheme_id = scheme.get('scheme_id', len(plans) + 3)

                # 使用SchemeGenerator生成实际方案
                plan = self.generator.generate_fixed_scheme(tags, scheme_id, excluded_material_ids)
                plans.append(plan)

            return plans

        except Exception as e:
            print(f"解析AI响应失败: {e}")
            return self._get_default_schemes(excluded_material_ids)

    def _get_default_schemes(self, excluded_material_ids: Set[str] = None) -> List[EditingPlan]:
        """获取默认方案（当AI失败时）"""
        if excluded_material_ids is None:
            excluded_material_ids = set()

        default_schemes = [
            ["F01", "F03", "F05", "F06"],
            ["F02", "F03", "F04", "F05", "F06"]
        ]

        plans = []
        for i, tags in enumerate(default_schemes):
            plan = self.generator.generate_fixed_scheme(tags, i + 3, excluded_material_ids)
            plans.append(plan)

        return plans


# ============================================================
# 视频剪辑器
# ============================================================
class VideoComposer:
    """视频剪辑器"""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.temp_dir = self.output_dir / "temp"
        self.temp_dir.mkdir(exist_ok=True)

    def _check_scene_logo(self, scene: MergedScene) -> bool:
        """检查场景是否有logo"""
        return scene.has_logo

    def _validate_logo_requirements(self, scenes: List[MergedScene]) -> Tuple[bool, str]:
        """验证Logo要求

        V4修改：非F06场景有logo已在_retag_logo_scenes()中重新标记为F06
        这里只验证F06场景必须有logo
        """
        for i, scene in enumerate(scenes):
            has_logo = self._check_scene_logo(scene)
            is_f06 = scene.tag == "F06"

            # F06必须有logo
            if is_f06 and not has_logo:
                return False, f"F06场景(第{i+1}个)没有logo"

        return True, ""

    def download_video(self, url: str, output_path: str) -> bool:
        """下载视频"""
        try:
            cmd = [
                "curl", "-L", "-o", output_path, url
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=300)
            return result.returncode == 0
        except Exception as e:
            print(f"下载视频失败: {e}")
            return False

    def cut_segment(self, video_path: str, start: float, end: float, output_path: str,
                    is_last_segment: bool = False, tag: str = "") -> bool:
        """剪辑单个片段

        V4修复：添加视频实际时长检查，防止end_time超出视频时长导致定格画面
        V4修改：移除V3的"剪掉1秒"逻辑（非F06场景有logo已在_retag_logo_scenes()中重新标记为F06）
        """
        try:
            # 获取视频实际时长
            probe_cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path
            ]
            probe_result = subprocess.run(probe_cmd, capture_output=True, timeout=30)
            actual_duration = float(probe_result.stdout.strip())

            # 检查请求的结束时间是否超出视频实际时长
            if end > actual_duration:
                print(f"  ⚠ 警告: 请求的end_time({end:.1f}s) 超出视频实际时长({actual_duration:.1f}s)")
                print(f"  将截断到视频实际时长")
                end = actual_duration

            # 最终检查：防止开始时间超过结束时间
            if end <= start:
                print(f"  ✗ 错误: 计算后的结束时间({end})小于开始时间({start})")
                return False

            duration = end - start

            if duration <= 0:
                print(f"  ✗ 错误: 片段时长为0，无法剪辑")
                return False

            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start),
                "-i", video_path,
                "-t", str(duration),
                "-c:v", "libx264", "-preset", "fast",
                "-c:a", "aac",
                "-avoid_negative_ts", "make_zero",
                output_path
            ]

            result = subprocess.run(cmd, capture_output=True, timeout=120)
            return result.returncode == 0
        except Exception as e:
            print(f"剪辑片段失败: {e}")
            return False

    def merge_videos(self, video_paths: List[str], output_path: str) -> bool:
        """合并视频"""
        try:
            # 创建concat文件
            concat_file = self.temp_dir / "concat.txt"
            with open(concat_file, 'w') as f:
                for path in video_paths:
                    f.write(f"file '{path}'\n")

            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(concat_file),
                "-c:v", "libx264", "-preset", "fast",
                "-c:a", "aac",
                output_path
            ]

            result = subprocess.run(cmd, capture_output=True, timeout=300)
            return result.returncode == 0

        except Exception as e:
            print(f"合并视频失败: {e}")
            return False

    def compose_scheme(self, plan: EditingPlan, material_videos: Dict[str, str],
                       material_cache_dir: Path) -> Optional[str]:
        """剪辑完整方案"""
        if not plan.is_valid or not plan.scenes:
            print(f"方案 {plan.scheme_id} 无效，跳过剪辑")
            return None

        # V4：验证Logo要求（只检查F06必须有logo）
        logo_valid, logo_reason = self._validate_logo_requirements(plan.scenes)
        if not logo_valid:
            print(f"✗ 方案 {plan.scheme_id} Logo验证失败: {logo_reason}")
            plan.is_valid = False
            plan.invalid_reason = logo_reason
            return None

        # 下载所需视频
        downloaded = {}
        segment_files = []

        for i, scene in enumerate(plan.scenes):
            material_id = scene.scenes[0].material_id
            video_url = material_videos.get(material_id)

            if not video_url:
                print(f"找不到素材 {material_id} 的视频URL")
                continue

            # 检查是否已下载
            video_path = material_cache_dir / f"{material_id}.mp4"
            if not video_path.exists():
                print(f"下载素材 {material_id}...")
                if not self.download_video(video_url, str(video_path)):
                    print(f"下载失败: {material_id}")
                    continue

            # 剪辑片段
            is_last = (i == len(plan.scenes) - 1)
            segment_file = self.temp_dir / f"scheme{plan.scheme_id}_seg{i}.mp4"

            print(f"剪辑片段 {i+1}/{len(plan.scenes)}: {scene.tag} ({scene.total_duration:.1f}秒)")

            if self.cut_segment(
                str(video_path),
                scene.start_time,
                scene.end_time,
                str(segment_file),
                is_last_segment=is_last,
                tag=scene.tag
            ):
                segment_files.append(str(segment_file))
            else:
                print(f"剪辑片段失败: {i}")

        if not segment_files:
            print(f"方案 {plan.scheme_id} 没有成功的片段")
            return None

        # 合并视频
        output_path = self.output_dir / f"方案{plan.scheme_id}_最终版.mp4"
        print(f"合并方案 {plan.scheme_id} 的视频...")

        if self.merge_videos(segment_files, str(output_path)):
            print(f"✓ 方案 {plan.scheme_id} 完成: {output_path}")
            return str(output_path)
        else:
            print(f"✗ 方案 {plan.scheme_id} 合并失败")
            return None


# ============================================================
# 视频相似度检查器
# ============================================================
class VideoSimilarityChecker:
    """视频相似度检查器 - 基于4个视频使用的素材ID重叠率计算相似度"""

    def __init__(self):
        self.video_materials = {}  # {scheme_id: set(material_ids)}

    def register_plan_materials(self, plan: EditingPlan):
        """记录方案使用的素材ID"""
        material_ids = set()
        for scene in plan.scenes:
            for s in scene.scenes:
                material_ids.add(s.material_id)
        self.video_materials[plan.scheme_id] = material_ids

    def compute_similarity(self, scheme_id1: int, scheme_id2: int) -> float:
        """计算两个方案的相似度（基于素材ID重叠率）"""
        materials1 = self.video_materials.get(scheme_id1, set())
        materials2 = self.video_materials.get(scheme_id2, set())

        if not materials1 or not materials2:
            return 0.0

        intersection = len(materials1 & materials2)
        union = len(materials1 | materials2)

        return intersection / union if union > 0 else 0.0

    def check_all_pairs(self, threshold: float = 0.7) -> Dict[Tuple[int, int], float]:
        """检查所有视频对的相似度，返回超过阈值的对"""
        high_similarity_pairs = {}
        scheme_ids = list(self.video_materials.keys())

        for i in range(len(scheme_ids)):
            for j in range(i + 1, len(scheme_ids)):
                id1, id2 = scheme_ids[i], scheme_ids[j]
                similarity = self.compute_similarity(id1, id2)
                print(f"  方案{id1} vs 方案{id2}: {similarity:.1%}")
                if similarity >= threshold:
                    high_similarity_pairs[(id1, id2)] = similarity

        return high_similarity_pairs

    def get_used_materials(self, exclude_scheme_id: int = None) -> Set[str]:
        """获取使用的素材ID

        Args:
            exclude_scheme_id: 排除的方案ID，如果为None则返回所有素材
        """
        if exclude_scheme_id is None:
            # 返回所有素材
            used = set()
            for materials in self.video_materials.values():
                used.update(materials)
            return used

        used = set()
        for scheme_id, materials in self.video_materials.items():
            if scheme_id != exclude_scheme_id:
                used.update(materials)
        return used

    def clear(self):
        """清空记录"""
        self.video_materials = {}


# ============================================================
# 主程序
# ============================================================
class MaterialRemakeTool:
    """素材重制工具主类"""

    def __init__(self):
        self.output_dir = Path(OUTPUT_DIR)
        self.output_dir.mkdir(exist_ok=True)

        # 数据
        self.material_list = []
        self.material_jsons = {}
        self.origin_json = None
        self.origin_scenes = []

        # 处理后的数据
        self.all_scenes = []
        self.tagged_scenes = []
        self.merged_scenes = {}  # {material_id: [MergedScene]}

        # 方案
        self.plans = []

    def load_data(self):
        """加载所有数据"""
        print("=" * 60)
        print("Step 1: 加载数据")
        print("=" * 60)

        # 1. 复制material_list.csv到输出目录
        shutil.copy(MATERIAL_LIST_PATH, self.output_dir / "material_list.csv")
        print(f"✓ 复制素材列表到输出目录")

        # 2. 加载素材列表
        with open(MATERIAL_LIST_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='|')
            for row in reader:
                self.material_list.append({
                    'id': row['id'],
                    'material_name': row['material_name'],
                    'video_url': row['video_url']
                })
        print(f"✓ 加载素材列表: {len(self.material_list)} 条")

        # 3. 加载所有素材JSON
        for item in self.material_list:
            json_path = Path(MATERIAL_JSON_DIR) / f"{item['id']}.json"
            if json_path.exists():
                with open(json_path, 'r', encoding='utf-8') as f:
                    self.material_jsons[item['id']] = json.load(f)
        print(f"✓ 加载素材JSON: {len(self.material_jsons)} 个")

        # 4. 加载原片JSON
        with open(ORIGIN_JSON_PATH, 'r', encoding='utf-8') as f:
            self.origin_json = json.load(f)
        print(f"✓ 加载原片JSON: {len(self.origin_json)} 集")

        # 5. 构建原片场景索引
        for episode_data in self.origin_json:
            episode = int(episode_data.get('video_name', '0'))
            segments = episode_data.get('result', {}).get('segments', [])

            for idx, seg in enumerate(segments):
                scene = OriginScene(
                    episode=episode,
                    segment_id=seg.get('segment_id', idx + 1),
                    segment_index=idx + 1,
                    start_time=seg.get('start_time', 0),
                    end_time=seg.get('end_time', 0),
                    duration=seg.get('duration', 0),
                    plot_summary=seg.get('plot_summary', ''),
                    narrative_function_tag=seg.get('narrative_function_tag', ''),
                    characters=seg.get('characters', [])
                )
                self.origin_scenes.append(scene)

        print(f"✓ 原片场景总数: {len(self.origin_scenes)}")

    def extract_scenes(self):
        """从素材JSON提取场景信息"""
        print("\n" + "=" * 60)
        print("Step 2: 提取场景信息")
        print("=" * 60)

        for material_id, json_data in self.material_jsons.items():
            material_name = json_data.get('material_name', '')
            video_url = json_data.get('video_url', '')
            segments = json_data.get('result', {}).get('segments', [])

            for seg in segments:
                scene = SceneInfo(
                    material_id=material_id,
                    material_name=material_name,
                    video_url=video_url,
                    segment_id=seg.get('segment_id', 0),
                    start_time=seg.get('start_time', 0),
                    end_time=seg.get('end_time', 0),
                    duration=seg.get('duration', 0),
                    plot_summary=seg.get('plot_summary', ''),
                    narrative_function_tag=seg.get('narrative_function_tag', ''),
                    characters=seg.get('characters', []),
                    main_location=seg.get('main_location', ''),
                    emotion_level=seg.get('emotion_level', 0),
                    emotion_polarity=seg.get('emotion_polarity', 0),
                    is_highlight=seg.get('is_highlight', False),
                    has_logo=seg.get('has_logo', False),
                    logo_position=seg.get('logo_position', '')
                )
                self.all_scenes.append(scene)

        print(f"✓ 提取场景总数: {len(self.all_scenes)}")

    def match_and_tag_scenes(self):
        """匹配和打标场景"""
        print("\n" + "=" * 60)
        print("Step 3: 场景匹配与打标")
        print("=" * 60)

        # 创建匹配器和打标器
        matcher = SceneMatcher(self.origin_scenes)
        tagger = SceneTagger(matcher, min_match_score=0.15)

        # 打标所有场景
        self.tagged_scenes = tagger.tag_all_scenes(self.all_scenes)

        # 统计匹配结果
        matched_count = sum(1 for s in self.tagged_scenes if s.is_matched)
        print(f"✓ 匹配成功: {matched_count}/{len(self.tagged_scenes)}")

        # 按tag统计
        tag_stats = defaultdict(lambda: {'matched': 0, 'total': 0})
        for scene in self.tagged_scenes:
            tag = scene.narrative_function_tag[:3] if scene.narrative_function_tag else 'Unknown'
            tag_stats[tag]['total'] += 1
            if scene.is_matched:
                tag_stats[tag]['matched'] += 1

        print("\n场景类型分布:")
        for tag, stats in sorted(tag_stats.items()):
            print(f"  {tag}: {stats['matched']}/{stats['total']} 匹配")

    def merge_scenes(self):
        """合并连续相同tag的场景"""
        print("\n" + "=" * 60)
        print("Step 4: 合并连续场景")
        print("=" * 60)

        merger = SceneMerger()

        # 按素材分组
        scenes_by_material = defaultdict(list)
        for scene in self.tagged_scenes:
            scenes_by_material[scene.material_id].append(scene)

        # 对每个素材的场景进行合并
        total_original = 0
        total_merged = 0

        for material_id, scenes in scenes_by_material.items():
            # 按segment_id排序
            scenes.sort(key=lambda s: s.segment_id)
            total_original += len(scenes)

            merged = merger.merge_consecutive(scenes)
            self.merged_scenes[material_id] = merged
            total_merged += len(merged)

        print(f"✓ 合并前场景数: {total_original}")
        print(f"✓ 合并后场景数: {total_merged}")
        print(f"✓ 减少场景数: {total_original - total_merged}")

    def _retag_logo_scenes(self):
        """V4：将非F06但有logo的场景重新标记为F06

        规则：
        1. 非F06场景有logo → 重新标记为F06
        2. 这样原本作为F06使用的场景不会受影响
        """
        print("\n" + "=" * 60)
        print("Step 4.5: 重新标记Logo场景（V4规则）")
        print("=" * 60)

        retagged_count = 0
        for material_id, scenes in self.merged_scenes.items():
            for scene in scenes:
                has_logo = scene.has_logo
                is_f06 = scene.tag == "F06"

                if not is_f06 and has_logo:
                    old_tag = scene.tag
                    scene.tag = "F06"
                    scene.narrative_function = "悬念结尾/付费卡点"
                    retagged_count += 1
                    print(f"  🔄 场景 {old_tag}(素材{material_id}) 有logo，重新标记为F06")

        print(f"✓ 重新标记场景数: {retagged_count}")

    def generate_schemes(self):
        """生成所有方案"""
        print("\n" + "=" * 60)
        print("Step 5: 生成剪辑方案")
        print("=" * 60)

        generator = SchemeGenerator(self.merged_scenes)

        # 方案1和方案2
        print("\n生成方案1 (F01 → F04 → F02 → F06)...")
        plan1 = generator.generate_fixed_scheme(SCHEME_1, 1)
        self.plans.append(plan1)
        self._print_plan_status(plan1)

        print("\n生成方案2 (F02 → F03 → F04 → F06)...")
        plan2 = generator.generate_fixed_scheme(SCHEME_2, 2)
        self.plans.append(plan2)
        self._print_plan_status(plan2)

        # 方案3和方案4 (AI生成)
        print("\n生成方案3和方案4 (AI生成)...")
        ai_generator = AISchemeGenerator(generator)
        ai_plans = ai_generator.generate_ai_schemes()

        for plan in ai_plans:
            self.plans.append(plan)
            self._print_plan_status(plan)

    def _print_plan_status(self, plan: EditingPlan):
        """打印方案状态"""
        if plan.is_valid:
            tags = " → ".join(s.tag for s in plan.scenes)
            print(f"  ✓ 方案{plan.scheme_id} 有效: {tags}")
            print(f"    总时长: {plan.total_duration:.1f}秒 ({plan.total_duration/60:.1f}分钟)")
        else:
            print(f"  ✗ 方案{plan.scheme_id} 无效: {plan.invalid_reason}")

    def compose_videos(self):
        """剪辑视频"""
        print("\n" + "=" * 60)
        print("Step 6: 视频剪辑")
        print("=" * 60)

        # 创建视频缓存目录
        material_cache_dir = self.output_dir / "material_videos"
        material_cache_dir.mkdir(exist_ok=True)

        # 构建视频URL映射
        material_videos = {}
        for item in self.material_list:
            material_videos[item['id']] = item['video_url']

        composer = VideoComposer(str(self.output_dir))

        for plan in self.plans:
            if plan.is_valid:
                print(f"\n处理方案 {plan.scheme_id}...")
                composer.compose_scheme(plan, material_videos, material_cache_dir)

    def compose_videos_with_similarity_check(self, max_iterations: int = 10):
        """带相似度检查的视频剪辑

        Args:
            max_iterations: 最大迭代次数（用于重新生成相似度过高的方案）
        """
        print("\n" + "=" * 60)
        print("Step 6: 视频剪辑（带相似度检查）")
        print("=" * 60)

        # 创建视频缓存目录
        material_cache_dir = self.output_dir / "material_videos"
        material_cache_dir.mkdir(exist_ok=True)

        # 构建视频URL映射
        material_videos = {}
        for item in self.material_list:
            material_videos[item['id']] = item['video_url']

        composer = VideoComposer(str(self.output_dir))
        similarity_checker = VideoSimilarityChecker()

        # 记录已剪辑的视频路径
        video_paths = {}

        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            print(f"\n--- 第 {iteration} 次迭代 ---")

            # 清空相似度检查器
            similarity_checker.clear()

            # 剪辑所有有效方案
            for plan in self.plans:
                if plan.is_valid and plan.scheme_id not in video_paths:
                    print(f"\n处理方案 {plan.scheme_id}...")
                    result = composer.compose_scheme(plan, material_videos, material_cache_dir)
                    if result:
                        video_paths[plan.scheme_id] = result
                        similarity_checker.register_plan_materials(plan)

            # 检查相似度
            print("\n检查视频相似度...")
            high_similarity_pairs = similarity_checker.check_all_pairs(threshold=0.7)

            if not high_similarity_pairs:
                print("✓ 所有视频相似度均低于70%，剪辑完成！")
                break

            # 重新生成相似度过高的方案
            print(f"\n发现 {len(high_similarity_pairs)} 对相似度过高的视频，重新生成方案...")

            # 找出需要重新生成的方案
            schemes_to_regenerate = set()
            for (id1, id2), sim in high_similarity_pairs.items():
                print(f"  方案{id1} vs 方案{id2}: {sim:.1%} - 需要重新生成方案{id2}")
                schemes_to_regenerate.add(id2)

            # 重新生成方案
            generator = SchemeGenerator(self.merged_scenes)

            for scheme_id in schemes_to_regenerate:
                # 获取其他方案使用的素材ID
                excluded_materials = similarity_checker.get_used_materials(scheme_id)

                # 找到原方案的标签
                original_plan = next((p for p in self.plans if p.scheme_id == scheme_id), None)
                if original_plan:
                    tags = [s.tag for s in original_plan.scenes]
                    print(f"  重新生成方案{scheme_id}，排除素材: {list(excluded_materials)[:5]}...")

                    new_plan = generator.generate_fixed_scheme(tags, scheme_id, excluded_materials)
                    # 更新方案列表
                    for i, p in enumerate(self.plans):
                        if p.scheme_id == scheme_id:
                            self.plans[i] = new_plan
                            self._print_plan_status(new_plan)
                            break

                    # 删除旧的视频文件
                    if scheme_id in video_paths:
                        old_path = Path(video_paths[scheme_id])
                        if old_path.exists():
                            old_path.unlink()
                            print(f"  删除旧视频: {old_path}")
                        del video_paths[scheme_id]

        if iteration >= max_iterations:
            print(f"\n达到最大迭代次数 {max_iterations}，停止重新生成")

        # 生成相似度报告
        self._generate_similarity_report(similarity_checker)

    def _generate_similarity_report(self, similarity_checker: VideoSimilarityChecker):
        """生成相似度报告"""
        report = {
            "generate_time": datetime.now().isoformat(),
            "similarity_matrix": {},
            "high_similarity_pairs": []
        }

        scheme_ids = list(similarity_checker.video_materials.keys())
        for id1 in scheme_ids:
            report["similarity_matrix"][str(id1)] = {}
            for id2 in scheme_ids:
                if id1 != id2:
                    sim = similarity_checker.compute_similarity(id1, id2)
                    report["similarity_matrix"][str(id1)][str(id2)] = round(sim, 4)
                    if sim >= 0.7 and id1 < id2:
                        report["high_similarity_pairs"].append({
                            "scheme_1": id1,
                            "scheme_2": id2,
                            "similarity": round(sim, 4)
                        })

        with open(self.output_dir / "视频相似度报告.json", 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"✓ 生成视频相似度报告")

    def generate_reports(self):
        """生成报告"""
        print("\n" + "=" * 60)
        print("Step 7: 生成报告")
        print("=" * 60)

        # 1. 场景匹配报告
        match_report = {
            "generate_time": datetime.now().isoformat(),
            "total_scenes": len(self.tagged_scenes),
            "matched_scenes": sum(1 for s in self.tagged_scenes if s.is_matched),
            "match_details": []
        }

        for scene in self.tagged_scenes:
            match_report["match_details"].append({
                "material_id": scene.material_id,
                "material_name": scene.material_name,
                "segment_id": scene.segment_id,
                "tag": scene.narrative_function_tag,
                "duration": scene.duration,
                "is_matched": scene.is_matched,
                "origin_episode": scene.origin_episode,
                "origin_segment_index": scene.origin_segment_index,
                "match_score": round(scene.match_score, 3),
                "match_note": scene.match_note
            })

        with open(self.output_dir / "场景匹配报告.json", 'w', encoding='utf-8') as f:
            json.dump(match_report, f, ensure_ascii=False, indent=2)
        print(f"✓ 生成场景匹配报告")

        # 2. 方案详情
        scheme_details = {
            "generate_time": datetime.now().isoformat(),
            "schemes": []
        }

        for plan in self.plans:
            scheme_data = {
                "scheme_id": plan.scheme_id,
                "scheme_name": plan.scheme_name,
                "is_valid": plan.is_valid,
                "invalid_reason": plan.invalid_reason,
                "total_duration": round(plan.total_duration, 2),
                "total_duration_minutes": round(plan.total_duration / 60, 2),
                "scenes": []
            }

            for scene in plan.scenes:
                scheme_data["scenes"].append({
                    "tag": scene.tag,
                    "material_id": scene.scenes[0].material_id,
                    "material_name": scene.scenes[0].material_name,
                    "start_time": scene.start_time,
                    "end_time": scene.end_time,
                    "duration": round(scene.total_duration, 2),
                    "merged_count": scene.merged_count,
                    "origin_episode": scene.origin_episode,
                    "origin_segment_index": scene.origin_segment_index,
                    "is_matched": scene.is_matched
                })

            scheme_details["schemes"].append(scheme_data)

        with open(self.output_dir / "方案详情.json", 'w', encoding='utf-8') as f:
            json.dump(scheme_details, f, ensure_ascii=False, indent=2)
        print(f"✓ 生成方案详情")

        # 3. 剪辑计划CSV
        with open(self.output_dir / "剪辑计划.csv", 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "方案ID", "方案名称", "有效", "场景序号", "场景类型",
                "素材ID", "素材名称", "开始时间", "结束时间", "时长(秒)",
                "原片集数", "原片场景序号", "是否匹配"
            ])

            for plan in self.plans:
                for i, scene in enumerate(plan.scenes):
                    writer.writerow([
                        plan.scheme_id,
                        plan.scheme_name,
                        "是" if plan.is_valid else "否",
                        i + 1,
                        scene.tag,
                        scene.scenes[0].material_id,
                        scene.scenes[0].material_name,
                        scene.start_time,
                        scene.end_time,
                        round(scene.total_duration, 2),
                        scene.origin_episode or "",
                        scene.origin_segment_index or "",
                        "是" if scene.is_matched else "否"
                    ])

        print(f"✓ 生成剪辑计划CSV")

        # 4. 执行摘要
        summary = f"""
# 素材剪辑测试方案 - 执行摘要

生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 数据统计

- 素材数量: {len(self.material_list)}
- 素材JSON: {len(self.material_jsons)}
- 原片集数: {len(self.origin_json)}
- 原片场景: {len(self.origin_scenes)}
- 素材场景(合并前): {len(self.all_scenes)}
- 素材场景(合并后): {sum(len(scenes) for scenes in self.merged_scenes.values())}

## 方案结果

| 方案 | 名称 | 状态 | 时长 | 场景数 |
|------|------|------|------|--------|
"""

        for plan in self.plans:
            status = "✓ 有效" if plan.is_valid else "✗ 无效"
            duration = f"{plan.total_duration/60:.1f}分钟" if plan.is_valid else "-"
            scenes = len(plan.scenes) if plan.is_valid else 0
            summary += f"| 方案{plan.scheme_id} | {plan.scheme_name.split(':')[0] if ':' in plan.scheme_name else plan.scheme_name} | {status} | {duration} | {scenes} |\n"

        if any(not p.is_valid for p in self.plans):
            summary += "\n## 无效方案原因\n\n"
            for plan in self.plans:
                if not plan.is_valid:
                    summary += f"- 方案{plan.scheme_id}: {plan.invalid_reason}\n"

        summary += """
## 输出文件

- `方案1_最终版.mp4` ~ `方案4_最终版.mp4` - 剪辑后的视频
- `剪辑计划.csv` - 详细的剪辑信息
- `场景匹配报告.json` - 素材场景与原片的匹配结果
- `方案详情.json` - 4个方案的具体配置
- `执行摘要.md` - 本文件
"""

        with open(self.output_dir / "执行摘要.md", 'w', encoding='utf-8') as f:
            f.write(summary)

        print(f"✓ 生成执行摘要")

    def run(self):
        """运行完整流程"""
        print("=" * 60)
        print("素材剪辑测试方案 - 开始执行")
        print("=" * 60)

        self.load_data()
        self.extract_scenes()
        self.match_and_tag_scenes()
        self.merge_scenes()
        self._retag_logo_scenes()  # V4新增：重新标记有logo的非F06场景
        self.generate_schemes()
        self.generate_reports()

        # 询问是否进行视频剪辑
        print("\n" + "=" * 60)
        print("报告生成完成！")
        print(f"输出目录: {self.output_dir}")
        print("=" * 60)

        return True


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='素材剪辑测试方案')
    parser.add_argument('--compose', action='store_true', help='是否进行视频剪辑')
    parser.add_argument('--with-similarity-check', action='store_true', help='是否进行相似度检查的视频剪辑')
    parser.add_argument('--max-iterations', type=int, default=10, help='相似度检查的最大迭代次数')

    args = parser.parse_args()

    tool = MaterialRemakeTool()
    tool.run()

    # 根据命令行参数决定是否进行视频剪辑
    if args.with_similarity_check:
        print("\n开始带相似度检查的视频剪辑...")
        tool.compose_videos_with_similarity_check(args.max_iterations)
    elif args.compose:
        print("\n开始视频剪辑...")
        tool.compose_videos()

    print("\n全部完成！")


if __name__ == "__main__":
    main()
