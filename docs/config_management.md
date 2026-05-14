# 配置管理系统

## 功能
统一管理所有配置项，消除硬编码，支持多环境部署。

## 特性
- ✅ 类型安全（Pydantic 模型）
- ✅ 环境变量覆盖
- ✅ 配置验证和错误提示
- ✅ 敏感信息隔离
- ✅ 多环境支持

## 快速开始

### 1. 安装依赖
```bash
pip install pydantic-settings
```

### 2. 创建配置文件
```bash
cp .env.example .env
# 编辑 .env 填写实际值
```

### 3. 使用配置
```python
from config import config

# 访问配置
print(config.wechat.wxid)
print(config.monitor.monitor_users)
print(config.database.index_db_path)
```

## 配置结构

```
AppConfig
├── wechat: WeChatConfig          # 微信相关
│   ├── wx_data_dir         # 数据目录
│   ├── wxid                      # 微信ID
│   └── wx_version                # 版本
├── monitor: MonitorConfig        # 监控配置
│   ├── monitor_users             # 监控用户列表
│   ├── monitor_interval          # 监控间隔
│   └── analysis_days             # 分析天数
├── database: DatabaseConfig      # 数据库配置
│   ├── decrypted_db_dir          # 解密DB目录
│   ├── index_db_path         # 索引DB路径
│   └── encrypted_db_dir          # 加密DB目录
├── api: APIConfig         # API配置
│   ├── anthropic_api_key         # API密钥
│   ├── anthropic_model           # 模型名称
│   └── api_timeout          # 超时时间
├── security: SecurityConfig      # 安全配置
│   ├── master_password           # 主密码
│   ├── audit_log_path            # 审计日志
│   └── data_retention_days       # 数据保留
└── kanban: KanbanConfig          # 看板配置
    ├── kanban_root               # 看板根目录
    └── project_mapping           # 项目映射
```

## 环境变量命名规则

使用双下划线 `__` 分隔嵌套配置：

```bash
# 格式：<父配置>__<子配置>
WECHAT__WXID=wxid_xxx
MONITOR__MONITOR_USERS=用户1,用户2
DATABASE__INDEX_DB_PATH=output/index.db
```

## 配置优先级

1. 环境变量（最高优先级）
2. .env 文件
3. 代码中的默认值（最低优先级）

## 迁移指南

### 旧代码（硬编码）
```python
MONITOR_USERS = ["三叶草", "编程仝芷硕"]
INDEX_DB_PATH = "output/wechat_index.db"
```

### 新代码（配置管理）
```python
from config import config

monitor_users = config.monitor.monitor_users
index_db_path = config.database.index_db_path
```

## 配置验证

配置会在加载时自动验证：

```python
# 路径验证
config.wechat.wx_data_dir  # 自动检查目录是否存在

# 范围验证
config.monitor.monitor_interval  # 必须 >= 60秒

# 类型验证
config.monitor.analysis_days  # 必须是整数
```

## 敏感信息保护

敏感配置（API密钥、密码）：
1. 不要提交到 Git（.env 已在 .gitignore）
2. 使用环境变量或密钥管理服务
3. 生产环境使用加密存储

## 多环境配置

```bash
# 开发环境
ENVIRONMENT=development
LOG_LEVEL=DEBUG

# 生产环境
ENVIRONMENT=production
LOG_LEVEL=WARNING
```

## 故障排查

### 配置加载失败
```bash
# 检查配置
python config.py

# 输出当前配置（JSON格式）
```

### 环境变量未生效
- 确认 .env 文件在项目根目录
- 确认环境变量命名正确（双下划线）
- 重启应用加载新配置
