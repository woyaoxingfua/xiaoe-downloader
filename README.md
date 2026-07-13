# 小鹅通 M3U8 视频下载器

一键嗅探并下载小鹅通（xiaoeknow）平台视频的本地工具。浏览器端通过 Tampermonkey 油猴脚本自动拦截 `.m3u8` 视频流地址，发送给本地 Python HTTP 服务进行多线程下载、解密与合并。

---

## 项目概览

核心组件:

- `downloader.py` - 核心下载引擎，HTTP API + M3U8 解析 + 并行下载 + ffmpeg 合并
- `小鹅通视频 m3u8 地址嗅探提取器.js` - Tampermonkey 油猴脚本，拦截 m3u8 请求
- `启动.bat` - Windows 一键启动脚本，自动寻找 Python
- `ffmpeg.exe` - 捆绑的 ffmpeg，TS 分片合并为 MP4
- `WPy32-3830/` - 捆绑的 WinPython 3.8.3 便携版
- `downloads/` - 视频输出目录
- `downloader.log` - 运行时日志
- `requirements.txt` - Python 依赖声明

---

## 工作流程

用户浏览小鹅通课程页面 -> 油猴脚本拦截 XHR/Fetch 请求中 .m3u8 地址 -> 弹出悬浮面板 -> 点击"发送到下载" -> 本地 Python 下载器（127.0.0.1:8910）接收任务 -> 请求 M3U8 索引 -> 解析 TS 分片列表与 AES 密钥 -> 并发下载 TS 分片（6线程） -> 探测嵌套 M3U8 -> 解密 AES-128 加密分片 -> ffmpeg 合并为 MP4 -> 清理临时文件

---

## 安装与使用

### 1. 安装油猴脚本

1. 浏览器安装 Tampermonkey 扩展
2. 打开 `小鹅通视频 m3u8 地址嗅探提取器.js` 文件，复制全部内容
3. 点击 Tampermonkey 图标 -> 添加新脚本 -> 粘贴 -> 保存
4. 脚本自动匹配域名: xiaoeknow.com, xet.tech, xiaoe-tech.com, xet.pomoho.com, xet-pc.citv.cn

### 2. 启动下载器

方式 A（推荐）: 双击 `启动.bat`

方式 B: `python -u downloader.py`

### 3. 开始下载

1. 打开任意小鹅通视频课程页面
2. 脚本自动嗅探视频流，页面右下角弹出浮窗
3. 点击"发送到下载"
4. 视频保存在 downloads/ 目录

控制台输出示例:

```
  [1/4] 下载索引...
  [2/4] 获取密钥... 无需密钥（视频未加密）
  [3/4] 下载中: 100%| 870/870
  [4/4] 合并 (126.1s 下载, 870/870 成功)... 1311.5 MB
```

---

## 功能特性

### 核心能力

- M3U8 解析: EXT-X-KEY（AES-128）、EXTINF、IV 等标签
- AES-128 解密: 密钥+IV 自动处理
- 嵌套 M3U8 检测: 自动探测并展开混淆索引
- 并行下载: 6 线程并发，进度条实时显示
- ffmpeg 合并: -c copy 无损合并，失败自动回退重编码
- Token 检测: 解析 URL 中 expires 参数，提前预警
- 并发队列: 最多 3 个视频同时排队下载
- 重试机制: 分片失败自动重试 3 次
- 自动装依赖: 启动时 pip 安装 requests/pycryptodome/tqdm

### 网络与兼容性

- CORS 全开，禁用系统代理直连 CDN
- Referer 自动锁定为课程页面
- 自动检测控制台编码（UTF-8/GBK）
- 文件名过滤非法字符

### 浏览器脚本

- XHR + Fetch 双重拦截
- 悬浮面板显示视频名称和 URL
- 连接状态实时检测
- 14+ 种 DOM 选择器逐级兜底提取标题

---

## 依赖

- requests - HTTP 请求
- pycryptodome - AES-128 CBC 解密
- tqdm - 下载进度条
- ffmpeg.exe - TS 合并为 MP4（捆绑提供）

---

## 技术细节

### AES-128 解密

每个 TS 分片使用独立 IV: `IV[:12] + 分片序号(4字节大端)`，符合 HLS 标准。

### 嵌套 M3U8

小鹅通部分视频使用混淆索引: 外层 M3U8 只有 1-2 个"分片"，实际指向另一个 M3U8。分片数 <= 2 时自动下载探针并展开。

### 日志

所有输出同时写入控制台和 downloader.log（UTF-8），包含请求状态、Token 分析、分片信息、错误堆栈。

---

## 项目结构

```
xiaoe-downloader-最终版/
  downloader.py               # 核心下载引擎
  小鹅通视频 m3u8 地址嗅探提取器.js # 油猴脚本
  启动.bat                    # Windows 启动脚本
  requirements.txt            # Python 依赖
  ffmpeg.exe                  # 视频合并工具
  downloader.log              # 运行时日志
  downloads/                  # 视频输出目录
  WPy32-3830/                 # 便携 Python 3.8.3
```

---

## 常见问题

浮窗未弹出: 确认 Tampermonkey 已启用、域名在 @match 中、打开控制台查看日志。

启动报错: 确保 ffmpeg.exe 在同级目录或系统 PATH 中；检查端口 8910 是否被占用。

下载 403: m3u8 链接有时效性，刷新页面重新嗅探后立即发送。

已下载示例: downloads/ 中的 `从负债到通过互联网年入百万的逆袭历程.mp4`（1.31 GB, 870 分片, 1080p）是工具实测成果。
