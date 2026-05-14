---
id: cc39
title: 三叶草-音频播放器-歌词下载功能集成
status: cancelled
priority: high
tags:
- 三叶草
- 音频播放器
- 歌词下载
- 功能开发
created_at: 2026-04-23T13:55:28.992901300+00:00
updated_at: 2026-04-24T00:00:00.000000000+00:00
---

## 客户信息
- 客户昵称：三叶草
- wxid: wxid_pr7g6zk2fmvm22
- 所在群：49487213350@chatroom
- 开发者：@长腿叔叔

## 需求来源
- 最新沟通时间：2026-04-23 20:20:51
- 需求确认时间：2026-04-23 14:32-20:20

## 功能需求

### 1. 歌词下载核心功能
- 点击按钮弹出下载窗口
- 支持歌词搜索（自动匹配或手动搜索）
- 下载歌词文件（LRC格式，带时间轴）

### 2. 文件保存 ⭐ 关键
- **歌词必须保存到音频文件所在目录**
- 文件命名：与音频文件同名，扩展名.lrc
- 示例：`C:\Music\歌曲名.mp3` → `C:\Music\歌曲名.lrc`

### 3. 快捷打开功能
- 提供"打开文件夹"按钮
- 点击后打开音频文件所在目录
- 可直接查看音频和歌词文件

### 4. UI交互
- 下载窗口：搜索框 + 歌词列表 + 下载按钮
- 参考酷狗音乐的歌词下载交互

## 技术要点

### 歌词API选择
- 网易云音乐API
- QQ音乐API
- 酷狗音乐API
- 建议优先级：网易云 > QQ音乐 > 酷狗

### 文件路径处理
```javascript
// 获取当前播放音频的完整路径
const audioPath = getCurrentAudioPath();
// 解析目录和文件名
const dir = path.dirname(audioPath);
const name = path.basename(audioPath, path.extname(audioPath));
// 生成歌词保存路径
const lrcPath = path.join(dir, `${name}.lrc`);
```

### 打开文件夹功能
```javascript
// Windows
const { shell } = require('electron');
shell.showItemInFolder(audioPath);
```

## 待确认问题
1. 歌词格式：LRC（带时间轴）还是纯文本？ → 建议LRC
2. 歌词来源：使用哪个平台的API？ → 建议网易云
3. 搜索方式：自动匹配歌曲名还是手动搜索？ → 建议自动+手动
4. 已有歌词处理：覆盖还是跳过？ → 建议提示用户选择

## 开发步骤
1. 查看现有源码结构，确认技术栈（Electron/Web/其他）
2. 集成歌词API（网易云音乐）
3. 实现歌词搜索和下载逻辑
4. 实现文件保存到音频目录
5. 实现打开文件夹功能
6. 设计并实现下载弹窗UI
7. 测试：下载、保存、打开功能
8. 打包交付

## 相关文件
- 源码压缩包：客户已于 2026-04-23 13:49-14:03 发送
- 聊天记录：output/sanyecao_messages.txt
- 需求分析：output/sanyecao_requirements_summary.md

## 项目背景
- 项目类型：桌面音频播放器
- 现有功能：音频播放、桌面歌词显示、保存歌曲
- 参考软件：酷狗音乐
- 技术栈：待确认（可能是Electron）

## 优先级
高 - 客户最新需求，需尽快实现