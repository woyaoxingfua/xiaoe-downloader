// ==UserScript==
// @name         小鹅通视频 m3u8 地址嗅探提取器
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  自动拦截并提取小鹅通视频 .m3u8 地址，点击"发送到下载"一键推送到本地下载器
// @match        *://*.xiaoeknow.com/*
// @match        *://*.xet.tech/*
// @match        *://*.xiaoe-tech.com/*
// @match        *://*.xet.pomoho.com/*
// @match        *://*.xet-pc.citv.cn/*
// @grant        GM_xmlhttpRequest
// @grant        GM_setClipboard
// @run-at       document-start
// @connect      127.0.0.1
// @connect      localhost
// ==/UserScript==

(function() {
    'use strict';

    let m3u8Urls = new Set(); // 存放抓到的去重 .m3u8 地址

    // 获取当前视频标题
    function getVideoTitle() {
        // 按优先级尝试页面 DOM 选择器
        const selectors = [
            '.video-title__font div',   // PC课程页标题
            '.video-title__font',
            '.video-title',
            '.lesson-title__text',      // H5课程页标题
            '.lesson-title',
            '.chapter-title',
            'h1',
            '.video-info-title',
            '.t-h1',
            '.title-text',
            '.course-title',
            '.video-name',
            '#video-title',
            '.xe-player-title',
            '[data-title]',
        ];

        for (let sel of selectors) {
            const elem = document.querySelector(sel);
            if (elem && elem.textContent.trim()) {
                return elem.textContent.trim();
            }
        }

        // 兜底：从 document.title 提取
        const docTitle = document.title;
        if (!docTitle) return '未找到视频名称';
        const clean = docTitle.replace(/^ch\d+_\d+[-\s]+/i, '');
        const parts = docTitle.split(' - ');
        const knownSuffix = ['小鹅通', '小鹅通平台', '小鹅知识店铺', 'xiaoeknow'];
        const filtered = parts.filter(p => !knownSuffix.includes(p.trim()));
        if (filtered.length > 0) return filtered[0].trim();

        return clean || docTitle;
    }

    let currentUrl = '';  // 当前嗅探到的地址

    // 显示/更新悬浮面板
    function showPanel(url) {
        currentUrl = url;
        let panel = document.getElementById('xe-m3u8-panel');
        const title = getVideoTitle();

        // 首次创建面板
        if (!panel) {
            panel = document.createElement('div');
            panel.id = 'xe-m3u8-panel';
            panel.style.cssText = `
                position: fixed; top: 20px; right: 20px; z-index: 2147483647;
                background: #fff; padding: 15px 20px; border-radius: 8px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.2); border: 2px solid #1890ff;
                font-family: sans-serif; width: 380px;
            `;
            panel.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <div style="font-size: 15px; font-weight: bold; color: #333;">
                        🎬 嗅探到 m3u8 视频流
                    </div>
                    <span id="xe-conn-status" style="font-size: 12px; color: #999;">🔗 检测中...</span>
                </div>
                <div style="font-size: 14px; margin-bottom: 8px; padding: 5px 8px; background: #f6f6f6; border-radius: 4px;">
                    <span style="color: #555;">📹 视频名称：</span>
                    <span id="xe-video-title" style="font-weight: 500; color: #000;">${title}</span>
                </div>
                <textarea id="xe-m3u8-input" readonly rows="3" style="
                    width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px;
                    font-size: 12px; resize: none; margin-bottom: 10px; word-break: break-all;
                "></textarea>
                <div style="display: flex; justify-content: space-between; gap: 8px;">
                    <button id="xe-m3u8-send-btn" style="
                        background: #1890ff; color: #fff; border: none; padding: 8px 12px;
                        border-radius: 4px; cursor: pointer; font-size: 13px; flex: 1;
                    ">📤 发送到下载</button>
                    <button id="xe-m3u8-copy-btn" style="
                        background: #52c41a; color: #fff; border: none; padding: 8px 12px;
                        border-radius: 4px; cursor: pointer; font-size: 13px; flex: 1;
                    ">📋 复制地址</button>
                    <button id="xe-m3u8-close-btn" style="
                        background: #f5f5f5; color: #666; border: 1px solid #ccc; padding: 6px 10px;
                        border-radius: 4px; cursor: pointer; font-size: 13px;
                    ">关闭</button>
                </div>
                <div id="xe-status-msg" style="margin-top: 8px; font-size: 12px; color: #999; min-height: 18px;"></div>
            `;
            document.body.appendChild(panel);

            document.getElementById('xe-m3u8-close-btn').onclick = () => {
                panel.style.display = 'none';
            };

            // 检测下载器连接状态
            checkConnStatus();
        } else {
            panel.style.display = 'block';
        }

        // 更新标题与地址
        document.getElementById('xe-video-title').textContent = title;
        document.getElementById('xe-m3u8-input').value = url;

        // 发送到下载按钮
        const sendBtn = document.getElementById('xe-m3u8-send-btn');
        sendBtn.onclick = function() {
            sendToDownloader(title, url, this);
        };

        // 复制按钮
        const copyBtn = document.getElementById('xe-m3u8-copy-btn');
        copyBtn.onclick = function() {
            const inputEl = document.getElementById('xe-m3u8-input');
            inputEl.select();
            document.execCommand("copy");
            try { GM_setClipboard(url, 'text'); } catch(e) {}
            showStatus(this, '✅ 已复制', '#52c41a');
        };
    }

    // 发送到本地下载器
    function sendToDownloader(title, url, btn) {
        if (!title || title === '未找到视频名称') {
            const msgEl = document.getElementById('xe-status-msg');
            if (msgEl) { msgEl.textContent = '请先输入视频名称'; msgEl.style.color = '#ff4d4f'; }
            return;
        }
        if (!url) {
            const msgEl = document.getElementById('xe-status-msg');
            if (msgEl) { msgEl.textContent = '未获取到 m3u8 地址'; msgEl.style.color = '#ff4d4f'; }
            return;
        }

        btn.disabled = true;
        btn.textContent = '发送中...';
        btn.style.background = '#faad14';

        const msgEl = document.getElementById('xe-status-msg');
        if (msgEl) { msgEl.textContent = '正在发送到下载器...'; msgEl.style.color = '#1890ff'; }

        GM_xmlhttpRequest({
            method: 'POST',
            url: 'http://127.0.0.1:8910/send',
            data: JSON.stringify({ name: title, url: url, referer: window.location.href }),
            headers: { 'Content-Type': 'application/json' },
            timeout: 10000,
            onload: function(resp) {
                try {
                    const r = JSON.parse(resp.responseText);
                    if (r.status === 'accepted') {
                        btn.textContent = '发送到下载';
                        btn.style.background = '#52c41a';
                        if (msgEl) { msgEl.textContent = r.msg + ' - 后台下载中...'; msgEl.style.color = '#52c41a'; }
                    } else {
                        btn.textContent = '发送到下载';
                        btn.style.background = '#ff4d4f';
                        if (msgEl) { msgEl.textContent = (r.msg || '服务器返回失败'); msgEl.style.color = '#ff4d4f'; }
                    }
                } catch(e) {
                    btn.textContent = '发送到下载';
                    btn.style.background = '#52c41a';
                    if (msgEl) { msgEl.textContent = '已发送，后台下载中...'; msgEl.style.color = '#52c41a'; }
                }
                btn.disabled = false;
                setTimeout(() => {
                    btn.style.background = '#1890ff';
                    if (msgEl) msgEl.textContent = '';
                }, 5000);
            },
            onerror: function() {
                btn.textContent = '发送到下载';
                btn.style.background = '#ff4d4f';
                btn.disabled = false;
                if (msgEl) { msgEl.textContent = '下载器未启动，请先运行 启动.bat'; msgEl.style.color = '#ff4d4f'; }
            },
            ontimeout: function() {
                btn.textContent = '发送到下载';
                btn.style.background = '#ff4d4f';
                btn.disabled = false;
                if (msgEl) { msgEl.textContent = '连接超时，请检查下载器'; msgEl.style.color = '#ff4d4f'; }
            }
        });
    }

    // 检查下载器连接
    function checkConnStatus() {
        const st = document.getElementById('xe-conn-status');
        GM_xmlhttpRequest({
            method: 'GET',
            url: 'http://127.0.0.1:8910/',
            timeout: 3000,
            onload: function() {
                if (st) { st.innerHTML = '🟢 已连接'; st.style.color = '#52c41a'; }
            },
            onerror: function() {
                if (st) { st.innerHTML = '🔴 未启动'; st.style.color = '#ff4d4f'; }
            }
        });
    }

    // 按钮状态提示
    function showStatus(btn, text, color) {
        const msgEl = document.getElementById('xe-status-msg');
        if (msgEl) {
            msgEl.textContent = text;
            msgEl.style.color = color;
        }
        btn.style.background = color;
        setTimeout(() => {
            btn.style.background = '#1890ff';
            if (msgEl) msgEl.textContent = '';
        }, 3000);
    }

    // 处理拦截到的 m3u8 地址
    function handleInterceptedUrl(url) {
        if (url.includes('.m3u8') && !m3u8Urls.has(url)) {
            // 将相对路径转为完整 URL（小鹅通播放器可能发相对路径如 /522ff1e0vod...）
            try {
                url = new URL(url, window.location.origin).href;
            } catch(e) {}
            m3u8Urls.add(url);
            console.log("[油猴嗅探器] 抓到 m3u8 地址:", url);
            // 延迟一下等页面渲染完成
            setTimeout(() => {
                showPanel(url);
            }, 500);
        }
    }

    // 拦截 XMLHttpRequest
    const originalXhrOpen = window.XMLHttpRequest.prototype.open;
    window.XMLHttpRequest.prototype.open = function(method, url) {
        if (typeof url === 'string') {
            handleInterceptedUrl(url);
        }
        return originalXhrOpen.apply(this, arguments);
    };

    // 拦截 Fetch API
    const originalFetch = window.fetch;
    window.fetch = async function(...args) {
        let url = '';
        if (typeof args[0] === 'string') {
            url = args[0];
        } else if (args[0] && args[0].url) {
            url = args[0].url;
        }
        handleInterceptedUrl(url);
        return originalFetch.apply(this, args);
    };
})();