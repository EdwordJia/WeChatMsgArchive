#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
用户画像挖掘工具
从微信聊天记录中分析用户行为、兴趣标签、社交特征和情感倾向
"""

import os
import sqlite3
import json
from datetime import datetime
from collections import defaultdict, Counter
from typing import Dict, List, Tuple
import jieba
import jieba.analyse
from pathlib import Path

# 配置
BASE_DIR = Path(__file__).parent
DECRYPTED_DB_DIR = BASE_DIR / 'output' / 'decrypted_db'
OUTPUT_DIR = BASE_DIR / 'output' / 'user_profiles'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 停用词列表（常见无意义词）
STOP_WORDS = set([
    '的', '了', '是', '我', '你', '他', '她', '它', '们', '在', '有', '和', '就',
    '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '吗',
    '会', '能', '这', '那', '啊', '哦', '嗯', '呢', '吧', '哈', '嘿', '额', '呃'
])


class UserProfiler:
    """用户画像分析器"""

    def __init__(self, wxid: str, user_name: str = None):
        self.wxid = wxid
        self.user_name = user_name or wxid
        self.messages = []
        self.profile = {
            'wxid': wxid,
            'user_name': user_name,
            'behavior': {},
            'interests': {},
            'social': {},
            'sentiment': {}
        }

    def load_messages(self):
        """从所有 MSG*.db 加载用户消息"""
        msg_dbs = list(DECRYPTED_DB_DIR.glob('MSG*.db')) + list(DECRYPTED_DB_DIR.glob('Multi/MSG*.db'))

        for db_path in msg_dbs:
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()

                # 查询用户发送的所有消息
                query = """
                    SELECT CreateTime, Type, StrContent, IsSender, StrTalker
                    FROM MSG
                    WHERE IsSender = 1
                    ORDER BY CreateTime
                """

                cursor.execute(query)
                rows = cursor.fetchall()

                for row in rows:
                    create_time, msg_type, content, is_sender, talker = row
                    self.messages.append({
                        'timestamp': create_time,
                        'type': msg_type,
                        'content': content or '',
                        'talker': talker,
                        'datetime': datetime.fromtimestamp(create_time / 1000) if create_time else None
                    })

                conn.close()
            except Exception as e:
                print(f"读取 {db_path} 失败: {e}")

        print(f"加载了 {len(self.messages)} 条消息")

    def analyze_behavior(self):
        """分析用户行为特征"""
        if not self.messages:
            return

        # 发言频率统计
        total_messages = len(self.messages)

        # 按消息类型统计
        type_counter = Counter(msg['type'] for msg in self.messages)

        # 按小时统计活跃时段
        hour_counter = Counter()
        weekday_counter = Counter()

        for msg in self.messages:
            if msg['datetime']:
                hour_counter[msg['datetime'].hour] += 1
                weekday_counter[msg['datetime'].weekday()] += 1

        # 找出最活跃时段
        most_active_hours = hour_counter.most_common(3)
        most_active_weekdays = weekday_counter.most_common(3)

        weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

        self.profile['behavior'] = {
            'total_messages': total_messages,
            'message_types': dict(type_counter),
            'most_active_hours': [(f"{h}:00-{h}:59", count) for h, count in most_active_hours],
            'most_active_weekdays': [(weekday_names[d], count) for d, count in most_active_weekdays],
            'avg_messages_per_day': self._calculate_avg_messages_per_day()
        }

    def _calculate_avg_messages_per_day(self) -> float:
        """计算平均每天消息数"""
        if not self.messages:
            return 0.0

        dates = set()
        for msg in self.messages:
            if msg['datetime']:
                dates.add(msg['datetime'].date())

        if not dates:
            return 0.0

        return len(self.messages) / len(dates)

    def analyze_interests(self, top_n: int = 20):
        """分析用户兴趣标签（关键词提取）"""
        # 合并所有文本消息
        text_messages = [msg['content'] for msg in self.messages if msg['type'] == 1 and msg['content']]
        all_text = ' '.join(text_messages)

        if not all_text:
            return

        # 使用 jieba 提取关键词（TF-IDF）
        keywords = jieba.analyse.extract_tags(all_text, topK=top_n, withWeight=True)

        # 过滤停用词
        filtered_keywords = [(word, weight) for word, weight in keywords if word not in STOP_WORDS and len(word) > 1]

        self.profile['interests'] = {
            'top_keywords': filtered_keywords[:top_n],
            'total_words': len(all_text.split())
        }

    def analyze_social(self):
        """分析社交特征"""
        # 统计聊天对象
        talker_counter = Counter(msg['talker'] for msg in self.messages)

        # 区分群聊和私聊
        group_chats = {talker: count for talker, count in talker_counter.items() if '@chatroom' in talker}
        private_chats = {talker: count for talker, count in talker_counter.items() if '@chatroom' not in talker}

        self.profile['social'] = {
            'total_contacts': len(talker_counter),
            'group_chats': len(group_chats),
            'private_chats': len(private_chats),
            'most_contacted_groups': sorted(group_chats.items(), key=lambda x: x[1], reverse=True)[:5],
            'most_contacted_users': sorted(private_chats.items(), key=lambda x: x[1], reverse=True)[:5]
        }

    def analyze_sentiment(self):
        """分析情感倾向（简单规则）"""
        positive_words = set(['好', '棒', '赞', '喜欢', '开心', '哈哈', '厉害', '牛', '优秀', '感谢', '谢谢'])
        negative_words = set(['不好', '差', '烂', '讨厌', '难过', '失望', '糟糕', '问题', '错误', '失败'])

        positive_count = 0
        negative_count = 0
        neutral_count = 0

        for msg in self.messages:
            if msg['type'] == 1 and msg['content']:
                content = msg['content']
                has_positive = any(word in content for word in positive_words)
                has_negative = any(word in content for word in negative_words)

                if has_positive and not has_negative:
                    positive_count += 1
                elif has_negative and not has_positive:
                    negative_count += 1
                else:
                    neutral_count += 1

        total = positive_count + negative_count + neutral_count

        self.profile['sentiment'] = {
            'positive': positive_count,
            'negative': negative_count,
            'neutral': neutral_count,
            'positive_ratio': positive_count / total if total > 0 else 0,
            'negative_ratio': negative_count / total if total > 0 else 0
        }

    def generate_report(self) -> str:
        """生成 Markdown 格式的用户画像报告"""
        report = f"""# 用户画像报告

