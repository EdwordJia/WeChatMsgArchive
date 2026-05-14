#!/usr/bin/env python
"""WeChat Data MCP Server Launcher"""
import sys
import os

# 切换到项目目录
project_dir = r"D:\develoment_home\project_home\WeChatMsgArchive"
os.chdir(project_dir)

# 添加项目目录到 Python 路径
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

# 设置数据库路径
db_path = os.path.join(project_dir, "output", "wechat_index.db")

# 启动服务器
from mcp_servers.wechat_data.server import main
sys.argv = ["server", "--db-path", db_path]
main()
