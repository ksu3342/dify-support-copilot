# Dify Internal Support Copilot

[English](./README.md)

一个面向自部署 Dify 场景的 deterministic support triage MVP：接收支持问题，基于官方文档做证据检索，然后在回答、追问一次或建单之间做明确决策。

[![Python](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)](./requirements.txt)
[![FastAPI](https://img.shields.io/badge/api-FastAPI-009688?logo=fastapi&logoColor=white)](./app/api/main.py)
[![Support%20Flow](https://img.shields.io/badge/support%20flow-deterministic-1F6FEB)](./app/support/service.py)
[![Tests](https://img.shields.io/badge/tests-pytest-6DB33F)](./tests/)
[![Replay%20Eval](https://img.shields.io/badge/eval-replay-F59E0B)](./scripts/run_eval.py)
[![Architecture](https://img.shields.io/badge/docs-architecture-6B7280)](./docs/ARCHITECTURE.md)

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python scripts\fetch_sources.py
.\.venv\Scripts\python scripts\build_index.py
.\.venv\Scripts\python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
Invoke-RestMethod -Method Get -Uri 'http://127.0.0.1:8000/readyz'
```

`/readyz` 才表示当前 support baseline 是否真的可回答问题；如果返回 `503`，说明本地语料或 chunk 索引还没准备好。

## What This Repo Does

这个仓库把一个受控的 Dify 支持流程落成了可运行的后端服务，而不是泛化成“什么都能聊”的问答系统。输入是一条支持问题，系统会做固定分类、从官方文档里找证据，并输出三种明确结果之一：

- `answered`
- `needs_clarification`
- `ticket_created`

范围刻意收窄为：

- 单一语料域：Dify 官方英文文档
- 单一路径：classify -> retrieve -> decide
- 最多只追问一轮
- 本地持久化 runs、retrieval hits、tickets 和 snapshot metadata

## What Is Implemented

- 对 `deployment`、`configuration`、`knowledge-base`、`integration`、`unclassified` 的 deterministic support triage
- 固定槽位抽取：`deployment_method`、`version`、`error_message`、`environment`
- 基于 manifest 的本地文档检索
- `POST /v1/support/ask` 的同步支持链路
- 通过 `follow_up_run_id` 处理一次补充提问
- 本地文档抓取、快照落盘、元数据入库，以及同一 `snapshot_version` 下的内容漂移拒绝覆盖
- replay eval 与阈值校验
- 通过 `GET /healthz` 和 `GET /readyz` 区分 liveness 与 readiness

## Why It Is Designed This Way

- 先做 deterministic baseline：当前实现不依赖外部模型密钥，行为更容易验证和复现。
- 只保留单一官方语料：支持回答必须建立在 Dify 官方文档上，而不是混入论坛或博客。
- 把升级当成能力的一部分：证据不足时先追问，再建单，比勉强回答更诚实。
- 把证据链落地：runs、retrieval hits、tickets、eval artifacts 都留在本地，方便复盘。

## Engineering Evidence

仓库里可以直接证明当前说法成立的入口：

- API 入口与健康检查：[`app/api/main.py`](./app/api/main.py)
- 支持决策主链：[`app/support/service.py`](./app/support/service.py)
- 本地检索与索引构建：[`app/retrieval/index.py`](./app/retrieval/index.py)
- 文档抓取与快照处理：[`app/ingest/`](./app/ingest/)
- SQLite schema 与持久化：[`scripts/init_db.sql`](./scripts/init_db.sql)、[`app/models/db.py`](./app/models/db.py)
- 集成与单元测试：[`tests/`](./tests/)
- replay eval 入口：[`scripts/run_eval.py`](./scripts/run_eval.py)
- 容器化打包入口：[`Dockerfile`](./Dockerfile)、[`docker-compose.yml`](./docker-compose.yml)

## Boundaries / Non-goals

这个项目是：

- AI 应用原型
- Python 后端服务
- 面向自部署 Dify 场景的受控 support baseline

这个项目不是：

- 远程 LLM 支持系统
- 多智能体运行时
- 前端或 dashboard 产品
- 基于队列的异步系统
- embedding 检索栈
- 面向生产部署的平台

刻意不做的部分：

- 不接外部模型提供方
- 不扩成多来源知识平台
- 不做 memory 或长期会话状态
- 不抽象多套 retrieval backend

## Further Reading

- 架构说明：[`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)
- 演示脚本：[`docs/DEMO_SCRIPT.md`](./docs/DEMO_SCRIPT.md)
- 面试讲解素材：[`docs/INTERVIEW_NOTES.md`](./docs/INTERVIEW_NOTES.md)
- 可安全写进简历的 bullet：[`docs/RESUME_BULLETS.md`](./docs/RESUME_BULLETS.md)
- 当前实现范围与冻结规格：[`SPEC.md`](./SPEC.md)
