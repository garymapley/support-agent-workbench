# 企业售后工单 Agent

当前里程碑：Agent 已具备订单查询、政策 RAG、人工审批闭环、FastAPI、固定评测集、结构化日志和 Next.js 工单工作台。

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
- 转人工：`POST /tickets/{ticket_id}/handoff`
- 发起退款审批：`POST /tickets/{ticket_id}/refund-approval`
- 人工审批：`POST /approvals/{approval_id}/decision`
- 最近运行记录：`GET /observability/runs`
- 指标汇总：`GET /observability/summary`

### 管理接口鉴权

除 `GET /health` 外，所有接口都要求请求头带 `X-Admin-Token`，值需与 `.env` 中的 `ADMIN_TOKEN` 一致。`ADMIN_TOKEN` 留空时管理接口一律返回 `503`，避免忘记配置就裸奔。

在 Swagger 页面测试时，先点右上角 `Authorize`，填入 `ADMIN_TOKEN` 的值，再执行接口；直接用 `curl` 或 PowerShell 调用时必须手动加上该请求头：

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/tickets?limit=5" -Headers @{ "X-Admin-Token" = "demo-admin-token-2026" }
```

审批人身份由服务端从 `ADMIN_REVIEWER` 注入，请求体里自报的 `reviewer` 会被覆盖，因此无法伪造审批记录。

可以使用模拟订单 `A1001`、`A1002` 或 `A1003` 测试：

```text
订单 A1001 的耳机到货后无法开机，应该怎么处理？
```

### 启动 Next.js 工单工作台

保持 FastAPI 在 `8000` 端口运行，再打开第二个 PowerShell：

```powershell
cd web
Copy-Item .env.local.example .env.local
npm install
npm run dev
```

访问 `http://localhost:3000`。`http://127.0.0.1:3000` 同样可用——`web/next.config.ts` 已通过 `allowedDevOrigins` 把该来源加入白名单，否则 Next.js 16 会把 dev 资源请求判为跨源而返回 403，页面会停在骨架屏。工作台包含：

- 工单队列、搜索、状态筛选与订单摘要
- Agent 多轮对话、工具调用和工具结果轨迹
- 退款人工审批，审批后恢复同一条 LangGraph 对话
- 人工接管、运行次数、成功率、延迟与待审批数

`NEXT_PUBLIC_API_BASE_URL` 可在 `web/.env.local` 中指向其他 FastAPI 地址。后端的 `CORS_ORIGINS` 用于限制可访问来源。

## 当前数据流

```text
命令行输入 -> LangGraph -> 聊天模型
                               |-> get_order -> SQLAlchemy -> SQLite
                               |-> search_policy -> Embedding -> Qdrant
                               |-> create_support_ticket -> SQLite（退款自动建审批）
                               |-> await_approval -> interrupt -> 人工决定
                               -> 聊天模型 -> 带政策来源的回答
```

首次运行时会自动创建 `data/app.db` 和四条相对日期的演示订单。重复启动不会重复插入。`knowledge/` 包含 17 篇虚构政策，其中 1 篇已失效，用于验证 RAG 的生效状态过滤。

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

运行固定评测集：

```powershell
.\.venv\Scripts\python.exe -m scripts.run_evaluation
```

评测会生成：

- `reports/eval_report.json`：机器可读明细
- `reports/eval_report.md`：面试展示报告

当前评测包含 13 个真实 Agent 场景、6 个风险边界检查和 1 个故障注入检查。基准结果为工具正确率 100%、策略合规率 100%、风险分级准确率 100%、失败保护通过率 100%，平均延迟约 5.31 秒，总计约 6.6 万 Token，按百炼 2026-11-11 忙时官方单价估算总成本约 ¥0.175。评测使用独立临时数据库，不计入业务指标。每次运行会记录工具、Token、延迟和状态，并在 `logs/agent.jsonl` 输出脱敏 JSON 日志。

审批演示会创建高风险退款工单，在主 LangGraph 的人工节点暂停，再模拟主管审批并从同一个 SQLite thread 检查点恢复。审批通过后的状态是 `approved_pending_execution`，项目不会执行真实退款。

`knowledge/` 中的政策全部是演示数据，不代表真实企业承诺。后续计划见 [ROADMAP.md](ROADMAP.md)。

## 已知限制

- **鉴权是演示级**：`ADMIN_TOKEN` 通过 `NEXT_PUBLIC_ADMIN_TOKEN` 一并下发到前端，任何打开工作台的人都能在浏览器里读到它。它挡的是"不知情的外部调用"，不是"有心的内部人员"。生产环境应改为登录态或 OIDC，令牌不下发前端。
- **不执行真实退款**：审批通过后的终态是 `approved_pending_execution`，退款由外部系统执行，项目不承担资金操作。
- **单实例假设**：业务库和 LangGraph 检查点都用本地 SQLite，加上进程内线程锁，不支持多副本水平扩展。
- **CLI 与脚本不写运行指标**：`logs/agent.jsonl` 与 `observability` 汇总只覆盖 FastAPI 入口，`app/main.py` 和 `scripts/` 下的冒烟与评测脚本不会产生运行记录。
- **评测的检索判定偏松**：`scripts/run_evaluation.py` 只检查来源文件名是否出现在回答中，不做 top-1 命中校验，因此策略合规率 100% 的可信度需结合手工检索实测一起看。
