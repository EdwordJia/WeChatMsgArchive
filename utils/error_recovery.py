""
错误恢复和降级机制

提供统一的错误处理、重试、降级策略，提升系统稳定性。

特性：
- 自动重试（指数退避）
- 降级策略
- 断点续传
- 错误上下文保存
"""

import time
import logging
import functools
from typing import Callable, Optional, Any, Type, Tuple
from pathlib import Path
import pickle

logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    重试装饰器（指数退避）

    Args:
        max_retries: 最大重试次数
      initial_delay: 初始延迟（秒）
        backoff_factor: 退避因子
        exceptions: 需要重试的异常类型

    Example:
        @retry_with_backoff(max_retries=3, initial_delay=1.0)
        def unstable_api_call():
            # 可能失败的操作
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                  if attempt == max_retries:
                  logger.error(f"{func.__name__} 失败（已重试{max_retries}次）: {e}")
                   raise

                    logger.warning(
           f"{func.__name__} 失败（第{attempt + 1}次），"
               f"{delay:.1f}秒后重试: {e}"
                  )
              time.sleep(delay)
                  delay *= backoff_factor

        return wrapper
    return decorator


class FallbackStrategy:
    """降级策略基类"""

    def execute(self, *args, **kwargs) -> Any:
        """执行降级逻辑"""
        raise NotImplementedError


class CachedDataFallback(FallbackStrategy):
    """使用缓存数据降级"""

    def __init__(self, cache_path: str):
        self.cache_path = Path(cache_path)

    def execute(self, *args, **kwargs) -> Any:
        """从缓存读取数据"""
      if not self.cache_path.exists():
            raise FileNotFoundError(f"缓存文件不存在: {self.cache_path}")

      logger.info(f"使用缓存数据: {self.cache_path}")
        with open(self.cache_path, 'rb') as f:
            return pickle.load(f)


class RuleFallback(FallbackStrategy):
    """降级到规则模式"""

    def __init__(self, rule_func: Callable):
        self.rule_func = rule_func

    def execute(self, *args, **kwargs) -> Any:
        """执行规则函数"""
        logger.info("降级到规则模式")
        return self.rule_func(*args, **kwargs)


def with_fallback(fallback: FallbackStrategy):
  """
    降级装饰器

    Example:
        @with_fallback(CachedDataFallback("cache/data.pkl"))
        def fetch_data():
            # 可能失败的数据获取
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
           return func(*args, **kwargs)
            except Exception as e:
          logger.warning(f"{func.__name__} 失败，启动降级策略: {e}")
                try:
                    return fallback.execute(*args, **kwargs)
              except Exception as fallback_error:
            logger.error(f"降级策略也失败: {fallback_error}")
                  raise e  # 抛出原始异常

        return wrapper
    return decorator


class CheckpointManager:
    """断点续传管理器"""

    def __init__(self, checkpoint_dir: str = "output/checkpoints"):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def save_checkpoint(self, task_id: str, state: dict):
        """保存断点""
        checkpoint_path = self.checkpoint_dir / f"{task_id}.checkpoint"
        with open(checkpoint_path, 'wb') as f:
            pickle.dump(state, f)
        logger.info(f"✓ 断点已保存: {checkpoint_path}")

    def load_checkpoint(self, task_id: str) -> Optional[dict]:
        """加载断点"""
        checkpoint_path = self.checkpoint_dir / f"{task_id}.checkpoint"
        if not checkpoint_path.exists():
            return None

        with open(checkpoint_path, 'rb') as f:
            state = pickle.load(f)
        logger.info(f"✓ 断点已加载: {checkpoint_path}")
        return state

    def clear_checkpoint(self, task_id: str):
        """清除断点"""
     checkpoint_path = self.checkpoint_dir / f"{task_id}.checkpoint"
        if checkpoint_path.exists():
            checkpoint_path.unlink()
          logger.info(f"✓ 断点已清除: {checkpoint_path}")


class ErrorContext:
    """错误上下文管理器"""

    def __init__(self, context_file: str = "output/error_context.log"):
        self.context_file = Path(context_file)

  def save_context(self, error: Exception, context: dict):
        """保存错误上下文"""
        import json
        from datetime import datetime

        error_info = {
            "timestamp": datetime.now().isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context
      }

        with open(self.context_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(error_info, ensure_ascii=False) + "\n")

        logger.info(f"✓ 错误上下文已保存: {self.context_file}")


# 使用示例
if __name__ == "__main__":
    # 1. 重试示例
    @retry_with_backoff(max_retries=3, initial_delay=1.0)
    def unstable_operation():
        import random
        if random.random() < 0.7:
            raise ConnectionError("网络不稳定")
        return "成功"

    # 2. 降级示例
    def rule_based_analysis(message: str):
        return {"type": "rule", "result": "基于规则的分析"}

    @with_fallback(RuleFallback(rule_based_analysis))
    def llm_analysis(message: str):
        # 模拟 LLM API 调用失败
        raise TimeoutError("API 超时")

    # 3. 断点续传示例
    checkpoint_mgr = CheckpointManager()

    def batch_process(items: list, task_id: str):
        # 尝试加载断点
        checkpoint = checkpoint_mgr.load_checkpoint(task_id)
        start_index = checkpoint["index"] if checkpoint else 0

        for i in range(start_index, len(items)):
            try:
          # 处理项目
            process_item(items[i])

                # 保存断点
                checkpoint_mgr.save_checkpoint(task_id, {"index": i + 1})
            except Exception as e:
         logger.error(f"处理失败: {e}")
            # 断点已保存，下次可以从这里继续
           raise

      # 完成后清除断点
        checkpoint_mgr.clear_checkpoint(task_id)

    # 测试
    try:
        result = unstable_operation()
        print(f"重试成功: {result}")
    except Exception as e:
        print(f"重试失败: {e}")

    try:
        result = llm_analysis("测试消息")
        print(f"分析结果: {result}")
    except Exception as e:
      print(f"分析失败: {e}")
