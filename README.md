# 小鹅通 M3U8 视频下载器（Windows / Termux）

> Fork 自 [likunqi/xiaoe-downloader](https://github.com/likunqi/xiaoe-downloader)，保留了原作者的提交历史与 Windows 版实现；在此之上新增了 [Termux / Android 平板移植版](termux/)，并为两个平台统一改进了分片合成与时长校验。

把你有权观看的小鹅通课程视频，一键嗅探并下载到本地 —— 方便转成文字、切片后交给大语言模型总结提炼，用几分钟吸收几小时课程的核心内容，比反复拖进度条高效得多。

## ⚠️ 使用须知

几个简单的约定，其实都是常识：

- 只下载**你有权限观看**的内容（自己注册、购买或被授权的课程），且仅用于个人学习；
- 下载的文件**只留在自己设备上**：不上传网盘、不分享、不转卖、不商用——版权始终属于课程作者；
- 本项目只是一个本地技术工具，与任何平台无关，按"现状"提供，使用中产生的问题由使用者自己负责；
- 本仓库的改动与原作者 [likunqi](https://github.com/likunqi) 无关，也请勿就本仓库的问题打扰原作者；内容相关方如有异议，提 Issue 即可，核实后处理。

> 📜 完整版免责声明（项目宗旨、合规前提、红线清单、版权归属、责任切割等七节全文）见 **[DISCLAIMER.md](DISCLAIMER.md)** —— 使用本项目的任何部分即视为已阅读并接受其全部内容。

---

## ✨ 功能特性

| 能力 | 说明 |
|------|------|
| 🔍 自动嗅探 | XHR + Fetch 双重拦截；油猴脚本 v1.2（Termux 版）还支持 iframe 内嗅探 + performance 资源补扫，防漏抓 |
| 🔐 AES-128 解密 | 密钥 + IV 自动处理，IV 按 HLS 标准随分片序号递增 |
| 🪆 嵌套 M3U8 展开 | 自动探测小鹅通私有混淆索引（外层分片 ≤ 2 时逐层展开） |
| ⏱ Token 预检 | 解析 URL 中的过期时间参数，提前预警 403 |
| ⚡ 并行下载 | 6 线程并发 + 进度条，最多 3 个视频排队 |
| 🎬 分片合成 + 时长校验 | TS 二进制拼接 → `+genpts` 重建时间戳无损重封装 → ffprobe 实测时长与 m3u8 声明时长对比，偏差超阈值自动回退重编码修复（两平台一致） |
| 🧰 自动装依赖 | 启动时自动 pip 安装缺失依赖（清华镜像） |
| 📄 完整日志 | 控制台 + downloader.log 双输出，403/404/401 分场景给出诊断提示 |

### 工作流程

```
浏览器打开小鹅通课程页
        │
        ▼
油猴脚本拦截 XHR/Fetch 中的 .m3u8 地址（含 iframe 内嵌播放器）
        │
        ▼  点击「发送到下载」
本地 Python 下载器（127.0.0.1:8910）接收任务
        │
        ▼
请求 M3U8 索引 → 解析 TS 分片与 AES-128 密钥（Token 过期预检）
        │
        ▼
6 线程并发下载分片 + AES-128-CBC 解密（失败自动重试 3 次）
        │
        ▼
TS 二进制拼接 → ffmpeg +genpts 重封装 → ffprobe 时长校验 ──异常──▶ 重编码修复
        │
        ▼
成品 MP4 存入 downloads/
```

> 关于时长校验：早期版本用 ffmpeg concat 列表合并，分片边界的独立时间戳间隙会让**成片时长莫名变长**（进度条跳帧、黑屏）。现在改为二进制拼接后重建时间轴，并用 ffprobe 校验实际时长与 m3u8 `EXTINF` 声明时长之和（阈值 `max(3s, 2%)`），异常自动重编码修复。此改进最初在 Termux 版实现，现已同步至 Windows 版。

---

## 📦 目录结构

```
xiaoe-downloader/
├── DISCLAIMER.md               # 完整版免责声明
├── downloader.py               # Windows 核心下载引擎
├── 小鹅通视频 m3u8 地址嗅探提取器.js   # 油猴脚本 v1.0（原版，保留）
├── 小鹅通视频 m3u8 地址嗅探提取器 (通用版)-1.2.user.js   # 油猴脚本 v1.2（推荐，双平台通用）
├── 启动.bat                     # Windows 一键启动
├── ffmpeg.exe                   # 捆绑的 ffmpeg（Windows）
├── requirements.txt            # Python 依赖
└── termux/                     # ★ Termux / Android 平板移植版
    ├── downloader.py           # Termux 版下载器（venv 运行）
    ├── 小鹅通视频 m3u8 地址嗅探提取器 (Termux版)-1.2.user.js
    └── README.md               # Termux 安装与使用指南
```

`downloads/` 为视频输出目录（运行时自动创建）；`downloader.log` 为运行日志（已 gitignore）。

---

## 🖥️ Windows 使用

1. **装油猴脚本**：浏览器安装 Tampermonkey → 新建脚本 → 粘贴 `小鹅通视频 m3u8 地址嗅探提取器 (通用版)-1.2.user.js` 全部内容并保存（推荐：含 iframe 嗅探与 performance 补扫，双平台通用；原版 v1.0 `小鹅通视频 m3u8 地址嗅探提取器.js` 也仍可用）；
2. **启动下载器**：双击 `启动.bat`，或命令行 `python -u downloader.py`（依赖会自动安装）；
3. **下载**：打开课程视频页 → 右下角浮窗弹出 → 点「发送到下载」→ 成品在 `downloads/`。

> 需保证 `ffmpeg.exe` 与脚本同目录（仓库已捆绑）或其在系统 PATH 中。时长读取优先用 `ffprobe`（完整版 ffmpeg 发行包自带），无 ffprobe 时自动回退解析 `ffmpeg -i` 的输出，仅有捆绑 `ffmpeg.exe` 也能完成时长校验。

## 📱 Termux / Android 平板使用

平板上"浏览器 + 下载器"一体：浏览器嗅探 → 本机 Termux 下载，无需电脑中转。

> **必须使用 venv**（Termux 全局 Python 受 PEP 668 保护）；ffmpeg 用 `pkg install ffmpeg` 安装。完整步骤见 **[termux/README.md](termux/README.md)**。

```bash
pkg update && pkg install python ffmpeg git
git clone --depth 1 --filter=blob:none --sparse https://github.com/woyaoxingfua/xiaoe-downloader.git
cd xiaoe-downloader && git sparse-checkout set termux && cd termux
python -m venv venv && source venv/bin/activate
python downloader.py   # 自动安装缺失依赖并重启
```

---

## ❓ 常见问题

- **浮窗未弹出**：确认 Tampermonkey 已启用、域名在 `@match` 列表内；看浏览器控制台的 `[油猴嗅探器]` 日志。
- **下载 403**：m3u8 链接有时效性，刷新课程页重新嗅探后立即发送（日志会显示 Token 剩余有效期）。
- **成片时长不对**：现在两平台都会自动校验并重编码修复；若仍异常，多半是分片没下全（看日志成功片数）。
- **Termux 后台被杀**：通知栏常驻 Termux、关闭电池优化、或 `termux-wake-lock`。
