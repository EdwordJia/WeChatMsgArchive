# 配置参考手册

## 📋 配置文件位置

本系统采用代码内配置方式，主要配置项分布在以下文件中：

```
auto_requirement_collector.py  - 需求收集配置
auto_workflow.py               - 工作流配置
wechat_monitor_v2.py           - 监控配置
wechat_index_db.py             - 数据库配置
```

## 🔧 核心配置项

### 1. 监控用户配置

**文件：** `auto_requirement_collector.py`
**位置：** 第16行
**默认值：**
```python
self.monitor_users = [
    '三叶草',
    '编程仝芷硕',
    'Estelle',
    '烨林',
    '沐光',
    '密码机'
]
```

**说明：**
- 只监控列表中的用户消息
- 用户名必须与微信昵称完全匹配
- 支持添加任意数量的用户

**修改示例：**
```python
self.monitor_users = [
    '三叶草',
    '编程仝芷硕',
    'Estelle',
    '烨林',
    '沐光',
    '密码机',
    # 添加新用户
    '张三',
    '李四',
]
```

### 2. 需求关键词配置

**文件：** `auto_requirement_collector.py`
**位置：** 第18-22行
**默认值：**
```python
self.requirement_keywords = [
    '需要', '想要', '能不能', '可以', '希望',
    '建议', '增加', '添加', '修改', '改成',
    '实现', '支持', '做一个', '加个', '弄个'
]
```

**说明：**
- 消息包含任一关键词即识别为需求
- 关键词不区分大小写
- 支持中英文关键词

**修改建议：**
```python
self.requirement_keywords = [
    # 基础需求词
    '需要', '想要', '能不能', '可以', '希望',
    '建议', '增加', '添加', '修改', '改成',

    # 动作词
    '实现', '支持', '做一个', '加个', '弄个',

    # 疑问词
    '怎么', '如何', '能否',

    # 自定义关键词
    '新功能', '优化',
]
```

### 3. Bug关键词配置

**文件：** `auto_requirement_collector.py`
**位置：** 第24-28行
**默认值：**
```python
self.bug_keywords = [
    'bug', '问题', '错误', '不行', '失败',
    '崩溃', '报错', '异常', '无法', '不能',
    '卡顿', '闪退', '白屏', '黑屏'
]
```

**说明：**
- 消息包含任一关键词即识别为Bug
- Bug优先级高于需求
- 支持中英文关键词

**修改建议：**
```python
self.bug_keywords = [
    # 英文Bug词
    'bug', 'error', 'crash', 'fail',

    # 中文问题词
    '问题', '错误', '不行', '失败',

    # 严重问题词
    '崩溃', '报错', '异常', '无法', '不能',

    # 性能问题词
    '卡顿', '闪退', '白屏', '黑屏', '慢', '卡',

    # 自定义关键词
    '有毛病', '不对劲',
]
```

### 4. 反馈关键词配置

**文件：** `auto_requirement_collector.py`
**位置：** 第30-31行
**默认值：**
```python
self.feedback_keywords = [
    '反馈', '意见', '体验', '不好用', '太慢', '卡顿'
]
```

**说明：**
- 用于识别一般性反馈
- 优先级低于需求和Bug

### 5. 项目关键词配置

**文件：** `auto_requirement_collector.py`
**位置：** 第33-37行
**默认值：**
```python
self.project_keywords = {
    'syc-player': ['播放器', '视频', '音频', 'player', '三叶草'],
    'qt-lens': ['镜片', '检测', 'Qt', '林爱新', 'B-boy'],
    'wechat-archive': ['微信', '聊天记录', '解密', '数据库']
}
```

**说明：**
- 根据关键词自动识别任务所属项目
- 支持多个关键词匹配
- 未匹配到则归类为'unknown'

**修改示例：**
```python
self.project_keywords = {
    'syc-player': [
        '播放器', '视频', '音频', 'player',
        '三叶草',  # 用户名也可作为项目标识
        '歌词', '播放', '暂停', '音量',
    ],
    'qt-lens': [
        '镜片', '检测', 'Qt', '林爱新', 'B-boy',
        '界面', '按钮', '显示',
    ],
    'wechat-archive': [
        '微信', '聊天记录', '解密', '数据库',
        '消息', '导出', '备份',
    ],
    # 添加新项目
    'new-project': [
        '关键词1', '关键词2', '关键词3',
    ],
}
```

### 6. 优先级关键词配置

