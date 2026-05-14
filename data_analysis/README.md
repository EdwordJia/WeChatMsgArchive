# WeChatMsgArchive 数据分析方案

## 项目概述

本方案为 WeChatMsgArchive 项目提供了一套完整的数据处理流水线，支持从微信解密数据库中提取、清洗、分析数据，并生成结构化的 Markdown 分析报告。

## 功能特性

- ✅ **双版本兼容**: 支持微信 v3 (3.9.x) 和 v4 (4.0.x) 数据库格式
- ✅ **增量更新**: 支持基于时间戳水印的增量数据提取
- ✅ **多维分析**: 用户画像、关系图谱、项目追踪三大分析维度
- ✅ **Markdown 输出**: 生成可直接阅读的结构化报告
- ✅ **可扩展架构**: 模块化设计，易于新增分析器和导出格式

## 目录结构

```
data_analysis/
├── README.md                          # 本文件
├── scripts/                           # Python 脚本
│   ├── data_extractor.py              # 数据提取框架
│   ├── data_cleaner.py                # 数据清洗框架
│   ├── profile_builder.py             # 分析数据集构建器
│   └── markdown_exporter.py           # Markdown 导出器
├── templates/                         # Markdown 模板
│   ├── user_profile.md                # 用户画像模板
│   ├── relation_graph.md              # 关系图谱模板
│   └── project_archive.md             # 项目档案模板
├── docs/                              # 文档
│   ├── 数据字典.md                     # 字段映射和清洗规则
│   ├── 数据处理流程.md                 # 架构图和流程说明
│   └── 数据更新维护策略.md             # 更新和维护指南
└── examples/                          # 示例
    └── example_output.md              # 输出样例
```

## 快速开始

### 环境准备

确保已安装项目主依赖：

```bash
# 在项目根目录
pip install -r requirements.txt
```

### 执行完整流水线

```bash
# 1. 数据提取（以 v3 为例）
python data_analysis/scripts/data_extractor.py \
    --version v3 \
    --db-dir output/decrypted_db \
    --output-dir data_analysis/output

# 2. 数据清洗
python data_analysis/scripts/data_cleaner.py \
    --input-db data_analysis/output/unified_data_v3.db \
    --output-db data_analysis/output/cleaned_data.db \
    --report data_analysis/output/clean_report.json

# 3. 构建分析数据集
python data_analysis/scripts/profile_builder.py \
    --cleaned-db data_analysis/output/cleaned_data.db \
    --output-dir data_analysis/output

# 4. 导出 Markdown 报告
python data_analysis/scripts/markdown_exporter.py \
    --template-dir data_analysis/templates \
    --data-dir data_analysis/output \
    --output-dir data_analysis/output/reports
```

### 增量更新

```bash
# 使用自动更新脚本（需先配置水印）
python data_analysis/scripts/auto_update.py \
    --version v3 \
    --db-dir output/decrypted_db \
    --output-dir data_analysis/output \
    --mode incremental
```

## 核心模块说明

### data_extractor.py - 数据提取框架

- **V3DataExtractor**: 适配微信 v3 的 MSG 表结构、Contact 表结构
- **V4DataExtractor**: 适配微信 v4 的分表结构、contact.db
- 统一输出为 `UnifiedMessage` / `UnifiedContact` / `ChatRoomInfo` 数据模型
- 支持全量提取和增量提取两种模式

### data_cleaner.py - 数据清洗框架

- **去重**: 基于 `server_id` 主键去重
- **时间戳校验**: 过滤 2010 年之前和未来 30 天后的异常时间
- **内容清洗**: 去除 ASCII 控制字符、填充类型默认内容、提取 URL
- **统计计算**: 自动生成 user_stats / talker_stats / daily_stats 汇总表
- 输出清洗报告 JSON

### profile_builder.py - 分析数据集构建器

- **UserProfileAnalyzer**: 计算用户时间模式、内容偏好、社交特征、自动生成标签
- **RelationGraphAnalyzer**: 构建群聊共现、回复互动、私聊三种关系边
- **ProjectTrackerAnalyzer**: 基于关键词和突发密度发现话题，推断话题状态
- 输出 `user_profiles.json` / `relation_graph.json` / `project_topics.json`

### markdown_exporter.py - Markdown 导出器

- 支持变量替换 `{{var}}`、循环 `{{#each}}`、条件 `{{#if}}`
- 生成用户画像、关系图谱、项目档案三种报告
- 自动生成 `profile_index.md` 索引页

## 数据字典

详见 [docs/数据字典.md](docs/数据字典.md)，包含：

- v3/v4 数据库字段映射对照表
- MessageType / ContactType 枚举定义
- 派生字段计算规则
- 数据质量校验规则
- 隐私脱敏策略

## 架构流程

详见 [docs/数据处理流程.md](docs/数据处理流程.md)，包含：

- 五层架构图（数据源层 → 解密层 → 提取层 → 清洗层 → 分析层 → 输出层）
- Mermaid 流水线流程图
- 中间数据库 Schema 定义
- JSON 数据集结构规范

## 维护策略

详见 [docs/数据更新维护策略.md](docs/数据更新维护策略.md)，包含：

- 增量更新机制与时间戳水印
- 定时任务配置（Windows 任务计划程序）
- 数据库快照与版本管理
- 存储空间清理策略
- 备份与灾难恢复流程
- 监控告警指标

## 扩展开发

### 新增分析维度

1. 在 `profile_builder.py` 中继承 `BaseAnalyzer`
2. 实现 `analyze()` 方法，返回分析结果
3. 在 `AnalysisDatasetBuilder.build_all()` 中调用新分析器
4. 在 `markdown_exporter.py` 中新增导出方法

```python
class NewAnalyzer(BaseAnalyzer):
    def analyze(self) -> dict:
        # 你的分析逻辑
        return result
```

### 新增 Markdown 模板

1. 在 `templates/` 目录下创建 `.md` 文件
2. 使用 `{{variable}}`、`{{#each list}}`、`{{#if cond}}` 语法
3. 在 `markdown_exporter.py` 中调用 `load_template()` 和 `render()`

## 注意事项

1. **微信必须运行**: 数据提取前确保微信客户端已登录运行（解密需要内存密钥）
2. **版本识别**: v3 和 v4 数据库结构差异大，务必指定正确版本
3. **隐私合规**: 分析结果包含个人社交数据，请注意存储和传输安全
4. **增量依赖**: 增量模式依赖 `watermark.json`，首次运行请使用全量模式

## 许可证

与 WeChatMsgArchive 主项目一致。
