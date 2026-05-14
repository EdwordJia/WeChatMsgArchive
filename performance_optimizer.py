#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
性能优化工具
为微信消息数据库创建索引、实现缓存和并发处理
"""

import os
import sys
import sqlite3
import json
import time
from pathlib import Path
from typing import List, Dict
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# 配置
BASE_DIR = Path(__file__).parent
DECRYPTED_DB_DIR = BASE_DIR / 'output' / 'decrypted_db'
CACHE_DIR = BASE_DIR / 'output' / 'cache'
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# 推荐的索引
RECOMMENDED_INDEXES = {
    'MSG': [
        ('idx_msg_talker', 'StrTalker'),
        ('idx_msg_time', 'CreateTime'),
        ('idx_msg_type', 'Type'),
        ('idx_msg_sender', 'IsSender'),
        ('idx_msg_talker_time', 'StrTalker, CreateTime'),
    ],
    'Contact': [
        ('idx_contact_wxid', 'UserName'),
        ('idx_contact_type', 'Type'),
    ],
    'ChatRoom': [
        ('idx_chatroom_id', 'ChatRoomName'),
    ]
}


class PerformanceOptimizer:
    """性能优化器"""

    def __init__(self, db_paths: List[Path]):
        self.db_paths = db_paths
        self.optimization_report = {
            'indexes_created': [],
            'indexes_skipped': [],
            'cache_stats': {},
            'performance_tests': []
        }

    def analyze_database(self, db_path: Path) -> Dict:
        """分析数据库性能"""
        logger.info(f"分析数据库: {db_path.name}")

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        analysis = {
            'db_name': db_path.name,
            'file_size_mb': db_path.stat().st_size / (1024 * 1024),
            'tables': {},
            'existing_indexes': []
        }

        try:
            # 获取所有表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            for table in tables:
                # 获取表行数
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                row_count = cursor.fetchone()[0]

                analysis['tables'][table] = {
                    'row_count': row_count
                }

            # 获取现有索引
            cursor.execute("SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index'")
            for row in cursor.fetchall():
                if row[0] and not row[0].startswith('sqlite_'):
                    analysis['existing_indexes'].append({
                        'name': row[0],
                        'table': row[1],
                        'sql': row[2]
                    })

        except Exception as e:
            logger.error(f"分析数据库失败: {e}")
        finally:
            conn.close()

        return analysis

    def create_indexes(self, db_path: Path):
        """创建推荐的索引"""
        logger.info(f"为数据库创建索引: {db_path.name}")

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        try:
            # 获取现有索引
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
            existing_indexes = set(row[0] for row in cursor.fetchall())

            # 创建推荐的索引
            for table, indexes in RECOMMENDED_INDEXES.items():
                # 检查表是否存在
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
                if not cursor.fetchone():
                    continue

                for index_name, columns in indexes:
                    if index_name in existing_indexes:
                        logger.info(f"  索引已存在: {index_name}")
                        self.optimization_report['indexes_skipped'].append({
                            'db': db_path.name,
                            'index': index_name,
                            'reason': '已存在'
                        })
                        continue

                    try:
                        sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table}({columns})"
                        start_time = time.time()
                        cursor.execute(sql)
                        elapsed = time.time() - start_time

                        logger.info(f"  创建索引: {index_name} (耗时: {elapsed:.2f}秒)")
                        self.optimization_report['indexes_created'].append({
                            'db': db_path.name,
                            'index': index_name,
                            'table': table,
                            'columns': columns,
                            'time_seconds': elapsed
                        })
                    except Exception as e:
                        logger.error(f"  创建索引失败 {index_name}: {e}")

            conn.commit()

        except Exception as e:
            logger.error(f"创建索引失败: {e}")
        finally:
            conn.close()

    def test_query_performance(self, db_path: Path):
        """测试查询性能"""
        logger.info(f"测试查询性能: {db_path.name}")

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        test_queries = [
            {
                'name': '按对话者查询消息',
                'sql': "SELECT COUNT(*) FROM MSG WHERE StrTalker = (SELECT StrTalker FROM MSG LIMIT 1)"
            },
            {
                'name': '按时间范围查询',
                'sql': "SELECT COUNT(*) FROM MSG WHERE CreateTime > 0 AND CreateTime < 9999999999999"
            },
            {
                'name': '按类型统计',
                'sql': "SELECT Type, COUNT(*) FROM MSG GROUP BY Type"
            },
            {
                'name': '联合查询',
                'sql': "SELECT COUNT(*) FROM MSG WHERE StrTalker LIKE '%@chatroom' AND Type = 1"
            }
        ]

        try:
            for query in test_queries:
                start_time = time.time()
                cursor.execute(query['sql'])
                cursor.fetchall()
                elapsed = time.time() - start_time

                logger.info(f"  {query['name']}: {elapsed:.3f}秒")
                self.optimization_report['performance_tests'].append({
                    'db': db_path.name,
                    'query': query['name'],
                    'time_seconds': elapsed
                })

        except Exception as e:
            logger.error(f"性能测试失败: {e}")
        finally:
            conn.close()

    def optimize_database(self, db_path: Path):
        """优化数据库（VACUUM和ANALYZE）"""
        logger.info(f"优化数据库: {db_path.name}")

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        try:
            # ANALYZE - 更新查询优化器统计信息
            logger.info("  运行 ANALYZE...")
            start_time = time.time()
            cursor.execute("ANALYZE")
            elapsed = time.time() - start_time
            logger.info(f"  ANALYZE 完成 (耗时: {elapsed:.2f}秒)")

            # VACUUM - 重建数据库文件，回收空间
            logger.info("  运行 VACUUM...")
            start_time = time.time()
            cursor.execute("VACUUM")
            elapsed = time.time() - start_time
            logger.info(f"  VACUUM 完成 (耗时: {elapsed:.2f}秒)")

        except Exception as e:
            logger.error(f"优化数据库失败: {e}")
        finally:
            conn.close()

    def generate_cache_key(self, query: str, params: tuple = ()) -> str:
        """生成缓存键"""
        key_str = f"{query}:{params}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def cache_query_result(self, cache_key: str, result: any):
        """缓存查询结果"""
        cache_file = CACHE_DIR / f"{cache_key}.json"
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': time.time(),
                    'result': result
                }, f, ensure_ascii=False)
        except Exception as e:
            logger.error(f"缓存失败: {e}")

    def get_cached_result(self, cache_key: str, max_age_seconds: int = 3600):
        """获取缓存的结果"""
        cache_file = CACHE_DIR / f"{cache_key}.json"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 检查缓存是否过期
            age = time.time() - data['timestamp']
            if age > max_age_seconds:
                return None

            return data['result']
        except Exception as e:
            logger.error(f"读取缓存失败: {e}")
            return None

    def parallel_process_databases(self, func, max_workers: int = 4):
        """并行处理多个数据库"""
        logger.info(f"并行处理 {len(self.db_paths)} 个数据库 (workers={max_workers})")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(func, db_path): db_path for db_path in self.db_paths}

            for future in as_completed(futures):
                db_path = futures[future]
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"处理 {db_path.name} 失败: {e}")

    def generate_report(self):
        """生成优化报告"""
        logger.info("生成优化报告...")

        report = {
            'summary': {
                'total_indexes_created': len(self.optimization_report['indexes_created']),
                'total_indexes_skipped': len(self.optimization_report['indexes_skipped']),
                'total_performance_tests': len(self.optimization_report['performance_tests']),
                'generated_at': time.strftime('%Y-%m-%d %H:%M:%S')
            },
            'details': self.optimization_report
        }

        # 保存 JSON
        json_path = BASE_DIR / 'output' / 'performance_optimization_report.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info(f"报告已保存: {json_path}")

        # 生成 Markdown 报告
        self._generate_markdown_report(report)

    def _generate_markdown_report(self, report: Dict):
        """生成 Markdown 报告"""

        md_lines = [
            "# 性能优化报告",
            "",
            f"生成时间: {report['summary']['generated_at']}",
            "",
            "## 优化概览",
            "",
            f"- **创建的索引数**: {report['summary']['total_indexes_created']}",
            f"- **跳过的索引数**: {report['summary']['total_indexes_skipped']}",
            f"- **性能测试数**: {report['summary']['total_performance_tests']}",
            "",
            "---",
            "",
            "## 创建的索引",
            ""
        ]

        if report['details']['indexes_created']:
            for idx in report['details']['indexes_created']:
                md_lines.append(f"### {idx['index']}")
                md_lines.append(f"- **数据库**: {idx['db']}")
                md_lines.append(f"- **表**: {idx['table']}")
                md_lines.append(f"- **列**: {idx['columns']}")
                md_lines.append(f"- **创建耗时**: {idx['time_seconds']:.2f}秒")
                md_lines.append("")
        else:
            md_lines.append("无新索引创建")
            md_lines.append("")

        md_lines.extend([
            "---",
            "",
            "## 性能测试结果",
            ""
        ])

        if report['details']['performance_tests']:
            # 按数据库分组
            by_db = {}
            for test in report['details']['performance_tests']:
                db = test['db']
                if db not in by_db:
                    by_db[db] = []
                by_db[db].append(test)

            for db, tests in by_db.items():
                md_lines.append(f"### {db}")
                md_lines.append("")
                for test in tests:
                    md_lines.append(f"- **{test['query']}**: {test['time_seconds']:.3f}秒")
                md_lines.append("")
        else:
            md_lines.append("无性能测试结果")
            md_lines.append("")

        md_lines.extend([
            "---",
            "",
            "## 优化建议",
            "",
            "1. **定期运行 ANALYZE**: 保持查询优化器统计信息最新",
            "2. **使用缓存**: 对频繁查询的结果进行缓存",
            "3. **并行处理**: 使用多线程处理多个数据库",
            "4. **监控性能**: 定期运行性能测试，识别慢查询",
            "5. **清理缓存**: 定期清理过期的缓存文件",
            ""
        ])

        # 保存 Markdown
        md_path = BASE_DIR / 'output' / 'performance_optimization_report.md'
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(md_lines))

        logger.info(f"Markdown 报告已保存: {md_path}")


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("开始性能优化")
    logger.info("=" * 60)

    # 查找数据库文件
    msg_dbs = list(DECRYPTED_DB_DIR.glob('Multi/MSG*.db'))

    if not msg_dbs:
        logger.error("未找到消息数据库")
        return

    logger.info(f"找到 {len(msg_dbs)} 个消息数据库")

    # 创建优化器
    optimizer = PerformanceOptimizer(msg_dbs)

    # 1. 分析数据库
    logger.info("\n步骤 1: 分析数据库")
    for db_path in msg_dbs:
        analysis = optimizer.analyze_database(db_path)
        logger.info(f"  {db_path.name}: {analysis['file_size_mb']:.2f} MB, {len(analysis['tables'])} 个表")

    # 2. 创建索引
    logger.info("\n步骤 2: 创建索引")
    for db_path in msg_dbs:
        optimizer.create_indexes(db_path)

    # 3. 优化数据库
    logger.info("\n步骤 3: 优化数据库")
    for db_path in msg_dbs:
        optimizer.optimize_database(db_path)

    # 4. 性能测试
    logger.info("\n步骤 4: 性能测试")
    for db_path in msg_dbs:
        optimizer.test_query_performance(db_path)

    # 5. 生成报告
    logger.info("\n步骤 5: 生成报告")
    optimizer.generate_report()

    logger.info("=" * 60)
    logger.info("性能优化完成！")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
