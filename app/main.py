import json
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command

from app.checkpointing import close_checkpointer
from app.graph import graph
from app.qdrant_store import close_qdrant_client
from app.seed import prepare_database


def main() -> None:
    inserted_orders = prepare_database()
    if inserted_orders:
        print(f"已初始化 {inserted_orders} 条演示订单。")
    print("售后工单 Agent 已启动。输入 exit 退出。")
    thread_id = f"agent:cli:{uuid4().hex}"
    config = {
        "recursion_limit": 12,
        "configurable": {"thread_id": thread_id},
    }

    while True:
        user_input = input("\n你：").strip()
        if user_input.lower() in {"exit", "quit", "q"}:
            close_qdrant_client()
            print("已退出。")
            return
        if not user_input:
            continue

        try:
            result = graph.invoke(
                {"messages": [HumanMessage(content=user_input)]},
                config=config,
            )
            while result.get("__interrupt__"):
                interrupt_payload = result["__interrupt__"][0].value
                approval = interrupt_payload["approval"]
                print(
                    "\n[等待人工审批] "
                    f"{approval['approval_id']}，"
                    f"退款金额 {approval['amount']} 元"
                )
                decision = ""
                while decision not in {"approve", "reject"}:
                    decision = input(
                        "审批决定（approve/reject）："
                    ).strip().lower()
                reviewer = input("审核人：").strip()
                while not reviewer:
                    reviewer = input("审核人不能为空，请重新输入：").strip()
                comment = input("审批备注（可留空）：").strip()
                result = graph.invoke(
                    Command(
                        resume={
                            "decision": decision,
                            "reviewer": reviewer,
                            "comment": comment,
                        }
                    ),
                    config=config,
                )
        except Exception as exc:
            print(f"\n调用失败：{exc}")
            continue

        for message in result["messages"]:
            if not isinstance(message, AIMessage):
                continue
            for tool_call in message.tool_calls:
                arguments = json.dumps(
                    tool_call["args"],
                    ensure_ascii=False,
                )
                print(
                    f"\n[工具调用] {tool_call['name']} {arguments}"
                )

        print(f"\nAgent：{result['messages'][-1].content}")


if __name__ == "__main__":
    try:
        main()
    finally:
        close_qdrant_client()
        close_checkpointer()

