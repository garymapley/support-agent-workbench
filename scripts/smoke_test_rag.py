import sys

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.graph import graph
from app.qdrant_store import close_qdrant_client
from app.seed import prepare_database


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    prepare_database()
    try:
        result = graph.invoke(
            {
                "messages": [
                    HumanMessage(
                        content=(
                            "订单 A1001 的耳机到货后无法开机，"
                            "请结合订单和公司政策给出处理建议，并标注政策来源。"
                        )
                    )
                ]
            },
            config={"recursion_limit": 10},
        )
    finally:
        close_qdrant_client()

    called_tools: list[str] = []
    tool_results = 0
    for message in result["messages"]:
        if isinstance(message, AIMessage):
            called_tools.extend(call["name"] for call in message.tool_calls)
        elif isinstance(message, ToolMessage):
            tool_results += 1

    print(f"CALLED_TOOLS={called_tools}")
    print(f"TOOL_RESULTS={tool_results}")
    print("FINAL_ANSWER_START")
    print(result["messages"][-1].content)
    print("FINAL_ANSWER_END")


if __name__ == "__main__":
    main()
