"""Pydantic 模型：cue、合并请求与响应。"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class Cue(BaseModel):
    """一条字幕 cue。除 id 外的字段均参与三方合并。"""

    id: str = Field(..., min_length=1)
    start: float = Field(..., ge=0, description="开始时间（秒）")
    end: float = Field(..., gt=0, description="结束时间（秒）")
    text: str = ""
    speaker: Optional[str] = None

    @model_validator(mode="after")
    def _check_interval(self) -> "Cue":
        if self.end <= self.start:
            raise ValueError("end 必须大于 start")
        return self


# 参与字段级合并的字段（id 仅作为键）
MERGE_FIELDS: tuple[str, ...] = ("start", "end", "text", "speaker")


class MergeRequest(BaseModel):
    """三方合并输入：base 为共同祖先，current / incoming 为两侧修订。"""

    base: list[Cue] = Field(default_factory=list)
    current: list[Cue] = Field(default_factory=list)
    incoming: list[Cue] = Field(default_factory=list)


class Conflict(BaseModel):
    """字段级冲突。type=delete_modify 表示一侧删除、另一侧修改。"""

    cue_id: str
    type: Literal["field", "delete_modify"]
    field: Optional[str] = None
    base: Any = None
    current: Any = None
    incoming: Any = None


class Overlap(BaseModel):
    """一对重叠 cue 及其重叠区间。"""

    cue_ids: list[str]
    overlap_start: float
    overlap_end: float


class MergeResponse(BaseModel):
    status: Literal["merged", "conflict", "overlap"]
    cues: Optional[list[Cue]] = None
    conflicts: Optional[list[Conflict]] = None
    overlaps: Optional[list[Overlap]] = None
