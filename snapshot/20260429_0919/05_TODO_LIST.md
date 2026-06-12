# 待办事项清单

## 🎯 优先级说明

- **P0 (Critical):** 阻塞性问题，必须立即处理
- **P1 (High):** 重要功能，应尽快完成
- **P2 (Medium):** 改进优化，可按计划进行
- **P3 (Low):** 锦上添花，有时间再做

## ✅ 已完成事项

- [x] 建立索引数据库系统
- [x] 实现智能需求收集器
- [x] 开发自动化工作流
- [x] 集成kanban-doc MCP
- [x] 配置定时监控系统
- [x] 编写完整系统文档
- [x] 执行系统测试验收
- [x] 创建4个示例任务
- [x] 生成状态快照文档

## 🔥 P0 - 紧急事项

目前无紧急事项。

## 🚀 P1 - 高优先级

### 1. 批量创建Kanban任务
**状态：** 待处理
**描述：** 将剩余43个任务批量创建到kanban-doc
**预期时间：** 10分钟
**操作步骤：**
```bash
# 在Claude Code中运行
python create_kanban_tasks.py

# 或手动创建
# 读取 output/tasks_to_create.json
# 逐个通过kanban-doc MCP创建
```

**任务分布：**
- syc-player: 42个任务
- qt-lens: 1个任务

**优先级分布：**
- high: 15个
- medium: 28个

### 2. 配置Windows任务计划程序（可选）
**状态：** 待处理
**描述：** 如果需要自动化运行，配置Windows任务计划程序
**预期时间：** 5分钟
**操作步骤：**
```bash
# 创建任务计划
schtasks /create /tn "WeChatMonitor" /tr "python D:\develoment_home\project_home\WeChatMsgArchive\wechat_monitor_v2.py" /sc minute /mo 30

# 查看任务
schtasks /query /tn "WeChatMonitor"

# 删除任务
schtasks /delete /tn "WeChatMonitor" /f
```

**注意事项：**
- 确保Python路径正确
- 确保脚本路径正确
- 测试任务是否正常运行

## 📈 P2 - 中优先级

### 3. 优化项目识别规则
**状态：** 待处理
**描述：** 当前基于关键词匹配，可能不够准确
**改进方向：**
- 增加更多项目特征关键词
- 支持正则表达式匹配
- 考虑上下文信息
- 集成LLM进行智能分析

**实现建议：**
```python
# 在 auto_requirement_collector.py 中
def _identify_project_advanced(self, content, user):
    # 1. 关键词匹配（当前方法）
    project = self._identify_project(content)

    # 2. 用户历史项目分析
    if not project:
        project = self._get_user_main_project(user)

    # 3. LLM智能分析（可选）
    if not project:
        project = self._llm_identify_project(content)

    return project
```

### 4. 增加更多监控用户
**状态：** 待处理
**描述：** 当前只监控6个用户，可能遗漏其他重要反馈
**操作步骤：**
1. 查看所有联系人列表
2. 识别活跃用户
3. 添加到监控列表

**修改位置：**
```python
# auto_requirement_collector.py 第16行
self.monitor_users = [
    '三叶草',
    '编程仝芷硕',
    'Estelle',
    '烨林',
    '沐光',
    '密码机',
    # 添加新用户
    '新用户1',
    '新用户2',
]
```

### 5. 调整需求/Bug识别关键词
**状态：** 待处理
**描述：** 根据实际使用情况，调整关键词以提高准确率
**改进方向：**
- 分析误报和漏报案例
- 增加新的关键词
- 移除不准确的关键词
- 支持否定关键词（排除）

**实现建议：**
```python
# 需求关键词
self.requirement_keywords = [
    '需要', '想要', '能不能', '可以', '希望',
    '建议', '增加', '添加', '修改', '改成',
    # 新增
    '支持', '实现', '做一个', '加个',
]

# Bug关键词
self.bug_keywords = [
    'bug', '问题', '错误', '不行', '失败',
    '崩溃', '报错', '异常', '无法', '不能',
    # 新增
    '卡顿', '闪退', '白屏', '黑屏',
]

# 否定关键词（排除）
self.exclude_keywords = [
    '没问题', '已解决', '正常了', '好了',
]
```

### 6. 优化任务标题生成
**状态：** 待处理
**描述：** 当前任务标题直接使用消息内容，可能过长或不清晰
**改进方向：**
- 提取关键信息作为标题
- 限制标题长度（50字符）
- 使用LLM生成摘要

**实现建议：**
```python
def _generate_task_title(self, content, user):
    # 1. 提取关键句
    title = self._extract_key_sentence(content)

    # 2. 限制长度
    if len(title) > 50:
        title = title[:47] + '...'

    # 3. 添加用户标签
    title = f'[{user}] {title}'

    return title
```

## 🎨 P3 - 低优先级

### 7. 集成LLM进行智能分析
**状态：** 待处理
**描述：** 使用LLM进行更智能的内容分析
**应用场景：**
- 需求/Bug识别
- 优先级判断
- 项目识别
- 任务标题生成
- 任务描述优化

