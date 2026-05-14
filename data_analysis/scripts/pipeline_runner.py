#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
流水线统一入口 - WeChatMsgArchive 数据分析

一键执行完整的数据处理流水线：
提取 -> 清洗 -> 分析 -> 导出

用法:
    python pipeline_runner.py --version v3 --db-dir output/decrypted_db
    python pipeline_runner.py --version v3 --db-dir output/decrypted_db --mode incremental
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime

# 确保可以导入同级模块
sys.path.insert(0, str(Path(__file__).resolve().parent))

from data_extractor import create_extractor, run_full_extraction
from data_cleaner import run_cleaning
from profile_builder import run_build_analysis
from markdown_exporter import run_export

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def load_watermark(output_dir: str) -> dict:
    """读取水印文件"""
    path = Path(output_dir) / 'watermark.json'
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_watermark(output_dir: str, watermark: dict):
    """保存水印文件"""
    path = Path(output_dir) / 'watermark.json'
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(watermark, f, ensure_ascii=False, indent=2)


def run_pipeline(version: str, db_dir: str, output_dir: str,
                 mode: str = 'full', talkers: list = None):
    """
    执行完整流水线
    
    Args:
        version: 'v3' 或 'v4'
        db_dir: 解密后的数据库目录
        output_dir: 输出目录
        mode: 'full' 全量, 'incremental' 增量
        talkers: 指定提取的聊天对象
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    unified_db = output_path / f'unified_data_{version}.db'
    cleaned_db = output_path / 'cleaned_data.db'
    report_path = output_path / 'clean_report.json'
    data_dir = output_path
    report_dir = output_path / 'reports'
    template_dir = Path(__file__).resolve().parent.parent / 'templates'
    
    watermark = load_watermark(output_dir)
    incremental_after = watermark.get('last_extract_time', 0) if mode == 'incremental' else 0
    
    logger.info("=" * 70)
    logger.info(f"启动数据分析流水线 [{mode} 模式]")
    logger.info(f"版本: {version} | 输入: {db_dir} | 输出: {output_dir}")
    if mode == 'incremental':
        logger.info(f"增量阈值: {incremental_after} ({datetime.fromtimestamp(incremental_after)})")
    logger.info("=" * 70)
    
    # 步骤1: 数据提取
    logger.info("\n>>> 步骤 1/4: 数据提取")
    if mode == 'full' or not unified_db.exists():
        run_full_extraction(version, db_dir, str(output_path), talkers)
    else:
        # 增量提取
        extractor = create_extractor(version, db_dir, str(output_path))
        try:
            extractor.init_db()
            extractor.extract_contacts()
            extractor.extract_chatrooms()
            extractor.extract_messages(talker_ids=talkers, incremental_after=incremental_after)
        finally:
            extractor.close()
    
    if not unified_db.exists():
        logger.error("提取失败，未生成统一数据库")
        return False
    
    # 步骤2: 数据清洗
    logger.info("\n>>> 步骤 2/4: 数据清洗")
    report = run_cleaning(str(unified_db), str(cleaned_db), str(report_path))
    
    if not cleaned_db.exists():
        logger.error("清洗失败，未生成清洗数据库")
        return False
    
    # 步骤3: 构建分析数据集
    logger.info("\n>>> 步骤 3/4: 构建分析数据集")
    run_build_analysis(str(cleaned_db), str(data_dir))
    
    # 步骤4: 导出 Markdown
    logger.info("\n>>> 步骤 4/4: 导出 Markdown 报告")
    if template_dir.exists():
        run_export(str(template_dir), str(data_dir), str(report_dir))
    else:
        logger.warning(f"模板目录不存在: {template_dir}")
    
    # 更新水印
    new_watermark = {
        'last_extract_time': int(datetime.now().timestamp()),
        'version': version,
        'mode': mode,
        'updated_at': datetime.now().isoformat()
    }
    save_watermark(output_dir, new_watermark)
    
    logger.info("\n" + "=" * 70)
    logger.info("流水线执行完成!")
    logger.info(f"输出目录: {output_dir}")
    logger.info(f"  - 统一数据库: {unified_db}")
    logger.info(f"  - 清洗数据库: {cleaned_db}")
    logger.info(f"  - 清洗报告: {report_path}")
    logger.info(f"  - 分析数据: {data_dir}/*.json")
    logger.info(f"  - Markdown 报告: {report_dir}/")
    logger.info("=" * 70)
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description='WeChatMsgArchive 数据分析流水线',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 全量运行
  python pipeline_runner.py --version v3 --db-dir output/decrypted_db
  
  # 增量更新
  python pipeline_runner.py --version v3 --db-dir output/decrypted_db --mode incremental
  
  # 只分析指定群聊
  python pipeline_runner.py --version v3 --db-dir output/decrypted_db --talkers xxx@chatroom
        """
    )
    parser.add_argument('--version', choices=['v3', 'v4'], required=True,
                        help='微信数据库版本')
    parser.add_argument('--db-dir', required=True,
                        help='解密后的数据库目录路径')
    parser.add_argument('--output-dir', default='data_analysis/output',
                        help='输出目录（默认: data_analysis/output）')
    parser.add_argument('--mode', choices=['full', 'incremental'], default='full',
                        help='运行模式: full=全量, incremental=增量（默认: full）')
    parser.add_argument('--talkers', nargs='+',
                        help='指定分析的聊天对象 wxid（默认全部）')
    
    args = parser.parse_args()
    
    success = run_pipeline(
        version=args.version,
        db_dir=args.db_dir,
        output_dir=args.output_dir,
        mode=args.mode,
        talkers=args.talkers
    )
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
