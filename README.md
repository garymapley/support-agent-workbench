# 企业售后工单 Agent

当前里程碑：Agent 已具备订单查询、政策 RAG、工单创建、风险判断和可暂停/恢复的人工退款审批。

主 Agent 对话和退款审批共用 SQLite checkpointer，并通过不同 `thread_id` 隔离。创建退款审批时会立即启动审批线程并暂停等待人工处理。模型、Embedding 和远程 Qdrant 查询均配置了超时与有限重试；创建工单、创建审批等写操作不会自动重试。

默认模型：

- 聊天：`deepseek-v4.1-flash`
- Embedding：`qwen3.7-text-embedding-flash`（1024 维）
- 向量库：Qdrant 本地持久化模式

## 1. 激活虚拟环境

```powershell
.\.venv\Scripts\Activate.ps1
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
python -m scripts.ingest_knowledge
```

导入会重建本项目的 `support_policies` Collection。如果 Agent 正在运行，请先退出 Agent 再重新导入。

然后启动 Agent：

```powershell
python -m app.main
```

可以使用模拟订单 `A1001`、`A1002` 或 `A1003` 测试：

```text
订单 A1001 的耳机到货后无法开机，应该怎么处理？
```

## 当前数据流

```text
命令行输入 -> LangGraph -> 聊天模型
                               |-> get_order -> SQLAlchemy -> SQLite
                               |-> search_policy -> Embedding -> Qdrant
                               |-> create_support_ticket -> SQLite
                               |-> request_refund_approval -> 人工暂停/恢复
                               -> 聊天模型 -> 带政策来源的回答
```

首次运行时会自动创建 `data/app.db` 和三条演示订单。重复启动不会重复插入。

运行无需 API 的本地工具测试：

```powershell
python -m unittest discover -s tests -v
```

运行一次需要真实 API 的端到端冒烟测试：

```powershell
python -m scripts.smoke_test_agent
```

运行订单 + RAG 联合冒烟测试：

```powershell
python -m scripts.smoke_test_rag
```

运行不调用模型的人工审批冒烟测试：

```powershell
python -m scripts.smoke_test_approval
```

审批演示会创建高风险退款工单，在 LangGraph 的人工节点暂停，再模拟主管审批并从 SQLite 检查点恢复。审批通过后的状态是 `approved_pending_execution`，项目不会执行真实退款。

`knowledge/` 中的政策全部是演示数据，不代表真实企业承诺。后续计划见 [ROADMAP.md](ROADMAP.md)。
