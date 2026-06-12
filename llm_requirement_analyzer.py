# -*- coding: utf-8 -*-
"""LLM semantic requirement analyzer for WeChat messages and threads."""

import json
import logging
import os
import re
from typing import Dict, List, Optional

from anthropic import Anthropic

logger = logging.getLogger(__name__)


class LLMRequirementAnalyzer:
    """Analyze chat messages or conversation threads into structured requirements."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")
        self.base_url = base_url or os.getenv("ANTHROPIC_BASE_URL")
        self.model = model or os.getenv("ANTHROPIC_MODEL") or "claude-opus-4-20250514"

        if not self.api_key:
            logger.warning("未配置 ANTHROPIC_API_KEY 或 ANTHROPIC_AUTH_TOKEN，将使用规则模式")
            self.client = None
        elif self.base_url:
            logger.info("使用自定义 API 端点: %s, 模型: %s", self.base_url, self.model)
            self.client = Anthropic(api_key=self.api_key, base_url=self.base_url)
        else:
            logger.info("使用默认 Anthropic API, 模型: %s", self.model)
            self.client = Anthropic(api_key=self.api_key)

        self.bug_keywords = ["崩溃", "闪退", "报错", "失败", "不行", "无效", "异常", "bug", "用不了", "服务器问题", "无法", "出错", "卡住", "死机", "没反应", "丢了", "丢失", "错乱", "重复", "缺失", "不对", "有问题"]
        self.requirement_keywords = ["需要", "希望", "能不能", "建议", "增加", "优化", "改进", "可以吗", "能否", "支持", "新增", "调整", "修改", "改成", "改为", "替换", "应该", "麻烦", "还有", "对了"]

    def analyze_message(self, message: str, context: Optional[List[str]] = None) -> Dict:
        if self.client:
            return self._analyze_with_llm(message, context)
        return self._analyze_with_rules(message)

    def analyze_thread(self, thread: Dict) -> Dict:
        content = thread.get("content") or ""
        if self.client:
            result = self._analyze_with_llm(content, None, is_thread=True)
        else:
            result = self._analyze_with_rules(content)
        result["source_thread"] = thread
        result["source_message"] = thread.get("source_message") or thread
        result["message_count"] = thread.get("message_count", 1)
        return result

    def _analyze_with_llm(self, message: str, context: Optional[List[str]] = None, is_thread: bool = False) -> Dict:
        unit_name = "对话线程" if is_thread else "聊天消息"
        system_prompt = """你是一个专业的软件项目需求分析师，负责从客户聊天中识别可执行的软件需求、Bug反馈和交付反馈。

分析原则：
1. 优先理解上下文，不要把连续补充说明拆成多个重复需求。
2. 区分客户真实诉求、我方回复、闲聊、确认收货、催促和技术讨论。
3. 只在需要创建或更新开发任务时输出 is_requirement=true。
4. 如果是同一事项的多个细节，合并成一个任务描述。
5. 保留证据：描述中要包含客户表达、背景、验收标准。
6. 图片、XML、文件、语音、撤回、[无文本内容]只能作为证据，不能作为标题或需求正文。如果消息包含附件描述（如[图片]、[语音] 5.4秒、[文件] 文件名等），请将这些描述作为分析需求的上下文证据，不要忽略。
7. 标题必须是可执行事项，不要包含时间戳、发送人、XML片段或“无文本”。

类型分类：
- bug: 软件缺陷、错误、异常、不可用
- feature: 新功能需求
- enhancement: 现有功能改进
- feedback: 对已交付结果的反馈或验收意见
- urgency_signal: 催促、紧急排期、上线压力
- question: 咨询问题
- other: 无需开发动作

优先级：
- critical: 影响上线/生产/客户验收，需立即处理
- high: 重要需求或明确客户反馈
- medium: 普通改进
- low: 可延后或信息不足

