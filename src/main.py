"""
SmartAgent - 智能对话助手主程序入口

运行方式：
    交互模式：
        python -m src.main --interactive --user user123
        python -m src.main -i -u user123

    单次查询：
        python -m src.main --user user123 --query "你好"
        python -m src.main -u user123 -q "今天天气怎么样"
"""

import argparse
import os

from .service import SmartAgentService


class SmartAgent:
    """命令行入口适配层"""

    def __init__(self):
        self.service = SmartAgentService()

    def chat(self, user_id: str, query: str) -> str:
        return self.service.process_query(user_id, query).response

    def run_interactive(self, user_id: str):
        print("=" * 50)
        print("  SmartAgent 智能助手")
        print("=" * 50)
        print("输入 'exit' 或 'quit' 退出")
        print("-" * 50)

        while True:
            try:
                query = input("\n 你: ").strip()
                if not query:
                    continue
                if query.lower() in ("exit", "quit"):
                    print(" 再见!")
                    break

                print(" 助手: ", end="", flush=True)
                response = self.chat(user_id, query)
                print(response)

            except KeyboardInterrupt:
                print("\n 再见!")
                break
            except Exception as e:
                print(f"\n 错误: {e}")

    def run_once(self, user_id: str, query: str) -> str:
        return self.chat(user_id, query)


def main():
    parser = argparse.ArgumentParser(description="SmartAgent 智能助手")
    parser.add_argument("--user", "-u", required=True, help="用户 ID")
    parser.add_argument("--query", "-q", default=None, help="单次查询内容")
    parser.add_argument("--interactive", "-i", action="store_true", help="交互模式")
    args = parser.parse_args()

    agent = SmartAgent()

    if args.query:
        response = agent.run_once(args.user, args.query)
        try:
            print(response)
        except UnicodeEncodeError:
            print(response.encode("gbk", errors="replace").decode("gbk"))
    else:
        agent.run_interactive(args.user)


if __name__ == "__main__":
    main()
