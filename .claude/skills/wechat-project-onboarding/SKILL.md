# 微信项目接入工作流

从微信聊天记录中挖掘新项目需求，创建 kanban-doc 项目，配置自动化工作流的完整流程。

## 使用场景

当用户说"有一个新项目"、"拉取下看看"、"群名为XXX"时触发。

## 执行步骤

### Step 1: 同步微信数据库

**关键**：必须先同步数据库到最新，否则找不到新群/新消息！

```bash
cd "D:\develoment_home\project_home\WeChatMsgArchive"
./venv/Scripts/python wechat_sync_facade.py
```

- 自动检测 `WeChat.exe` / `Weixin.exe` 并走对应 v3/v4 链路
- 同步结果统一汇总到索引库 `output/wechat_index.db`

**验证**：检查索引库最新消息时间是否是今天
```bash
sqlite3 output/wechat_index.db "SELECT datetime(MAX(create_time), 'unixepoch', 'localtime') FROM messages;"
```

### Step 2: 搜索目标群聊
根据用户提供的信息搜索群聊：

#### 方法A：通过群名搜索
```python
import sqlite3
conn = sqlite3.connect('output/decrypted_db/MicroMsg.db')
cur = conn.cursor()

cur.execute('''
    SELECT UserName, NickName
    FROM Contact
    WHERE UserName LIKE '%@chatroom'
    AND NickName LIKE ?
''', (f'%{群名关键词}%',))

results = cur.fetchall()
for chatroom_id, nickname in results:
    print(f'{nickname} | {chatroom_id}')
```

#### 方法B：通过成员名搜索
```python
# 1. 找到成员的 wxid
cur.execute('''
    SELECT UserName, NickName
    FROM Contact
    WHERE (NickName LIKE ? OR Remark LIKE ?)
    AND UserName NOT LIKE '%@chatroom'
''', (f'%{成员昵称}%', f'%{成员昵称}%'))

member_wxids = [row[0] for row in cur.fetchall()]

# 2. 查找包含该成员的群
for member_wxid in member_wxids:
    cur.execute('''
        SELECT ChatRoomName
        FROM ChatRoom
        WHERE UserNameList LIKE ?
    ''', (f'%{member_wxid}%',))

    for (chatroom_id,) in cur.fetchall():
        # 获取群名
        cur.execute('SELECT NickName FROM Contact WHERE UserName = ?', (chatroom_id,))
        row = cur.fetchone()
        print(f'{row[0] if row else "(未知)"} | {chatroom_id}')
```

## 方法C：通过消息内容搜索
```python
# 搜索包含关键词的群聊
conn_msg = sqlite3.connect('output/wechat_index.db')
cur_msg = conn_msg.cursor()
cur_msg.execute('''
    SELECT DISTINCT talker, COUNT(*) as msg_count
    FROM messages
    WHERE talker LIKE '%@chatroom'
    AND content LIKE ?
    AND create_time > ?
    GROUP BY talker
    ORDER BY msg_count DESC
''', (f'%{关键词}%', int((datetime.now() - timedelta(days=7)).timestamp())))
```

#### 方法D：列出最近活跃的群
```python
# 列出最近24小时有消息的群
today = int((datetime.now() - timedelta(hours=24)).timestamp())

cur_msg.execute('''
    SELECT DISTINCT talker, MAX(create_time), COUNT(*)
    FROM messages
    WHERE talker LIKE '%@chatroom'
    AND create_time > ?
    GROUP BY talker
    ORDER BY MAX(create_time) DESC
    LIMIT 30
''', (today,))
```

### Step 3: 查看群聊消息

找到目标群后，优先从索引库查看消息内容确认：

```python
import sqlite3
from datetime import datetime

chatroom_id = '目标群ID'
conn = sqlite3.connect('output/wechat_index.db')
cur = conn.cursor()

cur.execute('''
    SELECT create_time, content, msg_type, is_sender, sender_wxid
    FROM messages
    WHERE talker = ? AND msg_type = 1
    ORDER BY create_time ASC
    LIMIT 50
''', (chatroom_id,))

for create_time, content, msg_type, is_sender, sender_wxid in cur.fetchall():
    time_str = datetime.fromtimestamp(create_time).strftime('%m-%d %H:%M')
    sender = '我' if is_sender else sender_wxid
    if content and len(content) < 300:
        print(f'[{time_str}] {sender}: {content}')
```

