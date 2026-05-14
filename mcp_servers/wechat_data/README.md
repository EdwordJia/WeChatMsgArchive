# WeChat Data MCP Server

微信聊天数据 MCP 服务，提供标准化的数据访问接口。

## 功能特性

- 🔍 消息搜索 - 支持关键词搜索和时间范围过滤
- 👤 联系人消息 - 获取指定联系人的聊天记录
- 👥 群聊消息 - 获取群聊消息，支持筛选特定成员
- ⏰ 时间范围查询 - 按时间范围精确查询
- 📇 联系人信息 - 查询联系人详细信息
- 📋 群聊列表 - 获取所有群聊列表

## 安装

```bash
# 安装依赖
pip install mcp

# 或使用项目虚拟环境
./venv/Scripts/pip install mcp
```

## 配置

在 Claude Code 的配置文件中添加 MCP 服务器：

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

## 可用工具

### 1. search_messages

搜索微信消息内容。

**参数**:
- `keyword` (string, 必需): 搜索关键词
- `limit` (integer, 可选): 返回数量限制，默认100
- `days` (integer, 可选): 最近N天，默认7天

**示例**:
```json
{
  "keyword": "播放器",
  "limit": 50,
  "days": 7
}
```

### 2. get_contact_messages

获取指定联系人的聊天消息。

**参数**:
- `wxid` (string, 必需): 微信ID
- `days` (integer, 可选): 最近N天，默认7天
- `limit` (integer, 可选): 返回数量限制，默认100

**示例**:
```json
{
  "wxid": "wxid_eh3bqdf46zzj22",
  "days": 7,
  "limit": 100
}
```

### 3. get_group_messages

获取群聊消息。

**参数**:
- `group_id` (string, 必需): 群聊ID（通常以@chatroom结尾）
- `days` (integer, 可选): 最近N天，默认7天
- `limit` (integer, 可选): 返回数量限制，默认100
- `sender_wxid` (string, 可选): 发送者wxid，用于筛选特定成员

**示例**:
```json
{
  "group_id": "12345678@chatroom",
  "days": 7,
  "sender_wxid": "wxid_eh3bqdf46zzj22"
}
```

### 4. search_by_time_range

按时间范围查询消息。

**参数**:
- `start_time` (integer, 必需): 开始时间戳
- `end_time` (integer, 必需): 结束时间戳
- `talker_id` (string, 可选): 对话者ID
- `limit` (integer, 可选): 返回数量限制，默认100

**示例**:
```json
{
  "start_time": 1777269599,
  "end_time": 1777309337,
  "limit": 100
}
```

### 5. get_contact_info

获取联系人信息。

**参数**:
- `wxid` (string, 可选): 微信ID
- `nickname` (string, 可选): 昵称（支持模糊搜索）

**示例**:
```json
{
  "nickname": "三叶草"
}
```

### 6. get_all_groups

获取所有群聊列表。

**参数**: 无

## 使用示例

### 在 Claude Code 中使用

```python
# 搜索包含"播放器"的消息
result = mcp__wechat-data__search_messages({
    "keyword": "播放器",
    "days": 7
})

# 获取三叶草的聊天记录
result = mcp__wechat-data__get_contact_messages({
    "wxid": "wxid_eh3bqdf46zzj22",
    "days": 7
})

# 获取群聊消息
result = mcp__wechat-data__get_group_messages({
    "group_id": "12345678@chatroom",
    "days": 7
})
```

## 数据格式

### 消息对象

```json
{
  "create_time": 1777309337,
  "content": "消息内容",
  "is_sender": 0,
  "talker": "wxid_eh3bqdf46zzj22",
  "msg_type": 1
}
```

### 联系人对象

```json
{
  "wxid": "wxid_eh3bqdf46zzj22",
  "nickname": "三叶草",
  "remark": "潘苗苗",
  "type": 3
}
```

## 注意事项

1. **数据库路径**: 默认使用 `output/wechat_index.db`，确保数据库文件存在
2. **解密数据库**: 群聊消息查询需要解密后的数据库（`output/decrypted_db/Multi/`）
3. **时间戳**: 所有时间使用 Unix 时间戳（秒）
4. **编码**: 自动处理二进制内容，转换为 UTF-8 字符串

## 开发

### 项目结构

```
mcp_servers/wechat_data/
├── __init__.py      # 包初始化
├── server.py        # MCP 服务器主入口
├── tools.py         # 工具定义
├── database.py      # 数据库访问层
└── README.md        # 使用文档
```

### 测试

```bash
# 直接运行服务器
python -m mcp_servers.wechat_data.server

# 或使用虚拟环境
./venv/Scripts/python -m mcp_servers.wechat_data.server
```

## 许可证

MIT License
