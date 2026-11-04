---
id: mod-memo-ai
type: module-design
title: 本地 AI 聊天（MemoAI）
status: draft
parent: arch-overview
---

# 本地 AI 聊天（MemoAI）

## 职责

继承自上游 MemoTrace 的本地 AI 聊天组件，目标是低资源机器上可运行的微信聊天机器人：

- `qwen2-0.5b/`：基于 Qwen2-0.5B 的微调与部署套件——`app.py` 是 Gradio + DashInfer（CPU 推理）聊天应用，人设为"微信聊天机器人"；`di_config.json` 为推理引擎配置（Qwen_v20、CPU、`./dashinfer_models/`）；`train.md` / `train.ipynb` 是 ModelScope 免费 GPU 上的微调教程；`requirements.txt` 为依赖清单。部署流程文档见 `doc/ai-qwen/readme.md`。
- `api_server.py`：OpenAI 兼容格式的 FastAPI 问答 API（`/v1/chat/completions`、`/v1/models`、`/v1/embeddings`，支持流式）。
- `merge_json.py`：把导出的聊天记录 JSON 合并为微调用的 train/dev 数据集（训练数据准备，非运行时依赖）。
- `readme.md`：上游的大模型训练指南（ChatGLM 时代文档，含历史截图路径）。

## 边界

- **独立运行**：与解密、同步、分析、导出模块无代码级依赖，架构图中无依赖边；仅供本机/个人使用。
- 不消费微信明文库，也不产出供其他模块使用的数据；聊天记录 JSON 由 exporter 侧人工导出后喂给 `merge_json.py`。

## 已知出入（诚实声明）

- `api_server.py` 的文件头与默认环境变量指向 **ChatGLM3-6B**（上游遗留），且其 `from utils import ...` 在本仓库根目录 `utils/` 下找不到对应实现——该脚本的模型与依赖是否实际可用**（未确认）**。当前可工作的 Qwen2 路径是 `qwen2-0.5b/` 的 Gradio/DashInfer 应用。
- "api_server 基于本地 Qwen2-0.5b"的说法与代码不符：Qwen2 模型在 `qwen2-0.5b/app.py`，`api_server.py` 本身是 ChatGLM 风格**（未确认是否为待改造目标）**。
