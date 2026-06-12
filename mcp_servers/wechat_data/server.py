"""
WeChat Data MCP Server
提供微信聊天数据的标准化访问接口
"""
import sys
import os

# === 调试日志（最顶部，确保任何导入错误都能被捕获） ===
_log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mcp_startup.log')
try:
    with open(_log_path, 'w', encoding='utf-8') as _f:
        _f.write("=== MCP Server Startup Log ===\n")
        _f.write(f"script: {__file__}\n")
        _f.write(f"cwd: {os.getcwd()}\n")
        _f.write(f"sys.argv: {sys.argv}\n")
        _f.write(f"sys.executable: {sys.executable}\n")
        _f.write(f"PYTHONIOENCODING: {os.environ.get('PYTHONIOENCODING', 'NOT SET')}\n")
        _f.write(f"SystemRoot: {os.environ.get('SystemRoot', 'NOT SET')}\n")
        _f.write(f"PATH exists: {'PATH' in os.environ}\n")
        _f.write(f"VIRTUAL_ENV: {os.environ.get('VIRTUAL_ENV', 'NOT SET')}\n")
        _f.flush()
except Exception as _e:
    pass  # 忽略日志写入失败

import json
import asyncio
import traceback
from typing import Any, Dict
from mcp.server import Server
from mcp.types import Tool, TextContent

# 支持直接运行和模块导入两种方式
if __name__ == "__main__":
    # 直接运行时，添加项目根目录到 sys.path
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from mcp_servers.wechat_data.tools import WeChatTools, TOOLS
else:
    # 模块导入时使用相对导入
    from .tools import WeChatTools, TOOLS


class WeChatDataServer:
    """微信数据 MCP 服务器"""

    def __init__(self, db_path: str = None):
        self.server = Server("wechat-data")
        self.tools = WeChatTools(db_path)
        self._setup_handlers()

    def _setup_handlers(self):
        """设置请求处理器"""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """列出所有可用工具"""
            return [
                Tool(
                    name=tool["name"],
                    description=tool["description"],
                    inputSchema=tool["inputSchema"]
                )
                for tool in TOOLS
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> list[TextContent]:
            """调用工具"""
            # 根据工具名称调用对应的方法
            tool_methods = {
                "search_messages": self.tools.search_messages,
                "get_contact_messages": self.tools.get_contact_messages,
                "get_group_messages": self.tools.get_group_messages,
                "search_by_time_range": self.tools.search_by_time_range,
                "get_contact_info": self.tools.get_contact_info,
                "get_all_groups": self.tools.get_all_groups,
                "sync_messages": self.tools.sync_messages,
                "get_sync_status": self.tools.get_sync_status
            }

            if name not in tool_methods:
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": f"未知工具: {name}"}, ensure_ascii=False)
                )]

            try:
                result = tool_methods[name](arguments)
                return [TextContent(
                    type="text",
                    text=json.dumps(result, ensure_ascii=False, indent=2)
                )]
            except Exception as e:
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": str(e)}, ensure_ascii=False)
                )]

    async def run(self):
        """运行服务器"""
        from mcp.server.stdio import stdio_server

        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


def main():
    """主入口"""
    import argparse
    import traceback

    # 调试日志：记录启动信息到文件
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mcp_startup.log')
    try:
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(f"=== MCP Server Startup Log ===\n")
            f.write(f"cwd: {os.getcwd()}\n")
            f.write(f"sys.argv: {sys.argv}\n")
            f.write(f"sys.path[0]: {sys.path[0] if sys.path else 'EMPTY'}\n")
            f.write(f"PYTHONIOENCODING: {os.environ.get('PYTHONIOENCODING', 'NOT SET')}\n")
            f.write(f"SystemRoot: {os.environ.get('SystemRoot', 'NOT SET')}\n")
            f.write(f"PATH exists: {'PATH' in os.environ}\n")
    except Exception as e:
        pass  # 忽略日志写入失败

    parser = argparse.ArgumentParser(description="WeChat Data MCP Server")
    parser.add_argument(
        "--db-path",
        type=str,
        help="数据库路径（默认: output/wechat_index.db）"
    )
    args = parser.parse_args()

    try:
        server = WeChatDataServer(args.db_path)
        asyncio.run(server.run())
    except Exception as e:
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"\n!!! ERROR: {e}\n")
            f.write(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
