from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import desc, select

from app.database import session_scope
from app.db_models import ApprovalRequest, SupportTicket
from app.order_repository import find_order_by_id


def assess_risk(order: dict[str, Any], proposed_action: str) -> str:
    """根据订单与建议动作给出可解释的基础风险等级。"""

    action = proposed_action.strip().lower()
    if action == "refund":
        amount = float(order.get("amount", 0))
        refund_status = str(order.get("refund_status", "none"))
        if amount >= 500 or refund_status != "none":
            return "high"
        return "medium"
    if action in {"replace", "repair"}:
        return "medium"
    return "low"


def _ticket_to_dict(ticket: SupportTicket) -> dict[str, Any]:
    return {
        "ticket_id": ticket.ticket_id,
        "order_id": ticket.order_id,
        "issue_type": ticket.issue_type,
        "description": ticket.description,
        "proposed_action": ticket.proposed_action,
        "risk_level": ticket.risk_level,
        "status": ticket.status,
        "handoff_reason": ticket.handoff_reason,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
    }


def _approval_to_dict(approval: ApprovalRequest) -> dict[str, Any]:
    return {
        "approval_id": approval.approval_id,
        "ticket_id": approval.ticket_id,
        "order_id": approval.order_id,
        "thread_id": approval.thread_id,
        "action_type": approval.action_type,
        "amount": float(approval.amount),
        "reason": approval.reason,
        "status": approval.status,
        "reviewer": approval.reviewer,
        "review_comment": approval.review_comment,
        "reviewed_at": (
            approval.reviewed_at.isoformat() if approval.reviewed_at else None
        ),
        "requested_at": (
            approval.requested_at.isoformat() if approval.requested_at else None
        ),
    }


def create_support_ticket(
    order_id: str,
    issue_type: str,
    description: str,
    proposed_action: str,
    thread_id: str | None = None,
) -> dict[str, Any]:
    order = find_order_by_id(order_id)
    if order is None:
        raise ValueError(f"订单 {order_id.strip().upper()} 不存在")

    ticket_id = f"TKT-{uuid4().hex[:8].upper()}"
    normalized_action = proposed_action.strip().lower()
    ticket = SupportTicket(
        ticket_id=ticket_id,
        order_id=order["order_id"],
        issue_type=issue_type.strip().lower(),
        description=description.strip(),
        proposed_action=normalized_action,
        risk_level=assess_risk(order, proposed_action),
        status="open",
    )
    with session_scope() as session:
        session.add(ticket)
        session.flush()
        result = _ticket_to_dict(ticket)
        if normalized_action == "refund":
            if not thread_id:
                raise ValueError("退款工单必须关联 Agent thread_id")
            approval = ApprovalRequest(
                approval_id=f"APR-{uuid4().hex[:8].upper()}",
                ticket_id=ticket_id,
                order_id=order["order_id"],
                thread_id=thread_id,
                action_type="refund",
                amount=order["amount"],
                reason="退款工单由代码规则强制进入人工审批。",
                status="pending",
            )
            ticket.status = "pending_approval"
            session.add(approval)
            session.flush()
            result = _ticket_to_dict(ticket)
            result["approval"] = _approval_to_dict(approval)
        return result


def get_ticket(ticket_id: str) -> dict[str, Any] | None:
    with session_scope() as session:
        ticket = session.scalar(
            select(SupportTicket).where(
                SupportTicket.ticket_id == ticket_id.strip().upper()
            )
        )
        return _ticket_to_dict(ticket) if ticket else None


def list_tickets(
    limit: int = 50,
    status: str | None = None,
) -> list[dict[str, Any]]:
    with session_scope() as session:
        query = select(SupportTicket)
        if status:
            query = query.where(SupportTicket.status == status.strip().lower())
        query = query.order_by(desc(SupportTicket.created_at)).limit(limit)
        return [_ticket_to_dict(ticket) for ticket in session.scalars(query)]