**实现建议：**
```python
def _llm_analyze(self, content):
    prompt = f"""
    分析以下用户反馈，判断：
    1. 是否为需求或Bug
    2. 优先级（critical/high/medium/low）
    3. 所属项目（syc-player/qt-lens/wechat-archive）
    4. 生成简洁的任务标题

    用户反馈：{content}
    """

    # 调用LLM API
    response = llm_api.call(prompt)
    return response
```

### 8. 支持多渠道数据源
**状态：** 待处理
**描述：** 除了微信，还可以从其他渠道收集需求
**可能的渠道：**
- 邮件
- 钉钉
- Slack
- GitHub Issues
- 用户反馈表单

**实现建议：**
```python
class MultiChannelCollector:
    def __init__(self):
        self.channels = [
            WeChatChannel(),
            EmailChannel(),
            DingTalkChannel(),
            GitHubChannel(),
        ]

    def collect_all(self):
        all_requirements = []
        for channel in self.channels:
            requirements = channel.collect()
            all_requirements.extend(requirements)
        return all_requirements
```

### 9. 自动回复用户反馈
**状态：** 待处理
**描述：** 收到需求/Bug后，自动回复用户确认收到
**实现方式：**
- 微信自动回复（需要微信API）
- 邮件自动回复
- 钉钉自动回复

**回复模板：**
```
您好，您的反馈已收到：
- 类型：需求/Bug
- 优先级：high
- 预计处理时间：3天内

我们会尽快处理，感谢您的反馈！
```

### 10. 增加数据分析功能
**状态：** 待处理
**描述：** 分析需求趋势、用户活跃度等
**分析维度：**
- 需求趋势（按时间）
- 用户活跃度（按用户）
- 项目热度（按项目）
- Bug类型分布
- 优先级分布

**实现建议：**
```python
class RequirementAnalyzer:
    def analyze_trends(self, days=30):
        # 按天统计需求数量
        pass

    def analyze_user_activity(self):
        # 统计用户反馈次数
        pass

    def analyze_project_heat(self):
        # 统计项目需求数量
        pass

    def generate_report(self):
        # 生成分析报告
        pass
```

### 11. 增加通知功能
**状态：** 待处理
**描述：** 有新需求/Bug时，通知相关人员
**通知方式：**
- 邮件通知
- 微信通知
- 钉钉通知
- Slack通知

**实现建议：**
```python
class Notifier:
    def notify_new_requirement(self, requirement):
        # 发送邮件
        self.send_email(requirement)

        # 发送微信
        self.send_wechat(requirement)

        # 发送钉钉
        self.send_dingtalk(requirement)
```

### 12. 优化数据库性能
**状态：** 待处理
**描述：** 当数据量增长时，可能需要优化
**优化方向：**
- 增加更多索引
- 分表存储（按时间）
- 定期清理旧数据
- 使用更高效的数据库（PostgreSQL）

**实现建议：**
```sql
-- 增加复合索引
CREATE INDEX idx_talker_time ON messages(talker, create_time);

-- 分表存储
CREATE TABLE messages_2026_04 AS SELECT * FROM messages WHERE ...;

-- 定期清理
DELETE FROM messages WHERE create_time < ...;
```

### 13. 增加Web界面
**状态：** 待处理
**描述：** 提供Web界面查看需求、任务、统计等
**功能模块：**
- 需求列表
- 任务列表
- 数据统计
- 配置管理

**技术栈：**
- 后端：Flask/FastAPI
- 前端：Vue/React
- 数据库：SQLite

### 14. 支持任务状态同步
**状态：** 待处理
**描述：** 从kanban-doc同步任务状态，更新本地记录
**实现方式：**
- 定期查询kanban-doc任务状态
- 更新本地数据库
- 生成任务进度报告

### 15. 增加用户画像分析
**状态：** 待处理
**描述：** 分析用户特征、偏好、活跃度等
**分析维度：**
- 反馈频率
- 反馈类型（需求/Bug）
- 关注项目
- 活跃时间段

**参考文件：** `user_profiling.py`

## 📊 任务统计

```
总任务数: 15个
已完成: 9个 (60%)
待处理: 6个 (40%)

按优先级:
- P0: 0个
- P1: 2个
- P2: 4个
- P3: 9个
```

## 🔄 任务更新日志

**2026-04-29 09:19**
- 创建待办事项清单
- 标记已完成的9个任务
- 规划15个待办任务

## 📝 任务认领

如果你要接手某个任务，请在此记录：

```
任务ID: [任务编号]
认领人: [你的名字]
认领时间: [时间]
预计完成: [时间]
```

## 🎯 下一步行动

**建议优先处理：**
1. 批量创建Kanban任务（P1）
2. 配置Windows任务计划程序（P1，可选）
3. 优化项目识别规则（P2）

**长期规划：**
- 集成LLM进行智能分析
- 支持多渠道数据源
- 增加Web界面
