#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信消息实时监控器 - 基于文件系统监听
替代30分钟轮询机制，实现秒级实时推送

技术方案：
1. 使用 watchdog 监听 MSG*.db 文件变化
2. 触发增量同步到索引数据库
3. 可选：触发 webhook 通知外部系统

性能目标：
- 新消息延迟 < 10秒
- CPU占用 < 5%
- 内存占用 < 100MB
"""

import os
import sys
import time
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileModifiedEvent
except ImportError:
    print("Error: watchdog not installed. Run: pip install watchdog")
    sys.exit(1)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
      logging.FileHandler('output/realtime_monitor.log'),
      logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class WeChatDBChangeHandler(FileSystemEventHandler):
    """微信数据库文件变化处理器"""

    def __init__(self, index_db_path: str, callback=None):
        super().__init__()
        self.index_db_path = index_db_path
        self.callback = callback
        self.last_sync_time = {}  # 防抖：记录每个文件的最后同步时间
        self.debounce_seconds = 5  # 防抖间隔：5秒内同一文件只触发一次

    def on_modified(self, event: FileModifiedEvent):
        """文件修改事件处理"""
        if event.is_directory:
            return
        file_path = event.src_path

        # 只处理 MSG*.db 文件
        if not (file_path.endswith('.db') and 'MSG' in os.path.basename(file_path)):
            return

        # 防抖：避免短时间内重复触发
        now = time.time()
        last_sync = self.last_sync_time.get(file_path, 0)
        if now - last_sync < self.debounce_seconds:
            return

        self.last_sync_time[file_path] = now

        logger.info(f"检测到数据库变化: {os.path.basename(file_path)}")

        try:
          # 执行增量同步
            new_messages = self._sync_incremental(file_path)

            if new_messages > 0:
           logger.info(f"✓ 同步完成: 新增 {new_messages} 条消息")

             # 触发回调（可用于 webhook 通知）
                if self.callback:
                    self.callback(file_path, new_messages)
       else:
           logger.debug(f"无新消息")

        except Exception as e:
            logger.error(f"同步失败: {e}", exc_info=True)

    def _sync_incremental(self, db_path: str) -> int:
        """
        增量同步：只同步新消息

        Returns:
        新增消息数量
        """
        # 获取索引数据库中该文件的最新消息时间戳
        last_timestamp = self._get_last_timestamp(db_path)

        # 从源数据库读取新消息
        new_messages = self._fetch_new_messages(db_path, last_timestamp)

        if not new_messages:
            return 0

        # 写入索引数据库
        self._insert_to_index(new_messages)

        return len(new_messages)

    def _get_last_timestamp(self, db_path: str) -> int:
        """获取索引数据库中该文件的最新消息时间戳"""
      conn = sqlite3.connect(self.index_db_path)
        cursor = conn.cursor()

        # 假设索引数据库有 source_db 字段记录来源
        db_name = os.path.basename(db_path)
        cursor.execute(
            "SELECT MAX(CreateTime) FROM messages WHERE source_db = ?",
            (db_name,)
        )
        result = cursor.fetchone()
        conn.close()

        return result[0] if result and result[0] else 0

    def _fetch_new_messages(self, db_path: str, after_timestamp: int) -> List[Dict[str, Any]]:
        """从源数据库读取新消息"""
        try:
            conn = sqlite3.connect(db_path)
          cursor = conn.cursor()

            # 查询新消息（时间戳大于 last_timestamp）
            cursor.execute("""
          SELECT
           localId, TalkerId, Type, SubType, IsSender,
                CreateTime, Sequence, StatusEx, FlagEx, Status,
                    MsgServerID, MsgSequence, StrTalker, StrContent,
            BytesExtra, CompressContent
                FROM MSG
                WHERE CreateTime > ?
                ORDER BY CreateTime ASC
            """, (after_timestamp,))

            columns = [desc[0] for desc in cursor.description]
            messages = []

            for row in cursor.fetchall():
           msg = dict(zip(columns, row))
            msg['source_db'] = os.path.basename(db_path)
                messages.append(msg)

            conn.close()
          return messages

        except sqlite3.Error as e:
            logger.error(f"读取数据库失败 {db_path}: {e}")
        return []

    def _insert_to_index(self, messages: List[Dict[str, Any]]):
        """批量插入到索引数据库"""
        conn = sqlite3.connect(self.index_db_path)
        cursor = conn.cursor()

        # 假设索引数据库表结构与源数据库一致，增加 source_db 字段
        for msg in messages:
            try:
             cursor.execute("""
                    INSERT OR IGNORE INTO messages (
                    localId, TalkerId, Type, SubType, IsSender,
                        CreateTime, Sequence, StatusEx, FlagEx, Status,
                    MsgServerID, MsgSequence, StrTalker, StrContent,
                   BytesExtra, CompressContent, source_db
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
              """, (
                    msg['localId'], msg['TalkerId'], msg['Type'], msg['SubType'],
               msg['IsSender'], msg['CreateTime'], msg['Sequence'],
                 msg['StatusEx'], msg['FlagEx'], msg['Status'],
             msg['MsgServerID'], msg['MsgSequence'], msg['StrTalker'],
                    msg['StrContent'], msg['BytesExtra'], msg['CompressContent'],
                  msg['source_db']
                ))
            except sqlite3.Error as e:
              logger.warning(f"插入消息失败: {e}")

        conn.commit()
        conn.close()


class RealtimeMonitor:
    """实时监控管理器"""

    def __init__(self, watch_dir: str, index_db_path: str):
        self.watch_dir = Path(watch_dir)
        self.index_db_path = index_db_path
        self.observer: Optional[Observer] = None

    def start(self, callback=None):
      """启动监控"""
      if not self.watch_dir.exists():
            raise FileNotFoundError(f"监控目录不存在: {self.watch_dir}")

        logger.info(f"启动实时监控: {self.watch_dir}")
        logger.info(f"索引数据库: {self.index_db_path}")

        # 创建事件处理器
        event_handler = WeChatDBChangeHandler(self.index_db_path, callback)

    # 创建观察者
        self.observer = Observer()
      self.observer.schedule(event_handler, str(self.watch_dir), recursive=True)
        self.observer.start()

    logger.info("✓ 监控已启动，等待文件变化...")

        try:
            while True:
            time.sleep(1)
        except KeyboardInterrupt:
         self.stop()

    def stop(self):
        """停止监控"""
        if self.observer:
            logger.info("正在停止监控...")
            self.observer.stop()
          self.observer.join()
            logger.info("✓ 监控已停止")


def main():
    """主函数"""
    # 配置路径（TODO: 从配置文件读取）
    DECRYPTED_DB_DIR = "output/decrypted_db/Multi"
    INDEX_DB_PATH = "output/wechat_index.db"

    # 创建监控器
    monitor = RealtimeMonitor(DECRYPTED_DB_DIR, INDEX_DB_PATH)

    # 可选：定义回调函数（用于 webhook 通知）
    def on_new_messages(db_path: str, count: int):
        """新消息回调""
        logger.info(f"[Webhook] 新消息通知: {os.path.basename(db_path)} +{count}")
    # TODO: 发送 HTTP 请求到外部系统

    # 启动监控
    monitor.start(callback=on_new_messages)


if __name__ == "__main__":
    main()
