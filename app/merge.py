"""三方合并核心逻辑：按 cue id 对齐 base / current / incoming。"""
from __future__ import annotations

from .models import MERGE_FIELDS, Conflict, Cue, Overlap


class DuplicateCueIdError(ValueError):
    """同一列表中出现重复 cue id。"""


def index_by_id(cues: list[Cue], side: str) -> dict[str, Cue]:
    indexed: dict[str, Cue] = {}
    for cue in cues:
        if cue.id in indexed:
            raise DuplicateCueIdError(f"{side} 列表中 cue id 重复: {cue.id}")
        indexed[cue.id] = cue
    return indexed


def _fields_of(cue: Cue) -> dict[str, object]:
    return {f: getattr(cue, f) for f in MERGE_FIELDS}


def merge_cues(
    base: dict[str, Cue],
    current: dict[str, Cue],
    incoming: dict[str, Cue],
) -> tuple[dict[str, Cue], list[Conflict]]:
    """按 cue id 执行三方合并。

    返回 (合并结果, 冲突列表)。存在冲突时合并结果中不含冲突 cue，
    调用方应直接报告冲突而不输出合并版本。
    """
    merged: dict[str, Cue] = {}
    conflicts: list[Conflict] = []

    for cue_id in sorted(set(base) | set(current) | set(incoming)):
        b = base.get(cue_id)
        c = current.get(cue_id)
        i = incoming.get(cue_id)

        # base 中不存在：新增 cue
        if b is None:
            if c is not None and i is not None:
                if c == i:
                    merged[cue_id] = c  # 两侧同值
                else:
                    for f in MERGE_FIELDS:  # 两侧异值 → 字段级冲突
                        if getattr(c, f) != getattr(i, f):
                            conflicts.append(Conflict(
                                cue_id=cue_id, type="field", field=f,
                                base=None, current=getattr(c, f), incoming=getattr(i, f),
                            ))
            elif c is not None:
                merged[cue_id] = c  # 仅 current 新增
            elif i is not None:
                merged[cue_id] = i  # 仅 incoming 新增
            continue

        # 两侧均删除
        if c is None and i is None:
            continue

        # 删除与修改同时发生 → 冲突；删除与未变更 → 采纳删除
        if c is None:
            if _fields_of(i) == _fields_of(b):
                continue
            conflicts.append(Conflict(
                cue_id=cue_id, type="delete_modify",
                base=b.model_dump(), current=None, incoming=i.model_dump(),
            ))
            continue
        if i is None:
            if _fields_of(c) == _fields_of(b):
                continue
            conflicts.append(Conflict(
                cue_id=cue_id, type="delete_modify",
                base=b.model_dump(), current=c.model_dump(), incoming=None,
            ))
            continue

        # 三侧均存在：逐字段三方合并
        merged_fields: dict[str, object] = {}
        cue_has_conflict = False
        for f in MERGE_FIELDS:
            bv, cv, iv = getattr(b, f), getattr(c, f), getattr(i, f)
            if cv == iv:
                merged_fields[f] = cv  # 两侧同值
            elif bv == cv:
                merged_fields[f] = iv  # 仅 incoming 变化
            elif bv == iv:
                merged_fields[f] = cv  # 仅 current 变化
            else:
                cue_has_conflict = True  # 两侧异值
                conflicts.append(Conflict(
                    cue_id=cue_id, type="field", field=f,
                    base=bv, current=cv, incoming=iv,
                ))
        if not cue_has_conflict:
            merged[cue_id] = Cue(id=cue_id, **merged_fields)

    return merged, conflicts


def sort_cues(cues: list[Cue]) -> list[Cue]:
    """按开始时间排序（开始相同则按结束、id 保证稳定）。"""
    return sorted(cues, key=lambda c: (c.start, c.end, c.id))


def find_overlaps(sorted_cues: list[Cue]) -> list[Overlap]:
    """扫描已按开始时间排序的 cue，返回所有区间重叠对。

    端点相接（前一 cue 的 end == 后一 cue 的 start）不算重叠。
    """
    overlaps: list[Overlap] = []
    active: list[Cue] = []  # end 大于当前 start 的 cue
    for cue in sorted_cues:
        active = [a for a in active if a.end > cue.start]
        for a in active:
            overlaps.append(Overlap(
                cue_ids=[a.id, cue.id],
                overlap_start=max(a.start, cue.start),
                overlap_end=min(a.end, cue.end),
            ))
        active.append(cue)
    return overlaps
