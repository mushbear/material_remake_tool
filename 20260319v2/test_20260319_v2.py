#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
20260319 素材剪辑测试方案 - v2修复版 (最终版)
修复内容：
1. 素材使用限制改为每个视频单独限制
2. 完善F06场景Logo验证
3. 场景顺序验证放宽（混剪允许跨集组合）
4. 全局使用记录智能管理（确保4个方案都能生成）
5. 添加失败重试机制
6. 提高匹配阈值（0.15→0.25）
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

sys.path.insert(0, str(Path(__file__).parent.parent))

# 配置
MATERIAL_LIST_PATH = (
    "/Users/wangchenyi/video_ad_analyzer/test_20260319/material_list.csv"
)
MATERIAL_JSON_DIR = "/Users/wangchenyi/video_ad_analyzer/test_20260319/material"
ORIGIN_JSON_PATH = (
    "/Users/wangchenyi/video_ad_analyzer/test_20260319/origin_json/all.json"
)
OUTPUT_DIR = "/Users/wangchenyi/material_remake_tool/20260319v2"

SCHEME_1 = ["F01", "F04", "F02", "F06"]
SCHEME_2 = ["F02", "F03", "F04", "F06"]

MIN_DURATION_NON_SPECIAL = 15
MIN_MATCH_SCORE = 0.25
MAX_RETRY_ATTEMPTS = 10  # 增加重试次数


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
    has_logo: bool = False
    logo_position: str = ""
    is_last_segment: bool = False
    origin_episode: Optional[int] = None
    origin_segment_index: Optional[int] = None
    match_score: float = 0.0
    is_matched: bool = False
    is_usable: bool = True
    match_note: str = ""


@dataclass
class OriginScene:
    """原片场景信息"""

    episode: int
    segment_id: int
    segment_index: int
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
    has_logo: bool = False
    is_usable: bool = True
    is_last_segment: bool = False


@dataclass
class EditingPlan:
    """剪辑计划"""

    scheme_id: int
    scheme_name: str
    scenes: List[MergedScene]
    total_duration: float
    is_valid: bool
    invalid_reason: str = ""
    retry_count: int = 0


class SceneMatcher:
    """场景匹配器"""

    def __init__(self, origin_scenes: List[OriginScene]):
        self.origin_scenes = origin_scenes
        self.episode_index = defaultdict(list)
        for scene in origin_scenes:
            self.episode_index[scene.episode].append(scene)

    def _normalize_tag(self, tag: str) -> str:
        if not tag:
            return ""
        match = re.match(r"(F\d+)", tag)
        return match.group(1) if match else tag

    def _compute_text_similarity(self, text1: str, text2: str) -> float:
        if not text1 or not text2:
            return 0.0
        words1 = set(re.findall(r"\w+", text1.lower()))
        words2 = set(re.findall(r"\w+", text2.lower()))
        if not words1 or not words2:
            return 0.0
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        return intersection / union if union > 0 else 0.0

    def _compute_character_similarity(
        self, chars1: List[Dict], chars2: List[Dict]
    ) -> float:
        if not chars1 or not chars2:
            return 0.0
        names1 = {c.get("character_id", "").lower() for c in chars1}
        names2 = {c.get("character_id", "").lower() for c in chars2}
        names1 = {n for n in names1 if n}
        names2 = {n for n in names2 if n}
        if not names1 or not names2:
            return 0.0
        intersection = len(names1 & names2)
        union = len(names1 | names2)
        return intersection / union if union > 0 else 0.0

    def _compute_duration_similarity(self, dur1: float, dur2: float) -> float:
        if dur1 <= 0 or dur2 <= 0:
            return 0.0
        ratio = min(dur1, dur2) / max(dur1, dur2)
        return ratio

    def compute_similarity(
        self, material_scene: SceneInfo, origin_scene: OriginScene
    ) -> float:
        W_PLOT = 0.5
        W_CHAR = 0.35
        W_DURATION = 0.15

        plot_sim = self._compute_text_similarity(
            material_scene.plot_summary, origin_scene.plot_summary
        )

        char_sim = self._compute_character_similarity(
            material_scene.characters, origin_scene.characters
        )

        dur_sim = self._compute_duration_similarity(
            material_scene.duration, origin_scene.duration
        )

        return W_PLOT * plot_sim + W_CHAR * char_sim + W_DURATION * dur_sim

    def match_scene(
        self, material_scene: SceneInfo
    ) -> Tuple[Optional[OriginScene], float]:
        best_match = None
        best_score = 0.0

        for origin_scene in self.origin_scenes:
            score = self.compute_similarity(material_scene, origin_scene)
            if score > best_score:
                best_score = score
                best_match = origin_scene

        return best_match, best_score


class SceneTagger:
    """场景打标器"""

    def __init__(self, matcher: SceneMatcher, min_match_score: float = MIN_MATCH_SCORE):
        self.matcher = matcher
        self.min_match_score = min_match_score

    def tag_scene(self, scene: SceneInfo) -> SceneInfo:
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

            tag_prefix = self.matcher._normalize_tag(scene.narrative_function_tag)
            if tag_prefix == "F06":
                scene.is_usable = True
                scene.match_note = "F06类型，无需匹配原片"
            else:
                scene.is_usable = False
                scene.match_note = f"未找到匹配（相似度: {score:.2f}），该场景不使用"

        return scene


