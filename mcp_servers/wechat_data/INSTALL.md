# 安装指南

## 1. 安装依赖

```bash
# 使用项目虚拟环境
./venv/Scripts/pip install mcp

# 或使用系统 Python
pip install mcp
```

## 2. 配置到 Claude Code

### 方法一：手动配置

编辑 Claude Code 配置文件（通常在 `~/.claude/settings.json` 或 `~/.claude/settings.local.json`）：

```json
{
  "mcpServers": {
    "wechat-data": {
      "command": "python",
      "args": [
        "-m",
        "mcp_servers.wechat_data.server"
      ],
      "cwd": "D:\develoment_home\project_home\WeChatMsgArchive",
      "env": {}
    }
  }
}
```

**注意**: 
- 将 `cwd` 路径替换为你的实际项目路径
- Windows 路径使用双反斜杠 `\`

### 方法二：使用配置工具

```bash
# 使用 Claude Code 的配置技能
/update-config

# 然后添加 MCP 服务器配置
```

## 3. 验证安装

重启 Claude Code 后，检查 MCP 工具是否可用：

```python
# 在 Claude Code 中测试
# 搜索消息
mcp__wechat-data__search_messages({
    "keyword": "测试",
    "days": 7
})

# 获取联系人信息
mcp__wechat-data__get_contact_info({
    "nickname": "三叶草"
})
```

## 4. 常见问题

### Q: 提示 "No module named 'mcp'"

A: 需要安装 MCP 包：
```bash
./venv/Scripts/pip install mcp
```

### Q: 提示 "数据库文件不存在"

A: 确保以下文件存在：
- `output/wechat_index.db` - 索引数据库
- `output/decrypted_db/Multi/MSG0.db` - 解密数据库（用于群聊查询）

如果不存在，运行：
```bash
# 解密微信数据库
/wechat-decrypt-db

# 或手动运行
./venv/Scripts/python wechat_monitor.py
```

### Q: 查询结果为空

A: 可能原因：
1. 数据库未更新 - 重新解密数据库
2. wxid 不正确 - 使用 `get_contact_info` 查询正确的 wxid
3. 时间范围太短 - 增加 `days` 参数

## 5. 下一步

安装完成后，可以：

1. **创建配套技能**: `/wechat-requirement-collector`
2. **测试完整工作流**: 从聊天记录自动生成任务
3. **集成到自动化流程**: 定时监控和分析

## 6. 卸载

如果需要移除 MCP 服务：

1. 从 Claude Code 配置中删除 `wechat-data` 配置
2. 重启 Claude Code
3. （可选）删除 `mcp_servers/wechat_data/` 目录

