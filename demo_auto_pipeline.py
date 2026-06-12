# -*- coding: utf-8 -*-
"""
AutoPipeline使用示例

演示如何在Claude会话中使用AutoPipeline进行自动化流程
"""

import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from .claude.auto_pipeline import AutoPipeline


def demo_auto_pipeline():
    """演示AutoPipeline的完整流程"""

    print("=" * 60)
    print("AutoPipeline 使用示例")
    print("=" * 60)

    # 1. 创建AutoPipeline实例
    pipeline = AutoPipeline()

    # 2. 运行流程（获取待执行的操作）
    output = pipeline.run(mode="manual")
    print(output)

    # 3. 检查是否有待创建的任务
    if hasattr(pipeline, 'pending_tasks') and pipeline.pending_tasks:
        print("\n" + "=" * 60)
        print("待创建的Kanban任务：")
        print("=" * 60)

        for task in pipeline.pending_tasks:
         print(f"\n任务 {task['temp_id']}:")
        print(f"  项目: {task['project']}")
       print(f"  标题: {task['title']}")
            print(f"  优先级: {task['priority']}")
            print(f"  标签: {', '.join(task['tags'])}")

            # 在Claude会话中，这里应该调用MCP工具：
            # mcp__kanban-doc__create_task(
            #     project=task['project'],
            #     title=task['title'],
            #     body=task['body'],
            #     priority=task['priority'],
            #     tags=task['tags']
            # )

    # 4. 检查是否有待启动的执行
    if hasattr(pipeline, 'pending_executions') and pipeline.pending_executions:
      print("\n" + "=" * 60)
        print("待启动的Agent执行：")
        print("=" * 60)

        for execution in pipeline.pending_executions:
            print(f"\n执行 {execution['temp_id']}:")
            print(f"  任务ID: {execution['task_id']}")
       print(f"  Agent: {execution['agent']}")

            # 在Claude会话中，这里应该调用Agent工具：
            # Agent(
            #     description=f"处理任务{execution['task_id']}",
            #     prompt=f"执行任务{execution['task_id']}",
            #     subagent_type=f"{execution['agent']}-secretary",
            #     run_in_background=True
            # )

    print("\n" + "=" * 60)
    print("提示：在Claude会话中使用时，需要实际调用MCP工具和Agent工具")
    print("=" * 60)


if __name__ == "__main__":
    demo_auto_pipeline()