class SceneMerger:
    """场景合并器"""

    def merge_consecutive(self, scenes: List[SceneInfo]) -> List[MergedScene]:
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
                merged.append(self._create_merged_scene(current_group))
                current_group = [scene]
                current_tag = tag

        merged.append(self._create_merged_scene(current_group))
        return merged

    def _get_tag_prefix(self, tag: str) -> str:
        if not tag:
            return ""
        match = re.match(r"(F\d+)", tag)
        return match.group(1) if match else tag

    def _create_merged_scene(self, scenes: List[SceneInfo]) -> MergedScene:
        tag = self._get_tag_prefix(scenes[0].narrative_function_tag)
        start_time = scenes[0].start_time
        end_time = scenes[-1].end_time
        # 修复：使用end_time - start_time计算实际时长，而不是sum(duration)
        total_duration = end_time - start_time

        first_scene = scenes[0]
        last_scene = scenes[-1]

        has_logo = any(s.has_logo for s in scenes)
        is_usable = all(s.is_usable for s in scenes)
        is_last_segment = last_scene.is_last_segment

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
            is_usable=is_usable,
            is_last_segment=is_last_segment,
        )


class PreSimilarityChecker:
    """预相似度检查器"""

    def __init__(self):
        self.existing_plans: List[EditingPlan] = []

    def add_plan(self, plan: EditingPlan):
        if plan.is_valid:
            self.existing_plans.append(plan)

    def compute_material_overlap(self, new_plan: EditingPlan) -> Dict[int, float]:
        new_materials = self._get_plan_materials(new_plan)
        overlaps = {}

        for existing_plan in self.existing_plans:
            existing_materials = self._get_plan_materials(existing_plan)

            if not new_materials or not existing_materials:
                overlaps[existing_plan.scheme_id] = 0.0
                continue

            intersection = len(new_materials & existing_materials)
            union = len(new_materials | existing_materials)

            similarity = intersection / union if union > 0 else 0.0
            overlaps[existing_plan.scheme_id] = similarity

        return overlaps

    def _get_plan_materials(self, plan: EditingPlan) -> Set[str]:
        materials = set()
        for scene in plan.scenes:
            for s in scene.scenes:
                materials.add(s.material_id)
        return materials

    def check_similarity(
        self, new_plan: EditingPlan, threshold: float = 0.7
    ) -> Tuple[bool, List[int]]:
        overlaps = self.compute_material_overlap(new_plan)
        high_similarity = [
            scheme_id for scheme_id, sim in overlaps.items() if sim >= threshold
        ]
        return len(high_similarity) == 0, high_similarity

    def get_excluded_materials(self) -> Set[str]:
        excluded = set()
        for plan in self.existing_plans:
            excluded.update(self._get_plan_materials(plan))
        return excluded