**文件：** `auto_requirement_collector.py`
**位置：** `_get_priority()` 方法中

**默认规则：**
```python
# Critical - 严重问题
if any(word in content for word in ['崩溃', '数据丢失', '无法使用']):
    return 'critical'

# High - 紧急重要
if any(word in content for word in ['紧急', '严重', '重要', '马上', '立即']):
    return 'high'

# Medium - 一般需求
if any(word in content for word in ['希望', '建议', '优化', '改进']):
    return 'medium'

# Low - 其他
return 'low'
```

**修改示例：**
```python
def _get_priority(self, content):
    content = content.lower()

    # Critical - 严重问题
    critical_keywords = ['崩溃', '数据丢失', '无法使用', '闪退', '黑屏']
    if any(word in content for word in critical_keywords):
        return 'critical'

    # High - 紧急重要
    high_keywords = ['紧急', '严重', '重要', '马上', '立即', '尽快']
    if any(word in content for word in high_keywords):
        return 'high'

    # Medium - 一般需求
    medium_keywords = ['希望', '建议', '优化', '改进', '可以']
    if any(word in content for word in medium_keywords):
        return 'medium'

    # Low - 其他
    return 'low'
```

### 7. 时间范围配置

**文件：** `auto_workflow.py`
**位置：** `filter_tasks()` 函数参数
**默认值：**
```python
days = 7  # 最近7天
```

**说明：**
- 只筛选指定天数内的任务
- 用于减少待创建任务数量

**修改示例：**
```python
# 修改为最近14天
days = 14

# 修改为最近30天
days = 30

# 修改为所有任务
days = 9999
```

### 8. 优先级筛选配置

**文件：** `auto_workflow.py`
**位置：** `filter_tasks()` 函数参数
**默认值：**
```python
min_priority = 'medium'  # 最低优先级为medium
```

**说明：**
- 只保留指定优先级及以上的任务
- 优先级顺序：critical > high > medium > low

**修改示例：**
```python
# 只保留high及以上
min_priority = 'high'

# 只保留critical
min_priority = 'critical'

# 保留所有任务
min_priority = 'low'
```

### 9. 数据库路径配置

**文件：** `wechat_index_db.py`
**位置：** `__init__()` 方法
**默认值：**
```python
self.index_db_path = 'output/wechat_index.db'
```

**说明：**
- 索引数据库存储路径
- 相对于项目根目录

**修改示例：**
```python
# 使用绝对路径
self.index_db_path = 'D:/data/wechat_index.db'

# 使用其他目录
self.index_db_path = 'data/index.db'
```

### 10. 微信数据库路径配置

**文件：** `wechat_monitor.py` 或 `wechat_index_db.py`
**位置：** 解密函数中
**默认值：**
```python
wx_path = r"E:\腾讯电脑管家文件搬家\微信聊天文件搬家\Users\WeChat Files\wxid_ucag2pjrmhm822"
```

**说明：**
- 微信数据目录路径
- 需要根据实际情况修改

**修改示例：**
```python
# Windows默认路径
wx_path = r"C:\Users\YourName\Documents\WeChat Files\wxid_xxx"

# 自定义路径
wx_path = r"D:\WeChat\wxid_xxx"
```

### 11. 监控频率配置

**文件：** Windows任务计划程序
**默认值：** 每30分钟
**配置命令：**
```bash
# 每30分钟
schtasks /create /tn "WeChatMonitor" /tr "python wechat_monitor_v2.py" /sc minute /mo 30

# 每15分钟
schtasks /create /tn "WeChatMonitor" /tr "python wechat_monitor_v2.py" /sc minute /mo 15

# 每小时
schtasks /create /tn "WeChatMonitor" /tr "python wechat_monitor_v2.py" /sc hourly

# 每天
schtasks /create /tn "WeChatMonitor" /tr "python wechat_monitor_v2.py" /sc daily /st 09:00
```

### 12. 日志配置

**文件：** `wechat_monitor_v2.py`
**位置：** 日志路径设置
**默认值：**
```python
log_dir = 'output/cron_logs'
log_file = f'monitor_v2_{datetime.now().strftime("%Y%m%d_%H%M")}.log'
```

**说明：**
- 日志文件按时间命名
- 自动创建日志目录

**修改示例：**
```python
# 使用单一日志文件
log_file = 'monitor.log'

# 按日期分组
log_file = f'monitor_{datetime.now().strftime("%Y%m%d")}.log'

# 使用绝对路径
log_dir = 'D:/logs/wechat'
```

