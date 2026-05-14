#!/usr/bin/env python3
# 修复 wechat_realtime_monitor.py 的缩进问题

with open('wechat_realtime_monitor.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 修复第76-90行（索引75-89）
fixes = {
    75: '        try:\n',
    76: '            # 执行增量同步\n',
    77: '            new_messages = self._sync_incremental(file_path)\n',
    78: '\n',
    79: '       if new_messages > 0:\n',
  80: '                logger.info(f"✓ 同步完成: 新增 {new_messages} 条消息")\n',
    81: '\n',
    82: '           # 触发回调（可用于 webhook 通知）\n',
    83: '                if self.callback:\n',
    84: '                  self.callback(file_path, new_messages)\n',
    85: '            else:\n',
    86: '            logger.debug(f"无新消息")\n',
    87: '\n',
    88: '        except Exception as e:\n',
    89: '            logger.error(f"同步失败: {e}", exc_info=True)\n',
}

for idx, new_line in fixes.items():
    lines[idx] = new_line

with open('wechat_realtime_monitor.py', 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(lines)

print('Indentation fixed successfully')