class SchemeGenerator:
    """方案生成器 - v2修复版"""

    def __init__(self, all_merged_scenes: Dict[str, List[MergedScene]]):
        self.all_merged_scenes = all_merged_scenes
        self.tag_index = defaultdict(list)
        for material_id, scenes in all_merged_scenes.items():
            for scene in scenes:
                self.tag_index[scene.tag].append((material_id, scene))

        # 使用集合来跟踪已使用的场景
        self.used_scenes: Set[Tuple[str, str]] = set()  # (material_id, tag)

    def reset_usage(self):
        """重置使用记录"""
        self.used_scenes = set()

    def is_scene_used(self, material_id: str, tag: str) -> bool:
        """检查场景是否已被使用"""
        if tag == "F06":
            return False  # F06可复用
        return (material_id, tag) in self.used_scenes

    def mark_scene_used(self, material_id: str, tag: str):
        """标记场景已使用"""
        if tag != "F06":
            self.used_scenes.add((material_id, tag))

    def generate_fixed_scheme(
        self,
        scheme_tags: List[str],
        scheme_id: int,
        excluded_material_ids: Set[str] = None,
        existing_plans: List[EditingPlan] = None,
        max_material_per_video: int = 2,
    ) -> EditingPlan:
        """生成固定方案 - v2修复版"""
        if excluded_material_ids is None:
            excluded_material_ids = set()
        if existing_plans is None:
            existing_plans = []

        selected_scenes = []
        is_valid = True
        invalid_reason = ""

        # 当前视频内的素材使用计数
        material_scene_count: Dict[str, int] = defaultdict(int)

        for tag in scheme_tags:
            available_scenes = []

            for material_id, scene in self.tag_index.get(tag, []):
                if not scene.is_usable:
                    continue

                if material_id in excluded_material_ids:
                    continue

                # 检查每个视频内的素材使用限制
                if material_scene_count[material_id] >= max_material_per_video:
                    continue

                # F06可复用，其他检查使用记录
                if tag == "F06":
                    available_scenes.append((material_id, scene))
                else:
                    if not self.is_scene_used(material_id, tag):
                        available_scenes.append((material_id, scene))

            if not available_scenes:
                is_valid = False
                invalid_reason = f"找不到类型为 {tag} 的可用场景"
                break

            # 优先选择匹配度高的场景
            available_scenes.sort(key=lambda x: x[1].match_score, reverse=True)

            # 选择场景
            selected = available_scenes[0]
            material_id, scene = selected
            selected_scenes.append(scene)

            # 更新使用记录
            if tag != "F06":
                self.mark_scene_used(material_id, tag)

            # 更新当前视频内的素材使用计数
            material_scene_count[material_id] += 1

        # 验证时长
        if is_valid:
            for scene in selected_scenes:
                tag = scene.tag
                if tag not in ["F01", "F06"]:
                    if scene.total_duration < MIN_DURATION_NON_SPECIAL:
                        is_valid = False
                        invalid_reason = (
                            f"场景 {tag} 时长不足 {MIN_DURATION_NON_SPECIAL} 秒"
                        )
                        break

        # v2: 放宽场景顺序验证（混剪允许跨集）
        # 只检查同一素材内的场景顺序
        if is_valid and len(selected_scenes) > 1:
            order_valid, order_reason = self._validate_order_relaxed(selected_scenes)
            if not order_valid:
                is_valid = False
                invalid_reason = order_reason

        # 预检查相似度
        if is_valid:
            temp_plan = EditingPlan(
                scheme_id=scheme_id,
                scheme_name=f"方案{scheme_id}",
                scenes=selected_scenes,
                total_duration=sum(s.total_duration for s in selected_scenes),
                is_valid=True,
            )

            checker = PreSimilarityChecker()
            for plan in existing_plans:
                checker.add_plan(plan)

            passed, high_sim_ids = checker.check_similarity(temp_plan, threshold=0.7)
            if not passed:
                is_valid = False
                invalid_reason = f"与方案{high_sim_ids}素材重叠率超过70%"

        total_duration = (
            sum(s.total_duration for s in selected_scenes) if selected_scenes else 0
        )
        scheme_name = f"方案{scheme_id}: {' → '.join(scheme_tags)}"

        return EditingPlan(
            scheme_id=scheme_id,
            scheme_name=scheme_name,
            scenes=selected_scenes,
            total_duration=total_duration,
            is_valid=is_valid,
            invalid_reason=invalid_reason,
        )

    def _validate_order_relaxed(self, scenes: List[MergedScene]) -> Tuple[bool, str]:
        """放宽的场景顺序验证 - 只检查同一素材内的顺序"""
        # 按素材分组
        scenes_by_material: Dict[str, List[Tuple[int, MergedScene]]] = defaultdict(list)
        for idx, scene in enumerate(scenes):
            material_id = scene.scenes[0].material_id
            scenes_by_material[material_id].append((idx, scene))

        # 检查每个素材内的场景顺序
        for material_id, material_scenes in scenes_by_material.items():
            if len(material_scenes) < 2:
                continue

            # 按原片顺序排序
            sorted_by_origin = sorted(
                material_scenes,
                key=lambda x: (
                    x[1].origin_episode or 0,
                    x[1].origin_segment_index or 0,
                ),
            )

            # 检查方案中的顺序是否与原片一致
            for i in range(len(sorted_by_origin) - 1):
                idx1, scene1 = sorted_by_origin[i]
                idx2, scene2 = sorted_by_origin[i + 1]

                if idx2 < idx1:
                    return False, f"素材{material_id}内场景顺序与原片不符"

        return True, ""

    def regenerate_scheme(
        self,
        scheme_tags: List[str],
        scheme_id: int,
        excluded_material_ids: Set[str],
        max_attempts: int = MAX_RETRY_ATTEMPTS,
    ) -> EditingPlan:
        """重新生成方案"""
        original_excluded = excluded_material_ids.copy()

        for attempt in range(max_attempts):
            plan = self.generate_fixed_scheme(
                scheme_tags, scheme_id, excluded_material_ids
            )

            if plan.is_valid:
                return plan

            print(f"  重试 {attempt + 1}/{max_attempts}: {plan.invalid_reason}")

            # 根据不同错误类型采取不同策略
            if "找不到类型为" in plan.invalid_reason:
                # 场景用尽，只排除已使用的素材，不标记场景
                excluded_material_ids.update(
                    s.scenes[0].material_id for s in plan.scenes if s.scenes
                )
            elif "素材重叠率" in plan.invalid_reason:
                # 相似度过高，排除冲突素材
                for scene in plan.scenes:
                    if scene.scenes:
                        excluded_material_ids.add(scene.scenes[0].material_id)
            else:
                # 其他错误，扩大排除范围
                excluded_material_ids.update(
                    s.scenes[0].material_id for s in plan.scenes if s.scenes
                )

        # 最后一次尝试，最小限制
        return self.generate_fixed_scheme(scheme_tags, scheme_id, original_excluded)


