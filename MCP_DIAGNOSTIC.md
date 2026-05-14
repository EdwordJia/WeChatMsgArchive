# WeChat Data MCP 服务器诊断报告

生成时间: 2026-04-30

## 检查结果

### ✅ 配置文件
- 位置: `~/.claude/mcp.json`
- JSON 格式: 有效
- Python 路径: 存在
- 启动脚本: 存在

### ✅ 服务器启动
- 脚本可以执行
- 无错误输出
- 服务器进入等待状态（正常行为）

### ❓ 连接状态
- Claude Code 报告无法连接
- 可能原因：
  1. Claude Code 缓存问题
  2. MCP 协议版本不匹配
  3. stdio 通信被阻塞
  4. 权限问题

## 建议的解决步骤

### 方案 1: 完全重置 Claude Code
```bash
# 1. 完全退出 Claude Code（包括后台进程）
# 2. 删除缓存（可选）
rm -rf ~/.claude/cache
# 3. 重新启动 Claude Code
```

### 方案 2: 使用批处理文件启动
修改 `~/.claude/mcp.json` 中的 wechat-data 配置：
```json
"wechat-data": {
    "command": "cmd.exe",
    "args": [
        "/c",
        "D:\\develoment_home\\project_home\\WeChatMsgArchive\\start_wechat_mcp.bat"
    ]
}
```

### 方案 3: 直接使用 Python 模块
```json
"wechat-data": {
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

### 方案 4: 检查其他 MCP 服务器
测试其他 MCP 服务器（如 kanban-doc）是否正常工作：
- 如果其他服务器也无法连接 → Claude Code 问题
- 如果只有 wechat-data 无法连接 → 服务器配置问题

## 调试信息

### 环境变量
```bash
PYTHONPATH=D:\develoment_home\project_home\WeChatMsgArchive
```

### 数据库路径
```
D:\develoment_home\project_home\WeChatMsgArchive\output\wechat_index.db
```

### 服务器代码位置
```
D:\develoment_home\project_home\WeChatMsgArchive\mcp_servers\wechat_data\
```

## 下一步行动

1. 尝试方案 3（添加 cwd 参数）
2. 完全重启 Claude Code
3. 如果仍然失败，检查 Claude Code 日志文件
4. 考虑使用其他 MCP 客户端测试服务器
