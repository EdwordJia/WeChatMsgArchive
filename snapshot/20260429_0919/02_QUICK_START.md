# 快速启动指南

## 🚀 5分钟快速上手

### 前置条件
- Python 3.x 已安装
- 微信数据库已解密（或有解密密钥）
- 已安装依赖：`pywxdump`, `sqlite3`

### 第一步：验证环境

```bash
# 检查索引数据库是否存在
ls -lh output/wechat_index.db

# 如果不存在，执行全量同步
python wechat_index_db.py full
```

**预期输出：**
```
开始全量同步...
正在同步 MSG0.db...
正在同步 MSG1.db...
...
全量同步完成！总共索引 138947 条消息
```

### 第二步：运行自动化流程

```bash
python auto_workflow.py
```

**预期输出：**
```
=== 微信需求自动化收集系统 ===

[1/5] 解密微信数据库...
✓ 数据库已解密

[2/5] 同步到索引数据库...
✓ 增量同步完成，新增 0 条消息

[3/5] 收集需求和反馈...
✓ 收集到 213 条需求/反馈

[4/5] 筛选任务（最近7天，优先级>=medium）...
✓ 筛选出 47 个任务

[5/5] 生成任务列表...
✓ 任务列表已保存到: output/tasks_to_create.json

=== 完成 ===
```

### 第三步：查看生成的任务

```bash
# 查看待创建任务（简洁版）
cat output/tasks_to_create.json | head -20

# 或查看完整任务列表
cat output/pending_kanban_tasks.json
```

**任务格式示例：**
```json
{
  "user": "三叶草",
  "content": "现在就桌面歌词不行",
  "time": "2026-04-22 15:30:45",
  "priority": "high",
  "type": "bug",
  "project": "syc-player"
}
```

### 第四步：创建Kanban任务（可选）

在Claude Code中运行：
```python
# 读取任务列表
import json
with open('output/tasks_to_create.json', 'r', encoding='utf-8') as f:
    tasks = json.load(f)

# 通过kanban-doc MCP创建任务
# （需要在Claude Code环境中执行）
```

## 📋 常用命令

### 索引数据库操作

```bash
# 全量同步（首次使用或重建索引）
python wechat_index_db.py full

# 增量同步（只同步新消息）
python wechat_index_db.py incremental

# 搜索消息
python -c "
from wechat_index_db import WeChatIndexDB
db = WeChatIndexDB()
results = db.search_messages('关键词')
for r in results[:10]:
    print(f'{r[0]}: {r[1]}')
"
```

### 需求收集操作

```bash
# 收集最近30天的需求
python auto_requirement_collector.py

# 查看收集结果
cat output/pending_kanban_tasks.json
```

### 自动化流程操作

```bash
# 运行完整流程（默认7天，medium+）
python auto_workflow.py

# 自定义时间范围和优先级（需修改代码）
# 编辑 auto_workflow.py 第 XX 行
# days = 14  # 改为14天
# min_priority = 'high'  # 改为只收集high+
```

### 定时监控操作

```bash
# 手动运行监控
python wechat_monitor_v2.py

# 查看监控日志
cat output/cron_logs/monitor_v2_*.log
```

## 🔧 配置调整

### 修改监控用户

**文件：** `auto_requirement_collector.py`
**位置：** 第16行

```python
self.monitor_users = [
    '三叶草',
    '编程仝芷硕',
    'Estelle',
    '烨林',
    '沐光',
    '密码机',
    # 添加新用户
    '新用户昵称'
]
```

### 修改项目映射

**文件：** `auto_requirement_collector.py`
**位置：** 第33-37行

```python
self.project_keywords = {
    'syc-player': ['播放器', '视频', '音频', 'player', '三叶草'],
    'qt-lens': ['镜片', '检测', 'Qt', '林爱新', 'B-boy'],
    'wechat-archive': ['微信', '聊天记录', '解密', '数据库'],
    # 添加新项目
    'new-project': ['关键词1', '关键词2']
}
```

### 修改需求关键词

**文件：** `auto_requirement_collector.py`
**位置：** 第18-22行

```python
self.requirement_keywords = [
    '需要', '想要', '能不能', '可以', '希望',
    '建议', '增加', '添加', '修改', '改成',
    # 添加新关键词
    '新关键词'
]
```

### 修改Bug关键词

**文件：** `auto_requirement_collector.py`
**位置：** 第24-28行

```python
self.bug_keywords = [
    'bug', '问题', '错误', '不行', '失败',
    '崩溃', '报错', '异常', '无法', '不能',
    # 添加新关键词
    '新关键词'
]
```

### 修改时间范围和优先级

**文件：** `auto_workflow.py`
**位置：** 主函数中

```python
# 修改时间范围（天）
days = 7  # 改为你需要的天数

# 修改最低优先级
min_priority = 'medium'  # 可选: critical, high, medium, low
```

## 🧪 测试验证

### 测试索引数据库

```bash
python test_search.py
```

**预期输出：**
```
=== 测试索引数据库搜索 ===
搜索关键词: 模块
找到 20 条结果
...
```

### 测试需求收集

```bash
python test_collector.py
```

**预期输出：**
```
=== 测试需求收集器 ===
收集最近30天的需求...
找到 213 条需求/反馈
...
```

### 测试完整流程

```bash
python auto_workflow.py
```

**检查点：**
- ✓ 解密成功
- ✓ 同步完成
- ✓ 收集到需求
- ✓ 筛选出任务
- ✓ 生成JSON文件

## 🐛 常见问题

### Q1: 找不到微信数据库
**解决方案：**
```bash
# 检查路径是否正确
ls "E:\腾讯电脑管家文件搬家\微信聊天文件搬家\Users\WeChat Files\wxid_ucag2pjrmhm822"

# 如果路径不同，修改 wechat_monitor.py 中的路径
```

### Q2: 解密失败
**解决方案：**
```bash
# 重新获取解密密钥
python -c "from pywxdump import get_wechat_db; get_wechat_db()"

# 或手动指定密钥
# 修改代码中的 key 参数
```

### Q3: 搜索不到消息
**解决方案：**
```bash
# 重建索引数据库
rm output/wechat_index.db
python wechat_index_db.py full

# 检查是否有新消息
python wechat_index_db.py incremental
```

### Q4: 没有识别到需求
**解决方案：**
```bash
# 检查监控用户是否正确
python -c "
from auto_requirement_collector import RequirementCollector
collector = RequirementCollector()
print(collector.monitor_users)
"

# 调整关键词配置
# 编辑 auto_requirement_collector.py
```

### Q5: 任务创建失败
**解决方案：**
```bash
# 检查kanban-doc MCP是否可用
# 在Claude Code中测试

# 检查任务格式是否正确
cat output/tasks_to_create.json
```

## 📞 获取帮助

如果遇到问题：
1. 查看日志文件：`output/cron_logs/`
2. 查看完整文档：`README_AUTO_SYSTEM.md`
3. 查看架构说明：`snapshot/20260429_0919/01_ARCHITECTURE.md`
4. 查看测试结果：`snapshot/20260429_0919/03_TEST_RESULTS.md`

## 🎯 下一步

- [ ] 配置定时监控（Windows任务计划程序）
- [ ] 批量创建Kanban任务
- [ ] 调整配置参数以适应你的需求
- [ ] 探索更多功能（用户画像、关系图谱等）
