from typing import Any

from sqlalchemy import func, select

from app.database import session_scope
from app.db_models import Order


def find_order_by_id(order_id: str) -> dict[str, Any] | None:
    normalized_id = order_id.strip().upper()

    with session_scope() as session:
        order = session.scalar(
            select(Order).where(Order.order_id == normalized_id)
        )
        if order is None:
            return None

        return {
            "order_id": order.order_id,
            "customer_name": order.customer_name,
            "product_name": order.product_name,
            "product_category": order.product_category,
            "order_status": order.order_status,
            "shipped_at": (
                order.shipped_at.isoformat() if order.shipped_at else None
            ),
            "delivered_at": (
                order.delivered_at.isoformat() if order.delivered_at else None
            ),
            "amount": float(order.amount),
            "currency": order.currency,
            "refund_status": order.refund_status,
        }


def count_orders() -> int:
    with session_scope() as session:
        return int(session.scalar(select(func.count(Order.id))) or 0)