## 基本信息
- **微信ID**: {self.profile['wxid']}
- **用户名**: {self.profile['user_name']}
- **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 行为特征

### 发言统计
- **总消息数**: {self.profile['behavior'].get('total_messages', 0)}
- **日均消息数**: {self.profile['behavior'].get('avg_messages_per_day', 0):.1f}

### 消息类型分布
"""

        for msg_type, count in self.profile['behavior'].get('message_types', {}).items():
            type_name = self._get_message_type_name(msg_type)
            report += f"- {type_name}: {count}\n"

        report += "\n### 活跃时段\n"
        for hour, count in self.profile['behavior'].get('most_active_hours', []):
            report += f"- {hour}: {count} 条消息\n"

        report += "\n### 活跃日期\n"
        for weekday, count in self.profile['behavior'].get('most_active_weekdays', []):
            report += f"- {weekday}: {count} 条消息\n"

        report += "\n---\n\n## 兴趣标签\n\n"
        for word, weight in self.profile['interests'].get('top_keywords', []):
            report += f"- **{word}** (权重: {weight:.4f})\n"

        report += "\n---\n\n## 社交特征\n\n"
        report += f"- **总联系人数**: {self.profile['social'].get('total_contacts', 0)}\n"
        report += f"- **群聊数量**: {self.profile['social'].get('group_chats', 0)}\n"
        report += f"- **私聊数量**: {self.profile['social'].get('private_chats', 0)}\n"

        report += "\n### 最常联系的群组\n"
        for talker, count in self.profile['social'].get('most_contacted_groups', []):
            report += f"- {talker}: {count} 条消息\n"

        report += "\n### 最常联系的用户\n"
        for talker, count in self.profile['social'].get('most_contacted_users', []):
            report += f"- {talker}: {count} 条消息\n"

        report += "\n---\n\n## 情感倾向\n\n"
        sentiment = self.profile['sentiment']
        report += f"- **正面消息**: {sentiment.get('positive', 0)} ({sentiment.get('positive_ratio', 0):.1%})\n"
        report += f"- **负面消息**: {sentiment.get('negative', 0)} ({sentiment.get('negative_ratio', 0):.1%})\n"
        report += f"- **中性消息**: {sentiment.get('neutral', 0)}\n"

        return report

    def _get_message_type_name(self, msg_type: int) -> str:
        """获取消息类型名称"""
        type_names = {
            1: '文本',
            3: '图片',
            34: '语音',
            43: '视频',
            47: '表情',
            49: '链接/文件',
            10000: '系统消息'
        }
        return type_names.get(msg_type, f'未知类型({msg_type})')

    def save_report(self):
        """保存报告到文件"""
        report = self.generate_report()
        output_file = OUTPUT_DIR / f"{self.wxid}_profile.md"

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"用户画像报告已保存到: {output_file}")

        # 同时保存 JSON 格式
        json_file = OUTPUT_DIR / f"{self.wxid}_profile.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(self.profile, f, ensure_ascii=False, indent=2)

        print(f"JSON 数据已保存到: {json_file}")


def main():
    """主函数"""
    # 示例：分析当前用户（长腿叔叔）
    wxid = 'wxid_ucag2pjrmhm822'
    user_name = '长腿叔叔'

    print(f"开始分析用户: {user_name} ({wxid})")

    profiler = UserProfiler(wxid, user_name)

    print("1. 加载消息...")
    profiler.load_messages()

    print("2. 分析行为特征...")
    profiler.analyze_behavior()

    print("3. 分析兴趣标签...")
    profiler.analyze_interests()

    print("4. 分析社交特征...")
    profiler.analyze_social()

    print("5. 分析情感倾向...")
    profiler.analyze_sentiment()

    print("6. 生成报告...")
    profiler.save_report()

    print("\n✓ 用户画像分析完成！".encode('utf-8').decode('utf-8'))


if __name__ == '__main__':
    main()
