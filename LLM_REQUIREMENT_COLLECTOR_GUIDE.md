# LLM 语义分析需求收集器 - 使用指南

## 功能概述

智能需求收集器现已支持两种分析模式：

1. **LLM 模式**（默认）：使用 Claude API 进行深度语义理解
   - 识别隐含需求和情绪
   - 自动判定优先级
   - 生成结构化任务描述
   - 支持上下文分析

2. **规则模式**（降级）：基于关键词规则匹配
   - 无需 API Key
   - 快速响应
   - 适合简单场景

## 安装配置

### 1. 安装依赖

```bash
pip install anthropic
```

### 2. 配置 API Key（LLM 模式）

**Windows PowerShell:**
```powershell
[System.Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-...", "User")
```

**Linux/Mac:**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

## 使用方法

### 基本用法

```bash
# LLM 模式（默认）
python auto_requirement_collector.py

# 规则模式
python auto_requirement_collector.py --no-llm

# 指定时间范围
python auto_requirement_collector.py --hours 48

# 调整置信度阈值
python auto_requirement_collector.py --confidence 0.8
```

### 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--hours` | 收集最近N小时的需求 | 24 |
| `--no-llm` | 禁用 LLM，使用规则模式 | False |
| `--confidence` | LLM 置信度阈值（0-1） | 0.7 |

## 输出示例

### LLM 模式输出

```
==============================================
智能需求收集器
=====================================
模式: LLM 模式
时间范围: 最近 24 小时
===================================
2026-05-17 18:00:00,000 - INFO - ✓ LLM 模式已启用

收集最近24小时的需求和反馈...
2026-05-17 18:00:01,000 - INFO - ✓ LLM 识别需求: bug | high | 置信度 0.92
2026-05-17 18:00:02,000 - INFO - ✓ LLM 识别需求: feature | medium | 置信度 0.85

找到 5 条需求/反馈

三叶草: 2 条
  [bug] 播放器经常崩溃，点击下一首就闪退... (置信度: 0.92)
  [feature] 能不能增加歌词显示功能？... (置信度: 0.85)

烨林: 3 条
  [enhancement] 爬虫速度太慢了，能优化一下吗... (置信度: 0.78)

生成kanban任务...
生成 5 个待创建任务
任务文件: D:\...\output\pending_kanban_tasks.json

按项目分组:
  syc-player: 2 个任务
  MCE: 3 个任务

分析模式统计:
  LLM 分析: 5 个
  规则模式: 0 个

完成！
========================================
```

### 生成的任务格式（LLM 模式）

```json
{
  "project": "syc-player",
  "title": "[三叶草] 修复播放器点击下一首时的崩溃问题",
  "body": "## 反馈内容\n播放器经常崩溃，点击下一首就闪退...\n\n## LLM 分析\n**类型**: bug\n**优先级**: high\n**置信度**: 0.92\n**分析理由**: 用户明确描述了软件崩溃问题，影响核心功能\n\n## 任务描述\n修复播放器在切换歌曲时的崩溃问题...\n\n## 反馈人\n三叶草 (wxid_xxx)\n\n## 反馈时间\n2026-05-17 15:30:00\n\n## 反馈群聊\n三叶草播放器用户群",
  "priority": "high",
  "tags": ["用户反馈", "自动创建", "llm-analyzed", "bug", "crash"],
  "metadata": {
    "source": "wechat",
    "user": "三叶草",
    "timestamp": 1715958600,
    "group": "三叶草播放器用户群",
    "analysis_mode": "llm",
    "confidence": 0.92
  }
}
```

## 性能对比

| 指标 | LLM 模式 | 规则模式 |
|------|----------|----------|
| 准确率 | ~85-90% | ~60-70% |
| 响应时间 | 1-2秒/条 | <0.1秒/条 |
| 成本 | ~$0.01/100条 | 免费 |
| 隐含需求识别 | ✓ | ✗ |
| 优先级判定 | 智能 | 基于关键词 |
| 任务描述质量 | 结构化、专业 | 简单摘要 |

