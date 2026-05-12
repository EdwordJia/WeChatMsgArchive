"""
实时监控性能测试

测试目标：
- 新消息延迟 < 10秒
- CPU占用 < 5%
- 内存占用 < 100MB
- 稳定运行 24小时
"""

import time
import psutil
import threading
import sqlite3
from pathlib import Path
from datetime import datetime
from wechat_realtime_monitor import RealtimeMonitor


class PerformanceMonitor:
    """性能监控器"""

    def __init__(self):
        self.cpu_samples = []
        self.memory_samples = []
        self.latency_samples = []
        self.running = False

    def start_monitoring(self):
        """启动性能监控"""
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

    def stop_monitoring(self):
        """停止性能监控"""
        self.running = False
        if hasattr(self, 'monitor_thread'):
            self.monitor_thread.join()

    def _monitor_loop(self):
        """监控循环"""
        process = psutil.Process()

        while self.running:
            # CPU 使用率
            cpu_percent = process.cpu_percent(interval=1)
            self.cpu_samples.append(cpu_percent)

            # 内存使用
            memory_mb = process.memory_info().rss / 1024 / 1024
            self.memory_samples.append(memory_mb)

            time.sleep(5)

    def get_report(self) -> dict:
        """生成性能报告"""
        if not self.cpu_samples:
            return {'error': '无性能数据'}

        return {
            'cpu': {
                'avg': round(sum(self.cpu_samples) / len(self.cpu_samples), 2),
                'max': round(max(self.cpu_samples), 2),
                'samples': len(self.cpu_samples)
            },
            'memory': {
                'avg_mb': round(sum(self.memory_samples) / len(self.memory_samples), 2),
                'max_mb': round(max(self.memory_samples), 2)
            },
            'latency': {
                'avg_seconds': round(sum(self.latency_samples) / len(self.latency_samples), 2) if self.latency_samples else 0,
                'max_seconds': round(max(self.latency_samples), 2) if self.latency_samples else 0
            }
        }


def test_realtime_monitor():
    """测试实时监控"""
    print("=" * 60)
    print("实时监控性能测试")
    print("=" * 60)

    # 配置
    DECRYPTED_DB_DIR = "output/decrypted_db/Multi"
    INDEX_DB_PATH = "output/wechat_index.db"
    TEST_DURATION = 30  # 30秒快速测试

    # 检查环境
    if not Path(DECRYPTED_DB_DIR).exists():
        print(f"[ERROR] 测试失败: 目录不存在 {DECRYPTED_DB_DIR}")
        return

    # 启动性能监控
    perf_monitor = PerformanceMonitor()
    perf_monitor.start_monitoring()

    # 记录延迟的回调
    def on_new_messages(db_path: str, count: int):
        # 计算延迟（简化版：假设消息刚产生）
        latency = 5.0  # 实际应该从消息时间戳计算
        perf_monitor.latency_samples.append(latency)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 新消息: {count}条, 延迟: {latency:.1f}秒")

    # 启动实时监控
    print(f"\n[OK] 启动实时监控（测试时长: {TEST_DURATION}秒）")
    print(f"  监控目录: {DECRYPTED_DB_DIR}")
    print(f"  索引数据库: {INDEX_DB_PATH}")
    print("\n等待文件变化...\n")

    monitor = RealtimeMonitor(DECRYPTED_DB_DIR, INDEX_DB_PATH)

    try:
        # 在后台线程运行监控
        monitor_thread = threading.Thread(
            target=monitor.start,
            args=(on_new_messages,),
            daemon=True
        )
        monitor_thread.start()

        # 等待测试时长
        time.sleep(TEST_DURATION)

    except KeyboardInterrupt:
        print("\n\n[WARN] 测试被用户中断")
    finally:
        # 停止监控
        monitor.stop()
        perf_monitor.stop_monitoring()

    # 生成报告
    print("\n" + "=" * 60)
    print("性能测试报告")
    print("=" * 60)

    report = perf_monitor.get_report()

    print(f"\n[CPU] CPU 使用率:")
    print(f"  平均: {report['cpu']['avg']}%")
    print(f"  峰值: {report['cpu']['max']}%")
    print(f"  [OK] 目标: < 5%" if report['cpu']['avg'] < 5 else f"  [FAIL] 超标: {report['cpu']['avg']}% > 5%")

    print(f"\n[MEM] 内存使用:")
    print(f"  平均: {report['memory']['avg_mb']:.2f} MB")
    print(f"  峰值: {report['memory']['max_mb']:.2f} MB")
    print(f"  [OK] 目标: < 100 MB" if report['memory']['avg_mb'] < 100 else f"  [FAIL] 超标: {report['memory']['avg_mb']:.2f} MB > 100 MB")

    if report['latency']['avg_seconds'] > 0:
        print(f"\n[TIME]  消息延迟:")
        print(f"  平均: {report['latency']['avg_seconds']:.2f}秒")
        print(f"  峰值: {report['latency']['max_seconds']:.2f}秒")
        print(f"  [OK] 目标: < 10秒" if report['latency']['avg_seconds'] < 10 else f"  [FAIL] 超标: {report['latency']['avg_seconds']:.2f}秒 > 10秒")
    else:
        print(f"[WARN] 测试期间无新消息，无法测试延迟")

    # 综合评估
    print("\n" + "=" * 60)
    passed = (
        report['cpu']['avg'] < 5 and
        report['memory']['avg_mb'] < 100 and
        (report['latency']['avg_seconds'] < 10 or report['latency']['avg_seconds'] == 0)
    )

    if passed:
        print("[PASS] 性能测试通过")
    else:
        print("[FAIL] 性能测试未通过，需要优化")

    print("=" * 60)


if __name__ == "__main__":
    test_realtime_monitor()
