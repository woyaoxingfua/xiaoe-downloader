# 📱 Termux / Android 平板版使用说明

本目录是 [likunqi/xiaoe-downloader](https://github.com/likunqi/xiaoe-downloader) 的 **Termux / Android 平板移植版**。在平板上同时运行浏览器与 Termux，嗅探脚本与下载器通过 `127.0.0.1:8910` 本机通信，一台平板即可完成"看课 → 嗅探 → 下载"全流程。

> ⚠️ 使用前请务必阅读仓库根目录 [README.md](../README.md) 中的**免责声明**。仅限下载你有合法访问权限的内容，用于个人学习。

---

## 与 Windows 版的差异

| 项目 | Windows 版 | Termux 移植版 |
|------|-----------|---------------|
| ffmpeg | 捆绑 `ffmpeg.exe` | 来自 `pkg install ffmpeg`（含 ffprobe） |
| 控制台编码 | 自动探测 Windows 代码页（GBK/UTF-8） | 统一 UTF-8 |
| 依赖安装 | pip 自动安装（清华镜像） | pip 自动安装（清华镜像，**需 venv**） |
| 油猴脚本 | v1.0 | **v1.2**：iframe 内嗅探 + postMessage 汇总、performance 资源补扫 |

> 分片合成方式（TS 二进制拼接 + `-fflags +genpts` 重建时间戳 + ffprobe 时长校验 + 重编码回退）最初在 Termux 版实现，**现已同步至 Windows 版**，两平台行为一致。

### 为什么改分片合成？

早期版本使用 ffmpeg concat 列表合并，每个 TS 分片边界保留独立时间戳，遇到分片间 PTS 不连续时会插入间隙，导致**合成后的视频时长莫名变长**（拖进度条出现跳帧/黑屏）。移植版改为（现已同步至 Windows 版）：

1. **二进制拼接**：MPEG-TS 是流格式，直接按字节序拼接所有分片为单个 `.ts`；
2. **`+genpts` 无损重封装**：让 ffmpeg 基于连续流重新生成 PTS，`-avoid_negative_ts make_zero` 归零起始时间戳；
3. **ffprobe 时长校验**：与 m3u8 `EXTINF` 声明时长之和对比，偏差超阈值自动转**重编码**修复。

---

## 环境要求

- Android 7.0+，安装 [Termux](https://f-droid.org/packages/com.termux/)（**推荐 F-Droid 版**，Google Play 版已停止维护）
- 平板浏览器需支持 Tampermonkey 扩展，如 **Kiwi Browser**、**Firefox for Android**、**Edge Canary** 等
- 磁盘空间：Python + ffmpeg 约 500MB，另加视频输出空间

---

## 安装步骤（必须使用 venv）

> ⚠️ **必须创建 venv 虚拟环境**：Termux 的全局 Python 受 PEP 668 保护（externally-managed-environment），直接 `pip install` 会被拒绝。脚本自带的依赖自动安装也只在 venv 内才能正常工作。

### 1. 安装系统依赖

```bash
pkg update && pkg upgrade
pkg install python ffmpeg git
```

### 2. 克隆仓库（推荐稀疏检出，跳过原版捆绑的 100MB ffmpeg.exe）

```bash
git clone --depth 1 --filter=blob:none --sparse https://github.com/woyaoxingfua/xiaoe-downloader.git
cd xiaoe-downloader
git sparse-checkout set termux
```

> 若网络不畅，可先给 git 配置代理：`git config --global http.proxy http://127.0.0.1:7890`（端口按你的代理软件调整）。

### 3. 创建 venv 并安装依赖

```bash
cd termux
python -m venv venv
source venv/bin/activate
pip install requests pycryptodome tqdm
```

> 依赖也可以不手动装 —— 在 venv 内直接运行 `python downloader.py`，脚本检测到缺依赖会自动通过清华镜像安装并自动重启。

### 4. 启动下载器

```bash
source venv/bin/activate   # 每次新开终端都要先激活 venv
python downloader.py
```

看到如下输出即启动成功：

```
==================================================
小鹅通 M3U8 视频下载器 (Termux 版)
ffmpeg: /data/data/com.termux/files/usr/bin/ffmpeg
输出:   .../termux/downloads
端口:   localhost:8910
等待浏览器发送下载任务...
==================================================
```

---

## 浏览器端（同一天平板）

1. 浏览器安装 Tampermonkey 扩展
2. 新建脚本，粘贴本目录 `小鹅通视频 m3u8 地址嗅探提取器 (Termux版)-1.2.user.js` 全部内容并保存
3. 脚本自动匹配域名: `xiaoeknow.com`、`xet.tech`、`xiaoe-tech.com`、`xet.pomoho.com`、`xet-pc.citv.cn`

---

## 使用流程

1. Termux 中启动下载器（保持前台或通知栏常驻，必要时在系统设置中关闭 Termux 电池优化）
2. 浏览器打开课程视频页面，脚本自动嗅探 `.m3u8` 地址（含 iframe 内嵌播放器），右上角弹出悬浮面板
3. 确认面板显示 **🟢 已连接**，点击「📤 发送到下载」
4. 回到 Termux 查看下载进度，成品 MP4 在 `termux/downloads/` 目录

---

## 常见问题

**提示 `externally-managed-environment`**
未激活 venv。执行 `source venv/bin/activate` 后再运行。

**提示未找到 ffmpeg**
执行 `pkg install ffmpeg`。脚本同时需要 ffprobe 做时长校验，ffmpeg 包自带。

**下载 403**
m3u8 链接有时效性（token 过期 / Referer 校验 / IP 变化）。日志中会输出 Token 剩余有效期，刷新课程页面重新嗅探后立即发送。

**合成的视频时长异常**
脚本会用 ffprobe 自动校验并回退到重编码修复；若仍异常，检查网络中断导致的丢片（日志会显示 `N/总M 成功`）。

**Termux 切到后台下载就停了**
Android 杀后台所致：通知栏常驻 Termux 会话、关闭电池优化、或使用 `termux-wake-lock` 保持唤醒。
