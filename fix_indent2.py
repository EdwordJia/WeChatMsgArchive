#!/usr/bin/env python3
import sys

with open('wechat_realtime_monitor.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

fixed = [
    '        try:\n',
    '            # 执行增量同步\n',
    '            new_messages = self._sync_incremental(file_path)\n',
    '\n',
    '            if new_messages > 0:\n',
    '      logger.info(f"✓ 同步完成: 新增 {new_messages} 条消息")\n',
    '\n',
    '                # 触发回调（可用于 webhook 通知）\n',
    '         if self.callback:\n',
    '                 self.callback(file_path, new_messages)\n',
    '            else:\n',
    '                logger.debug(f"无新消息")\n',
    '\n',
    '        except Exception as e:\n',
    '            logger.error(f"同步失败: {e}", exc_info=True)\n',
]

new_lines = lines[:75] + fixed + lines[90:]

with open('wechat_realtime_monitor.py', 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(new_lines)

print('OK')
