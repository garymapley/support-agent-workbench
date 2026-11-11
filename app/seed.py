from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.database import session_scope
from app.db_models import Order


_today = date.today()

SEED_ORDERS = [
    {
        "order_id": "A1001",
        "customer_name": "张三",
        "product_name": "Aurora X1 无线耳机",
        "product_category": "electronics",
        "order_status": "delivered",
        "delivered_at": _today - timedelta(days=2),
        "amount": Decimal("299.00"),
        "currency": "CNY",
        "refund_status": "none",
    },
    {
        "order_id": "A1002",
        "customer_name": "李四",
        "product_name": "Nova Pro 机械键盘",
        "product_category": "electronics",
        "order_status": "shipped",
        "shipped_at": _today - timedelta(days=3),
        "amount": Decimal("459.00"),
        "currency": "CNY",
        "refund_status": "none",
    },
    {
        "order_id": "A1003",
        "customer_name": "王五",
        "product_name": "CloudFit 运动鞋",
        "product_category": "apparel",
        "order_status": "refund_pending",
        "delivered_at": _today - timedelta(days=10),
        "amount": Decimal("529.00"),
        "currency": "CNY",
        "refund_status": "pending_manual_approval",
    },
    {
        "order_id": "A1004",
        "customer_name": "赵六",
        "product_name": "VisionMax 4K 显示器",
        "product_category": "electronics",
        "order_status": "delivered",
        "delivered_at": _today - timedelta(days=4),
        "amount": Decimal("899.00"),
        "currency": "CNY",
        "refund_status": "none",
    },
]


def seed_orders() -> int:
    """幂等导入演示订单，返回本次新增数量。"""

    inserted = 0
    with session_scope() as session:
        existing_ids = set(
            session.scalars(
                select(Order.order_id).where(
                    Order.order_id.in_(
                        order["order_id"] for order in SEED_ORDERS
                    )
                )
            )
        )

        for order_data in SEED_ORDERS:
            if order_data["order_id"] in existing_ids:
                existing = session.scalar(
                    select(Order).where(
                        Order.order_id == order_data["order_id"]
                    )
                )
                if existing is not None:
                    existing.shipped_at = order_data.get("shipped_at")
                    existing.delivered_at = order_data.get("delivered_at")
                continue
            session.add(Order(**order_data))
            inserted += 1

    return inserted


def prepare_database() -> int:
    from app.database import initialize_database

    initialize_database()
    return seed_orders()

