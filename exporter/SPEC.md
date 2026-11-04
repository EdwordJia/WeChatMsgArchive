---
id: mod-exporter
type: module-design
title: 多格式导出器（exporter）
status: draft
parent: arch-overview
depends-on:
  - mod-wxmanager
---

# 多格式导出器（exporter）

## 职责

继承自上游的统一导出层：把微信消息与联系人导出为人类可读与机器可读的文件。当前支持 HTML、CSV、DOCX、TXT、JSON、Markdown、XLSX、AI 友好文本（`exporter_ai_txt.py`）。

## 结构约定

- `exporter.py` 定义 `ExporterBase` 基类与共享辅助逻辑（目录创建、资源复制、音频转码、文件名去重），并做统一调度。
- 每种格式一个 `exporter_<fmt>.py`，实现各自的 `export()`；`__init__.py` 汇总暴露各导出器；`config.py` 定义 `FileType` 枚举；`resources/` 存放 HTML 模板、emoji 与图标资源；自带 `ffmpeg.exe` 用于语音（silk）转码。

## 边界

- **导出格式只在这里扩展**：新导出需求新增 `exporter_*.py`，分析脚本不得自行生成 HTML/DOCX（架构不变量 3）。
- 输入是 `wxManager` 解密后的数据（`Message` / `Contact` / `Me` / `DataBaseInterface`），**不直接读加密库**；仅复用 `wxManager.decrypt.decrypt_dat` 的图片解码能力处理 `.dat` 图片资源。
- 不含任何分析逻辑；导出是数据流向"消费层"的终点，分析结论不走本模块。
