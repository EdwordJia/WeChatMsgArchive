"""
LLM 语义分析需求识别器

替代关键词规则，使用 Claude API 进行深度语义理解：
1. 识别隐含需求和情绪
2. 自动判定优先级
3. 生成结构化任务描述
4. 支持多轮对话澄清需求

性能目标：
- 识别准确率 > 85%
- API 调用成本可控
- 支持离线降级到规则模式
"""

import os
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from anthropic import Anthropic

logger = logging.getLogger(__name__)


class LLMRequirementAnalyzer:
    """基于 LLM 的需求分析器"""

    def __init__(self, api_key: Optional[str] = None):
      """
      初始化分析器

    Args:
            api_key: Anthropic API Key（默认从环境变量读取）
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            logger.warning("未配置 ANTHROPIC_API_KEY，将使用规则模式")
            self.client = None
        else:
       self.client = Anthropic(api_key=self.api_key)

        # 规则模式的关键词（作为降级方案）
      self.bug_keywords = ["崩溃", "闪退", "报错", "失败", "不行", "无效", "异常", "bug"]
        self.requirement_keywords = ["需要", "希望", "能不能", "建议", "增加", "优化", "改进"]

    def analyze_message(self, message: str, context: Optional[List[str]] = None) -> Dict:
        """
        分析消息，识别需求/Bug

        Args:
            message: 待分析的消息内容
        context: 上下文消息列表（可选）

        Returns:
            {
              "is_requirement": bool,
            "type": "bug" | "feature" | "enhancement" | "question" | "other",
             "priority": "critical" | "high" | "medium" | "low",
                "title": str,
                "description": str,
                "tags": List[str],
             "confidence": float,  # 0-1
                "reasoning": str  # 分析理由
            }
        """
        if self.client:
            return self._analyze_with_llm(message, context)
        else:
          return self._analyze_with_rules(message)

    def _analyze_with_llm(self, message: str, context: Optional[List[str]] = None) -> Dict:
        """使用 Claude API 进行语义分析"""

        # 构建 Prompt
        system_prompt = """你是一个专业的需求分析师，负责从用户的聊天消息中识别软件需求和Bug。

分析维度：
1. **是否为需求/Bug**: 判断消息是否包含软件开发相关的需求、Bug报告或改进建议
2. **类型分类**:
   - bug: 软件缺陷、错误、异常
   - feature: 新功能需求
   - enhancement: 现有功能改进
   - question: 咨询问题
   - other: 其他

3. **优先级判定**:
   - critical: 严重影响使用，需立即处理
   - high: 重要但不紧急
   - medium: 一般优先级
   - low: 可延后处理

4. **生成任务描述**: 提取关键信息，生成结构化的任务标题和描述

输出格式（JSON）：
{
  "is_requirement": true/false,
  "type": "bug|feature|enhancement|question|other",
  "priority": "critical|high|medium|low",
  "title": "简洁的任务标题（<50字）",
  "description": "详细描述，包括背景、需求、验收标准",
  "tags": ["标签1", "标签2"],
  "confidence": 0.0-1.0,
  "reasoning": "分析理由"
}"""

        user_prompt = f"请分析以下消息：\n\n{message}"

        if context:
            user_prompt += f"\n\n上下文消息：\n" + "\n".join(f"- {msg}" for msg in context[-3:])

        try:
            response = self.client.messages.create(
                model="claude-opus-4-20250514",
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
       )

            # 解析 JSON 响应
            content = response.content[0].text
            result = json.loads(content)

            logger.info(f"✓ LLM 分析完成: {result['type']} | {result['priority']} | 置信度 {result['confidence']:.2f}")
            return result

        except json.JSONDecodeError as e:
        logger.error(f"LLM 响应解析失败: {e}")
            return self._analyze_with_rules(message)
        except Exception as e:
            logger.error(f"LLM API 调用失败: {e}")
            return self._analyze_with_rules(message)

    def _analyze_with_rules(self, message: str) -> Dict:
        """规则模式（降级方案）"""
        logger.info("使用规则模式分析")

        is_bug = any(kw in message for kw in self.bug_keywords)
        is_requirement = any(kw in message for kw in self.requirement_keywords)

        if is_bug:
            return {
                "is_requirement": True,
            "type": "bug",
              "priority": "high",
            "title": f"Bug: {message[:30]}...",
                "description": message,
           "tags": ["bug"],
             "confidence": 0.6,
                "reasoning": "基于关键词规则匹配"
       }
        elif is_requirement:
            return {
                "is_requirement": True,
         "type": "feature",
                "priority": "medium",
        "title": f"需求: {message[:30]}...",
             "description": message,
           "tags": ["feature"],
         "confidence": 0.5,
                "reasoning": "基于关键词规则匹配"
            }
        else:
            return {
                "is_requirement": False,
                "type": "other",
                "priority": "low",
         "title": "",
                "description": ",
                "tags": [],
                "confidence": 0.3,
                "reasoning": "未匹配到需求关键词"
            }

    def batch_analyze(self, messages: List[Dict[str, str]], threshold: float = 0.7) -> List[Dict]:
      """
        批量分析消息

        Args:
          messages: 消息列表 [{"content": "...", "sender": "...", "time": "..."}]
            threshold: 置信度阈值，低于此值的结果将被过滤
        Returns:
            识别出的需求列表
        """
        results = []

        for i, msg in enumerate(messages):
            # 提取上下文（前3条消息）
            context = [m["content"] for m in messages[max(0, i-3):i]]

            result = self.analyze_message(msg["content"], context)

            # 过滤低置信度结果
          if result["is_requirement"] and result["confidence"] >= threshold:
         result["source_message"] = msg
            results.append(result)

        logger.info(f"✓ 批量分析完成: {len(messages)} 条消息 → {len(results)} 个需求")
        return results


# 使用示例
if __name__ == "__main__":
    analyzer = LLMRequirementAnalyzer()

    # 单条消息分析
    message = "播放器经常崩溃，点击下一首就闪退，能不能修复一下？"
    result = analyzer.analyze_message(message)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 批量分析
    messages = [
        {"content": "这个功能不错，但是能不能增加歌词显示？", "sender": "用户A", "time": "2026-05-12 10:00"},
        {"content": "好的，我记录下来", "sender": "我", "time": "2026-05-12 10:01"},
        {"content": "还有，播放列表能不能支持拖拽排序？", "sender": "用户A", "time": "2026-05-12 10:02"},
    ]
    results = analyzer.batch_analyze(messages, threshold=0.6)
    print(f"\n识别到 {len(results)} 个需求")