class AISchemeGenerator:
    """AI方案生成器"""

    def __init__(self, generator: SchemeGenerator):
        self.generator = generator
        self.distribution = self._get_distribution()

    def _get_distribution(self) -> Dict[str, int]:
        distribution = defaultdict(int)
        for tag, scenes in self.generator.tag_index.items():
            usable_count = sum(1 for _, s in scenes if s.is_usable)
            distribution[tag] = usable_count
        return dict(distribution)

    def generate_ai_schemes(
        self,
        existing_plans: List[EditingPlan] = None,
        excluded_material_ids: Set[str] = None,
    ) -> List[EditingPlan]:
        if existing_plans is None:
            existing_plans = []
        if excluded_material_ids is None:
            excluded_material_ids = set()

        prompt = self._build_prompt()

        try:
            import dashscope
            from dashscope import Generation

            api_key = os.environ.get("DASHSCOPE_API_KEY")
            if not api_key:
                print("未设置DASHSCOPE_API_KEY，使用默认方案")
                return self._get_default_schemes(existing_plans, excluded_material_ids)

            dashscope.api_key = api_key

            response = Generation.call(
                model="qwen-plus",
                prompt=prompt,
                max_tokens=2000,
                temperature=0.7,
                result_format="message",
            )

            if response.status_code == 200:
                ai_response = response.output.choices[0].message.content
                schemes = self._parse_ai_response(
                    ai_response, existing_plans, excluded_material_ids
                )
                return schemes
            else:
                print(f"AI调用失败: {response.code}")
                return self._get_default_schemes(existing_plans, excluded_material_ids)

        except Exception as e:
            print(f"AI生成失败: {e}")
            return self._get_default_schemes(existing_plans, excluded_material_ids)

    def _build_prompt(self) -> str:
        available_tags = {
            tag: count for tag, count in self.distribution.items() if count > 0
        }

        prompt = f"""作为短视频剪辑师，设计2个剪辑方案。

可用场景类型及数量：
{json.dumps(available_tags, ensure_ascii=False, indent=2)}

场景类型：
- F01: 开场钩子/悬念引入
- F02: 背景速递/设定交代
- F03: 极限施压/受辱
- F04: 金手指觉醒/身份曝光
- F05: 高潮打脸/绝地反击
- F06: 结尾悬念/下集预告

要求：
1. 每个方案4-6个场景，必须以F06结尾
2. 场景类型可重复
3. 两个方案侧重点不同
4. 优先使用数量较多的场景类型

输出JSON格式：
[
  {{"scheme_id": 3, "tags": ["F01", "F03", "F05", "F06"], "reason": "..."}},
  {{"scheme_id": 4, "tags": ["F02", "F03", "F04", "F05", "F06"], "reason": "..."}}
]
"""
        return prompt

    def _parse_ai_response(
        self,
        response: str,
        existing_plans: List[EditingPlan] = None,
        excluded_material_ids: Set[str] = None,
    ) -> List[EditingPlan]:
        try:
            json_match = re.search(r"\[.*\]", response, re.DOTALL)
            if json_match:
                schemes_data = json.loads(json_match.group())
            else:
                raise ValueError("无法提取JSON")

            plans = []
            for scheme in schemes_data:
                tags = scheme.get("tags", [])
                scheme_id = scheme.get("scheme_id", len(plans) + 3)

                plan = self.generator.generate_fixed_scheme(
                    tags, scheme_id, excluded_material_ids, existing_plans
                )
                plans.append(plan)

            return plans

        except Exception as e:
            print(f"解析失败: {e}")
            return self._get_default_schemes(existing_plans, excluded_material_ids)

    def _get_default_schemes(
        self,
        existing_plans: List[EditingPlan] = None,
        excluded_material_ids: Set[str] = None,
    ) -> List[EditingPlan]:
        if existing_plans is None:
            existing_plans = []
        if excluded_material_ids is None:
            excluded_material_ids = set()

        # 根据可用场景数量选择默认方案
        available = self.distribution

        # 选择可用场景最多的组合
        default_schemes = []

        # 方案3：优先使用F03, F05
        if available.get("F03", 0) > 0 and available.get("F05", 0) > 0:
            default_schemes.append((["F01", "F03", "F05", "F06"], 3))
        else:
            default_schemes.append((["F01", "F02", "F04", "F06"], 3))

        # 方案4：使用不同组合
        if available.get("F02", 0) > 0 and available.get("F04", 0) > 0:
            default_schemes.append((["F02", "F03", "F04", "F05", "F06"], 4))
        else:
            default_schemes.append((["F01", "F04", "F05", "F06"], 4))

        plans = []
        for tags, sid in default_schemes:
            plan = self.generator.generate_fixed_scheme(
                tags, sid, excluded_material_ids, existing_plans
            )
            plans.append(plan)

        return plans


