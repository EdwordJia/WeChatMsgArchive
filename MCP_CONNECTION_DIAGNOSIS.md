# WeChat Data MCP 连接诊断报告

生成时间: 2026-04-30

## 测试结果

### ✅ MCP 服务器功能正常

通过独立测试脚本验证：
- 服务器能够正常启动
- stdio 通信正常
- 能够正确响应 initialize 请求
- 返回有效的 JSON-RPC 2.0 响应

**测试响应**：
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {
      "experimental": {},
      "tools": {
        "listChanged": false
      }
    },
    "serverInfo": {
      "name": "wechat-data",
      "version": "1.27.0"
    }
  }
}
```

### ✅ MCP 配置正确

配置文件 `~/.claude/mcp.json` 中的 wechat-data 配置：
```json
{
  "command": "D:/develoment_home/project_home/WeChatMsgArchive/venv/Scripts/python.exe",
  "args": [
    "-m",
    "mcp_servers.wechat_data.server",
    "--db-path",
    "D:/develoment_home/project_home/WeChatMsgArchive/output/wechat_index.db"
  ],
  "cwd": "D:/develoment_home/project_home/WeChatMsgArchive"
}
```

## 问题分析

### 根本原因

MCP 服务器本身工作正常，问题出在 **Claude Code 的 MCP 客户端连接机制**：

1. **进程管理问题**：Claude Code 可能在启动 MCP 服务器后没有正确管理进程生命周期
2. **缓存问题**：Claude Code 可能缓存了旧的连接状态
3. **超时设置**：Claude Code 的连接超时可能过短
4. **环境隔离**：Claude Code 启动的进程环境可能与手动测试不同

### 证据

- ✅ 手动测试：`python -m mcp_servers.wechat_data.server` 正常工作
- ✅ 独立脚本测试：能够成功连接并收到响应
- ❌ Claude Code 报告：`Failed to reconnect to wechat-data`

## 解决方案

### 方案 1: 完全重启 Claude Code（推荐）

```bash
# 1. 完全退出 Claude Code（包括所有后台进程）
# 2. 清理缓存（可选）
rm -rf ~/.claude/cache
# 3. 重新启动 Claude Code
```

### 方案 2: 使用环境变量

修改 MCP 配置，添加环境变量：
```json
"wechat-data": {
  "command": "D:/develoment_home/project_home/WeChatMsgArchive/venv/Scripts/python.exe",
  "args": [
    "-m",
    "mcp_servers.wechat_data.server",
    "--db-path",
    "D:/develoment_home/project_home/WeChatMsgArchive/output/wechat_index.db"
  ],
  "cwd": "D:/develoment_home/project_home/WeChatMsgArchive",
  "env": {
    "PYTHONIOENCODING": "utf-8",
    "PYTHONUNBUFFERED": "1"
  }
}
```

### 方案 3: 使用启动脚本

创建 `start_mcp.bat`：
```batch
@echo off
cd /d D:\develoment_home\project_home\WeChatMsgArchive
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
D:\develoment_home\project_home\WeChatMsgArchive\venv\Scripts\python.exe -m mcp_servers.wechat_data.server --db-path "D:\develoment_home\project_home\WeChatMsgArchive\output\wechat_index.db"
```

然后修改配置：
```json
"wechat-data": {
  "command": "D:/develoment_home/project_home/WeChatMsgArchive/start_mcp.bat"
}
```

### 方案 4: 检查 Claude Code 日志

查看 Claude Code 的详细日志：
```bash
# Windows 日志位置
%APPDATA%\Claude\logs\
# 或
~/.claude/logs/
```

查找包含 "wechat-data" 或 "MCP" 的错误信息。

### 方案 5: 增加启动延迟

如果是启动时序问题，可以在服务器代码中添加启动日志：

修改 `mcp_servers/wechat_data/server.py`，在 `main()` 函数开始处添加：
```python
def main():
    """主入口"""
    import sys
    import argparse

    # 添加启动日志到 stderr（不影响 stdio 通信）
    print("WeChat MCP Server starting...", file=sys.stderr, flush=True)

    parser = argparse.ArgumentParser(description="WeChat Data MCP Server")
    # ... 其余代码
```

## 验证步骤

1. **验证服务器**：运行 `python test_mcp_connection.py` 确认服务器正常
2. **重启 Claude Code**：完全退出并重新启动
3. **测试连接**：在 Claude Code 中尝试使用 wechat-data 工具
4. **查看日志**：如果仍然失败，检查 Claude Code 日志

## 结论

**MCP 服务器本身没有问题**，问题出在 Claude Code 的客户端连接层。建议：

1. 首先尝试完全重启 Claude Code
2. 如果重启无效，添加环境变量配置
3. 如果仍然失败，查看 Claude Code 日志定位具体错误

## 测试文件

- `test_mcp_connection.py` - 独立的 MCP 连接测试脚本
- 测试结果：✅ 通过（服务器响应正常）
