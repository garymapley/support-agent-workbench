import json

from langchain_core.tools import tool

from app.order_repository import find_order_by_id


@tool
def get_order(order_id: str) -> str:
    """根据订单号查询订单的商品、金额、物流与退款状态。

    Args:
        order_id: 客户提供的完整订单号，例如 A1001。
    """

    normalized_id = order_id.strip().upper()
    order = find_order_by_id(normalized_id)
    if order is None:
        return json.dumps(
            {
                "found": False,
                "order_id": normalized_id,
                "message": "未找到该订单，请核对订单号或转交人工客服。",
            },
            ensure_ascii=False,
        )

    return json.dumps(
        {"found": True, "order": order},
        ensure_ascii=False,
    )


ORDER_TOOLS = [get_order]

