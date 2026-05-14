"""
统一配置管理系统

使用 Pydantic Settings 管理所有配置项，消除硬编码。

特性：
- 类型安全的配置模型
- 环境变量覆盖
- 配置验证和错误提示
- 敏感信息加密
- 多环境支持（dev/prod）
"""

from typing import List, Optional
from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class WeChatConfig(BaseSettings):
    """微信相关配置"""

    # 微信数据目录
    wx_data_dir: str = Field(
        default="E:/腾讯电脑管家文件搬家/微信聊天文件搬家/Users/WeChat Files",
        description="微信数据根目录"
    )

    # 微信 ID
    wxid: str = Field(
        default="",
        description="微信ID（如 wxid_xxx）"
    )

    # 微信版本
    wx_version: str = Field(
        default="v3",
      description="微信版本（v3 或 v4）"
    )

    @field_validator("wx_data_dir")
    @classmethod
    def validate_wx_data_dir(cls, v: str) -> str:
    """验证微信数据目录存在"""
        if v and not Path(v).exists():
            raise ValueError(f"微信数据目录不存在: {v}")
        return v


class MonitorConfig(BaseSettings):
    """监控配置"""

    # 监控用户列表
    monitor_users: List[str] = Field(
        default=["三叶草", "编程仝芷硕", "Estelle", "烨林", "沐光", "密码机"],
        description="需要监控的用户昵称列表"
    )

    # 监控间隔（秒）
    monitor_interval: int = Field(
        default=1800,  # 30分钟
        ge=60,  # 最小1分钟
        description="监控间隔（秒）"
    )

    # 分析时间范围（天）
    analysis_days: int = Field(
        default=1,
        ge=1,
        le=30,
        description="分析最近N天的消息"
    )


class DatabaseConfig(BaseSettings):
    """数据库配置"""

    # 解密数据库输出目录
    decrypted_db_dir: str = Field(
        default="output/decrypted_db",
        description="解密后的数据库存储目录"
    )

    # 索引数据库路径
    index_db_path: str = Field(
        default="output/wechat_index.db",
        description="消息索引数据库路径"
    )

    # 加密数据库目录
    encrypted_db_dir: str = Field(
      default="output/encrypted_db",
        description="加密存储的数据库目录"
    )


class APIConfig(BaseSettings):
    """API 配置"""

    # Anthropic API Key
    anthropic_api_key: Optional[str] = Field(
        default=None,
        description="Anthropic API Key（用于 LLM 分析）"
    )

    # API 模型
    anthropic_model: str = Field(
        default="claude-opus-4-20250514",
        description="使用的 Claude 模型"
    )

    # API 超时（秒）
    api_timeout: int = Field(
        default=30,
        ge=5,
        description="API 请求超时时间"
    )


class SecurityConfig(BaseSettings):
    """安全配置"""

    # 数据加密主密码
    master_password: Optional[str] = Field(
    default=None,
        description="数据加密主密码"
    )

    # 审计日志路径
    audit_log_path: str = Field(
        default="output/security_audit.log",
        description="安全审计日志路径"
    )

    # 数据保留天数
    data_retention_days: int = Field(
      default=7,
        ge=1,
        description="解密数据保留天数"
    )


class KanbanConfig(BaseSettings):
    """看板配置"""

    # kanban-doc 根目录
    kanban_root: str = Field(
        default="D:/develoment_home/project_home/videKanban/kanban-doc/.kanban",
        description="kanban-doc 数据目录"
    )

    # 项目映射
    project_mapping: dict = Field(
        default={
            "syc-player": "三叶草播放器",
        "linux-qt-jr": "镜片检测系统",
            "MCE": "MCE项目"
        },
      description="项目名称映射"
    )


class AppConfig(BaseSettings):
    """应用主配置"""

    # 应用名称
    app_name: str = Field(
      default="WeChatMsgArchive",
        description="应用名称"
    )

    # 环境
    environment: str = Field(
        default="development",
        description="运行环境（development/production）"
    )

    # 日志级别
    log_level: str = Field(
        default="INFO",
        description="日志级别"
    )

    # 日志文件路径
    log_file: str = Field(
        default="output/app.log",
        description="日志文件路径"
    )

    # 子配置
    wechat: WeChatConfig = Field(default_factory=WeChatConfig)
    monitor: MonitorConfig = Field(default_factory=MonitorConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    kanban: KanbanConfig = Field(default_factory=KanbanConfig)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False
    )

# 全局配置实例
config = AppConfig()


# 使用示例
if __name__ == "__main__":
    import json

    # 打印当前配置
    print("当前配置：")
    print(json.dumps(config.model_dump(), indent=2, ensure_ascii=False))

    # 验证配置
    print(f"\n微信数据目录: {config.wechat.wx_data_dir}")
    print(f"监控用户: {', '.join(config.monitor.monitor_users)}")
    print(f"索引数据库: {config.database.index_db_path}")
