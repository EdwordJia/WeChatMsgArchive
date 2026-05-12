# 实时消息监控器

## 功能
替代30分钟轮询机制，实现秒级实时消息推送。

## 技术方案
- 使用 `watchdog` 监听 `MSG*.db` 文件变化
- 触发增量同步到索引数据库
- 支持 webhook 回调通知外部系统

## 性能目标
- 新消息延迟 < 10秒
- CPU占用 < 5%
- 内存占用 < 100MB

## 安装依赖
```bash
pip install watchdog
```

## 使用方法

### 1. 基础使用
```bash
python wechat_realtime_monitor.py
```

### 2. 配置路径
编辑 `wechat_realtime_monitor.py` 中的配置：
```python
DECRYPTED_DB_DIR = "output/decrypted_db/Multi"  # 解密数据库目录
INDEX_DB_PATH = "output/wechat_index.db"      # 索引数据库路径
```

### 3. 自定义回调
```python
def on_new_messages(db_path: str, count: int):
    """新消息回调"""
    # 发送通知到外部系统
    requests.post("https://your-webhook.com/notify", json={
        "source": db_path,
        "count": count,
        "timestamp": time.time()
    })

monitor.start(callback=on_new_messages)
```

## 工作原理

1. **文件监听**: 监听 `MSG*.db` 文件的修改事件
2. **防抖处理**: 5秒内同一文件只触发一次同步
3. **增量同步**: 只同步时间戳大于上次同步的新消息
4. **批量写入**: 批量插入到索引数据库，提升性能

## 日志
日志文件：`output/realtime_monitor.log`

## 注意事项
- 需要先运行解密脚本生成解密数据库
- 监控器会持续运行，按 Ctrl+C 停止
- 建议配合 Windows 服务或 systemd 实现开机自启

## 后续优化
- [ ] 支持配置文件
- [ ] 支持多种通知方式（邮件、钉钉、企业微信）
- [ ] 性能监控和指标上报
- [ ] 支持分布式部署