class VideoComposer:
    """视频剪辑器"""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.temp_dir = self.output_dir / "temp"
        self.temp_dir.mkdir(exist_ok=True)

    def _validate_logo_requirements_v2(
        self, scenes: List[MergedScene]
    ) -> Tuple[bool, str]:
        for i, scene in enumerate(scenes):
            has_logo = scene.has_logo
            is_f06 = scene.tag == "F06"
            is_last = scene.is_last_segment

            if is_f06 and not has_logo:
                return False, f"F06场景(第{i + 1}个)没有logo"

            if is_last and has_logo and not is_f06:
                return False, f"最后场景(第{i + 1}个)有logo但标记为{scene.tag}"

        return True, ""

    def download_video(self, url: str, output_path: str) -> bool:
        try:
            cmd = ["curl", "-L", "-o", output_path, url]
            result = subprocess.run(cmd, capture_output=True, timeout=300)
            return result.returncode == 0
        except Exception as e:
            print(f"下载失败: {e}")
            return False

    def cut_segment(
        self, video_path: str, start: float, end: float, output_path: str
    ) -> bool:
        try:
            probe_cmd = [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                video_path,
            ]
            probe_result = subprocess.run(probe_cmd, capture_output=True, timeout=30)
            actual_duration = float(probe_result.stdout.strip())

            if end > actual_duration:
                print(
                    f"  ⚠ 警告: end_time({end:.1f}s)超出视频时长({actual_duration:.1f}s)"
                )
                end = actual_duration

            if end <= start:
                print(f"  ✗ 错误: 结束时间({end})<=开始时间({start})")
                return False

            duration = end - start

            cmd = [
                "ffmpeg",
                "-y",
                "-ss",
                str(start),
                "-i",
                video_path,
                "-t",
                str(duration),
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-c:a",
                "aac",
                "-avoid_negative_ts",
                "make_zero",
                output_path,
            ]

            result = subprocess.run(cmd, capture_output=True, timeout=120)
            return result.returncode == 0
        except Exception as e:
            print(f"剪辑失败: {e}")
            return False

    def merge_videos(self, video_paths: List[str], output_path: str) -> bool:
        try:
            concat_file = self.temp_dir / "concat.txt"
            with open(concat_file, "w") as f:
                for path in video_paths:
                    f.write(f"file '{path}'\n")

            cmd = [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-c:a",
                "aac",
                output_path,
            ]

            result = subprocess.run(cmd, capture_output=True, timeout=300)
            return result.returncode == 0
        except Exception as e:
            print(f"合并失败: {e}")
            return False

    def compose_scheme(
        self,
        plan: EditingPlan,
        material_videos: Dict[str, str],
        material_cache_dir: Path,
    ) -> Optional[str]:
        if not plan.is_valid or not plan.scenes:
            print(f"方案 {plan.scheme_id} 无效")
            return None

        logo_valid, logo_reason = self._validate_logo_requirements_v2(plan.scenes)
        if not logo_valid:
            print(f"✗ 方案 {plan.scheme_id} Logo验证失败: {logo_reason}")
            return None

        segment_files = []

        for i, scene in enumerate(plan.scenes):
            material_id = scene.scenes[0].material_id
            video_url = material_videos.get(material_id)

            if not video_url:
                print(f"找不到素材 {material_id}")
                continue

            video_path = material_cache_dir / f"{material_id}.mp4"
            if not video_path.exists():
                print(f"下载素材 {material_id}...")
                if not self.download_video(video_url, str(video_path)):
                    continue

            segment_file = self.temp_dir / f"scheme{plan.scheme_id}_seg{i}.mp4"

            print(
                f"剪辑片段 {i + 1}/{len(plan.scenes)}: {scene.tag} ({scene.total_duration:.1f}s)"
            )

            if self.cut_segment(
                str(video_path), scene.start_time, scene.end_time, str(segment_file)
            ):
                segment_files.append(str(segment_file))
            else:
                print(f"剪辑片段失败: {i}")

        if not segment_files:
            print(f"方案 {plan.scheme_id} 无成功片段")
            return None

        output_path = self.output_dir / f"方案{plan.scheme_id}_最终版.mp4"
        print(f"合并方案 {plan.scheme_id}...")

        if self.merge_videos(segment_files, str(output_path)):
            print(f"✓ 方案 {plan.scheme_id} 完成: {output_path}")
            return str(output_path)
        else:
            print(f"✗ 方案 {plan.scheme_id} 合并失败")
            return None


