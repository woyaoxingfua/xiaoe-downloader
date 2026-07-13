"""小鹅通 M3U8 视频下载器 — 交互式命令行版"""

# ============================================================
#  自动检测并安装依赖
# ============================================================
import sys, subprocess as _sp, importlib as _im

_required = {
    'requests': 'requests',
    'Crypto': 'pycryptodome',
    'tqdm': 'tqdm',
}
_missing = []
for _mod, _pkg in _required.items():
    try:
        _im.import_module(_mod)
    except ImportError:
        _missing.append(_pkg)

if _missing:
    print(f'[依赖] 正在安装: {" ".join(_missing)} ...')
    _sp.check_call(
        [sys.executable, '-m', 'pip', 'install', *_missing,
         '-i', 'https://pypi.tuna.tsinghua.edu.cn/simple'],
        stdout=_sp.DEVNULL, stderr=_sp.DEVNULL
    )
    print('[依赖] 安装完成，重启程序...\n')
    _sp.run([sys.executable] + sys.argv)
    sys.exit(0)

# ============================================================
import os, time, shutil, subprocess, binascii, re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from tqdm import tqdm

# 强制 stdout 行缓冲，确保 Windows CMD 中实时输出
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE_DIR, 'downloads')
os.makedirs(OUT, exist_ok=True)
LOG_FILE = os.path.join(BASE_DIR, 'downloader.log')


def _console_encoding():
    """获取 Windows 控制台实际代码页，避免 UTF-8/GBK 猜错"""
    try:
        import ctypes
        cp = ctypes.windll.kernel32.GetConsoleOutputCP()
        if cp == 65001:
            return 'utf-8'
        elif cp == 936:
            return 'gbk'
        else:
            return f'cp{cp}'
    except Exception:
        return (sys.stdout.encoding or 'utf-8').lower()


CONSOLE_ENC = _console_encoding()


def log(msg, end='\n'):
    """同时输出到控制台和日志文件。控制台按实际代码页编码，避免乱码"""
    ts = time.strftime('%H:%M:%S')
    line = f'[{ts}] {msg}'
    # 1. 文件日志（始终可靠）
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(line)
            if end:
                f.write(end)
            f.flush()
    except Exception:
        pass
    # 2. 控制台：按真实代码页编码
    try:
        data = (line + end).encode(CONSOLE_ENC, errors='replace')
    except Exception:
        data = (line + end).encode('utf-8', errors='replace')
    try:
        os.write(1, data)
    except Exception:
        try:
            os.write(2, data)
        except Exception:
            pass


FFMPEG = os.path.join(BASE_DIR, 'ffmpeg.exe')


def safe_name(name):
    """去除文件名中的非法字符"""
    return re.sub(r'[<>:"/\\|?*]', '_', name).strip()


def find_ffmpeg():
    for p in [FFMPEG, shutil.which('ffmpeg'), shutil.which('ffmpeg.exe')]:
        if p and os.path.isfile(p):
            return p
    return None


# 小鹅通及其 CDN 域名白名单
XIAOE_DOMAINS = (
    'xiaoeknow.com', 'xiaoe-tech.com', 'xiaoecloud.com',
    'xe-live.com', 'xiaoe-live.com', 'xeknow.com',
    'citv.cn', 'xet.tech', 'pomoho.com',
    'xiaoeeye.com', 'xiaoedata.com', 'e-quanzi.com',
    'baomihua.com', 'hainanzhenjun.com',
)


def _parse_url_token(url):
    """从 URL 参数中提取 token 过期时间信息，返回 (expiry_ts, 人类可读)"""
    from urllib.parse import urlparse, parse_qs
    params = parse_qs(urlparse(url).query)
    for key in ('expires', 'expire', 'deadline', 'exp', 't', 'timestamp', 'ts', 'etime', 'end'):
        vals = params.get(key, [])
        if vals:
            try:
                ts = int(vals[0])
                if ts > 1000000000:  # 秒级时间戳（2001年以后）
                    dt_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))
                    return ts, dt_str
            except (ValueError, OSError):
                pass
    return None, None


