# 企业售后工单 Agent

当前里程碑：使用 LangGraph 调用百炼聊天模型，通过 SQLAlchemy 查询 SQLite 订单，并使用 Qdrant + Embedding 检索企业售后政策。

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

`knowledge/` 中的政策全部是演示数据，不代表真实企业承诺。后续计划见 [ROADMAP.md](ROADMAP.md)。
