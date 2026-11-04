---
id: mod-analysis
type: module-design
title: 消息分析与洞察
status: draft
parent: arch-overview
depends-on:
  - mod-sync-monitor
references:
  - mod-data-analysis
---

# 消息分析与洞察

## 职责

在明文库与消息索引之上做价值挖掘，把原始消息变成可读的分析结论：

- `wechat_msg_reader.py`：消息读取层，分析侧的统一取数入口（含昵称缓存、附件解析）。
- `message_threader.py`：消息串线，把群消息按时间与频道还原为会话线程，供需求分析使用。
- `user_profiling.py`：用户画像——行为统计、兴趣标签（jieba 分词 + 关键词提取）、情感倾向。
- `social_graph_analysis.py`：关系图谱——群聊共现与私聊关系，基于 networkx 构建社交网络并分析社区结构。
- `business_opportunity.py`：商机识别，从聊天记录中识别可商业化的项目机会。
- `project_tracker.py`：副业项目追踪，按关键词词典识别和跟踪项目线索。

## 输入

- mod-sync-monitor 产出的明文库（`output/decrypted_db/`）与索引库（`output/wechat_index.db`）。

## 输出

- Markdown/JSON 分析报告与结构化结果，均写到 `output/` 下各自的分析目录（如 `output/user_profiles/`、`output/social_graph/`）。

## 边界

- **只读明文库，不做解密**；解密归 mod-wxmanager。
- 新分析应优先复用标准数据层 data_analysis（spec id `mod-data-analysis`，已收编于 `data_analysis/docs/数据处理流程.md`），不重复造取数与清洗逻辑。
- 商机/项目的关键词与词典目前内嵌在各脚本中，尚未抽取到统一配置（未确认是否有此计划）。