class SchemeManager:
    """方案管理器"""

    def __init__(self, generator: SchemeGenerator):
        self.generator = generator
        self.plans: List[EditingPlan] = []
        self.pre_checker = PreSimilarityChecker()

    def generate_all_schemes(self) -> List[EditingPlan]:
        """生成所有方案 - v2修复版"""
        # 重置使用记录
        self.generator.reset_usage()

        # 方案1
        print("\n生成方案1...")
        plan1 = self._generate_with_retry(SCHEME_1, 1)
        self.plans.append(plan1)
        if plan1.is_valid:
            self.pre_checker.add_plan(plan1)
        self._print_plan_status(plan1)

        # 方案2
        print("\n生成方案2...")
        plan2 = self._generate_with_retry(SCHEME_2, 2)
        self.plans.append(plan2)
        if plan2.is_valid:
            self.pre_checker.add_plan(plan2)
        self._print_plan_status(plan2)

        # AI方案3和4
        print("\n生成方案3和方案4...")
        ai_generator = AISchemeGenerator(self.generator)
        ai_plans = ai_generator.generate_ai_schemes(self.plans)

        for plan in ai_plans:
            if not plan.is_valid:
                plan = self._regenerate_plan(plan)

            # 检查相似度
            if plan.is_valid:
                passed, high_sim = self.pre_checker.check_similarity(plan)
                if not passed:
                    print(f"  与方案{high_sim}相似度过高，重新生成...")
                    excluded = self.pre_checker.get_excluded_materials()
                    plan = self.generator.regenerate_scheme(
                        [s.tag for s in plan.scenes]
                        if plan.scenes
                        else ["F01", "F03", "F05", "F06"],
                        plan.scheme_id,
                        excluded,
                    )

            self.plans.append(plan)
            if plan.is_valid:
                self.pre_checker.add_plan(plan)
            self._print_plan_status(plan)

        # 统计结果
        valid_count = sum(1 for p in self.plans if p.is_valid)
        print(f"\n✓ 成功生成 {valid_count}/4 个方案")

        return self.plans

    def _generate_with_retry(self, tags: List[str], scheme_id: int) -> EditingPlan:
        """带重试的生成"""
        for attempt in range(MAX_RETRY_ATTEMPTS):
            plan = self.generator.generate_fixed_scheme(
                tags, scheme_id, existing_plans=self.plans
            )

            if plan.is_valid:
                return plan

            print(
                f"  尝试 {attempt + 1}/{MAX_RETRY_ATTEMPTS} 失败: {plan.invalid_reason}"
            )

            # 策略：如果是找不到场景，尝试排除已用素材
            if "找不到类型为" in plan.invalid_reason:
                used_materials = set()
                for p in self.plans:
                    for s in p.scenes:
                        for scene_info in s.scenes:
                            used_materials.add(scene_info.material_id)

                plan = self.generator.generate_fixed_scheme(
                    tags, scheme_id, used_materials, self.plans
                )
                if plan.is_valid:
                    return plan

            elif "素材重叠率" in plan.invalid_reason:
                excluded = self.pre_checker.get_excluded_materials()
                plan = self.generator.regenerate_scheme(tags, scheme_id, excluded)
                if plan.is_valid:
                    return plan

        # 最后一次尝试
        return self.generator.generate_fixed_scheme(tags, scheme_id, set(), self.plans)

    def _regenerate_plan(self, failed_plan: EditingPlan) -> EditingPlan:
        """重新生成失败的方案"""
        tags = (
            [s.tag for s in failed_plan.scenes]
            if failed_plan.scenes
            else ["F01", "F03", "F05", "F06"]
        )
        excluded = self.pre_checker.get_excluded_materials()
        return self.generator.regenerate_scheme(tags, failed_plan.scheme_id, excluded)

    def _print_plan_status(self, plan: EditingPlan):
        """打印方案状态"""
        if plan.is_valid:
            tags = " → ".join(s.tag for s in plan.scenes)
            materials = [s.scenes[0].material_id for s in plan.scenes]
            print(f"  ✓ 方案{plan.scheme_id}: {tags}")
            print(f"    总时长: {plan.total_duration:.1f}秒")
            print(f"    素材: {materials}")
        else:
            print(f"  ✗ 方案{plan.scheme_id}: {plan.invalid_reason}")


