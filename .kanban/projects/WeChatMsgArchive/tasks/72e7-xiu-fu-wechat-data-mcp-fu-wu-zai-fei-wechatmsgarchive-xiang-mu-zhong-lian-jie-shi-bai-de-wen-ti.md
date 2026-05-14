---
id: '72e7'
title: 修复 wechat-data MCP 服务在非 WeChatMsgArchive 项目中连接失败的问题
status: todo
priority: high
tags:
- bug
- mcp
- cross-project
created_at: 2026-04-30T09:42:59.227190600+00:00
updated_at: 2026-04-30T09:42:59.227190600+00:00
---

# 问题描述

wechat-data MCP 服务在 WeChatMsgArchive 项目中可以正常连接和使用，但在其他项目（如 wx-claw）中显示 `wechat-data · ✘ failed`，无法连接。

## 症状

- **WeChatMsgArchive 项目**：wechat-data 服务正常 ✅
- **wx-claw 项目**：wechat-data 服务显示 failed ❌
- **子代理新会话**：在 wx-claw 项目中测试正常 ✅（说明服务本身可用）
- **用户现有会话**：即使重启命令行窗口也无法连接 ❌

## 已完成的排查和修复

### 1. 修复了 database.py 的路径问题 ✅

**问题**：`WeChatDatabase.__init__` 使用 `os.getcwd()` 构建 `decrypted_db_dir` 路径，导致在不同工作目录下路径错误。

**修复**：
```python
# 修复前
self.decrypted_db_dir = os.path.join(os.getcwd(), 'output', 'decrypted_db', 'Multi')

# 修复后
db_dir = os.path.dirname(os.path.abspath(self.db_path))
self.decrypted_db_dir = os.path.join(db_dir, 'decrypted_db', 'Multi')
```

**文件**：`mcp_servers/wechat_data/database.py` 第 27 行

### 2. 修复了 server.py 的模块导入问题 ✅

**问题**：直接运行 `server.py` 时相对导入失败。

**修复**：添加了路径处理逻辑，支持直接运行和模块导入两种方式。

```python
# 支持直接运行和模块导入两种方式
if __name__ == "__main__":
    # 直接运行时，添加项目根目录到 sys.path
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from mcp_servers.wechat_data.tools import WeChatTools, TOOLS
else:
    # 模块导入时使用相对导入
    from .tools import WeChatTools, TOOLS
```

**文件**：`mcp_servers/wechat_data/server.py` 第 13-22 行

### 3. 更新了 MCP 配置 ✅

**修改**：
- 从 `-m` 模块方式改为直接运行脚本
- 使用 Windows 反斜杠路径格式
- 添加 `PYTHONIOENCODING=utf-8` 环境变量

**配置文件**：`C:\Users\Administrator\.claude\mcp.json`

```json
"wechat-data": {
  "command": "D:\\develoment_home\\project_home\\WeChatMsgArchive\\venv\\Scripts\\python.exe",
  "args": [
    "D:\\develoment_home\\project_home\\WeChatMsgArchive\\mcp_servers\\wechat_data\\server.py",
    "--db-path",
    "D:\\develoment_home\\project_home\\WeChatMsgArchive\\output\\wechat_index.db"
  ],
  "env": {
    "PYTHONIOENCODING": "utf-8"
  }
}
```

### 4. 验证测试 ✅

**测试结果**：
- 手动启动服务：正常 ✅
- 数据库连接：正常（139870 条消息）✅
- 子代理新会话测试：所有 8 个工具正常工作 ✅
- 用户现有会话：仍然失败 ❌

## 未解决的问题

### 核心问题：会话缓存/连接状态问题

**现象**：
- 子代理在新会话中可以正常连接和使用 wechat-data
- 用户的现有会话即使重启命令行窗口也无法连接
- 说明问题不在服务本身，而在 Claude Code 的会话管理或 MCP 连接缓存

**可能原因**：
1. Claude Code 缓存了旧的 MCP 连接状态
2. 会话级别的 MCP 初始化失败后没有重试机制
3. 某些会话元数据导致 MCP 服务无法正确重新连接
4. 项目级别的 MCP 配置覆盖或冲突（已排除，wx-claw 无项目级配置）

## 需要进一步排查的方向

1. **Claude Code 会话管理机制**
   - 会话如何初始化 MCP 连接
   - 连接失败后的重试策略
   - 会话缓存的清理机制

2. **MCP 连接生命周期**
   - 连接何时建立
   - 失败状态如何持久化
   - 如何强制重新连接

3. **日志和诊断**
   - Claude Code 的 MCP 连接日志位置
   - 如何获取详细的连接失败原因
   - 是否有调试模式可以查看 MCP 通信

4. **配置加载顺序**
   - 全局配置 vs 项目配置的优先级
   - 配置更新后何时生效
   - 是否需要特定的重启流程

## 临时解决方案

用户可以通过以下方式使用 wechat-data 功能：
1. 在 WeChatMsgArchive 项目中使用（正常工作）
2. 创建新的 Claude Code 会话（子代理验证可用）
3. 使用 Python 脚本直接调用 `WeChatTools` 类

## 相关文件

- `mcp_servers/wechat_data/server.py` - MCP 服务主文件
- `mcp_servers/wechat_data/database.py` - 数据库访问层（已修复路径问题）
- `mcp_servers/wechat_data/tools.py` - 工具定义
- `C:\Users\Administrator\.claude\mcp.json` - 全局 MCP 配置
- `test_mcp_startup.py` - 测试脚本

## 经验总结

1. **路径问题是跨项目 MCP 服务的常见陷阱**
   - 避免使用 `os.getcwd()`，应基于配置文件或数据文件的绝对路径
   - 使用 `os.path.abspath()` 和 `os.path.dirname()` 构建可靠的路径

2. **MCP 服务需要支持直接运行**
   - 不能依赖 `-m` 模块方式，因为工作目录不可控
   - 需要在 `if __name__ == "__main__"` 中处理 `sys.path`

3. **Windows 编码问题**
   - 必须设置 `PYTHONIOENCODING=utf-8`
   - 测试脚本需要处理 stdout/stderr 编码

4. **MCP 连接状态的持久化**
   - Claude Code 会缓存 MCP 连接状态
   - 配置更新后可能需要完全重启应用
   - 会话级别的连接失败可能无法自动恢复

5. **测试策略**
   - 使用子代理创建新会话可以验证服务本身是否正常
   - 手动启动服务可以排查启动问题
   - 直接调用 Python 类可以验证业务逻辑

## 下一步行动

1. 研究 Claude Code 的 MCP 连接管理机制
2. 查找 Claude Code 的 MCP 日志和诊断工具
3. 尝试不同的配置格式（stdio vs HTTP）
4. 考虑是否需要向 Claude Code 团队报告此问题