# Dify Internal Support Copilot

[English](./README.en.md) | [旧中文入口](./README.zh-CN.md)

面向 self-hosted Dify 运维支持场景的证据驱动 support triage backend。

Self-hosted Dify 的支持问题通常分散在安装、配置、知识库、插件/API 集成等文档里。这个项目把这类请求整理成一条可运行的后端链路：读取官方文档证据，判断问题类型，检索相关内容，然后在 `answered`、`needs_clarification`、`ticket_created` 之间做明确分流。

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python scripts\fetch_sources.py
.\.venv\Scripts\python scripts\build_index.py
.\.venv\Scripts\python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
Invoke-RestMethod -Method Get -Uri 'http://127.0.0.1:8000/readyz'
```

`/healthz` 只表示服务存活；`/readyz` 才表示当前 Dify 文档快照和 chunk 索引已经准备好，可以回答 support 问题。

## 一个支持请求如何被处理

下面样例来自当前仓库本地 API 验证，不是手写的理想输出。

**Question**

```text
How do I configure chunk settings for a knowledge base in Dify?
```

**Classification**

```json
{
  "status": "answered",
  "category": "knowledge-base",
  "answer_generation_mode": "deterministic"
}
```

**Retrieved evidence**

```json
[
  {
    "chunk_id": "chunk_0a2e3366da743c0b1403aaee",
    "source_url": "https://docs.dify.ai/en/guides/knowledge-base/create-knowledge-and-upload-documents/chunking-and-cleaning-text",
    "snapshot_version": "dify-docs-en-2026-04-21-v2",
    "title": "Configure the Chunk Settings - Dify Docs",
    "chunk_index": 1
  },
  {
    "chunk_id": "chunk_1ddcceb284436856cbeaec27",
    "source_url": "https://docs.dify.ai/en/use-dify/knowledge/create-knowledge/setting-indexing-methods",
    "snapshot_version": "dify-docs-en-2026-04-21-v2",
    "title": "Specify the Index Method and Retrieval Settings - Dify Docs",
    "chunk_index": 8
  }
]
```

**Answer snippet**

```text
Relevant Dify documentation excerpts:
- Configure the Chunk Settings - Dify Docs: ... a Chunk Mode The chunk mode cannot be changed once the knowledge base is created. However, chunk settings ...
- Specify the Index Method and Retrieval Settings - Dify Docs: ... Utilizing embedding models, even if the exact terms from the query do not appear in the knowledge base ...
```

另外两条主链路径也有 integration coverage：

- `My plugin integration fails.` -> `needs_clarification`
- `Still failing after I retried the integration.` with `follow_up_run_id` -> `ticket_created`

## 这个项目在做什么

这个仓库不是泛化聊天机器人。它把 self-hosted Dify 的内部支持请求收敛到一个可检查的后端 baseline：

- 从 Dify 官方英文文档抓取、清洗并保存本地快照
- 基于 manifest metadata 做分类后的定向检索
- 对支持问题执行固定类别分流
- 证据足够时回答并保留 citation
- 信息不足时只追问一次
- 仍不足或无法归类时创建本地 ticket
- 记录 run、retrieval hits、tickets 和 snapshot metadata
- 用 replay eval 回放当前支持行为

## 当前已实现

- Dify 官方文档 ingestion、cleaning、snapshot persistence
- 同一 `snapshot_version` 下的内容漂移拒绝覆盖
- deterministic classification：`deployment`、`configuration`、`knowledge-base`、`integration`、`unclassified`
- fixed-slot extraction：`deployment_method`、`version`、`error_message`、`environment`
- manifest-guided local retrieval
- `POST /v1/support/ask` 同步返回 `answered`、`needs_clarification` 或 `ticket_created`
- `retrieval_hits` logging 和 SQLite ticket persistence
- `GET /healthz` liveness 与 `GET /readyz` readiness 分离
- replay eval runner 与版本控制内 eval cases
- answered 路径的 optional OpenAI-compatible answer synthesis 入口
- provider 失败或限流时的 deterministic fallback

## 主链如何决策

```text
support question
  -> deterministic classification
  -> fixed-slot extraction
  -> manifest-guided retrieval
  -> decision
       -> answered + citations
       -> needs_clarification
       -> ticket_created
  -> support_runs / retrieval_hits / tickets
```

关键规则：

- `unclassified` 直接进入 `ticket_created`
- deployment / configuration 问题缺少足够槽位时先进入 `needs_clarification`
- knowledge-base / integration 的模糊故障描述会先澄清，不会因为检索有命中就强答
- 同一请求链只允许一轮澄清；第二轮仍不足时进入 ticket
- `/v1/support/ask` 不在请求路径里隐式抓文档或建索引；未 ready 时应先运行 ingest/index 命令

## 工程证据

这些入口可以直接对应当前 README 的能力描述：

- API 入口、`/healthz`、`/readyz`：[`app/api/main.py`](./app/api/main.py)
- support 主链和决策规则：[`app/support/service.py`](./app/support/service.py)
- optional LLM answer synthesis client：[`app/llm/client.py`](./app/llm/client.py)
- ingestion、cleaning、snapshot handling：[`app/ingest/`](./app/ingest/)
- chunking、indexing、local retrieval：[`app/retrieval/`](./app/retrieval/)
- SQLite schema：[`scripts/init_db.sql`](./scripts/init_db.sql)
- support API integration tests：[`tests/integration/`](./tests/integration/)
- replay eval runner：[`scripts/run_eval.py`](./scripts/run_eval.py)
- eval cases：[`data/evals/support_eval_v1.yaml`](./data/evals/support_eval_v1.yaml)
- demo script：[`docs/DEMO_SCRIPT.md`](./docs/DEMO_SCRIPT.md)
- architecture notes：[`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)

## 可选 LLM Answer Synthesis

`answered` 路径支持一个可选的 OpenAI-compatible answer synthesis 入口。它只在检索证据已经足够、请求已经进入 `answered` 分支后尝试调用 LLM，用于把 retrieved evidence 组织成更自然的回答。

当前约束：

- classification 仍是 deterministic
- clarification 和 ticket decision 不调用 LLM
- citations 仍来自 retrieval hits
- provider 成功时可返回 `answer_generation_mode = llm`
- provider 失败、超时或限流时会回退到 `answer_generation_mode = deterministic_fallback`
- 当前不声明 live provider success 已经稳定完成

因此，这一能力应理解为可切换的回答生成增强，而不是完整 LLM Copilot 或 Agent orchestration。

## 边界 / Non-goals

这个仓库当前是一个 AI application prototype / Python backend service，用于演示 self-hosted Dify 支持分诊链路的最小工程闭环。

当前没有实现：

- 面向生产部署的完整支持平台
- 前端或 dashboard
- 多智能体编排
- async worker / queue
- embedding-based retrieval 或向量库基准
- 复杂权限系统
- 稳定验证完成的 live LLM provider path

这些边界是刻意保留的。当前优先级是让支持链路可运行、可检查、可测试、可回放评测，而不是把项目扩成平台。

## 进一步阅读

- [Demo Script](./docs/DEMO_SCRIPT.md)
- [Architecture](./docs/ARCHITECTURE.md)
- [Interview Notes](./docs/INTERVIEW_NOTES.md)
- [Resume Bullets](./docs/RESUME_BULLETS.md)
- [Specification](./SPEC.md)