> 备选方式（直接查解密 DB）：如果索引库未覆盖或需要原始字段，可解密后查 `output/decrypted_db/Multi/MSG*.db`：
> ```python
> cur_msg.execute('''
>     SELECT CreateTime, StrContent, Type, IsSender
>     FROM MSG
>     WHERE StrTalker = ? AND Type = 1
>     ORDER BY CreateTime ASC
>     LIMIT 50
> ''', (chatroom_id,))
> ```

### Step 4: 提取需求信息

从聊天记录中提取：
- **项目类型**：什么系统/功能
- **核心功能**：主要需求点
- **技术要求**：技术栈、性能要求
- **预算和周期**：费用、交付时间
- **关键参与者**：客户、开发者

### Step 5: 创建 kanban-doc 项目

```python
mcp__kanban-doc__bootstrap_project(
    name="项目名称",  # 使用 kebab-case
    description="项目简短描述",
    visibility="private",
    auto_start=True,  # 自动认领初始任务
    initial_task={
        "title": "设计并实现XXX核心功能",
        "body": """
## 项目背景
[从聊天记录提取的背景]

## 核心功能需求
1. 功能A
2. 功能B
3. 功能C

## 技术要求
- 简单易用
- 成本控制
- 快速交付

## 参考信息
- 微信群: {chatroom_id}
- 客户: @XXX
- 开发: @长腿叔叔
- 讨论时间: YYYY-MM-DD HH:MM 开始
        """,
        "priority": "high",
        "tags": ["feature", "backend", "frontend", "database"]
    }
)
```

### Step 6: 配置业务渠道

编辑 `business_channels.py`，添加群聊映射：

```python
CHANNEL_TO_PROJECT = {
    # ... 现有配置 ...
    "群ID@chatroom": "项目名称",  # 客户名 - 项目描述
}
```

### Step 7: 更新项目映射记忆

在 `memory/project_mapping.md` 中记录：
```markdown
## 项目名称
- **类型**: Web应用 / 爬虫 / 小程序 / ...
- **本地路径**: ./项目名称
- **看板路径**: ~/.kanban/项目名称
- **客户**: @客户昵称 (wxid)
- **沟通群组**: 群名 (群ID)
- **创建时间**: YYYY-MM-DD
- **状态**: 开发中 / 已交付 / ...
```

### Step 8: 开始开发

项目创建后，任务已自动认领，可以直接开始开发：

```bash
cd ./项目名称
# 初始化项目结构
# 开始编码
```

## 常见问题

### Q1: 同步失败或密钥获取失败
**原因**: 微信未运行、未以管理员权限运行，或 v3 内存密钥读取失败
**解决**:
- 确认微信已登录并保持运行
- 以管理员权限运行 PowerShell/终端
- 重启微信后重试
- 查看 `wechat_sync_facade.py` 输出中的具体报错步骤

### Q2: 找不到新群/新消息
**原因**: 数据库未同步到最新
**解决**: 先执行 Step 1 同步数据库，验证索引库最新消息时间

### Q3: 群名为空
**原因**: 新群可能还没设置群名，或索引未同步
**解决**:
- 通过成员名搜索（方法B）
- 通过消息内容搜索（方法C）
- 列出最近活跃的群（方法D）

### Q4: 搜索到多个候选群
**原因**: 关键词不够精确
**解决**:
- 查看消息内容确认
- 询问用户提供更多信息（成员名、关键词）

## 输出格式

完成后向用户展示：

```
项目创建成功！

**项目名称**: distribution-management-system
**项目路径**: ./distribution-management-system
**GitHub 仓库**: https://github.com/用户名/distribution-management-system
**初始任务**: d4e1 - 设计并实现XXX核心功能（已自动认领）

**业务渠道已配置**:
- 群ID: 44637051187@chatroom
- 映射到: distribution-management-system

**下一步**:
1. 开始开发核心功能
2. 定期更新任务进度
3. 完成后提交代码并创建 PR
```

## 注意事项

1. **必须先同步数据库**，否则找不到新消息
2. **验证索引库最新消息时间**，确保数据是最新的
3. **多种搜索方式结合**，提高找到目标群的成功率
4. **查看消息内容确认**，避免找错群
5. **提取完整需求**，确保任务描述清晰
6. **配置业务渠道**，启用自动化工作流
7. **更新项目映射**，方便后续查找

## 相关技能

- `wechat-decrypt-db`: 解密/同步微信数据库
- `wechat-contact-search`: 搜索联系人
- `wechat-group-analysis`: 分析群聊消息
- `wechat-member-trace`: 追踪成员消息
