# Subtitle Timeline Merge API

供字幕团队合并时间轴修订的三方合并服务。基于 Python + FastAPI + Pydantic。

## 启动（单条命令）

```bash
docker compose up --build
```

依赖安装与服务初始化均在容器内完成，无需本地环境。

## 访问地址

| 入口 | 地址 |
| --- | --- |
| 服务地址 | http://localhost:8000 |
| 交互式文档 | http://localhost:8000/docs |
| 健康检查 | http://localhost:8000/health |
| 合并接口 | POST http://localhost:8000/merge |

端口：`8000`（宿主机）→ `8000`（容器）。

## 接口说明

### POST /merge

接收 `base`、`current`、`incoming` 三版 cue 列表，按 cue `id` 执行三方合并：

- 仅一侧变化 → 采纳该侧；
- 两侧同值 → 采纳该值；
- 两侧异值 → 返回字段级冲突（`status: "conflict"`）；
- 一侧删除、另一侧修改 → 返回 `delete_modify` 冲突；一侧删除、另一侧未变 → 采纳删除。

无冲突时按开始时间排序；若任意字幕区间重叠（端点相接不算重叠），返回相关 cue id
与重叠区间（`status: "overlap"`），不输出合并版本。全部通过才返回
`status: "merged"` 及排序后的 `cues`。

Cue 字段：`id`（字符串，合并键）、`start` / `end`（秒，`end > start`）、
`text`、`speaker`（可选）。除 `id` 外的字段均参与字段级合并。

请求示例：

```bash
curl -X POST http://localhost:8000/merge \
  -H "Content-Type: application/json" \
  -d '{
    "base":     [{"id": "1", "start": 0, "end": 2, "text": "你好"}],
    "current":  [{"id": "1", "start": 0, "end": 2.5, "text": "你好"}],
    "incoming": [{"id": "1", "start": 0, "end": 2, "text": "你好，世界"}]
  }'
```

响应（合并成功）：

```json
{
  "status": "merged",
  "cues": [{"id": "1", "start": 0.0, "end": 2.5, "text": "你好，世界", "speaker": null}],
  "conflicts": null,
  "overlaps": null
}
```

冲突响应示例：

```json
{
  "status": "conflict",
  "cues": null,
  "conflicts": [
    {"cue_id": "1", "type": "field", "field": "text", "base": "a", "current": "x", "incoming": "y"}
  ],
  "overlaps": null
}
```

重叠响应示例：

```json
{
  "status": "overlap",
  "cues": null,
  "conflicts": null,
  "overlaps": [
    {"cue_ids": ["a", "b"], "overlap_start": 2.0, "overlap_end": 3.0}
  ]
}
```

### GET /health

返回 `{"status": "ok"}`，用于容器健康检查与负载探活。

## 本地开发（可选）

```bash
pip install -r requirements-dev.txt
pytest            # 运行测试
uvicorn app.main:app --reload
```

## 项目结构

```
app/
  main.py    # FastAPI 入口：/merge、/health
  models.py  # Pydantic 模型
  merge.py   # 三方合并与重叠检测逻辑
tests/
  test_merge.py
Dockerfile
docker-compose.yml
requirements.txt
```
