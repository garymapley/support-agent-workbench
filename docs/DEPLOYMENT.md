# 部署说明

## 部署边界

当前 Compose 适合单台 Linux 云主机或本机 Demo：Next.js、FastAPI、Qdrant 和 SQLite 都运行在同一台机器。Web 是唯一需要公开的应用端口；FastAPI 只绑定宿主机 `127.0.0.1:8000`，Qdrant 完全不暴露宿主机端口。

由于业务库和 LangGraph 检查点使用 SQLite，本项目只支持一个 API 副本。不要直接扩容多个 `api` 容器；需要水平扩展时应先迁移到 PostgreSQL，并更换支持多副本的检查点存储。

## 云主机步骤

1. 安装 Docker Engine 与 Compose 插件，克隆仓库。
2. 从 `.env.example` 创建 `.env`，配置真实 `DASHSCOPE_API_KEY`，并为 `ADMIN_TOKEN`、`OPERATOR_TOKEN`、两组工作台密码和 `WORKBENCH_SESSION_SECRET` 生成互不相同的随机值。
3. 运行 `docker compose build` 与 `docker compose up -d`。
4. 首次部署运行 `docker compose --profile tools run --rm knowledge-init`。
5. 用 `docker compose ps` 确认 `web`、`api`、`qdrant` 都是 `healthy`。
6. 只在云防火墙开放 `80/443`，不要开放 `6333/6334`；通过 Caddy、Nginx 或云负载均衡把域名反向代理到 `127.0.0.1:3000`。

## 密钥与备份

- `.env` 不进入镜像且已被 Git 忽略。云端优先使用平台 Secret Manager 注入同名环境变量。
- 不要把 `ADMIN_TOKEN` 改成 `NEXT_PUBLIC_*` 变量；带该前缀的值会进入浏览器包。
- 公网 HTTPS 部署必须设置 `WORKBENCH_COOKIE_SECURE=true`，使登录 Cookie 只通过加密连接发送。
- 备份前短暂停止 API，备份 `api_data` 和 `qdrant_data` 两个卷；恢复时使用相同或兼容版本的 Qdrant。
- 正式多用户服务应把环境变量账号替换为 OIDC/企业登录态；后端角色令牌仍只保留在服务端。

## 发布检查

```powershell
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
```

验收标准：未登录访问工作台会跳转 `/login`，匿名代理请求返回 `401`，操作员能读取工单但审批返回 `403`，审批管理员能进入审批接口，快速超过 Agent 配额时返回 `429`；三个服务均为 `healthy`。
