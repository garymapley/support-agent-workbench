"""对 Agent -> Tool -> Agent 链路进行一次真实冒烟测试。"""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.graph import graph
from app.qdrant_store import close_qdrant_client
from app.seed import prepare_database


def main() -> None:
    prepare_database()
    result = graph.invoke(
        {
            "messages": [
                HumanMessage(
                    content="请查询订单 A1001。客户反馈耳机到货后无法开机，该怎么处理？"
                )
            ]
        },
        config={"recursion_limit": 8},
    )

    called_tools: list[str] = []
    tool_results = 0
    for message in result["messages"]:
        if isinstance(message, AIMessage):
            called_tools.extend(
                call["name"] for call in message.tool_calls
            )
        elif isinstance(message, ToolMessage):
            tool_results += 1

    print(f"CALLED_TOOLS={called_tools}")
    print(f"TOOL_RESULTS={tool_results}")
    print("FINAL_ANSWER_START")
    print(result["messages"][-1].content)
    print("FINAL_ANSWER_END")


if __name__ == "__main__":
    try:
        main()
    finally:
        close_qdrant_client()