def create_refund_approval(
    ticket_id: str,
    reason: str,
    thread_id: str,
) -> dict[str, Any]:
    normalized_id = ticket_id.strip().upper()
    with session_scope() as session:
        ticket = session.scalar(
            select(SupportTicket).where(
                SupportTicket.ticket_id == normalized_id
            )
        )
        if ticket is None:
            raise ValueError(f"工单 {normalized_id} 不存在")
        if ticket.proposed_action != "refund":
            raise ValueError("只有建议动作为 refund 的工单可以申请退款审批")

        existing = session.scalar(
            select(ApprovalRequest).where(
                ApprovalRequest.ticket_id == normalized_id,
                ApprovalRequest.status == "pending",
            )
        )
        if existing:
            if existing.thread_id and existing.thread_id != thread_id:
                raise ValueError("该工单的待审批已关联到另一段 Agent 对话")
            if not existing.thread_id:
                existing.thread_id = thread_id
                session.flush()
            return _approval_to_dict(existing)

        order = find_order_by_id(ticket.order_id)
        if order is None:
            raise ValueError(f"订单 {ticket.order_id} 不存在")

        approval = ApprovalRequest(
            approval_id=f"APR-{uuid4().hex[:8].upper()}",
            ticket_id=ticket.ticket_id,
            order_id=ticket.order_id,
            thread_id=thread_id,
            action_type="refund",
            amount=order["amount"],
            reason=reason.strip(),
            status="pending",
        )
        ticket.status = "pending_approval"
        session.add(approval)
        session.flush()
        return _approval_to_dict(approval)


def get_approval(approval_id: str) -> dict[str, Any] | None:
    with session_scope() as session:
        approval = session.scalar(
            select(ApprovalRequest).where(
                ApprovalRequest.approval_id == approval_id.strip().upper()
            )
        )
        return _approval_to_dict(approval) if approval else None


def get_latest_approval_for_ticket(
    ticket_id: str,
) -> dict[str, Any] | None:
    with session_scope() as session:
        approval = session.scalar(
            select(ApprovalRequest)
            .where(
                ApprovalRequest.ticket_id == ticket_id.strip().upper()
            )
            .order_by(desc(ApprovalRequest.requested_at))
            .limit(1)
        )
        return _approval_to_dict(approval) if approval else None


def list_approvals(
    limit: int = 50,
    status: str | None = None,
) -> list[dict[str, Any]]:
    with session_scope() as session:
        query = select(ApprovalRequest)
        if status:
            query = query.where(ApprovalRequest.status == status.strip().lower())
        query = query.order_by(desc(ApprovalRequest.requested_at)).limit(limit)
        return [_approval_to_dict(item) for item in session.scalars(query)]


def apply_approval_decision(
    approval_id: str,
    decision: str,
    reviewer: str,
    comment: str = "",
) -> dict[str, Any]:
    normalized_decision = decision.strip().lower()
    if normalized_decision not in {"approve", "reject"}:
        raise ValueError("decision 只能是 approve 或 reject")

    with session_scope() as session:
        approval = session.scalar(
            select(ApprovalRequest).where(
                ApprovalRequest.approval_id == approval_id.strip().upper()
            )
        )
        if approval is None:
            raise ValueError(f"审批 {approval_id} 不存在")
        if approval.status != "pending":
            return _approval_to_dict(approval)

        ticket = session.scalar(
            select(SupportTicket).where(
                SupportTicket.ticket_id == approval.ticket_id
            )
        )
        if ticket is None:
            raise ValueError(f"关联工单 {approval.ticket_id} 不存在")

        approval.status = "approved" if normalized_decision == "approve" else "rejected"
        approval.reviewer = reviewer.strip()
        approval.review_comment = comment.strip() or None
        approval.reviewed_at = datetime.now()
        ticket.status = (
            "approved_pending_execution"
            if normalized_decision == "approve"
            else "approval_rejected"
        )
        session.flush()
        return _approval_to_dict(approval)


def escalate_ticket(ticket_id: str, reason: str) -> dict[str, Any]:
    normalized_id = ticket_id.strip().upper()
    with session_scope() as session:
        ticket = session.scalar(
            select(SupportTicket).where(
                SupportTicket.ticket_id == normalized_id
            )
        )
        if ticket is None:
            raise ValueError(f"工单 {normalized_id} 不存在")
        ticket.status = "human_handoff"
        ticket.handoff_reason = reason.strip()
        session.flush()
        return _ticket_to_dict(ticket)
