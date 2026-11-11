from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        index=True,
        nullable=False,
    )
    customer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    product_category: Mapped[str] = mapped_column(String(50), nullable=False)
    order_status: Mapped[str] = mapped_column(String(50), nullable=False)
    shipped_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivered_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="CNY")
    refund_status: Mapped[str] = mapped_column(String(50), default="none")
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, nullable=False
    )
    order_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    issue_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_action: Mapped[str] = mapped_column(String(50), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="open")
    handoff_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    thread_id: Mapped[str | None] = mapped_column(
        String(160), index=True, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    approval_id: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, nullable=False
    )
    ticket_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("support_tickets.ticket_id"),
        index=True,
        nullable=False,
    )
    order_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    thread_id: Mapped[str | None] = mapped_column(
        String(160), index=True, nullable=True
    )
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    reviewer: Mapped[str | None] = mapped_column(String(100), nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AgentRunRecord(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(40), unique=True, index=True, nullable=False
    )
    thread_id: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    run_type: Mapped[str] = mapped_column(String(40), nullable=False)
    run_scope: Mapped[str] = mapped_column(
        String(20), index=True, default="runtime", nullable=False
    )
    status: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    user_input: Mapped[str] = mapped_column(Text, default="")
    answer: Mapped[str] = mapped_column(Text, default="")
    tools_json: Mapped[str] = mapped_column(Text, default="[]")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0)
    estimated_cost_cny: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True
    )