def download_one(name, m3u8_url, referer=None):
    """下载单个视频"""
    # 记录域名信息（调试用）
    from urllib.parse import urlparse
    _host = urlparse(m3u8_url).hostname or ''
    if not any(_host.endswith(d) for d in XIAOE_DOMAINS):
        log(f'    域名: {_host} (非小鹅通体系)')

    s = requests.Session()
    s.trust_env = False  # 禁用系统代理，直连
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': referer or 'https://xiaoe-tech.com/',
    })

    log(f'\n  {name}')
    log(f'  {"─" * 50}')

    # 1. 下载 M3U8
    log('  [1/4] 下载索引...')
    log(f'    请求 URL: {m3u8_url[:200]}')
    log(f'    Referer:  {s.headers.get("Referer", "")}')

    # Token 过期预检
    exp_ts, exp_str = _parse_url_token(m3u8_url)
    if exp_ts:
        now_ts = int(time.time())
        if exp_ts < now_ts:
            log(f'    ⚠ Token 已过期！过期时间: {exp_str} (已过 {now_ts - exp_ts} 秒)')
        else:
            remain = exp_ts - now_ts
            log(f'    Token 有效，过期时间: {exp_str} (剩余 {remain}s / {remain/60:.0f}min)')

    try:
        resp = s.get(m3u8_url, timeout=30)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if hasattr(e, 'response') and e.response else 0
        body = (e.response.text or '')[:200] if hasattr(e, 'response') and e.response else ''
        log(f'    失败: HTTP {code}')
        if code == 403:
            log(f'    ┌ 403 可能原因:')
            log(f'    │ 1. M3U8 链接中的 token 已过期（小鹅通链接通常有时效）')
            log(f'    │ 2. Referer 不匹配 CDN 防盗链白名单')
            log(f'    │ 3. 请求 IP 与 token 签发时的 IP 不一致')
            log(f'    └ 建议: 刷新课程页面后重新嗅探 m3u8 地址再发送')
            if body:
                log(f'    响应体: {body}')
        elif code == 404:
            log(f'    ┌ 404: M3U8 文件已被 CDN 移除，通常意味着链接已失效')
            log(f'    └ 建议: 刷新页面重新嗅探')
        elif code == 401:
            log(f'    ┌ 401: 需要认证，token 可能已过期')
            log(f'    └ 建议: 刷新页面重新嗅探')
        elif code >= 500:
            log(f'    CDN 服务器错误，可稍后重试')
        else:
            if body:
                log(f'    响应体: {body}')
        return False
    except requests.exceptions.ProxyError as e:
        log(f'    失败: 代理连接错误')
        log(f'    ┌ 系统配置了代理但代理不可用')
        log(f'    └ 详情: {e}')
        return False
    except requests.exceptions.ConnectionError as e:
        log(f'    失败: 无法连接服务器')
        log(f'    ┌ DNS 解析失败或网络不通')
        log(f'    └ 详情: {str(e)[:150]}')
        return False
    except requests.exceptions.Timeout:
        log(f'    失败: 连接超时 (30s)')
        log(f'    ┌ 服务器无响应，可能 CDN 节点不可达')
        log(f'    └ 建议: 检查网络或稍后重试')
        return False
    except Exception as e:
        log(f'    失败: {type(e).__name__}: {e}')
        return False
    m3u8 = resp.text
    base = '/'.join(m3u8_url.split('/')[:-1]) + '/'
    log(f'    状态码: {resp.status_code}  |  大小: {len(m3u8)} 字符')
    log(f'    基础路径: {base[:120]}')
    # 打印 m3u8 前几行，便于确认内容格式
    for i, line in enumerate(m3u8.strip().split('\n')[:6]):
        log(f'    m3u8[{i}]: {line.strip()[:150]}')

    # 检测 [xiaoe] 私有编码（confusion_index 格式：base64+嵌入=号混淆，需解码后AES解密）
    if m3u8.strip().startswith('[xiaoe]'):
        log('')
        log('  ⚠ 检测到 [xiaoe] 私有编码格式（confusion_index）')
        log('  ┌ 该格式使用 base64 + 嵌入 = 号混淆 + AES 加密')
        log('  └ 当前版本暂不支持，正在跳过...')
        return False

    # 2. 解析
    segments = []
    key_url = None
    iv = b'\x00' * 16
    for line in m3u8.split('\n'):
        line = line.strip()
        if 'URI=' in line and 'AES-128' in line:
            # 兼容 URI="..." 和 URI=... 两种格式
            uri_match = re.search(r'URI="?([^",]+)"?', line)
            if uri_match:
                key_url = uri_match.group(1)
                if not key_url.startswith('http'):
                    key_url = urljoin(base, key_url)
            iv_s = line.find('IV=0x')
            if iv_s != -1:
                iv = binascii.unhexlify(line[iv_s + 5:iv_s + 37])
        elif line and not line.startswith('#'):
            u = line if line.startswith('http') else urljoin(base, line)
            segments.append(u)

    log(f'    总片段: {len(segments)} 个')
    if key_url:
        log(f'    加密: AES-128 | 密钥地址: {key_url[:150]}')
        log(f'    IV: {iv.hex()}')
    else:
        log(f'    加密: 无（明文 TS）')
    if segments:
        log(f'    TS[0]:    {segments[0][:150]}')
        if len(segments) > 1:
            log(f'    TS[-1]:   {segments[-1][:150]}')

    # 2.5 检测嵌套 M3U8（confusion_index 等混淆索引：只有1个"片段"实为另一层 m3u8）
    if len(segments) <= 2:
        log('  [2.5] 检测嵌套索引...', end=' ')
        if not segments:
            log('M3U8 中无 TS 片段')
        else:
            try:
                probe = s.get(segments[0], timeout=30).content
                if probe.strip()[:20].startswith(b'#EXTM3U'):
                    log('发现嵌套 M3U8，展开中...')
                    inner_text = probe.decode('utf-8', errors='replace')
                    inner_base = '/'.join(segments[0].split('/')[:-1]) + '/'
                    new_segments = []
                    new_key_url = None
                    new_iv = b'\x00' * 16
                    for line in inner_text.split('\n'):
                        line = line.strip()
                        if 'URI=' in line and 'AES-128' in line:
                            uri_match = re.search(r'URI="?([^",]+)"?', line)
                            if uri_match:
                                new_key_url = uri_match.group(1)
                                if not new_key_url.startswith('http'):
                                    new_key_url = urljoin(inner_base, new_key_url)
                            iv_s2 = line.find('IV=0x')
                            if iv_s2 != -1:
                                new_iv = binascii.unhexlify(line[iv_s2 + 5:iv_s2 + 37])
                        elif line and not line.startswith('#'):
                            u = line if line.startswith('http') else urljoin(inner_base, line)
                            new_segments.append(u)
                    if new_segments:
                        segments = new_segments
                        key_url = new_key_url   # 以内层密钥为准（None = 未加密）
                        iv = new_iv
                        log(f'{len(segments)} 个真实片段')
                        if key_url:
                            log(f'    真实密钥: {key_url[:150]}')
                        else:
                            log(f'    内层未加密')
                        log(f'    真实 IV:   {iv.hex()}')
                        if segments:
                            log(f'    TS[0]:     {segments[0][:150]}')
                    else:
                        log('嵌套 M3U8 中无有效片段')
                else:
                    # 检查是否是 [xiaoe] 私有编码
                    if probe.strip()[:20].startswith(b'[xiaoe]'):
                        log('[xiaoe] 私有编码（暂不支持）')
                    else:
                        log('非嵌套（直接 TS 片段）')
            except Exception as e:
                log(f'检测跳过: {e}（继续正常下载）')

    # 3. 获取密钥（仅加密视频需要）
    log('  [2/4] 获取密钥...', end=' ')
    if key_url is None:
        log('无需密钥（视频未加密）')
        key = None
    else:
        try:
            key = s.get(key_url, timeout=15).content
            log(f'{len(key)} 字节')
        except Exception as e:
            log(f'失败: {e}')
            return False

    # 4. 并行下载
    tmp = os.path.join(OUT, f'tmp_{int(time.time())}')
    os.makedirs(tmp, exist_ok=True)

    def dl_one(url, key, iv, idx):
        for _ in range(3):
            try:
                data = s.get(url, timeout=60).content
                break
            except:
                time.sleep(1)
        else:
            return None
        if key is not None:
            seg_iv = iv[:12] + idx.to_bytes(4, 'big')
            dec = AES.new(key, AES.MODE_CBC, iv=seg_iv).decrypt(data)
            try:
                dec = unpad(dec, AES.block_size)
            except:
                pass
        else:
            dec = data
        fp = os.path.join(tmp, f's_{idx:05d}.ts')
        with open(fp, 'wb') as f:
            f.write(dec)
        return fp

    t0 = time.time()
    results = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        fut = {ex.submit(dl_one, u, key, iv, i): i for i, u in enumerate(segments)}
        with tqdm(total=len(segments), desc='  [3/4] 下载中', unit='片',
                  ncols=60, bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt}') as pbar:
            for f in as_completed(fut):
                if f.result():
                    results[fut[f]] = f.result()
                    pbar.update(1)
    elapsed = time.time() - t0

    if not results:
        log('  所有片段下载失败')
        shutil.rmtree(tmp, ignore_errors=True)
        return False

    # 5. 合并
    log(f'  [4/4] 合并 ({elapsed:.1f}s 下载, {len(results)}/{len(segments)} 成功)...', end=' ')
    files = [results[i] for i in sorted(results)]
    output = os.path.join(OUT, f'{safe_name(name)}.mp4')

    # Concat 列表
    lst = os.path.join(OUT, '_concat.txt')
    with open(lst, 'w', encoding='utf-8') as f:
        for fp in files:
            f.write(f"file '{fp.replace(os.sep, '/')}'\n")

    if os.path.exists(output):
        os.remove(output)

    cmd = [find_ffmpeg() or 'ffmpeg', '-f', 'concat', '-safe', '0',
           '-i', lst, '-c', 'copy', '-movflags', '+faststart', '-y', output]
    r = subprocess.run(cmd, capture_output=True, encoding='utf-8',
                       errors='replace', timeout=600)
    if os.path.exists(lst):
        os.remove(lst)

    if r.returncode != 0:
        # 重编码回退
        lst2 = os.path.join(OUT, '_concat2.txt')
        with open(lst2, 'w', encoding='utf-8') as f:
            for fp in files:
                f.write(f"file '{fp.replace(os.sep, '/')}'\n")
        cmd2 = [find_ffmpeg() or 'ffmpeg', '-f', 'concat', '-safe', '0',
                '-i', lst2, '-c:v', 'libx264', '-c:a', 'aac',
                '-movflags', '+faststart', '-y', output]
        subprocess.run(cmd2, capture_output=True, encoding='utf-8',
                       errors='replace', timeout=600)
        if os.path.exists(lst2):
            os.remove(lst2)

    shutil.rmtree(tmp, ignore_errors=True)

    if os.path.exists(output):
        mb = os.path.getsize(output) / 1048576
        log(f'  {mb:.1f} MB  ->  {output}')
        return True
    else:
        log('  合并失败')
        return False


