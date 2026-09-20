"""合并逻辑与 API 的端到端测试。"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def cue(cid, start, end, text="t", speaker=None):
    c = {"id": cid, "start": start, "end": end, "text": text}
    if speaker is not None:
        c["speaker"] = speaker
    return c


def merge(base, current, incoming):
    resp = client.post("/merge", json={
        "base": base, "current": current, "incoming": incoming,
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_only_one_side_changed():
    base = [cue("1", 0, 2, "a"), cue("2", 3, 5, "b")]
    current = [cue("1", 0, 2, "a"), cue("2", 3, 6, "b")]  # current 改 end
    incoming = [cue("1", 0, 2, "A"), cue("2", 3, 5, "b")]  # incoming 改 text
    result = merge(base, current, incoming)
    assert result["status"] == "merged"
    by_id = {c["id"]: c for c in result["cues"]}
    assert by_id["1"]["text"] == "A"
    assert by_id["2"]["end"] == 6


def test_both_sides_same_value():
    base = [cue("1", 0, 2, "a")]
    changed = [cue("1", 0, 2, "same")]
    result = merge(base, changed, changed)
    assert result["status"] == "merged"
    assert result["cues"][0]["text"] == "same"


def test_field_level_conflict():
    base = [cue("1", 0, 2, "a")]
    current = [cue("1", 0, 2, "x")]
    incoming = [cue("1", 0, 2, "y")]
    result = merge(base, current, incoming)
    assert result["status"] == "conflict"
    assert result["cues"] is None
    assert result["conflicts"] == [{
        "cue_id": "1", "type": "field", "field": "text",
        "base": "a", "current": "x", "incoming": "y",
    }]


def test_delete_vs_modify_conflict():
    base = [cue("1", 0, 2, "a"), cue("2", 3, 5, "b")]
    current = [cue("2", 3, 5, "b")]                       # current 删除 1
    incoming = [cue("1", 0, 2, "changed"), cue("2", 3, 5, "b")]  # incoming 修改 1
    result = merge(base, current, incoming)
    assert result["status"] == "conflict"
    conflict = result["conflicts"][0]
    assert conflict["cue_id"] == "1"
    assert conflict["type"] == "delete_modify"
    assert conflict["current"] is None
    assert conflict["incoming"]["text"] == "changed"


def test_delete_vs_unchanged_is_deleted():
    base = [cue("1", 0, 2, "a"), cue("2", 3, 5, "b")]
    current = [cue("2", 3, 5, "b")]           # 删除 1
    incoming = [cue("1", 0, 2, "a"), cue("2", 3, 5, "b")]  # 未动 1
    result = merge(base, current, incoming)
    assert result["status"] == "merged"
    assert [c["id"] for c in result["cues"]] == ["2"]


def test_both_deleted_is_deleted():
    result = merge([cue("1", 0, 2)], [[], []][0], [])
    assert result == {"status": "merged", "cues": [], "conflicts": None, "overlaps": None}


def test_additions_from_both_sides():
    base = []
    current = [cue("a", 0, 1)]
    incoming = [cue("b", 2, 3)]
    result = merge(base, current, incoming)
    assert result["status"] == "merged"
    assert [c["id"] for c in result["cues"]] == ["a", "b"]


def test_same_addition_both_sides_no_conflict():
    result = merge([], [cue("a", 0, 1, "x")], [cue("a", 0, 1, "x")])
    assert result["status"] == "merged"
    assert len(result["cues"]) == 1


def test_conflicting_addition_both_sides():
    result = merge([], [cue("a", 0, 1, "x")], [cue("a", 0, 1, "y")])
    assert result["status"] == "conflict"
    assert result["conflicts"][0]["field"] == "text"


def test_sorted_by_start_time():
    base = []
    current = [cue("b", 5, 6), cue("a", 1, 2)]
    incoming = []
    result = merge(base, current, incoming)
    assert result["status"] == "merged"
    assert [c["id"] for c in result["cues"]] == ["a", "b"]


def test_overlap_reported_without_merged_cues():
    base = []
    current = [cue("a", 0, 3), cue("b", 2, 5)]
    incoming = []
    result = merge(base, current, incoming)
    assert result["status"] == "overlap"
    assert result["cues"] is None
    assert result["overlaps"] == [{
        "cue_ids": ["a", "b"], "overlap_start": 2.0, "overlap_end": 3.0,
    }]


def test_overlap_with_non_adjacent_cue():
    # 长区间跨越多个 cue：排序后非相邻的重叠也要被捕获
    base = []
    current = [cue("long", 0, 10), cue("x", 1, 2), cue("y", 3, 4)]
    incoming = []
    result = merge(base, current, incoming)
    assert result["status"] == "overlap"
    pairs = {tuple(o["cue_ids"]) for o in result["overlaps"]}
    assert pairs == {("long", "x"), ("long", "y")}


def test_touching_intervals_not_overlap():
    result = merge([], [cue("a", 0, 2), cue("b", 2, 4)], [])
    assert result["status"] == "merged"


def test_duplicate_id_rejected():
    resp = client.post("/merge", json={
        "base": [], "current": [cue("a", 0, 1), cue("a", 2, 3)], "incoming": [],
    })
    assert resp.status_code == 422


def test_invalid_interval_rejected():
    resp = client.post("/merge", json={
        "base": [], "current": [cue("a", 3, 3)], "incoming": [],
    })
    assert resp.status_code == 422