class MaterialRemakeToolV2:
    """素材重制工具v2"""

    def __init__(self):
        self.output_dir = Path(OUTPUT_DIR)
        self.output_dir.mkdir(exist_ok=True)

        self.material_list = []
        self.material_jsons = {}
        self.origin_json = None
        self.origin_scenes = []

        self.all_scenes = []
        self.tagged_scenes = []
        self.merged_scenes = {}

        self.plans = []

    def load_data(self):
        print("=" * 60)
        print("Step 1: 加载数据")
        print("=" * 60)

        shutil.copy(MATERIAL_LIST_PATH, self.output_dir / "material_list.csv")

        with open(MATERIAL_LIST_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="|")
            for row in reader:
                self.material_list.append(
                    {
                        "id": row["id"],
                        "material_name": row["material_name"],
                        "video_url": row["video_url"],
                    }
                )
        print(f"✓ 素材列表: {len(self.material_list)} 条")

        for item in self.material_list:
            json_path = Path(MATERIAL_JSON_DIR) / f"{item['id']}.json"
            if json_path.exists():
                with open(json_path, "r", encoding="utf-8") as f:
                    self.material_jsons[item["id"]] = json.load(f)
        print(f"✓ 素材JSON: {len(self.material_jsons)} 个")

        with open(ORIGIN_JSON_PATH, "r", encoding="utf-8") as f:
            self.origin_json = json.load(f)
        print(f"✓ 原片JSON: {len(self.origin_json)} 集")

        for episode_data in self.origin_json:
            episode = int(episode_data.get("video_name", "0"))
            segments = episode_data.get("result", {}).get("segments", [])

            for idx, seg in enumerate(segments):
                scene = OriginScene(
                    episode=episode,
                    segment_id=seg.get("segment_id", idx + 1),
                    segment_index=idx + 1,
                    start_time=seg.get("start_time", 0),
                    end_time=seg.get("end_time", 0),
                    duration=seg.get("duration", 0),
                    plot_summary=seg.get("plot_summary", ""),
                    narrative_function_tag=seg.get("narrative_function_tag", ""),
                    characters=seg.get("characters", []),
                )
                self.origin_scenes.append(scene)

        print(f"✓ 原片场景: {len(self.origin_scenes)}")

    def extract_scenes(self):
        print("\n" + "=" * 60)
        print("Step 2: 提取场景")
        print("=" * 60)

        for material_id, json_data in self.material_jsons.items():
            material_name = json_data.get("material_name", "")
            video_url = json_data.get("video_url", "")
            segments = json_data.get("result", {}).get("segments", [])

            total_segments = len(segments)

            for idx, seg in enumerate(segments):
                scene = SceneInfo(
                    material_id=material_id,
                    material_name=material_name,
                    video_url=video_url,
                    segment_id=seg.get("segment_id", 0),
                    start_time=seg.get("start_time", 0),
                    end_time=seg.get("end_time", 0),
                    duration=seg.get("duration", 0),
                    plot_summary=seg.get("plot_summary", ""),
                    narrative_function_tag=seg.get("narrative_function_tag", ""),
                    characters=seg.get("characters", []),
                    main_location=seg.get("main_location", ""),
                    emotion_level=seg.get("emotion_level", 0),
                    emotion_polarity=seg.get("emotion_polarity", 0),
                    is_highlight=seg.get("is_highlight", False),
                    has_logo=seg.get("has_logo", False),
                    logo_position=seg.get("logo_position", ""),
                    is_last_segment=(idx == total_segments - 1),
                )
                self.all_scenes.append(scene)

        print(f"✓ 提取场景: {len(self.all_scenes)}")

    def match_and_tag_scenes(self):
        print("\n" + "=" * 60)
        print("Step 3: 场景匹配与打标")
        print("=" * 60)

        matcher = SceneMatcher(self.origin_scenes)
        tagger = SceneTagger(matcher, min_match_score=MIN_MATCH_SCORE)

        self.tagged_scenes = [tagger.tag_scene(s) for s in self.all_scenes]

        matched_count = sum(1 for s in self.tagged_scenes if s.is_matched)
        print(f"✓ 匹配成功: {matched_count}/{len(self.tagged_scenes)}")

        tag_stats = defaultdict(lambda: {"matched": 0, "total": 0})
        for scene in self.tagged_scenes:
            tag = (
                scene.narrative_function_tag[:3]
                if scene.narrative_function_tag
                else "Unknown"
            )
            tag_stats[tag]["total"] += 1
            if scene.is_matched:
                tag_stats[tag]["matched"] += 1

        print("\n场景类型分布:")
        for tag, stats in sorted(tag_stats.items()):
            print(f"  {tag}: {stats['matched']}/{stats['total']} 匹配")

    def merge_scenes(self):
        print("\n" + "=" * 60)
        print("Step 4: 合并连续场景")
        print("=" * 60)

        merger = SceneMerger()

        scenes_by_material = defaultdict(list)
        for scene in self.tagged_scenes:
            scenes_by_material[scene.material_id].append(scene)

        total_original = 0
        total_merged = 0

        for material_id, scenes in scenes_by_material.items():
            scenes.sort(key=lambda s: s.segment_id)
            total_original += len(scenes)

            merged = merger.merge_consecutive(scenes)
            self.merged_scenes[material_id] = merged
            total_merged += len(merged)

        print(f"✓ 合并前: {total_original}")
        print(f"✓ 合并后: {total_merged}")
        print(f"✓ 减少: {total_original - total_merged}")

    def _retag_logo_scenes(self):
        print("\n" + "=" * 60)
        print("Step 4.5: 重新标记结尾Logo场景")
        print("=" * 60)

        retagged_count = 0
        for material_id, scenes in self.merged_scenes.items():
            # 找到最后一个有logo的场景（真正的结尾）
            logo_scenes = [(i, s) for i, s in enumerate(scenes) if s.has_logo]

            if not logo_scenes:
                continue

            # 优先选择最后一个场景
            last_logo_scene_idx, last_logo_scene = logo_scenes[-1]

            # 如果不是F06，则重新标记
            if last_logo_scene.tag != "F06":
                old_tag = last_logo_scene.tag
                last_logo_scene.tag = "F06"
                retagged_count += 1
                print(f"  🔄 {old_tag}(素材{material_id})→F06 (结尾场景)")

        print(f"✓ 重新标记结尾Logo场景: {retagged_count}")

    def generate_schemes(self):
        print("\n" + "=" * 60)
        print("Step 5: 生成剪辑方案")
        print("=" * 60)

        generator = SchemeGenerator(self.merged_scenes)
        manager = SchemeManager(generator)

        self.plans = manager.generate_all_schemes()

    def compose_videos(self):
        print("\n" + "=" * 60)
        print("Step 6: 视频剪辑")
        print("=" * 60)

        material_cache_dir = self.output_dir / "material_videos"
        material_cache_dir.mkdir(exist_ok=True)

        material_videos = {item["id"]: item["video_url"] for item in self.material_list}

        composer = VideoComposer(str(self.output_dir))

        for plan in self.plans:
            if plan.is_valid:
                print(f"\n处理方案 {plan.scheme_id}...")
                composer.compose_scheme(plan, material_videos, material_cache_dir)

    def generate_reports(self):
        print("\n" + "=" * 60)
        print("Step 7: 生成报告")
        print("=" * 60)

        # 场景匹配报告
        match_report = {
            "version": "v2-final",
            "generate_time": datetime.now().isoformat(),
            "total_scenes": len(self.tagged_scenes),
            "matched_scenes": sum(1 for s in self.tagged_scenes if s.is_matched),
            "match_details": [],
        }

        for scene in self.tagged_scenes:
            match_report["match_details"].append(
                {
                    "material_id": scene.material_id,
                    "segment_id": scene.segment_id,
                    "tag": scene.narrative_function_tag,
                    "is_matched": scene.is_matched,
                    "match_score": round(scene.match_score, 3),
                    "match_note": scene.match_note,
                }
            )

        with open(self.output_dir / "场景匹配报告.json", "w", encoding="utf-8") as f:
            json.dump(match_report, f, ensure_ascii=False, indent=2)
        print("✓ 场景匹配报告")

        # 方案详情
        scheme_details = {
            "version": "v2-final",
            "generate_time": datetime.now().isoformat(),
            "schemes": [],
        }

        for plan in self.plans:
            scheme_data = {
                "scheme_id": plan.scheme_id,
                "scheme_name": plan.scheme_name,
                "is_valid": plan.is_valid,
                "invalid_reason": plan.invalid_reason,
                "total_duration": round(plan.total_duration, 2),
                "scenes": [
                    {
                        "tag": s.tag,
                        "material_id": s.scenes[0].material_id,
                        "duration": round(s.total_duration, 2),
                    }
                    for s in plan.scenes
                ],
            }
            scheme_details["schemes"].append(scheme_data)

        with open(self.output_dir / "方案详情.json", "w", encoding="utf-8") as f:
            json.dump(scheme_details, f, ensure_ascii=False, indent=2)
        print("✓ 方案详情")

        # 预相似度报告
        similarity_report = {
            "version": "v2-final",
            "generate_time": datetime.now().isoformat(),
            "similarity_matrix": {},
        }

        checker = PreSimilarityChecker()
        for plan in self.plans:
            checker.add_plan(plan)

        for i, plan1 in enumerate(self.plans):
            for j, plan2 in enumerate(self.plans):
                if i < j:
                    temp_checker = PreSimilarityChecker()
                    temp_checker.add_plan(plan1)
                    overlaps = temp_checker.compute_material_overlap(plan2)
                    key = f"{plan1.scheme_id}_vs_{plan2.scheme_id}"
                    similarity_report["similarity_matrix"][key] = round(
                        overlaps.get(plan1.scheme_id, 0.0), 4
                    )

        with open(self.output_dir / "预相似度报告.json", "w", encoding="utf-8") as f:
            json.dump(similarity_report, f, ensure_ascii=False, indent=2)
        print("✓ 预相似度报告")

        # 执行摘要
        valid_count = sum(1 for p in self.plans if p.is_valid)

        summary = f"""# 素材剪辑测试方案v2-final - 执行摘要

生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 修复内容
1. ✓ 素材使用限制改为每个视频单独限制（非全局）
2. ✓ 完善F06场景Logo验证
3. ✓ 场景顺序验证放宽（混剪允许跨集）
4. ✓ 全局使用记录智能管理
5. ✓ 添加失败重试机制
6. ✓ 提高匹配阈值（0.15→0.25）

## 数据统计
- 素材数量: {len(self.material_list)}
- 素材场景: {len(self.all_scenes)}
- 成功方案: {valid_count}/4

## 方案结果

| 方案 | 状态 | 时长 | 场景数 |
|------|------|------|--------|
"""

        for plan in self.plans:
            status = "✓" if plan.is_valid else "✗"
            duration = f"{plan.total_duration / 60:.1f}分钟" if plan.is_valid else "-"
            scenes = len(plan.scenes) if plan.is_valid else 0
            summary += f"| 方案{plan.scheme_id} | {status} | {duration} | {scenes} |\n"

        summary += """
## 输出文件
- `方案X_最终版.mp4` - 剪辑后的视频
- `剪辑计划.csv` - 详细剪辑信息
- `场景匹配报告.json` - 匹配结果
- `方案详情.json` - 方案配置
- `预相似度报告.json` - v2新增
- `执行摘要.md` - 本文件
"""

        with open(self.output_dir / "执行摘要.md", "w", encoding="utf-8") as f:
            f.write(summary)
        print("✓ 执行摘要")

    def run(self):
        print("=" * 60)
        print("素材剪辑测试方案v2-final - 开始")
        print("=" * 60)

        self.load_data()
        self.extract_scenes()
        self.match_and_tag_scenes()
        self.merge_scenes()
        self._retag_logo_scenes()
        self.generate_schemes()
        self.generate_reports()

        print("\n" + "=" * 60)
        print("报告生成完成！")
        print(f"输出: {self.output_dir}")
        print("=" * 60)

        return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="素材剪辑测试方案v2-final")
    parser.add_argument("--compose", action="store_true", help="进行视频剪辑")
    parser.add_argument("--test", action="store_true", help="仅测试生成报告")

    args = parser.parse_args()

    tool = MaterialRemakeToolV2()

    if args.test:
        print("测试模式：仅生成报告")
        tool.run()
    else:
        tool.run()
        if args.compose:
            print("\n开始视频剪辑...")
            tool.compose_videos()

    print("\n✓ 全部完成！")


if __name__ == "__main__":
    main()