# ============================================================
#  HTTP 服务 — 接收浏览器发来的下载任务
# ============================================================

import json
import traceback
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8910
total_count = 0
count_lock = threading.Lock()

# 线程池：支持同时下载最多3个
download_pool = ThreadPoolExecutor(max_workers=3)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_OPTIONS(self):
        log(f'HTTP OPTIONS {self.path}')
        self._cors()

    def do_GET(self):
        log(f'HTTP GET {self.path}')
        self._cors()
        self._json({'status': 'running', 'port': PORT, 'total': total_count})

    def do_POST(self):
        global total_count
        log(f'HTTP POST {self.path} 开始处理')
        try:
            length = int(self.headers.get('Content-Length', 0))
            raw = self.rfile.read(length)
            data = json.loads(raw)
            name = data.get('name', '').strip()
            url = data.get('url', '').strip()
            referer = data.get('referer', '').strip() or None

            log(f'HTTP POST {self.path} body_len={length}')
            log(f'JSON: name={name!r} referer={referer!r} url={url[:60]}...')

            if not name or not url:
                log('拒绝任务：name 或 url 为空')
                self._cors()
                self._json({'status': 'error', 'msg': 'missing name or url'})
                return

            log(f'>>> 收到任务: [{name}]')
            log(f'    URL: {url[:80]}...')

            self._cors()
            self._json({'status': 'accepted', 'msg': f'已接收: {name}'})
            log(f'已响应 accepted，提交后台下载...')

            download_pool.submit(self._do_download, name, url, referer)

        except Exception as e:
            tb = traceback.format_exc()
            log(f'HTTP POST 异常: {e}')
            log(f'异常堆栈: {tb}')
            self._cors()
            self._json({'status': 'error', 'msg': str(e)})

    def _do_download(self, name, url, referer=None):
        """在单独线程中执行下载"""
        global total_count
        log(f'开始下载: [{name}]')
        ok = download_one(name, url, referer)
        with count_lock:
            if ok:
                total_count += 1
            log(f'--- 任务结束: [{name}] {"成功" if ok else "失败"} (累计: {total_count}) ---')
            log('等待新任务...')

    def _cors(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Content-Type', 'application/json')
        self.end_headers()

    def _json(self, obj):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.wfile.write(body)


def main():
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        log('未找到 ffmpeg.exe，请放到本目录下')
        sys.exit(1)

    server = HTTPServer(('127.0.0.1', PORT), Handler)

    log('=' * 50)
    log('小鹅通 M3U8 视频下载器 启动')
    log(f'ffmpeg: {ffmpeg}')
    log(f'输出:   {OUT}')
    log(f'端口:   localhost:{PORT}')
    log('等待浏览器发送下载任务...')
    log('在课程页面点击 "发送到下载" 即可')
    log('按 Ctrl+C 退出')
    log('=' * 50)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log('\n退出。本次共下载 {} 个视频。'.format(total_count))
        server.shutdown()


if __name__ == '__main__':
    main()
