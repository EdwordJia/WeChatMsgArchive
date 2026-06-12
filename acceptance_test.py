#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
7个任务的验收测试脚本
逐步验证每个任务的输出和功能
"""

import os
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime

class AcceptanceTest:
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.output_dir = self.base_dir / "output"
        self.results = []

    def print_header(self, task_num, task_name):
        """打印任务标题"""
        print("\n" + "="*80)
        print(f"任务 {task_num}: {task_name}")
        print("="*80)

    def print_result(self, check_name, passed, details=""):
        """打印检查结果"""
        status = "[PASS]" if passed else "[FAIL]"
        try:
            print(f"{status} - {check_name}")
            if details:
                print(f"  详情: {details}")
        except UnicodeEncodeError:
            print(f"{status} - {check_name}".encode('utf-8', errors='ignore').decode('utf-8'))
            if details:
                print(f"  详情: {details}".encode('utf-8', errors='ignore').decode('utf-8'))
        self.results.append({
            "check": check_name,
            "passed": passed,
            "details": details
        })

    def test_task1_user_profiling(self):
        """任务1: 用户画像 - 11,380条消息分析"""
        self.print_header(1, "用户画像分析")

        # 检查脚本存在
        script = self.base_dir / "user_profiling.py"
        self.print_result("脚本存在", script.exists(), str(script))

        # 检查输出目录
        profile_dir = self.output_dir / "user_profiles"
        if profile_dir.exists():
            profiles = list(profile_dir.glob("*.json"))
            self.print_result(
                "用户画像文件",
                len(profiles) > 0,
                f"找到 {len(profiles)} 个用户画像"
            )

            # 检查画像内容
            if profiles:
                with open(profiles[0], 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    has_behavior = "behavior_patterns" in data
                    has_interests = "interests" in data
                    has_social = "social_characteristics" in data
                    has_emotion = "emotional_analysis" in data

                    self.print_result(
                        "四维分析完整性",
                        has_behavior and has_interests and has_social and has_emotion,
                        f"行为:{has_behavior}, 兴趣:{has_interests}, 社交:{has_social}, 情感:{has_emotion}"
                    )
        else:
            self.print_result("用户画像文件", False, "输出目录不存在")

    def test_task2_social_graph(self):
        """任务2: 社交关系图谱 - 111节点社交网络"""
        self.print_header(2, "社交关系图谱")

        # 检查脚本
        script = self.base_dir / "social_graph_analysis.py"
        self.print_result("脚本存在", script.exists(), str(script))

        # 检查输出文件
        graph_dir = self.output_dir / "social_graph"
        if graph_dir.exists():
            graphml = graph_dir / "social_network.graphml"
            stats = graph_dir / "network_stats.json"

            self.print_result("GraphML文件", graphml.exists(), str(graphml))

            if stats.exists():
                with open(stats, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    nodes = data.get("total_nodes", 0)
                    communities = data.get("communities", 0)

                    self.print_result(
                        "网络规模",
                        nodes > 0,
                        f"{nodes} 个节点, {communities} 个社区"
                    )
            else:
                self.print_result("统计文件", False, "network_stats.json 不存在")
        else:
            self.print_result("输出目录", False, "social_graph 目录不存在")

    def test_task3_business_projects(self):
        """任务3: 副业项目识别 - 61个项目"""
        self.print_header(3, "副业项目识别")

        # 检查脚本
        script = self.base_dir / "business_opportunity.py"
        self.print_result("脚本存在", script.exists(), str(script))

        # 检查输出
        biz_dir = self.output_dir / "business_opportunities"
        if biz_dir.exists():
            projects_file = biz_dir / "projects_timeline.json"

            if projects_file.exists():
                with open(projects_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    projects = data.get("projects", [])

                    self.print_result(
                        "项目数量",
                        len(projects) > 0,
                        f"识别到 {len(projects)} 个项目"
                    )

                    # 检查时间线
                    has_timeline = all("timeline" in p for p in projects[:5])
                    self.print_result(
                        "时间线追踪",
                        has_timeline,
                        "项目包含完整时间线"
                    )
            else:
                self.print_result("项目文件", False, "projects_timeline.json 不存在")
        else:
            self.print_result("输出目录", False, "business_opportunities 目录不存在")

    def test_task4_business_opportunities(self):
        """任务4: 商机识别 - 108个商机"""
        self.print_header(4, "商机识别")

        biz_dir = self.output_dir / "business_opportunities"
        if biz_dir.exists():
            opps_file = biz_dir / "opportunities.json"

            if opps_file.exists():
                with open(opps_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    opps = data.get("opportunities", [])
                    high_value = [o for o in opps if o.get("score", 0) >= 3.0]

                    self.print_result(
                        "商机总数",
                        len(opps) > 0,
                        f"识别到 {len(opps)} 个商机"
                    )

                    self.print_result(
                        "高价值商机",
                        len(high_value) > 0,
                        f"{len(high_value)} 个高价值商机 (≥3.0分)"
                    )
            else:
                self.print_result("商机文件", False, "opportunities.json 不存在")
        else:
            self.print_result("输出目录", False, "business_opportunities 目录不存在")

    def test_task5_markdown_export(self):
        """任务5: Markdown转换 - 13个MD文档"""
        self.print_header(5, "Markdown导出")

        # 检查导出器
        exporter = self.base_dir / "exporter" / "exporter_markdown.py"
        self.print_result("Markdown导出器", exporter.exists(), str(exporter))

        # 检查输出文件
        md_files = list(self.output_dir.glob("**/*.md"))
        self.print_result(
            "Markdown文件",
            len(md_files) > 0,
            f"找到 {len(md_files)} 个 .md 文件"
        )

        # 检查AI友好格式
        if md_files:
            sample = md_files[0]
            with open(sample, 'r', encoding='utf-8') as f:
                content = f.read()
                has_structure = "##" in content or "###" in content
                has_metadata = "---" in content[:100]

                self.print_result(
                    "AI友好格式",
                    has_structure,
                    f"包含结构化标题: {has_structure}"
                )

    def test_task6_performance_optimization(self):
        """任务6: 性能优化 - 10个索引"""
        self.print_header(6, "性能优化")

        # 检查脚本
        script = self.base_dir / "performance_optimizer.py"
        self.print_result("优化脚本", script.exists(), str(script))

        # 检查报告
        report_json = self.output_dir / "performance_optimization_report.json"
        report_md = self.output_dir / "performance_optimization_report.md"

        self.print_result("JSON报告", report_json.exists(), str(report_json))
        self.print_result("Markdown报告", report_md.exists(), str(report_md))

        if report_json.exists():
            with open(report_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
                indexes = data.get("indexes_created", [])

                self.print_result(
                    "索引创建",
                    len(indexes) > 0,
                    f"创建了 {len(indexes)} 个索引"
                )

        # 检查数据库索引
        db_path = self.output_dir / "decrypted_db" / "MSG0.db"
        if db_path.exists():
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")
                indexes = cursor.fetchall()
                conn.close()

                self.print_result(
                    "数据库索引",
                    len(indexes) > 0,
                    f"数据库中有 {len(indexes)} 个自定义索引"
                )
            except Exception as e:
                self.print_result("数据库索引", False, f"检查失败: {e}")
        else:
            self.print_result("数据库文件", False, "MSG0.db 不存在")

    def test_task7_multi_platform(self):
        """任务7: 多平台扩展架构"""
        self.print_header(7, "多平台扩展")

        # 检查框架脚本
        framework = self.base_dir / "multi_platform_framework.py"
        self.print_result("框架脚本", framework.exists(), str(framework))

        # 检查架构文档
        arch_doc = self.base_dir / "MULTI_PLATFORM_ARCHITECTURE.md"
        self.print_result("架构文档", arch_doc.exists(), str(arch_doc))

        # 检查适配器
        if framework.exists():
            with open(framework, 'r', encoding='utf-8') as f:
                content = f.read()
                has_base_adapter = "BaseAdapter" in content or "PlatformAdapter" in content
                has_wechat = "WeChatAdapter" in content or "wechat" in content.lower()

                self.print_result(
                    "适配器架构",
                    has_base_adapter,
                    "包含基础适配器类"
                )

                self.print_result(
                    "微信适配器",
                    has_wechat,
                    "包含微信平台适配"
                )

    def generate_summary(self):
        """生成验收总结"""
        print("\n" + "="*80)
        print("验收总结")
        print("="*80)

        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        failed = total - passed

        print(f"\n总计: {total} 项检查")
        print(f"[PASS] 通过: {passed} 项")
        print(f"[FAIL] 失败: {failed} 项")
        print(f"通过率: {passed/total*100:.1f}%")

        if failed > 0:
            print("\n失败项目:")
            for r in self.results:
                if not r["passed"]:
                    print(f"  - {r['check']}: {r['details']}")

        # 保存报告
        report = {
            "test_time": datetime.now().isoformat(),
            "summary": {
                "total": total,
                "passed": passed,
                "failed": failed,
                "pass_rate": f"{passed/total*100:.1f}%"
            },
            "details": self.results
        }

        report_file = self.output_dir / "acceptance_test_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n详细报告已保存: {report_file}")

    def run_all_tests(self):
        """运行所有测试"""
        print("开始验收测试...")
        print(f"基础目录: {self.base_dir}")
        print(f"输出目录: {self.output_dir}")

        self.test_task1_user_profiling()
        self.test_task2_social_graph()
        self.test_task3_business_projects()
        self.test_task4_business_opportunities()
        self.test_task5_markdown_export()
        self.test_task6_performance_optimization()
        self.test_task7_multi_platform()

        self.generate_summary()

if __name__ == "__main__":
    tester = AcceptanceTest()
    tester.run_all_tests()
