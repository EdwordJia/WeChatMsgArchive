---
id: mod-llm-pipeline
type: module-design
title: LLM 辅助分析流水线
status: draft
parent: arch-overview
depends-on:
  - mod-config
---

# LLM 辅助分析流水线

## 职责

用 LLM 对消息数据做语义级分析与自动化，打通「微信群消息 → 识别需求 → Kanban 任务 → Agent 执行」链路：

- **LLM 语义需求收集**：`llm_requirement_analyzer.py`（LLM 需求分析器，Anthropic 协议，未配置密钥时降级为规则模式）+ `auto_requirement_collector.py`（从群聊消息中自动识别需求/反馈），Root 下另有 `create_kanban_tasks.py` 读取待办任务 JSON 并经 kanban-doc MCP 创建任务。
- **自动流水线**：`.claude/` 下的 `auto_pipeline.py`、`project_manager.py`（AI 项目经理，单会话管理所有 agent）、`daily_sync.py`（每日状态恢复入口）、`process_runtime_queue.py`（runtime_queue 桥接，产出报告供会话审批/启动）等；`dedup_state.py` 提供消息与需求的状态去重，保证流水线幂等。
- **看板产出**：`kanban_writer.py` 把任务直接写盘到 `.kanban` 看板目录（kanban-doc 格式）。

LLM 支持 DeepSeek / Claude 等 Anthropic 兼容协议，经 base_url / model / api_key 配置切换。

## 输入

- 已同步/已分析的消息数据（明文库、线程、需求中间产物）；LLM 配置与密钥。

## 输出

- 结构化需求/商机 JSON、看板任务文件（`.kanban/`）、流水线运行报告。

## 边界

- LLM 密钥与端点经配置显式提供（环境变量 + mod-config 的配置加载），**不走硬编码**；无密钥时降级为规则模式而非报错。
- 本模块不直接解密，输入一律是上游已同步/已分析的明文数据。
- `.claude/` 下的 `xhs_*` 系列（小红书采集/OCR 脚本）属临时业务采集，不在本模块边界内。
- `.claude/` 中的其他杂项脚本（如 WAL 合并、群成员探查）是否属于流水线本体未逐一确认（未确认）。
