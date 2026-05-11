"""
MCP 高级分析工具扩展
新增工具：
1. message_statistics - 消息统计分析
2. sentiment_analysis - 情感分析
3. trend_detection - 趋势检测
4. relationship_strength - 关系强度分析
5. export_report - 导出分析报告
"""

from typing import Dict, Any, List
from datetime import datetime, timedelta
from collections import Counter, defaultdict
import json


class AdvancedAnalytics:
    """高级分析工具"""

    def __init__(self, db):
        self.db = db

    def message_statistics(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        消息统计分析

        参数:
            days (int): 统计最近N天，默认7天
            group_by (str): 分组维度（time/user/group），默认time
         talker (str, optional): 指定联系人/群聊
        """
        days = arguments.get('days', 7)
        group_by = arguments.get('group_by', 'time')
        talker = arguments.get('talker')

        since_time = int((datetime.now() - timedelta(days=days)).timestamp())

        try:
            # 获取消息数据
            if talker:
              messages = self.db.get_messages_by_talker(talker, since_time)
            else:
                messages = self.db.get_all_messages(since_time)

         # 按维度统计
            if group_by == 'time':
            stats = self._stats_by_time(messages)
            elif group_by == 'user':
                stats = self._stats_by_user(messages)
            elif group_by == 'group':
              stats = self._stats_by_group(messages)
            else:
                return {'error': f'不支持的分组维度: {group_by}'}

            return {
                'success': True,
          'period': f'最近{days}天',
                'group_by': group_by,
                'total_messages': len(messages),
                'statistics': stats
            }
    except Exception as e:
            return {'error': str(e)}

    def _stats_by_time(self, messages: List[Dict]) -> Dict:
        """按时间统计"""
        daily_counts = defaultdict(int)
        hourly_counts = defaultdict(int)

        for msg in messages:
          dt = datetime.fromtimestamp(msg['time'])
          date_key = dt.strftime('%Y-%m-%d')
            hour_key = dt.strftime('%H:00')

            daily_counts[date_key] += 1
            hourly_counts[hour_key] += 1

        return {
            'daily': dict(sorted(daily_counts.items())),
            'hourly': dict(sorted(hourly_counts.items())),
            'peak_hour': max(hourly_counts.items(), key=lambda x: x[1])[0] if hourly_counts else None
      }

    def _stats_by_user(self, messages: List[Dict]) -> Dict:
        """按用户统计"""
        user_counts = Counter(msg['sender'] for msg in messages if msg.get('sender'))
        top_users = user_counts.most_common(10)

     return {
            'total_users': len(user_counts),
            'top_10': [{'user': user, 'count': count} for user, count in top_users]
        }

    def _stats_by_group(self, messages: List[Dict]) -> Dict:
        """按群聊统计"""
        group_counts = Counter(
            msg['talker'] for msg in messages
            if msg.get('talker', '').endswith('@chatroom')
        )
        top_groups = group_counts.most_common(10)

        return {
            'total_groups': len(group_counts),
            'top_10': [{'group': group, 'count': count} for group, count in top_groups]
        }

    def sentiment_analysis(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        情感分析（基于关键词规则，可扩展为LLM）

        参数:
            talker (str): 联系人/群聊ID
            days (int): 分析最近N天，默认7天
        """
        talker = arguments.get('talker')
        if not talker:
            return {'error': '缺少参数: talker'}

        days = arguments.get('days', 7)
        since_time = int((datetime.now() - timedelta(days=days)).timestamp())

        try:
          messages = self.db.get_messages_by_talker(talker, since_time)

            # 简单情感分类（基于关键词）
            positive_keywords = ['好', '棒', '赞', '喜欢', '开心', '哈哈', '👍', '😊']
            negative_keywords = ['不好', '差', '烂', '讨厌', '生气', '😡', '😢']

            sentiment_counts = {'positive': 0, 'negative': 0, 'neutral': 0}

            for msg in messages:
                content = msg.get('content', '')
           if any(kw in content for kw in positive_keywords):
                    sentiment_counts['positive'] += 1
                elif any(kw in content for kw in negative_keywords):
                    sentiment_counts['negative'] += 1
                else:
               sentiment_counts['neutral'] += 1

            total = len(messages)
            sentiment_ratio = {
              k: round(v / total * 100, 2) if total > 0 else 0
              for k, v in sentiment_counts.items()
            }

            return {
            'success': True,
                'talker': talker,
            'period': f'最近{days}天',
                'total_messages': total,
          'sentiment_counts': sentiment_counts,
                'sentiment_ratio': sentiment_ratio,
                'overall': self._get_overall_sentiment(sentiment_ratio)
          }
     except Exception as e:
          return {'error': str(e)}

    def _get_overall_sentiment(self, ratio: Dict) -> str:
        """判断整体情感倾向"""
        if ratio['positive'] > 50:
            return 'positive'
        elif ratio['negative'] > 30:
            return 'negative'
        else:
            return 'neutral'

    def trend_detection(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        趋势检测

        参数:
            keyword (str): 关键词
          days (int): 检测最近N天，默认30天
        """
        keyword = arguments.get('keyword')
        if not keyword:
            return {'error': '缺少参数: keyword'}

        days = arguments.get('days', 30)
        since_time = int((datetime.now() - timedelta(days=days)).timestamp())

        try:
            messages = self.db.search_messages(keyword, limit=10000, since_time=since_time)

            # 按日期统计
            daily_counts = defaultdict(int)
            for msg in messages:
                date_key = datetime.fromtimestamp(msg['time']).strftime('%Y-%m-%d')
            daily_counts[date_key] += 1

            # 计算趋势
            sorted_dates = sorted(daily_counts.items())
            if len(sorted_dates) < 2:
         trend = 'insufficient_data'
            else:
                first_half = sum(count for _, count in sorted_dates[:len(sorted_dates)//2])
                second_half = sum(count for _, count in sorted_dates[len(sorted_dates)//2:])

              if second_half > first_half * 1.2:
             trend = 'rising'
                elif second_half < first_half * 0.8:
               trend = 'falling'
                else:
           trend = 'stable'

            return {
          'success': True,
              'keyword': keyword,
                'period': f'最近{days}天',
                'total_mentions': len(messages),
                'daily_counts': dict(sorted_dates),
              'trend': trend
            }
        except Exception as e:
            return {'error': str(e)}

    def relationship_strength(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        关系强度分析

        参数:
            user1 (str): 用户1的wxid
            user2 (str): 用户2的wxid
            days (int): 分析最近N天，默认30天
        ""
        user1 = arguments.get('user1')
        user2 = arguments.get('user2')

     if not user1 or not user2:
            return {'error': '缺少参数: user1, user2'}

        days = arguments.get('days', 30)
        since_time = int((datetime.now() - timedelta(days=days)).timestamp())

        try:
            # 获取两人的互动消息
            messages = self.db.get_interaction_messages(user1, user2, since_time)

            if not messages:
              return {
               'success': True,
                  'user1': user1,
                    'user2': user2,
             'strength': 'no_interaction',
                    'score': 0
                }

            # 计算互动指标
            total_messages = len(messages)
            user1_messages = sum(1 for msg in messages if msg['sender'] == user1)
            user2_messages = sum(1 for msg in messages if msg['sender'] == user2)

          # 互动频率（每天平均消息数）
            frequency = total_messages / days

            # 互动平衡度（0-1，越接近1越平衡）
            balance = 1 - abs(user1_messages - user2_messages) / total_messages

          # 综合评分（0-100）
            score = min(100, int(frequency * 10 + balance * 50))

            # 关系强度等级
        if score >= 80:
                strength = 'very_strong'
            elif score >= 60:
             strength = 'strong'
            elif score >= 40:
              strength = 'moderate'
        elif score >= 20:
                strength = 'weak'
            else:
                strength = 'very_weak'

            return {
                'success': True,
                'user1': user1,
          'user2': user2,
                'period': f'最近{days}天',
             'total_messages': total_messages,
             'frequency': round(frequency, 2),
          'balance': round(balance, 2),
                'score': score,
                'strength': strength
            }
        except Exception as e:
            return {'error': str(e)}

    def export_report(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
      导出分析报告

        参数:
            report_type (str): 报告类型（summary/detailed）
            days (int): 报告时间范围，默认7天
          format (str): 输出格式（json/markdown），默认json
        """
        report_type = arguments.get('report_type', 'summary')
        days = arguments.get('days', 7)
        output_format = arguments.get('format', 'json')

    try:
            # 生成报告数据
            report_data = {
         'title': f'微信消息分析报告（最近{days}天）',
           'generated_at': datetime.now().isoformat(),
           'period': f'{days}天',
                'sections': []
            }

            # 添加统计数据
            stats = self.message_statistics({'days': days, 'group_by': 'time'})
            if stats.get('success'):
                report_data['sections'].append({
                    'name': '消息统计',
                'data': stats
                })

            # 格式化输出
            if output_format == 'markdown':
                report_content = self._format_markdown_report(report_data)
            else:
                report_content = json.dumps(report_data, ensure_ascii=False, indent=2)

            # 保存到文件
            output_path = f"output/reports/report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{output_format}"

            return {
                'success': True,
                'report_path': output_path,
                'report_content': report_content[:1000] + '...' if len(report_content) > 1000 else report_content
            }
        except Exception as e:
          return {'error': str(e)}

    def _format_markdown_report(self, data: Dict) -> str:
        """格式化为Markdown报告"""
        md = f"# {data['title']}\n\n"
        md += f"**生成时间**: {data['generated_at']}\n\n"
        md += f"**统计周期**: {data['period']}\n\n"

        for section in data['sections']:
            md += f"## {section['name']}\n\n"
            md += f"```json\n{json.dumps(section['data'], ensure_ascii=False, indent=2)}\n```\n\n"

        return md
