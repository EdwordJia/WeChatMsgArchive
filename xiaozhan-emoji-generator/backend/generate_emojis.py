#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
通义万相API表情包批量生成脚本
生成30种不同表情的Q版校园风表情包
"""

import os
import time
import json
import requests
from datetime import datetime
from pathlib import Path
import dashscope
from dashscope import ImageSynthesis

# API配置
API_KEY = "sk-678716b8423d4d268baf96dc11cbda44"
MODEL = "wanx-v1"
IMAGE_SIZE = "1024*1024"

# 30种表情列表
EMOTIONS = [
    "开心笑", "大笑", "害羞", "生气", "哭泣",
    "惊讶", "困惑", "得意", "无语", "尴尬",
    "卖萌", "傲娇", "委屈", "害怕", "兴奋",
    "疲惫", "思考", "吃惊", "调皮", "撒娇",
    "冷漠", "愤怒", "悲伤", "喜悦", "焦虑",
    "放松", "自信", "羞涩", "搞怪", "酷"
]

# 目录配置
OUTPUT_DIR = Path("output/demo_results")
UPLOADS_DIR = Path("uploads")


def init_api():
    """初始化API"""
    dashscope.api_key = API_KEY
    print(f"✓ API初始化完成")
    print(f"✓ 模型: {MODEL}")
    print(f"✓ 尺寸: {IMAGE_SIZE}")


def generate_prompt(emotion):
    """生成prompt"""
    return f"Q版校园风格，{emotion}表情，可爱的Q版卡通人物，简洁背景，表情包风格，高清"


def generate_single_emoji(emotion, index, total):
    """生成单个表情包"""
    prompt = generate_prompt(emotion)
    print(f"\n[{index}/{total}] 正在生成: {emotion}")
    print(f"  Prompt: {prompt}")

    try:
        start_time = time.time()

        # 调用通义万相API
        response = ImageSynthesis.call(
            model=MODEL,
            prompt=prompt,
            n=1,
            size=IMAGE_SIZE
        )

        elapsed_time = time.time() - start_time

        # 检查响应
        if response.status_code == 200:
            if hasattr(response.output, 'results') and len(response.output.results) > 0:
                image_url = response.output.results[0].url

                # 下载图片
                img_response = requests.get(image_url, timeout=30)

                if img_response.status_code == 200:
                    # 保存图片
                    filename = f"{index:02d}_{emotion}.png"
                    filepath = OUTPUT_DIR / filename

                    with open(filepath, 'wb') as f:
                        f.write(img_response.content)

                    file_size = len(img_response.content)

                    print(f"  ✓ 成功! 耗时: {elapsed_time:.2f}s, 大小: {file_size/1024:.1f}KB")

                    return {
                        'success': True,
                        'emotion': emotion,
                        'filename': filename,
                        'filepath': str(filepath),
                        'time': elapsed_time,
                        'size': file_size,
                        'url': image_url
                    }
                else:
                    print(f"  ✗ 下载失败: HTTP {img_response.status_code}")
                    return {
                        'success': False,
                        'emotion': emotion,
                        'error': f'下载失败: HTTP {img_response.status_code}'
                    }
            else:
                print(f"  ✗ API返回结果为空")
                return {
                    'success': False,
                    'emotion': emotion,
                    'error': 'API返回结果为空'
                }
        else:
            error_msg = f"API调用失败: {response.status_code}"
            if hasattr(response, 'message'):
                error_msg += f" - {response.message}"
            print(f"  ✗ {error_msg}")
            return {
                'success': False,
                'emotion': emotion,
                'error': error_msg
            }

    except Exception as e:
        print(f"  ✗ 异常: {str(e)}")
        return {
            'success': False,
            'emotion': emotion,
            'error': str(e)
        }


def calculate_cost(success_count):
    """计算预估成本
    通义万相 wanx-v1 定价约为 0.08元/张
    """
    price_per_image = 0.08
    total_cost = success_count * price_per_image
    return total_cost


def main():
    """主函数"""
    print("=" * 60)
    print("通义万相表情包批量生成")
    print("=" * 60)

    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"✓ 输出目录: {OUTPUT_DIR.absolute()}")

    # 初始化API
    init_api()

    # 开始生成
    print(f"\n开始生成 {len(EMOTIONS)} 个表情包...")
    print("-" * 60)

    start_time = time.time()
    results = []

    for i, emotion in enumerate(EMOTIONS, 1):
        result = generate_single_emoji(emotion, i, len(EMOTIONS))
        results.append(result)

        # 每次请求间隔1秒，避免频率限制
        if i < len(EMOTIONS):
            time.sleep(1)

    total_time = time.time() - start_time

    # 统计结果
    print("\n" + "=" * 60)
    print("生成完成！统计结果：")
    print("=" * 60)

    success_results = [r for r in results if r['success']]
    failed_results = [r for r in results if not r['success']]

    success_count = len(success_results)
    failed_count = len(failed_results)
    success_rate = (success_count / len(EMOTIONS)) * 100

    print(f"\n📊 基本统计:")
    print(f"  总数量: {len(EMOTIONS)}")
    print(f"  成功: {success_count}")
    print(f"  失败: {failed_count}")
    print(f"  成功率: {success_rate:.1f}%")
    print(f"  总耗时: {total_time:.2f}s")
    print(f"  平均耗时: {total_time/len(EMOTIONS):.2f}s/张")

    if success_results:
        total_size = sum(r['size'] for r in success_results)
        avg_size = total_size / len(success_results)
        avg_time = sum(r['time'] for r in success_results) / len(success_results)

        print(f"\n📦 文件统计:")
        print(f"  总大小: {total_size/1024/1024:.2f}MB")
        print(f"  平均大小: {avg_size/1024:.1f}KB")
        print(f"  平均生成时间: {avg_time:.2f}s")

    # 成本预估
    estimated_cost = calculate_cost(success_count)
    print(f"\n💰 成本预估:")
    print(f"  单价: ¥0.08/张")
    print(f"  成功生成: {success_count}张")
    print(f"  预估成本: ¥{estimated_cost:.2f}")

    # 失败列表
    if failed_results:
        print(f"\n❌ 失败列表:")
        for r in failed_results:
            print(f"  - {r['emotion']}: {r.get('error', '未知错误')}")

    # 保存详细结果到JSON
    report = {
        'timestamp': datetime.now().isoformat(),
        'total': len(EMOTIONS),
        'success': success_count,
        'failed': failed_count,
        'success_rate': success_rate,
        'total_time': total_time,
        'estimated_cost': estimated_cost,
        'results': results
    }

    report_file = OUTPUT_DIR / 'generation_report.json'
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n📄 详细报告已保存: {report_file}")
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
