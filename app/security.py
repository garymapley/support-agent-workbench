"""静态令牌角色控制，适用于单实例演示部署。"""

import secrets
from typing import Literal

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from app.config import get_settings

Role = Literal["operator", "admin"]

access_token_header = APIKeyHeader(name="X-Admin-Token", auto_error=False)


def _authenticate(token: str | None) -> Role:
    settings = get_settings()
    admin_token = settings.admin_token.strip()
    operator_token = settings.operator_token.strip()
    if not admin_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="服务未配置 ADMIN_TOKEN，管理接口已关闭。",
        )
    if token and secrets.compare_digest(token, admin_token):
        return "admin"
    if operator_token and token and secrets.compare_digest(token, operator_token):
        return "operator"
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="缺少或无效的 X-Admin-Token。",
        headers={"WWW-Authenticate": "X-Admin-Token"},
    )


def require_operator(
    token: str | None = Depends(access_token_header),
) -> Role:
    """允许操作员或管理员访问日常工单功能。"""

    return _authenticate(token)


def require_reviewer(
    token: str | None = Depends(access_token_header),
) -> str:
    """仅允许管理员执行退款审批，并返回服务端审批人身份。"""

    role = _authenticate(token)
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前令牌没有退款审批权限。",
        )
    return get_settings().admin_reviewer


# 保留旧导入名，避免外部演示脚本立即失效。
require_admin = require_reviewer