输出格式要求（严格遵守）：
- 不要输出任何 JSON 之外的内容，不要输出 markdown 表格、列表、分析说明等额外内容。
- 直接输出纯 JSON 对象，不要用 ```json 代码块包裹。
- 确保 JSON 格式合法，可以被标准 JSON 解析器直接解析。

输出示例：
{"is_requirement": true, "type": "feature", "priority": "high", "title": "首页添加搜索功能", "description": "客户希望在首页增加搜索框...", "tags": ["feature"], "confidence": 0.85, "reasoning": "客户明确表达了搜索需求"}"""

        user_prompt = f"请分析以下{unit_name}：\n\n{message}"
        if context:
            user_prompt += "\n\n上下文消息：\n" + "\n".join(f"- {msg}" for msg in context[-3:])

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1200,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            content = self._extract_text(response)
            if not content:
                logger.error("无法从响应中提取文本内容")
                return self._analyze_with_rules(message)
            result = self._extract_json(content)
            if result is None:
                logger.error("LLM 响应中未找到有效 JSON")
                return self._analyze_with_rules(message)
            logger.info("✓ LLM 分析完成: %s | %s | 置信度 %.2f", result.get("type"), result.get("priority"), result.get("confidence", 0))
            return result
        except Exception as exc:
            logger.error("LLM API 调用失败: %s", exc)
            return self._analyze_with_rules(message)

    def _extract_json(self, text: str) -> Optional[Dict]:
        """从 LLM 响应文本中提取 JSON，支持 ```json 代码块或直接 JSON。"""
        if not text:
            return None
        # 尝试直接解析
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # 尝试提取 ```json ... ``` 代码块
        import re
        m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        # 尝试提取第一个 { ... } 块
        m = re.search(r"(\{.*\})", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        return None

    def _extract_text(self, response) -> Optional[str]:
        for block in response.content:
            if hasattr(block, "text"):
                return block.text
            if getattr(block, "type", None) == "text":
                return block.text
        return None

    def _meaningful_lines(self, message: str) -> List[str]:
        lines = []
        for raw in (message or "").splitlines():
            line = raw.strip()
            if not line or "[无文本内容]" in line:
                continue
            lower = line.lower()
            if lower.startswith("<?xml") or lower.startswith("<msg"):
                continue
            if any(token in lower for token in ("<img ", "<voicemsg", "<appmsg", "cdnthumburl=", "aeskey=")):
                continue
            # 保留附件描述行
            cleaned = re.sub(r"^[-*]\s+", "", line).strip()
            if cleaned.startswith(("[图片]", "[语音]", "[视频]", "[文件]", "[链接]", "[小程序]", "[合并转发聊天记录]", "[表情包]", "[系统消息]")):
                lines.append(cleaned)
                continue
            if any(marker in line for marker in ("图片/xml证据", "无文本/附件消息", "撤回消息证据", "[附件/多模态证据]")):
                continue
            line = re.sub(r"^\[[^\]]+\]\s*[^:：]{1,40}[:：]\s*", "", line).strip()
            line = re.sub(r"^#+\s*", "", line).strip()
            line = re.sub(r"^[-*]\s+", "", line).strip()
            line = re.sub(r"@\S+\s*", "", line).strip()
            if line in ("背景", "背景/问题", "客户原话", "客户原话/上下文", "验收标准", "原始证据摘要", "来源"):
                continue
            if line and len(line) >= 2:
                lines.append(line)
        return lines

    def _make_rule_title(self, lines: List[str], prefix: str = "") -> str:
        for line in lines:
            # 去掉附件描述前缀（如 [语音] 8.3秒 转文字: ...）
            cleaned = re.sub(r"^\[(图片|语音|视频|文件|链接|小程序|合并转发聊天记录|表情包|系统消息)\][^:：]*[：:]\s*", "", line).strip()
            # 去掉前缀后如果只剩文件路径，跳过
            cleaned = cleaned.rstrip("]")
            if re.search(r'[\\/][^\\/]+\.(png|jpg|jpeg|gif|webp|psd|pdf|doc|docx|xls|xlsx)$', cleaned, re.IGNORECASE):
                continue
            cleaned = re.sub(r"[。！？!?].*$", "", cleaned).strip(" ，,。]")
            cleaned = re.sub(r"^(这里|这个|那边|咱们|同时|就是)", "", cleaned).strip(" ，,。]") or cleaned
            if len(cleaned) > 48:
                cleaned = cleaned[:48].rstrip("，,。]")
            if cleaned:
                if prefix and not cleaned.startswith(prefix):
                    return prefix + cleaned
                return cleaned
        return ""

    def _rule_description(self, lines: List[str]) -> str:
        original = "\n".join(f"- {line}" for line in lines[:8])
        return "## 背景/客户原话\n" + original + "\n\n## 验收标准\n- 按客户反馈完成对应功能或缺陷修复\n- 相关页面/流程与客户描述一致"

    def _analyze_with_rules(self, message: str) -> Dict:
        logger.info("使用规则模式分析")
        lines = self._meaningful_lines(message)
        if not lines:
            return {
                "is_requirement": False,
                "type": "other",
                "priority": "low",
                "title": "",
                "description": "",
                "tags": [],
                "confidence": 0.2,
                "reasoning": "没有有效文本需求，只有附件或无文本消息",
            }
        text = "\n".join(lines)
        is_bug = any(kw in text for kw in self.bug_keywords)
        is_requirement = any(kw in text for kw in self.requirement_keywords)

        if is_bug:
            title = self._make_rule_title(lines, "修复")
            return {
                "is_requirement": bool(title),
                "type": "bug",
                "priority": "high",
                "title": title,
                "description": self._rule_description(lines),
                "tags": ["bug"],
                "confidence": 0.65,
                "reasoning": "基于有效文本关键词规则匹配",
            }
        if is_requirement:
            title = self._make_rule_title(lines)
            return {
                "is_requirement": bool(title),
                "type": "feature",
                "priority": "medium",
                "title": title,
                "description": self._rule_description(lines),
                "tags": ["feature"],
                "confidence": 0.6,
                "reasoning": "基于有效文本关键词规则匹配",
            }
        return {
            "is_requirement": False,
            "type": "other",
            "priority": "low",
            "title": "",
            "description": "",
            "tags": [],
            "confidence": 0.3,
            "reasoning": "未匹配到需求关键词",
        }

    def batch_analyze(self, messages: List[Dict[str, str]], threshold: float = 0.7) -> List[Dict]:
        results = []
        for i, msg in enumerate(messages):
            context = [m.get("content", "") for m in messages[max(0, i - 3):i]]
            result = self.analyze_message(msg.get("content", ""), context)
            if result.get("is_requirement") and result.get("confidence", 0) >= threshold:
                result["source_message"] = msg
                results.append(result)
        logger.info("✓ 批量分析完成: %d 条消息 → %d 个需求", len(messages), len(results))
        return results

    def batch_analyze_threads(self, threads: List[Dict], threshold: float = 0.7) -> List[Dict]:
        results = []
        for thread in threads:
            result = self.analyze_thread(thread)
            if result.get("is_requirement") and result.get("confidence", 0) >= threshold:
                results.append(result)
        logger.info("✓ 线程分析完成: %d 个线程 → %d 个需求", len(threads), len(results))
        return results


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    analyzer = LLMRequirementAnalyzer()
    sample_thread = {
        "content": "[2026-05-29 09:00:00] 客户: 这个页面颜色不对\n[2026-05-29 09:02:00] 我: 好的我看下\n[2026-05-29 09:04:00] 客户: Logo也换掉",
        "message_count": 3,
        "source_message": {"sender": "客户", "time": "2026-05-29 09:04:00"},
    }
    print(json.dumps(analyzer.analyze_thread(sample_thread), ensure_ascii=False, indent=2))
