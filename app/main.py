"""FastAPI 入口：/merge 三方合并接口与 /health 健康检查。"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException

from .merge import DuplicateCueIdError, find_overlaps, index_by_id, merge_cues, sort_cues
from .models import MergeRequest, MergeResponse

app = FastAPI(
    title="Subtitle Timeline Merge API",
    version="1.0.0",
    description="供字幕团队合并时间轴修订的三方合并服务。",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/merge", response_model=MergeResponse)
def merge(request: MergeRequest) -> MergeResponse:
    try:
        base = index_by_id(request.base, "base")
        current = index_by_id(request.current, "current")
        incoming = index_by_id(request.incoming, "incoming")
    except DuplicateCueIdError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    merged, conflicts = merge_cues(base, current, incoming)
    if conflicts:
        return MergeResponse(status="conflict", conflicts=conflicts)

    cues = sort_cues(list(merged.values()))
    overlaps = find_overlaps(cues)
    if overlaps:
        return MergeResponse(status="overlap", overlaps=overlaps)

    return MergeResponse(status="merged", cues=cues)
