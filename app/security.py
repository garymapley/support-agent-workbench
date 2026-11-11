"""管理接口的访问控制。

演示级实现：单张静态令牌，通过 ``X-Admin-Token`` 请求头传递。
生产环境应替换为登录态或 OIDC，详见 README 的「已知限制」。
"""

import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from app.config import get_settings

admin_token_header = APIKeyHeader(name="X-Admin-Token", auto_error=False)


def require_admin(token: str | None = Depends(admin_token_header)) -> str:
    """校验管理令牌，返回服务端认定的审批人身份。

    未配置令牌时直接拒绝服务，避免"忘记配置就裸奔"。
    """

    settings = get_settings()
    configured = settings.admin_token.strip()
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="服务未配置 ADMIN_TOKEN，管理接口已关闭。",
        )
    if not token or not secrets.compare_digest(token, configured):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少或无效的 X-Admin-Token。",
            headers={"WWW-Authenticate": "X-Admin-Token"},
        )
    return settings.admin_reviewer
