# LLM 需求分析器 - 快速开始

## 🚀 5分钟快速上手

### 1. 配置 DeepSeek API

```bash
# 加载配置
source .env.deepseek

# 或手动设置
export ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
export ANTHROPIC_AUTH_TOKEN=sk-a1ba3c597fb4450c90149f2c43241692
export ANTHROPIC_MODEL=deepseek-v4-pro
```

### 2. 运行需求收集器

```bash
# LLM 模式（推荐）
python auto_requirement_collector.py

# 规则模式（无需 API Key）
python auto_requirement_collector.py --no-llm

# 自定义参数
python auto_requirement_collector.py --hours 48 --confidence 0.8
```

### 3. 查看结果

生成的任务文件：`output/pending_kanban_tasks.json`

```json
{
  "project": "syc-player",
  "title": "[三叶草] 播放器点击下一首时崩溃闪退",
  "priority": "high",
  "tags": ["用户反馈", "自动创建", "LLM分析", "bug"],
  "metadata": {
    "llm_analyzed": true,
    "confidence": 0.98
  }
}
```

## 📊 性能对比

| 模式 | 准确率 | 响应时间 | 成本 |
|------|--------|----------|------|
| **DeepSeek** | ~95% | ~9秒/条 | ¥0.001/条 |
| **Claude** | ~85-90% | ~1-2秒/条 | $0.0001/条 |
| **规则** | ~60-70% | <0.1秒/条 | 免费 |

## 💡 使用建议

### 生产环境
```bash
# 使用 DeepSeek（成本低、稳定）
source .env.deepseek
python auto_requirement_collector.py --hours 24
```

### 快速测试
```bash
# 使用规则模式（无需配置）
python auto_requirement_collector.py --no-llm --hours 1
```

### 高精度场景
```bash
# 提高置信度阈值
python auto_requirement_collector.py --confidence 0.85
```

## 📖 完整文档

- **使用指南**: [LLM_REQUIREMENT_COLLECTOR_GUIDE.md](LLM_REQUIREMENT_COLLECTOR_GUIDE.md)
- **LLM 集成报告**: [LLM_INTEGRATION_REPORT.md](LLM_INTEGRATION_REPORT.md)
- **DeepSeek 集成报告**: [DEEPSEEK_INTEGRATION_REPORT.md](DEEPSEEK_INTEGRATION_REPORT.md)

## 🔧 故障排查

### 问题1：LLM 模式不工作
```bash
# 检查环境变量
echo $ANTHROPIC_AUTH_TOKEN
echo $ANTHROPIC_BASE_URL

# 测试 API
python test_deepseek.py
```

### 问题2：识别准确率低
```bash
# 降低置信度阈值
python auto_requirement_collector.py --confidence 0.6
```

### 问题3：响应太慢
```bash
# 使用快速模型
export ANTHROPIC_MODEL=deepseek-v4-flash
```

## ✅ 验收标准

- ✅ 需求识别准确率 > 85%
- ✅ 自动生成的任务描述可用
- ✅ API 调用成本可控
- ✅ 支持离线降级到规则模式

---

**快速帮助**: `python auto_requirement_collector.py --help`