## 降级机制

系统会在以下情况自动降级到规则模式：

1. 未配置 `ANTHROPIC_API_KEY`
2. API 调用失败（网络错误、配额超限等）
3. LLM 返回的置信度低于阈值
4. 用户显式指定 `--no-llm`

降级时会记录日志：
```
2026-05-17 18:00:00,000 - WARNING - ⚠ ANTHROPIC_API_KEY 未配置，降级到规则模式
```

## 最佳实践

### 1. 选择合适的模式

- **LLM 模式**：适合重要客户、复杂需求、需要高准确率的场景
- **规则模式**：适合快速筛选、大批量处理、成本敏感的场景

### 2. 调整置信度阈值

```bash
# 高精度（减少误报）
python auto_requirement_collector.py --confidence 0.85

# 高召回（减少漏报）
python auto_requirement_collector.py --confidence 0.6
```

### 3. 批量处理

```bash
# 每天定时运行
python auto_requirement_collector.py --hours 24

# 每周汇总
python auto_requirement_collector.py --hours 168
```

### 4. 监控日志

日志文件：`requirement_collector.log`

```bash
# 查看最近的分析结果
tail -f requirement_collector.log

# 统计 LLM 识别的需求数量
grep "✓ LLM 识别需求" requirement_collector.log | wc -l
```

## 故障排查

### 问题1：LLM 模式不工作

**症状**：
```
⚠ ANTHROPIC_API_KEY 未配置，降级到规则模式
```

**解决方案**：
1. 检查环境变量是否设置：`echo $ANTHROPIC_API_KEY`
2. 重启终端或 PowerShell
3. 确认 API Key 有效：访问 https://console.anthropic.com/

### 问题2：识别准确率低

**症状**：很多需求被漏掉或误判

**解决方案**：
1. 降低置信度阈值：`--confidence 0.6`
2. 检查监控用户列表是否完整
3. 查看日志中的 `reasoning` 字段，了解 LLM 的判断依据

### 问题3：API 调用超时

**症状**：
```
LLM 分析失败: timeout，降级到规则模式
```

**解决方案**：
1. 检查网络连接
2. 减少批量处理的消息数量
3. 使用规则模式作为备选

## 进阶用法

### 集成到 AutoPipeline

在 `auto_pipeline.py` 中调用：

```python
from auto_requirement_collector import RequirementCollector

# 使用 LLM 模式
collector = RequirementCollector(use_llm=True, confidence_threshold=0.75)
requirements = collector.collect_requirements(hours=24)
tasks = collector.generate_kanban_tasks(requirements)

# 创建 kanban 任务
for task in tasks:
    create_kanban_task(task['project'], task['title'], task['body'], ...)
```

### 自定义 LLM Prompt

修改 `llm_requirement_analyzer.py` 中的 `system_prompt`：

```python
system_prompt = """你是一个专业的需求分析师...
[自定义你的 Prompt]
"""
```

## 更新日志

### v2.0 (2026-05-17)
- ✨ 新增 LLM 语义分析支持
- ✨ 新增自动降级机制
- ✨ 新增命令行参数
- ✨ 新增置信度过滤
- ✨ 新增上下文分析
- 📝 改进任务描述格式
- 📝 添加分析模式统计

### v1.0 (2026-05-11)
- 🎉 初始版本
- ✨ 基于关键词规则的需求识别
- ✨ 支持多用户监控
- ✨ 自动生成 kanban 任务

## 相关文件

- `auto_requirement_collector.py` - 主程序
- `llm_requirement_analyzer.py` - LLM 分析器
- `wechat_index_db.py` - 微信数据库接口
- `requirement_collector.log` - 运行日志
- `output/pending_kanban_tasks.json` - 生成的任务文件

## 技术支持

如有问题，请查看：
1. 日志文件：`requirement_collector.log`
2. 任务进度：kanban-doc 项目 WeChatMsgArchive
3. 相关文档：`README_AUTOPIPELINE.md`
