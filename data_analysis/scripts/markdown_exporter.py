#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Markdown 导出器 - WeChatMsgArchive 数据分析流水线

职责：
1. 读取分析数据集（user_profiles.json, relation_graph.json, project_topics.json）
2. 根据 Markdown 模板生成结构化报告
3. 支持批量导出和单个导出

模板系统：
- 使用 Jinja2 风格的简单占位符替换
- 支持循环渲染列表和表格
"""

import os
import sys
import json
import re
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
from string import Template

sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


# =============================================================================
# 模板引擎（简化版）
# =============================================================================

class SimpleTemplate:
    """简化模板引擎，支持基本变量替换和循环"""
    
    def __init__(self, template_text: str):
        self.template_text = template_text
    
    def render(self, context: Dict[str, Any]) -> str:
        """渲染模板"""
        result = self.template_text
        
        # 处理 {{#each items}}...{{/each}} 循环
        result = self._render_loops(result, context)
        
        # 处理 {{#if cond}}...{{else}}...{{/if}}
        result = self._render_conditionals(result, context)
        
        # 处理 {{variable}} 和 {{variable.property}}
        result = self._render_variables(result, context)
        
        return result
    
    def _render_loops(self, text: str, context: Dict) -> str:
        """渲染循环块"""
        pattern = r'\{\{#each\s+(\w+)\}\}(.*?)\{\{/each\}\}'
        
        def replace_loop(match):
            list_name = match.group(1)
            inner_template = match.group(2)
            items = context.get(list_name, [])
            
            if not items:
                return ''
            
            results = []
            for item in items:
                item_context = {**context, '_item': item}
                # 支持 {{_item.prop}} 和 {{prop}}（如果 item 是 dict）
                if isinstance(item, dict):
                    item_context.update(item)
                elif isinstance(item, (list, tuple)) and len(item) == 2:
                    item_context['key'] = item[0]
                    item_context['value'] = item[1]
                
                rendered = SimpleTemplate(inner_template).render(item_context)
                results.append(rendered)
            
            return '\n'.join(results)
        
        return re.sub(pattern, replace_loop, text, flags=re.DOTALL)
    
    def _render_conditionals(self, text: str, context: Dict) -> str:
        """渲染条件块"""
        pattern = r'\{\{#if\s+(\w+)\}\}(.*?)\{\{/if\}\}'
        
        def replace_if(match):
            var_name = match.group(1)
            inner = match.group(2)
            
            # 处理 {{else}}
            if '{{else}}' in inner:
                true_part, false_part = inner.split('{{else}}', 1)
            else:
                true_part, false_part = inner, ''
            
            value = context.get(var_name)
            is_true = bool(value) and value != '0' and value != '[]' and value != '{}'
            
            return true_part.strip() if is_true else false_part.strip()
        
        return re.sub(pattern, replace_if, text, flags=re.DOTALL)
    
    def _render_variables(self, text: str, context: Dict) -> str:
        """渲染变量"""
        pattern = r'\{\{\s*([^}\s]+)\s*\}\}'
        
        def replace_var(match):
            var_path = match.group(1)
            parts = var_path.split('.')
            
            value = context
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part, '')
                elif hasattr(value, part):
                    value = getattr(value, part, '')
                else:
                    value = ''
                    break
            
            if value is None:
                return ''
            if isinstance(value, (list, dict)):
                return json.dumps(value, ensure_ascii=False)
            return str(value)
        
        return re.sub(pattern, replace_var, text)


# =============================================================================
# Markdown 导出器
# =============================================================================

class MarkdownExporter:
    """Markdown 报告导出器"""
    
    def __init__(self, template_dir: str, output_dir: str):
        self.template_dir = Path(template_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def load_template(self, template_name: str) -> SimpleTemplate:
        """加载模板文件"""
        template_path = self.template_dir / f"{template_name}.md"
        with open(template_path, 'r', encoding='utf-8') as f:
            return SimpleTemplate(f.read())
    
    def export_user_profile(self, profile_data: Dict, output_name: Optional[str] = None):
        """导出单个用户画像"""
        template = self.load_template('user_profile')
        
        # 数据预处理
        context = self._prepare_profile_context(profile_data)
        markdown = template.render(context)
        
        filename = output_name or f"profile_{profile_data.get('wxid', 'unknown')}.md"
        output_path = self.output_dir / filename
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown)
        
        logger.info(f"用户画像已导出: {output_path}")
        return output_path
    
    def export_all_profiles(self, profiles_json: str):
        """批量导出所有用户画像"""
        with open(profiles_json, 'r', encoding='utf-8') as f:
            profiles = json.load(f)
        
        output_paths = []
        for wxid, profile in profiles.items():
            # 安全文件名
            safe_name = re.sub(r'[\\/:*?"<>|]', '_', profile.get('display_name', wxid))
            path = self.export_user_profile(profile, f"profile_{safe_name}.md")
            output_paths.append(path)
        
        # 生成索引页
        self._generate_profile_index(profiles, output_paths)
        return output_paths
    
    def export_relation_graph(self, relation_json: str, profile_json: str):
        """导出关系图谱报告"""
        with open(relation_json, 'r', encoding='utf-8') as f:
            relations = json.load(f)
        with open(profile_json, 'r', encoding='utf-8') as f:
            profiles = json.load(f)
        
        template = self.load_template('relation_graph')
        context = self._prepare_relation_context(relations, profiles)
        markdown = template.render(context)
        
        output_path = self.output_dir / 'relation_graph.md'
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown)
        
        logger.info(f"关系图谱已导出: {output_path}")
        return output_path
    
    def export_project_archive(self, project_json: str, profile_json: str):
        """导出项目档案报告"""
        with open(project_json, 'r', encoding='utf-8') as f:
            projects = json.load(f)
        with open(profile_json, 'r', encoding='utf-8') as f:
            profiles = json.load(f)
        
        template = self.load_template('project_archive')
        context = self._prepare_project_context(projects, profiles)
        markdown = template.render(context)
        
        output_path = self.output_dir / 'project_archive.md'
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown)
        
        logger.info(f"项目档案已导出: {output_path}")
        return output_path
    
    def _prepare_profile_context(self, profile: Dict) -> Dict:
        """准备用户画像的模板上下文"""
        # 格式化数据用于展示
        hourly = profile.get('hourly_distribution', {})
        hourly_list = [{'hour': f"{h:02d}:00", 'count': c} for h, c in sorted(hourly.items())]
        
        weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        weekday = profile.get('weekday_distribution', {})
        weekday_list = [{'day': weekday_names.get(w, f'周{w}'), 'count': c} for w, c in sorted(weekday.items())]
        
        types = profile.get('type_distribution', {})
        type_list = [{'name': k, 'count': v, 'percent': f"{v/max(sum(types.values()),1)*100:.1f}%"} for k, v in sorted(types.items(), key=lambda x: -x[1])]
        
        top_interact = profile.get('top_interact_with', [])
        interact_list = [{'name': item[0] if isinstance(item, (list, tuple)) else item.get('display_name', '未知'), 
                         'count': item[1] if isinstance(item, (list, tuple)) else item.get('count', 0)} for item in top_interact[:5]]
        
        return {
            **profile,
            'hourly_list': hourly_list,
            'weekday_list': weekday_list,
            'type_list': type_list,
            'interact_list': interact_list,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def _prepare_relation_context(self, relations: Dict, profiles: Dict) -> Dict:
        """准备关系图谱的模板上下文"""
        nodes = set()
        edges = []
        
        for source, edge_list in relations.items():
            nodes.add(source)
            for edge in edge_list:
                target = edge.get('target', '')
                if source < target:  # 避免重复边
                    nodes.add(target)
                    edges.append({
                        'source': profiles.get(source, {}).get('display_name', source),
                        'target': profiles.get(target, {}).get('display_name', target),
                        'type': edge.get('relation_type', ''),
                        'weight': edge.get('weight', 0),
                        'common_groups': len(edge.get('common_groups', []))
                    })
        
        # 按权重排序，取前50
        edges = sorted(edges, key=lambda x: -x['weight'])[:50]
        
        node_list = []
        for n in nodes:
            p = profiles.get(n, {})
            node_list.append({
                'wxid': n,
                'name': p.get('display_name', n),
                'message_count': p.get('total_messages', 0),
                'groups': p.get('groups_active_in', 0)
            })
        
        return {
            'node_count': len(nodes),
            'edge_count': len(edges),
            'node_list': node_list,
            'edge_list': edges,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def _prepare_project_context(self, projects: List[Dict], profiles: Dict) -> Dict:
        """准备项目档案的模板上下文"""
        project_list = []
        
        for p in projects:
            status_map = {
                'ongoing': '🟡 进行中',
                'completed': '🟢 已完成',
                'stalled': '🔴 已停滞',
                'unknown': '⚪ 未知'
            }
            
            participants = []
            for par in p.get('participants', []):
                participants.append({
                    'name': profiles.get(par, {}).get('display_name', par),
                    'count': p.get('participant_messages', {}).get(par, 0)
                })
            participants = sorted(participants, key=lambda x: -x['count'])
            
            project_list.append({
                'topic_id': p.get('topic_id', ''),
                'topic_name': p.get('topic_name', '未命名话题'),
                'status': status_map.get(p.get('status', ''), p.get('status', '')),
                'keywords': '、'.join(p.get('keywords', [])[:5]),
                'start_time': p.get('start_time', '')[:10],
                'end_time': p.get('end_time', '')[:10],
                'active_days': p.get('active_days', 0),
                'message_count': p.get('message_count', 0),
                'participant_count': len(p.get('participants', [])),
                'participants': participants,
                'key_messages': p.get('key_messages', [])[:5]
            })
        
        # 按状态排序
        status_order = {'🟡 进行中': 0, '🟢 已完成': 1, '🔴 已停滞': 2, '⚪ 未知': 3}
        project_list = sorted(project_list, key=lambda x: status_order.get(x['status'], 99))
        
        return {
            'total_projects': len(project_list),
            'ongoing_count': sum(1 for p in project_list if '🟡' in p['status']),
            'completed_count': sum(1 for p in project_list if '🟢' in p['status']),
            'stalled_count': sum(1 for p in project_list if '🔴' in p['status']),
            'project_list': project_list,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def _generate_profile_index(self, profiles: Dict, paths: List[Path]):
        """生成用户画像索引页"""
        lines = [
            "# 用户画像索引\n",
            f"\n> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"> 总计: {len(profiles)} 人\n",
            "| 序号 | 昵称 | 标签 | 消息数 | 活跃天数 | 档案 |",
            "|------|------|------|--------|----------|------|"
        ]
        
        for i, (wxid, profile) in enumerate(sorted(profiles.items(), key=lambda x: -x[1].get('total_messages', 0)), 1):
            safe_name = re.sub(r'[\\/:*?"<>|]', '_', profile.get('display_name', wxid))
            filename = f"profile_{safe_name}.md"
            tags = '、'.join(profile.get('tags', [])[:3])
            lines.append(f"| {i} | {profile.get('display_name', wxid)} | {tags} | {profile.get('total_messages', 0)} | {profile.get('active_days', 0)} | [{filename}]({filename}) |")
        
        index_path = self.output_dir / 'profile_index.md'
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        logger.info(f"画像索引已生成: {index_path}")


# =============================================================================
# 便捷入口
# =============================================================================

def run_export(template_dir: str, data_dir: str, output_dir: str):
    """运行完整导出"""
    exporter = MarkdownExporter(template_dir, output_dir)
    
    profile_json = Path(data_dir) / 'user_profiles.json'
    relation_json = Path(data_dir) / 'relation_graph.json'
    project_json = Path(data_dir) / 'project_topics.json'
    
    if profile_json.exists():
        exporter.export_all_profiles(str(profile_json))
    
    if relation_json.exists() and profile_json.exists():
        exporter.export_relation_graph(str(relation_json), str(profile_json))
    
    if project_json.exists() and profile_json.exists():
        exporter.export_project_archive(str(project_json), str(profile_json))
    
    logger.info("全部 Markdown 导出完成!")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Markdown 报告导出器')
    parser.add_argument('--template-dir', required=True, help='模板目录')
    parser.add_argument('--data-dir', required=True, help='分析数据目录')
    parser.add_argument('--output-dir', required=True, help='输出目录')
    
    args = parser.parse_args()
    run_export(args.template_dir, args.data_dir, args.output_dir)