## 🎯 配置模板

### 快速配置模板

创建 `config.py` 文件（推荐）：

```python
# config.py - 集中配置文件

# 监控用户
MONITOR_USERS = [
    '三叶草',
    '编程仝芷硕',
    'Estelle',
    '烨林',
    '沐光',
    '密码机',
]

# 需求关键词
REQUIREMENT_KEYWORDS = [
    '需要', '想要', '能不能', '可以', '希望',
    '建议', '增加', '添加', '修改', '改成',
]

# Bug关键词
BUG_KEYWORDS = [
    'bug', '问题', '错误', '不行', '失败',
    '崩溃', '报错', '异常', '无法', '不能',
]

# 项目关键词
PROJECT_KEYWORDS = {
    'syc-player': ['播放器', '视频', '音频', 'player'],
    'qt-lens': ['镜片', '检测', 'Qt'],
    'wechat-archive': ['微信', '聊天记录', '解密'],
}

# 时间范围（天）
TIME_RANGE_DAYS = 7

# 最低优先级
MIN_PRIORITY = 'medium'

# 数据库路径
INDEX_DB_PATH = 'output/wechat_index.db'
WECHAT_PATH = r"E:\腾讯电脑管家文件搬家\微信聊天文件搬家\Users\WeChat Files\wxid_ucag2pjrmhm822"

# 日志配置
LOG_DIR = 'output/cron_logs'
```

然后在各个文件中导入：
```python
from config import *
```

## 📊 配置验证

### 验证配置是否正确

```python
# test_config.py
from auto_requirement_collector import RequirementCollector

collector = RequirementCollector()

print("监控用户:", collector.monitor_users)
print("需求关键词:", collector.requirement_keywords)
print("Bug关键词:", collector.bug_keywords)
print("项目关键词:", collector.project_keywords)
```

## 🔄 配置更新流程

1. **备份当前配置**
   ```bash
   cp auto_requirement_collector.py auto_requirement_collector.py.bak
   ```

2. **修改配置**
   - 编辑对应文件
   - 修改配置项

3. **测试配置**
   ```bash
   python test_collector.py
   ```

4. **应用配置**
   ```bash
   python auto_workflow.py
   ```

## 🐛 配置问题排查

### 问题1: 没有识别到需求
**可能原因：**
- 关键词配置不匹配
- 监控用户配置错误

**解决方案：**
```python
# 检查关键词
print(collector.requirement_keywords)

# 检查监控用户
print(collector.monitor_users)

# 测试识别
content = "能不能增加一个功能"
print(collector._is_requirement(content))
```

### 问题2: 项目识别错误
**可能原因：**
- 项目关键词配置不准确

**解决方案：**
```python
# 检查项目关键词
print(collector.project_keywords)

# 测试识别
content = "播放器的视频无法播放"
print(collector._identify_project(content))
```

### 问题3: 优先级判断不准确
**可能原因：**
- 优先级关键词配置不合理

**解决方案：**
```python
# 测试优先级判断
content = "紧急修复这个bug"
print(collector._get_priority(content))
```

## 📝 配置最佳实践

1. **定期审查配置**
   - 每周检查一次识别准确率
   - 根据实际情况调整关键词

2. **版本控制**
   - 使用git管理配置变更
   - 记录每次修改的原因

3. **测试驱动**
   - 修改配置后必须测试
   - 保留测试用例

4. **文档同步**
   - 配置修改后更新文档
   - 记录配置变更历史

## 🎯 推荐配置

### 保守配置（高准确率）
```python
# 只监控核心用户
MONITOR_USERS = ['三叶草', '编程仝芷硕']

# 只使用明确的关键词
REQUIREMENT_KEYWORDS = ['需要', '想要', '能不能']
BUG_KEYWORDS = ['bug', '崩溃', '报错']

# 只保留high及以上
MIN_PRIORITY = 'high'
```

### 激进配置（高覆盖率）
```python
# 监控所有活跃用户
MONITOR_USERS = ['三叶草', '编程仝芷硕', 'Estelle', '烨林', '沐光', '密码机', ...]

# 使用更多关键词
REQUIREMENT_KEYWORDS = ['需要', '想要', '能不能', '可以', '希望', '建议', ...]
BUG_KEYWORDS = ['bug', '问题', '错误', '不行', '失败', ...]

# 保留所有任务
MIN_PRIORITY = 'low'
```

### 平衡配置（推荐）
```python
# 当前默认配置
# 已在实际使用中验证
```
