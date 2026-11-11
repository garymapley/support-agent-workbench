# 企业售后工单 Agent

当前里程碑：Agent 已具备订单查询、政策 RAG、工单创建、风险判断和可暂停/恢复的人工退款审批。

退款审批已经接入主 Agent 图：退款工单会由代码规则自动创建审批，原对话通过 `interrupt()` 暂停，人工决定后使用同一个 `thread_id` 恢复。模型、Embedding 和远程 Qdrant 查询均配置了超时与有限重试；创建工单、创建审批等写操作不会自动重试。

默认模型：

- 聊天：`deepseek-v4.1-flash`
- Embedding：`qwen3.7-text-embedding-flash`（1024 维）
- 向量库：Qdrant 本地持久化模式

## 1. 使用项目虚拟环境

本项目可以直接调用虚拟环境中的 Python，不依赖 PowerShell 激活脚本：

```powershell
.\.venv\Scripts\python.exe --version
```

## 2. 配置千问 API

将 `.env.example` 复制为 `.env`：

```powershell
Copy-Item .env.example .env
```

打开 `.env`，将：

```text
DASHSCOPE_API_KEY=sk-your-key-here
```

替换为你的阿里云百炼 API Key。`.env` 已加入 `.gitignore`，不要将密钥提交到 GitHub。

## 3. 运行

首次运行前，先将 `knowledge/` 中的演示政策导入 Qdrant：

```powershell
.\.venv\Scripts\python.exe -m scripts.ingest_knowledge
```

导入会重建本项目的 `support_policies` Collection。如果 Agent 正在运行，请先退出 Agent 再重新导入。

然后启动 Agent：

```powershell
.\.venv\Scripts\python.exe -m app.main
```

也可以启动 FastAPI 后端：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api:app --reload
```

启动后访问：

- Swagger API 测试页面：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/health`
- Agent 对话：`POST /agent/runs`
- 会话历史：`GET /agent/threads/{thread_id}/history`
- 工单：`GET/POST /tickets`
- 发起退款审批：`POST /tickets/{ticket_id}/refund-approval`
- 人工审批：`POST /approvals/{approval_id}/decision`

可以使用模拟订单 `A1001`、`A1002` 或 `A1003` 测试：

```text
订单 A1001 的耳机到货后无法开机，应该怎么处理？
```

## 当前数据流

```text
命令行输入 -> LangGraph -> 聊天模型
                               |-> get_order -> SQLAlchemy -> SQLite
                               |-> search_policy -> Embedding -> Qdrant
                               |-> create_support_ticket -> SQLite（退款自动建审批）
                               |-> await_approval -> interrupt -> 人工决定
                               -> 聊天模型 -> 带政策来源的回答
```

首次运行时会自动创建 `data/app.db` 和三条相对日期的演示订单。重复启动不会重复插入。`knowledge/` 包含 17 篇虚构政策，其中 1 篇已失效，用于验证 RAG 的生效状态过滤。

运行无需 API 的本地工具测试：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

运行一次需要真实 API 的端到端冒烟测试：

```powershell
.\.venv\Scripts\python.exe -m scripts.smoke_test_agent
```

运行订单 + RAG 联合冒烟测试：

```powershell
.\.venv\Scripts\python.exe -m scripts.smoke_test_rag
```

运行不调用模型的人工审批冒烟测试：

```powershell
.\.venv\Scripts\python.exe -m scripts.smoke_test_approval
```

运行需要真实模型的主图审批闭环测试：

```powershell
.\.venv\Scripts\python.exe -m scripts.smoke_test_main_graph_approval
```

审批演示会创建高风险退款工单，在主 LangGraph 的人工节点暂停，再模拟主管审批并从同一个 SQLite thread 检查点恢复。审批通过后的状态是 `approved_pending_execution`，项目不会执行真实退款。

`knowledge/` 中的政策全部是演示数据，不代表真实企业承诺。后续计划见 [ROADMAP.md](ROADMAP.md)。
