# Support Agent Workbench

<p align="center">
  <strong>A locally reproducible, production-oriented reference implementation of an enterprise support agent.</strong>
</p>

<p align="center">
  LangGraph · RAG · Human-in-the-loop · FastAPI · Next.js · Qdrant · Docker
</p>

<p align="center">
  <img alt="Python 3.12" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white">
  <img alt="LangGraph" src="https://img.shields.io/badge/Agent-LangGraph-1C3C3C">
  <img alt="FastAPI" src="https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white">
  <img alt="Next.js 16" src="https://img.shields.io/badge/Web-Next.js%2016-000000?logo=next.js&logoColor=white">
  <img alt="Docker Compose" src="https://img.shields.io/badge/Deploy-Docker%20Compose-2496ED?logo=docker&logoColor=white">
  <img alt="MIT License" src="https://img.shields.io/badge/License-MIT-green">
</p>

Support Agent Workbench demonstrates how to turn an LLM-powered chatbot into a complete agent workflow with business tools, grounded policy answers, human approval, authorization boundaries, persistent state, and auditable execution.

This repository is a local reference implementation, not a production refund system or a hosted demo. All orders, policies, and evaluation data are fictional and can be reproduced locally with Docker.

## Why This Project

A basic agent demo often looks like this:

```text
User input → Model call → Answer
```

This project models a workflow closer to a real enterprise support operation:

```text
Customer request
  → Authentication and authorization
  → Agent calls order and policy tools
  → Support ticket is created
  → High-risk refund requires human approval
  → Conversation state is paused and persisted
  → The same conversation resumes after a decision
  → Agent returns a grounded, auditable outcome
```

The goal is not to give the model more authority. It is to place explicit business rules, security boundaries, and human accountability around the model.

## Key Capabilities

- **Business tool use** — Look up orders, retrieve policies, create tickets, check approval status, and escalate cases to a human.
- **Policy-grounded RAG** — Retrieve fictional policy documents with Qwen Embeddings and Qdrant, including source and version references in answers.
- **Human-in-the-loop approval** — Pause high-risk refund workflows with LangGraph `interrupt()` and resume the same `thread_id` after review.
- **Code-enforced risk controls** — Refund tickets must create an approval request through business rules; the model cannot bypass approval through prompting alone.
- **Role-based workbench** — Operators handle support cases, while approval administrators can approve or reject refunds.
- **Persistent state and auditability** — Store orders, tickets, approvals, and LangGraph checkpoints in SQLite, with structured JSON execution logs.
- **Reliability safeguards** — Apply timeouts and bounded retries to external reads, avoid automatic retries for writes, and provide rate limiting and failure protection.
- **Reproducible deployment** — Run FastAPI, Next.js, Qdrant, and knowledge initialization through Docker Compose.

## Quick Start

### Prerequisites

- Docker Desktop, or Docker Engine with Docker Compose
- An Alibaba Cloud Model Studio (DashScope) API key

### 1. Create the environment file

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

macOS / Linux:

```bash
cp .env.example .env
```

Edit `.env` and replace at least the following values:

```dotenv
DASHSCOPE_API_KEY=your-dashscope-api-key
ADMIN_TOKEN=your-random-admin-token
OPERATOR_TOKEN=your-random-operator-token
WORKBENCH_ADMIN_PASSWORD=your-strong-admin-password
WORKBENCH_OPERATOR_PASSWORD=your-strong-operator-password
WORKBENCH_SESSION_SECRET=at-least-32-random-characters
```

The real `.env` file is ignored by Git. Never commit credentials to the repository.

### 2. Start the services

```bash
docker compose build
docker compose up -d
```

On the first run, ingest the demo policy documents:

```bash
docker compose --profile tools run --rm knowledge-init
```

Check the service status:

```bash
docker compose ps
```

### 3. Open the application

- Workbench: <http://localhost:3000>
- FastAPI documentation: <http://127.0.0.1:8000/docs>
- Health check: <http://127.0.0.1:8000/health>

The default usernames are `operator` and `admin`. Their passwords are the values configured in `.env`. Demo order IDs include `A1001`, `A1002`, and `A1003`.

## Human Approval Flow

The agent never executes a refund autonomously. When a customer explicitly requests a refund, the system creates a support ticket and an approval record, then pauses the active conversation inside the primary LangGraph workflow.

After an approval administrator makes a decision, FastAPI resumes the original conversation using the same `thread_id`. The agent then explains the next step based on the human decision. Even an approved request only reaches `approved_pending_execution`; this project never performs a real financial transaction.

![Human approval flow for refund requests](docs/images/human-approval-flow.png)

## Architecture

![Support Agent Workbench architecture](docs/images/architecture.png)

- **Next.js workbench** — Login, ticket queue, conversation trace, approval, and human takeover interfaces.
- **FastAPI** — APIs, role-based authorization, rate limiting, failure protection, and observability endpoints.
- **LangGraph** — Model and tool orchestration, conversation state, and human-approval pause/resume behavior.
- **SQLite** — Fictional orders, tickets, approval records, and LangGraph checkpoints.
- **Qdrant** — Policy vectors with payload filtering for inactive documents.
- **Alibaba Cloud Model Studio** — `deepseek-v4.1-flash` for chat and `qwen3.7-text-embedding-flash` for embeddings.

## Roles and Security Boundaries

| Capability | Operator | Approval administrator |
|---|:---:|:---:|
| View orders and tickets | ✅ | ✅ |
| Run the agent | ✅ | ✅ |
| Create tickets and escalate to a human | ✅ | ✅ |
| View refund approvals | ✅ | ✅ |
| Approve or reject refunds | ❌ | ✅ |

Security decisions include:

- The browser talks only to a same-origin Next.js proxy and never receives FastAPI role tokens.
- Signed HttpOnly cookies hold authenticated sessions.
- The backend injects the approver identity; clients cannot forge it in the request body.
- Code-level rules force high-risk refunds into approval instead of trusting the model to call the correct tool.
- FastAPI binds only to the host loopback interface, and Qdrant does not expose a host port.
- Containers use non-root users, read-only root filesystems, dropped capabilities, and resource limits.

## Tech Stack

| Layer | Technology |
|---|---|
| Agent orchestration | LangGraph |
| Chat model | `deepseek-v4.1-flash` |
| Embeddings | `qwen3.7-text-embedding-flash` |
| RAG / vector database | Qdrant |
| Business data and checkpoints | SQLite · SQLAlchemy |
| Backend API | FastAPI |
| Web workbench | Next.js 16 · React 19 |
| Evaluation and logging | Fixed JSONL cases · Redacted JSON logs |
| Deployment | Docker Compose |

## Known Limitations

- The project runs locally and does not provide a persistent hosted demo.
- Accounts and passwords come from environment variables and are suitable only for a demo. A production deployment should use OIDC, MFA, and per-user audit trails.
- SQLite and in-process rate limiting support only a single API replica. Horizontal scaling would require PostgreSQL, shared checkpoints, and Redis or gateway-level rate limiting.
- Approval does not mean a refund has been executed. The project does not connect to a payment or refund provider.
- All knowledge-base documents, orders, policies, and evaluation data are fictional and do not represent a real company's commitments.
- Fixed evaluation results support regression testing and engineering demonstration; they are not a production SLA.

See [Deployment Notes](docs/DEPLOYMENT.md) for additional deployment boundaries.

## License

Licensed under the [MIT License](LICENSE).
