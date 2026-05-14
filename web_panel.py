import os
import secrets
from functools import wraps
from flask import Flask, request, redirect, session, jsonify

import config
from database import (
    get_user, get_all_users, ban_user, set_premium,
    get_global_stats, get_setting, set_setting
)
from file_manager import list_user_files
from process_manager import (
    get_all_processes, get_process_info, get_total_process_count,
    is_running, run_script, stop_script, stop_all_scripts, get_system_stats
)
from log_manager import read_log

flask_app = Flask(__name__)
flask_app.secret_key = secrets.token_hex(32)

def get_web_username():
    v = get_setting("web_username")
    return v if v else "admin"

def get_web_password():
    v = get_setting("web_password")
    return v if v else "admin123"

def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin"):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

def get_file_list(uid):
    raw = list_user_files(uid)
    result = []
    for f in raw:
        if isinstance(f, dict):
            fname = f["filename"]
            size = f.get("size_bytes", 0)
        else:
            fname = f
            size = 0
        fp = os.path.join(config.USERS_DIR, str(uid), fname)
        if os.path.exists(fp):
            size = os.path.getsize(fp)
        result.append({
            "filename": fname,
            "size_bytes": size,
            "uploaded_at": os.path.getmtime(fp) if os.path.exists(fp) else 0,
            "running": is_running(uid, fname),
        })
    return result

# ══════════════════════════════════════════════════════════════════════════════
# LOGIN PAGE
# ══════════════════════════════════════════════════════════════════════════════
LOGIN_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CloudBot Admin</title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#04060d;--surf:#080e1c;--bdr:rgba(255,255,255,0.07);--acc:#6ee7ff;--acc2:#a78bfa;--txt:#f0f4ff;--muted:#6b7a9e;--danger:#f87171}
body{background:var(--bg);color:var(--txt);font-family:'Plus Jakarta Sans',sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;overflow:hidden}
.bg{position:fixed;inset:0;z-index:0;pointer-events:none}
.bg-mesh{position:absolute;inset:0;background:radial-gradient(ellipse 80% 60% at 20% 10%,rgba(110,231,255,0.06) 0%,transparent 60%),radial-gradient(ellipse 60% 80% at 80% 90%,rgba(167,139,250,0.06) 0%,transparent 60%)}
.bg-grid{position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,0.025) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,0.025) 1px,transparent 1px);background-size:60px 60px}
.orb{position:absolute;border-radius:50%;filter:blur(100px);animation:drift 20s ease-in-out infinite}
.o1{width:500px;height:500px;background:rgba(110,231,255,0.05);top:-150px;right:-150px}
.o2{width:400px;height:400px;background:rgba(167,139,250,0.05);bottom:-100px;left:-100px;animation-delay:-8s}
@keyframes drift{0%,100%{transform:translate(0,0)}50%{transform:translate(20px,-15px)}}
.card{position:relative;z-index:1;width:420px;background:var(--surf);border:1px solid var(--bdr);border-radius:24px;padding:44px 40px;box-shadow:0 40px 80px rgba(0,0,0,0.6);animation:up .6s cubic-bezier(.16,1,.3,1)}
@keyframes up{from{opacity:0;transform:translateY(28px)}to{opacity:1;transform:translateY(0)}}
.brand{display:flex;align-items:center;gap:14px;margin-bottom:32px}
.brand-icon{width:48px;height:48px;border-radius:14px;background:linear-gradient(135deg,var(--acc),var(--acc2));display:flex;align-items:center;justify-content:center;font-size:22px;box-shadow:0 8px 24px rgba(110,231,255,0.2)}
.brand-name{font-size:20px;font-weight:800}
.brand-sub{font-size:10px;color:var(--muted);letter-spacing:2px;font-family:'DM Mono',monospace;text-transform:uppercase}
.line{height:1px;background:var(--bdr);margin-bottom:28px}
.lbl{font-size:10px;color:var(--muted);letter-spacing:1.5px;text-transform:uppercase;font-family:'DM Mono',monospace;margin-bottom:8px;display:block}
.field{margin-bottom:18px}
.iw{position:relative}
.ii{position:absolute;left:16px;top:50%;transform:translateY(-50%);opacity:.5}
input[type=text],input[type=password]{width:100%;padding:14px 16px 14px 44px;background:rgba(255,255,255,0.04);border:1px solid var(--bdr);border-radius:12px;color:var(--txt);font-family:'DM Mono',monospace;font-size:14px;outline:none;transition:all .2s}
input:focus{border-color:rgba(110,231,255,.4);background:rgba(110,231,255,.03);box-shadow:0 0 0 4px rgba(110,231,255,.06)}
input::placeholder{color:var(--muted)}
.btn{width:100%;padding:15px;margin-top:8px;background:linear-gradient(135deg,rgba(110,231,255,.12),rgba(167,139,250,.12));border:1px solid rgba(110,231,255,.25);border-radius:12px;color:var(--acc);font-family:'Plus Jakarta Sans',sans-serif;font-size:14px;font-weight:700;letter-spacing:1px;cursor:pointer;transition:all .2s;text-transform:uppercase}
.btn:hover{background:linear-gradient(135deg,rgba(110,231,255,.22),rgba(167,139,250,.22));box-shadow:0 8px 24px rgba(110,231,255,.15);transform:translateY(-1px)}
.err{background:rgba(248,113,113,.08);border:1px solid rgba(248,113,113,.25);border-radius:10px;padding:12px 16px;color:var(--danger);font-size:13px;margin-bottom:20px}
.foot{text-align:center;margin-top:22px;font-size:12px;color:var(--muted)}
.foot a{color:var(--acc);text-decoration:none;font-weight:600}
</style>
</head>
<body>
<div class="bg"><div class="bg-mesh"></div><div class="bg-grid"></div><div class="orb o1"></div><div class="orb o2"></div></div>
<div class="card">
  <div class="brand">
    <div class="brand-icon">⚡</div>
    <div><div class="brand-name">CloudBot</div><div class="brand-sub">Admin Console</div></div>
  </div>
  <div class="line"></div>
  {ERROR}
  <form method="POST" action="/admin/login">
    <div class="field">
      <label class="lbl">Username</label>
      <div class="iw"><span class="ii">👤</span><input type="text" name="username" placeholder="Enter username" autocomplete="off"></div>
    </div>
    <div class="field">
      <label class="lbl">Password</label>
      <div class="iw"><span class="ii">🔑</span><input type="password" name="password" placeholder="••••••••"></div>
    </div>
    <button type="submit" class="btn">→ Access Console</button>
  </form>
  <div class="foot">User portal? <a href="/portal">Click here →</a></div>
</div>
</body>
</html>"""

# ══════════════════════════════════════════════════════════════════════════════
# ADMIN DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
ADMIN_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CloudBot Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#04060d;--surf:#080e1c;--surf2:#0c1425;--bdr:rgba(255,255,255,0.07);--acc:#6ee7ff;--acc2:#a78bfa;--acc3:#34d399;--txt:#f0f4ff;--muted:#6b7a9e;--danger:#f87171;--warn:#fbbf24;--ok:#34d399;--sw:260px}
body{background:var(--bg);color:var(--txt);font-family:'Plus Jakarta Sans',sans-serif;min-height:100vh;display:flex}
body::before{content:'';position:fixed;inset:0;z-index:0;pointer-events:none;background:radial-gradient(ellipse 70% 50% at 5% 0%,rgba(110,231,255,.04) 0%,transparent 60%),radial-gradient(ellipse 60% 70% at 95% 100%,rgba(167,139,250,.04) 0%,transparent 60%)}
.sidebar{position:fixed;left:0;top:0;bottom:0;width:var(--sw);background:var(--surf);border-right:1px solid var(--bdr);display:flex;flex-direction:column;z-index:100}
.sl{padding:22px 18px;border-bottom:1px solid var(--bdr);display:flex;align-items:center;gap:12px}
.si{width:38px;height:38px;border-radius:11px;background:linear-gradient(135deg,var(--acc),var(--acc2));display:flex;align-items:center;justify-content:center;font-size:17px;box-shadow:0 4px 14px rgba(110,231,255,.2)}
.sn{font-size:15px;font-weight:800}
.sv{font-size:9px;color:var(--muted);font-family:'DM Mono',monospace;letter-spacing:1px}
nav{flex:1;padding:14px 10px;overflow-y:auto}
.ns{font-size:9px;color:var(--muted);letter-spacing:2px;text-transform:uppercase;font-family:'DM Mono',monospace;padding:14px 10px 6px}
.ni{display:flex;align-items:center;gap:10px;width:100%;padding:10px 12px;border-radius:10px;border:none;background:none;color:var(--muted);font-family:'Plus Jakarta Sans',sans-serif;font-size:13px;font-weight:500;cursor:pointer;transition:all .15s;text-align:left;margin-bottom:2px}
.ni:hover{background:rgba(255,255,255,.04);color:var(--txt)}
.ni.active{background:linear-gradient(135deg,rgba(110,231,255,.1),rgba(167,139,250,.1));color:var(--acc);border:1px solid rgba(110,231,255,.15)}
.sf{padding:14px 10px;border-top:1px solid var(--bdr)}
.lo{display:flex;align-items:center;gap:10px;width:100%;padding:10px 12px;border-radius:10px;border:1px solid rgba(248,113,113,.2);background:rgba(248,113,113,.05);color:var(--danger);font-size:13px;font-weight:500;cursor:pointer;font-family:'Plus Jakarta Sans',sans-serif;transition:all .15s;text-decoration:none}
.lo:hover{background:rgba(248,113,113,.12)}
.main{margin-left:var(--sw);padding:30px;flex:1;position:relative;z-index:1}
.pg{display:none}.pg.active{display:block;animation:fi .3s ease}
@keyframes fi{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.ph{margin-bottom:26px;display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:12px}
.pt{font-size:23px;font-weight:800;letter-spacing:-.5px}
.ps{color:var(--muted);font-size:13px;margin-top:4px;display:flex;align-items:center;gap:6px}
.live-dot{width:7px;height:7px;border-radius:50%;background:var(--acc3);box-shadow:0 0 8px var(--acc3);animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.sg{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:22px}
.sc{background:var(--surf);border:1px solid var(--bdr);border-radius:16px;padding:20px;transition:all .2s;position:relative;overflow:hidden}
.sc::before{content:'';position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,rgba(110,231,255,.3),transparent)}
.sc:hover{border-color:rgba(110,231,255,.2);transform:translateY(-2px);box-shadow:0 8px 24px rgba(0,0,0,.3)}
.si2{font-size:26px;margin-bottom:10px}
.sl2{font-size:10px;color:var(--muted);letter-spacing:1px;text-transform:uppercase;font-family:'DM Mono',monospace;margin-bottom:5px}
.sv2{font-size:30px;font-weight:800;letter-spacing:-1px}
.sysg{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:22px}
.sysc{background:var(--surf);border:1px solid var(--bdr);border-radius:16px;padding:16px}
.syl{font-size:10px;color:var(--muted);font-family:'DM Mono',monospace;letter-spacing:1px;margin-bottom:6px;text-transform:uppercase}
.syv{font-size:22px;font-weight:800;margin-bottom:8px}
.pb{height:4px;background:rgba(255,255,255,.05);border-radius:2px;overflow:hidden}
.pf{height:100%;border-radius:2px;background:linear-gradient(90deg,var(--acc),var(--acc2));transition:width .8s cubic-bezier(.4,0,.2,1)}
.card{background:var(--surf);border:1px solid var(--bdr);border-radius:16px;overflow:hidden;margin-bottom:18px}
.ch{padding:14px 18px;border-bottom:1px solid var(--bdr);display:flex;align-items:center;justify-content:space-between}
.ct{font-size:14px;font-weight:700}
table{width:100%;border-collapse:collapse}
th{padding:11px 14px;text-align:left;font-size:10px;color:var(--muted);letter-spacing:1.5px;text-transform:uppercase;font-family:'DM Mono',monospace;border-bottom:1px solid var(--bdr);font-weight:400}
td{padding:11px 14px;font-size:13px;border-bottom:1px solid rgba(255,255,255,.03);vertical-align:middle}
tr:last-child td{border-bottom:none}
tr:hover td{background:rgba(255,255,255,.015)}
.badge{display:inline-flex;align-items:center;gap:3px;padding:3px 9px;border-radius:20px;font-size:11px;font-weight:600}
.bok{background:rgba(52,211,153,.1);color:var(--ok);border:1px solid rgba(52,211,153,.2)}
.berr{background:rgba(248,113,113,.1);color:var(--danger);border:1px solid rgba(248,113,113,.2)}
.bwarn{background:rgba(251,191,36,.1);color:var(--warn);border:1px solid rgba(251,191,36,.2)}
.bacc{background:rgba(110,231,255,.1);color:var(--acc);border:1px solid rgba(110,231,255,.2)}
.bmut{background:rgba(107,122,158,.1);color:var(--muted);border:1px solid rgba(107,122,158,.2)}
.btn{padding:6px 13px;border-radius:8px;border:none;cursor:pointer;font-size:12px;font-weight:600;font-family:'Plus Jakarta Sans',sans-serif;transition:all .15s}
.bp{background:rgba(110,231,255,.1);color:var(--acc);border:1px solid rgba(110,231,255,.2)}.bp:hover{background:rgba(110,231,255,.2)}
.bd{background:rgba(248,113,113,.1);color:var(--danger);border:1px solid rgba(248,113,113,.2)}.bd:hover{background:rgba(248,113,113,.2)}
.bs{background:rgba(52,211,153,.1);color:var(--ok);border:1px solid rgba(52,211,153,.2)}.bs:hover{background:rgba(52,211,153,.2)}
.bb{width:100%;padding:12px;font-size:13px;border-radius:10px;margin-bottom:8px}
.srch{padding:9px 14px;background:rgba(255,255,255,.04);border:1px solid var(--bdr);border-radius:10px;color:var(--txt);font-family:'DM Mono',monospace;font-size:13px;outline:none;width:230px;transition:all .2s}
.srch:focus{border-color:rgba(110,231,255,.3)}
.srch::placeholder{color:var(--muted)}
.term{background:#020408;border:1px solid var(--bdr);border-radius:16px;overflow:hidden}
.th{background:var(--surf);padding:11px 14px;display:flex;align-items:center;gap:7px;border-bottom:1px solid var(--bdr)}
.dot{width:11px;height:11px;border-radius:50%}
.tt{font-size:11px;color:var(--muted);margin-left:8px;font-family:'DM Mono',monospace}
.tb2{padding:16px;font-size:12px;line-height:1.8;color:#4ade80;min-height:300px;max-height:480px;overflow-y:auto;white-space:pre-wrap;word-break:break-all;font-family:'DM Mono',monospace}
.tb2::-webkit-scrollbar{width:4px}.tb2::-webkit-scrollbar-thumb{background:rgba(255,255,255,.1);border-radius:2px}
.ov{display:none;position:fixed;inset:0;z-index:999;background:rgba(0,0,0,.8);backdrop-filter:blur(8px);align-items:center;justify-content:center}
.ov.open{display:flex}
.modal{background:var(--surf);border:1px solid var(--bdr);border-radius:20px;padding:26px;width:560px;max-width:95vw;max-height:85vh;overflow-y:auto;animation:up .3s cubic-bezier(.16,1,.3,1);box-shadow:0 40px 80px rgba(0,0,0,.6)}
@keyframes up{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}
.mh{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px}
.mt2{font-size:17px;font-weight:800}
.mc{background:none;border:none;color:var(--muted);font-size:20px;cursor:pointer;padding:4px;border-radius:6px}
.mc:hover{background:rgba(255,255,255,.06);color:var(--txt)}
.fr{display:flex;align-items:center;justify-content:space-between;padding:12px 14px;background:var(--surf2);border:1px solid var(--bdr);border-radius:10px;margin-bottom:8px}
.si3{width:100%;padding:12px 14px;background:rgba(255,255,255,.04);border:1px solid var(--bdr);border-radius:10px;color:var(--txt);font-family:'DM Mono',monospace;font-size:13px;outline:none;margin-bottom:12px;transition:all .2s}
.si3:focus{border-color:rgba(110,231,255,.3)}
@media(max-width:1100px){.sg{grid-template-columns:repeat(2,1fr)}}
</style>
</head>
<body>
<div class="sidebar">
  <div class="sl"><div class="si">⚡</div><div><div class="sn">CloudBot</div><div class="sv">ADMIN v2</div></div></div>
  <nav>
    <div class="ns">Overview</div>
    <button class="ni active" onclick="go('dashboard',this)">📊 Dashboard</button>
    <button class="ni" onclick="go('users',this)">👥 Users</button>
    <button class="ni" onclick="go('files',this)">📁 All Files</button>
    <div class="ns">Monitor</div>
    <button class="ni" onclick="go('processes',this)">⚙️ Processes</button>
    <button class="ni" onclick="go('terminal',this)">💻 Terminal</button>
    <div class="ns">Config</div>
    <button class="ni" onclick="go('settings',this)">🔧 Settings</button>
  </nav>
  <div class="sf"><a href="/admin/logout" class="lo">🚪 Sign Out</a></div>
</div>

<div class="main">
  <div class="pg active" id="pg-dashboard">
    <div class="ph"><div><div class="pt">Dashboard</div><div class="ps"><span class="live-dot"></span>Live &nbsp;·&nbsp; <span id="clock"></span></div></div></div>
    <div class="sg">
      <div class="sc"><div class="si2">👥</div><div class="sl2">Users</div><div class="sv2" style="color:var(--acc)" id="d-users">—</div></div>
      <div class="sc"><div class="si2">⭐</div><div class="sl2">Premium</div><div class="sv2" style="color:var(--acc2)" id="d-premium">—</div></div>
      <div class="sc"><div class="si2">📁</div><div class="sl2">Files</div><div class="sv2" style="color:var(--acc3)" id="d-files">—</div></div>
      <div class="sc"><div class="si2">⚙️</div><div class="sl2">Running</div><div class="sv2" style="color:var(--warn)" id="d-procs">—</div></div>
    </div>
    <div class="sysg">
      <div class="sysc"><div class="syl">CPU</div><div class="syv" id="cpu-v">—</div><div class="pb"><div class="pf" id="cpu-b" style="width:0"></div></div></div>
      <div class="sysc"><div class="syl">RAM</div><div class="syv" id="ram-v">—</div><div class="pb"><div class="pf" id="ram-b" style="width:0"></div></div></div>
      <div class="sysc"><div class="syl">Disk</div><div class="syv" id="dsk-v">—</div><div class="pb"><div class="pf" id="dsk-b" style="width:0"></div></div></div>
    </div>
    <div class="card">
      <div class="ch"><div class="ct">⚡ Recent Activity</div></div>
      <table><thead><tr><th>User ID</th><th>Action</th><th>Detail</th><th>Time</th></tr></thead>
      <tbody id="act-tb"><tr><td colspan="4" style="text-align:center;color:var(--muted);padding:24px">Loading...</td></tr></tbody></table>
    </div>
  </div>

  <div class="pg" id="pg-users">
    <div class="ph"><div><div class="pt">Users</div><div class="ps">All registered users</div></div><input class="srch" id="u-srch" placeholder="Search..." oninput="filterU()"></div>
    <div class="card">
      <table><thead><tr><th>User</th><th>ID</th><th>Plan</th><th>Status</th><th>Files</th><th>Joined</th><th>Actions</th></tr></thead>
      <tbody id="u-tb"><tr><td colspan="7" style="text-align:center;color:var(--muted);padding:24px">Loading...</td></tr></tbody></table>
    </div>
  </div>

  <div class="pg" id="pg-files">
    <div class="ph"><div><div class="pt">All Files</div><div class="ps">Every uploaded file</div></div></div>
    <div class="card">
      <table><thead><tr><th>Filename</th><th>Owner</th><th>Status</th><th>Size</th><th>Uploaded</th><th>Actions</th></tr></thead>
      <tbody id="f-tb"><tr><td colspan="6" style="text-align:center;color:var(--muted);padding:24px">Loading...</td></tr></tbody></table>
    </div>
  </div>

  <div class="pg" id="pg-processes">
    <div class="ph"><div><div class="pt">Processes</div><div class="ps">Live running scripts</div></div></div>
    <div class="card">
      <table><thead><tr><th>User</th><th>File</th><th>PID</th><th>CPU</th><th>RAM</th><th>Uptime</th><th>Action</th></tr></thead>
      <tbody id="p-tb"><tr><td colspan="7" style="text-align:center;color:var(--muted);padding:24px">Loading...</td></tr></tbody></table>
    </div>
  </div>

  <div class="pg" id="pg-terminal">
    <div class="ph"><div><div class="pt">Terminal</div><div class="ps">Real-time script logs</div></div></div>
    <div style="display:flex;gap:10px;margin-bottom:14px;flex-wrap:wrap">
      <input class="srch" id="t-uid" placeholder="User ID" style="width:140px">
      <input class="srch" id="t-file" placeholder="filename.py" style="width:190px">
      <button class="btn bp" onclick="loadLog()">Load</button>
      <button class="btn bs" onclick="startAR()">▶ Auto</button>
      <button class="btn bd" onclick="stopAR()">■ Stop</button>
    </div>
    <div class="term">
      <div class="th">
        <div class="dot" style="background:#f87171"></div>
        <div class="dot" style="background:#fbbf24"></div>
        <div class="dot" style="background:#34d399"></div>
        <span class="tt" id="t-title">no session</span>
      </div>
      <div class="tb2" id="t-out">$ Waiting...<br></div>
    </div>
  </div>

  <div class="pg" id="pg-settings">
    <div class="ph"><div><div class="pt">Settings</div><div class="ps">Panel configuration</div></div></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;max-width:780px">
      <div class="card">
        <div class="ch"><div class="ct">🔐 Credentials</div></div>
        <div style="padding:18px">
          <div style="font-size:10px;color:var(--muted);font-family:'DM Mono',monospace;letter-spacing:1px;text-transform:uppercase;margin-bottom:7px">New Username</div>
          <input class="si3" id="s-user" placeholder="Username">
          <div style="font-size:10px;color:var(--muted);font-family:'DM Mono',monospace;letter-spacing:1px;text-transform:uppercase;margin-bottom:7px">New Password</div>
          <input class="si3" id="s-pass" type="password" placeholder="Password">
          <button class="btn bp bb" onclick="saveCreds()">💾 Save</button>
          <div id="cm" style="font-size:12px;text-align:center;margin-top:4px;font-family:'DM Mono',monospace"></div>
        </div>
      </div>
      <div class="card">
        <div class="ch"><div class="ct">🔧 Bot Controls</div></div>
        <div style="padding:18px">
          <button class="btn bd bb" onclick="botAct('maintenance_on')">🔒 Enable Maintenance</button>
          <button class="btn bs bb" onclick="botAct('maintenance_off')">🟢 Disable Maintenance</button>
          <button class="btn bd bb" onclick="botAct('stop_all')">💀 Stop All Scripts</button>
          <div id="am" style="font-size:12px;text-align:center;margin-top:4px;font-family:'DM Mono',monospace"></div>
        </div>
      </div>
    </div>
  </div>
</div>

<div class="ov" id="um">
  <div class="modal">
    <div class="mh"><div class="mt2" id="m-title">User</div><button class="mc" onclick="closeM()">✕</button></div>
    <div id="m-body"></div>
  </div>
</div>

<script>
let allU=[],arT=null;
function go(n,el){
  document.querySelectorAll('.pg').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.ni').forEach(b=>b.classList.remove('active'));
  document.getElementById('pg-'+n).classList.add('active');
  if(el)el.classList.add('active');
  if(n==='dashboard')loadDash();
  if(n==='users')loadUsers();
  if(n==='files')loadFiles();
  if(n==='processes')loadProcs();
}
setInterval(()=>{document.getElementById('clock').textContent=new Date().toLocaleTimeString()},1000);
document.getElementById('clock').textContent=new Date().toLocaleTimeString();
const api=async u=>{const r=await fetch(u);return r.json()};
async function loadDash(){
  const[s,sys]=await Promise.all([api('/api/stats'),api('/api/system')]);
  document.getElementById('d-users').textContent=s.total_users||0;
  document.getElementById('d-premium').textContent=s.premium_users||0;
  document.getElementById('d-files').textContent=s.total_files||0;
  document.getElementById('d-procs').textContent=s.running_processes||0;
  document.getElementById('cpu-v').textContent=(sys.cpu_percent||0).toFixed(1)+'%';
  document.getElementById('ram-v').textContent=(sys.ram_percent||0).toFixed(1)+'%';
  document.getElementById('dsk-v').textContent=(sys.disk_percent||0).toFixed(1)+'%';
  document.getElementById('cpu-b').style.width=(sys.cpu_percent||0)+'%';
  document.getElementById('ram-b').style.width=(sys.ram_percent||0)+'%';
  document.getElementById('dsk-b').style.width=(sys.disk_percent||0)+'%';
  try{const a=await api('/api/activity');
  document.getElementById('act-tb').innerHTML=a.length?a.map(x=>`<tr><td style="font-family:'DM Mono',monospace;font-size:11px">${x.user_id}</td><td><span class="badge bacc">${x.action}</span></td><td style="color:var(--muted)">${x.detail||'—'}</td><td style="color:var(--muted);font-size:11px;font-family:'DM Mono',monospace">${new Date(x.timestamp*1000).toLocaleString()}</td></tr>`).join(''):'<tr><td colspan="4" style="text-align:center;color:var(--muted);padding:20px">No activity</td></tr>';}catch(e){}
}
async function loadUsers(){allU=await api('/api/users');renderU(allU)}
function renderU(data){
  document.getElementById('u-tb').innerHTML=data.length?data.map(u=>`<tr>
    <td><div style="font-weight:700">${u.full_name||'Unknown'}</div><div style="color:var(--muted);font-size:11px;font-family:'DM Mono',monospace">@${u.username||'—'}</div></td>
    <td style="font-family:'DM Mono',monospace;font-size:11px;color:var(--muted)">${u.user_id}</td>
    <td><span class="badge ${u.plan==='premium'?'bwarn':'bmut'}">${u.plan==='premium'?'⭐ Premium':'Free'}</span></td>
    <td><span class="badge ${u.is_banned?'berr':'bok'}">${u.is_banned?'🚫 Banned':'✓ Active'}</span></td>
    <td style="font-weight:700">${u.file_count||0}</td>
    <td style="color:var(--muted);font-size:11px">${new Date((u.join_date||0)*1000).toLocaleDateString()}</td>
    <td><div style="display:flex;gap:5px;flex-wrap:wrap">
      <button class="btn bp" onclick="viewU(${u.user_id})">👁 View</button>
      <button class="btn ${u.is_banned?'bs':'bd'}" onclick="toggleBan(${u.user_id},${u.is_banned})">${u.is_banned?'Unban':'Ban'}</button>
      <button class="btn bs" onclick="setPrem(${u.user_id})">⭐</button>
    </div></td>
  </tr>`).join(''):'<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:24px">No users</td></tr>';
}
function filterU(){const q=document.getElementById('u-srch').value.toLowerCase();renderU(allU.filter(u=>(u.full_name||'').toLowerCase().includes(q)||(u.username||'').toLowerCase().includes(q)||String(u.user_id).includes(q)))}
async function loadFiles(){
  const data=await api('/api/files');
  document.getElementById('f-tb').innerHTML=data.length?data.map(f=>`<tr>
    <td style="font-weight:600">📄 ${f.filename}</td>
    <td style="font-family:'DM Mono',monospace;font-size:11px;color:var(--muted)">${f.user_id}</td>
    <td><span class="badge ${f.running?'bok':'bmut'}">${f.running?'▶ Running':'■ Stopped'}</span></td>
    <td style="font-family:'DM Mono',monospace;font-size:12px">${(f.size_bytes/1024).toFixed(1)} KB</td>
    <td style="color:var(--muted);font-size:11px">${new Date(f.uploaded_at*1000).toLocaleString()}</td>
    <td><div style="display:flex;gap:5px"><button class="btn bp" onclick="loadLogD(${f.user_id},'${f.filename}')">📋 Log</button><button class="btn ${f.running?'bd':'bs'}" onclick="toggleScript(${f.user_id},'${f.filename}',${f.running})">${f.running?'Stop':'Start'}</button></div></td>
  </tr>`).join(''):'<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:24px">No files</td></tr>';
}
async function loadProcs(){
  const data=await api('/api/processes');
  document.getElementById('p-tb').innerHTML=data.length?data.map(p=>`<tr>
    <td style="font-family:'DM Mono',monospace;font-size:11px">${p.user_id}</td>
    <td>📄 ${p.filename}</td>
    <td style="color:var(--acc);font-family:'DM Mono',monospace">${p.pid}</td>
    <td>${(p.cpu_percent||0).toFixed(1)}%</td>
    <td>${(p.memory_mb||0).toFixed(1)} MB</td>
    <td style="color:var(--muted);font-size:11px">${Math.floor((Date.now()/1000-(p.started_at||0))/60)}m</td>
    <td><button class="btn bd" onclick="stopS(${p.user_id},'${p.filename}')">■ Stop</button></td>
  </tr>`).join(''):'<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:24px">No running processes</td></tr>';
}
async function viewU(uid){
  document.getElementById('um').classList.add('open');
  document.getElementById('m-body').innerHTML='<div style="text-align:center;padding:40px;color:var(--muted)">Loading...</div>';
  const d=await api('/api/user/'+uid);
  document.getElementById('m-title').textContent=(d.full_name||'User')+' · @'+(d.username||'unknown');
  const fh=(d.files||[]).length?(d.files||[]).map(f=>`<div class="fr"><div><div style="font-weight:600;font-size:13px">📄 ${f.filename}</div><div style="font-size:11px;color:var(--muted);font-family:'DM Mono',monospace;margin-top:2px">${(f.size_bytes/1024).toFixed(1)} KB</div></div><span class="badge ${f.running?'bok':'bmut'}">${f.running?'▶ Running':'■ Stopped'}</span></div>`).join(''):'<div style="color:var(--muted);font-size:13px;text-align:center;padding:20px">No files</div>';
  document.getElementById('m-body').innerHTML=`<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:18px">
    <div style="background:var(--surf2);border:1px solid var(--bdr);border-radius:10px;padding:12px"><div style="font-size:9px;color:var(--muted);font-family:'DM Mono',monospace;margin-bottom:4px;text-transform:uppercase;letter-spacing:1px">USER ID</div><div style="font-weight:700;font-family:'DM Mono',monospace;font-size:13px">${d.user_id}</div></div>
    <div style="background:var(--surf2);border:1px solid var(--bdr);border-radius:10px;padding:12px"><div style="font-size:9px;color:var(--muted);font-family:'DM Mono',monospace;margin-bottom:4px;text-transform:uppercase;letter-spacing:1px">PLAN</div><span class="badge ${d.plan==='premium'?'bwarn':'bmut'}">${d.plan||'free'}</span></div>
    <div style="background:var(--surf2);border:1px solid var(--bdr);border-radius:10px;padding:12px"><div style="font-size:9px;color:var(--muted);font-family:'DM Mono',monospace;margin-bottom:4px;text-transform:uppercase;letter-spacing:1px">STATUS</div><span class="badge ${d.is_banned?'berr':'bok'}">${d.is_banned?'Banned':'Active'}</span></div>
  </div>
  <div style="font-weight:700;margin-bottom:10px">Files (${(d.files||[]).length})</div>${fh}`;
}
function closeM(){document.getElementById('um').classList.remove('open')}
async function toggleBan(uid,banned){await fetch('/api/user/'+uid+(banned?'/unban':'/ban'),{method:'POST'});loadUsers()}
async function setPrem(uid){await fetch('/api/user/'+uid+'/premium',{method:'POST'});loadUsers()}
async function toggleScript(uid,fname,running){await fetch(running?'/api/stop':'/api/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:uid,filename:fname})});loadFiles()}
async function stopS(uid,fname){await fetch('/api/stop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:uid,filename:fname})});loadProcs()}
function loadLogD(uid,fname){document.getElementById('t-uid').value=uid;document.getElementById('t-file').value=fname;go('terminal',null);document.querySelectorAll('.ni').forEach(b=>b.classList.remove('active'));loadLog()}
async function loadLog(){
  const uid=document.getElementById('t-uid').value.trim();
  const fname=document.getElementById('t-file').value.trim();
  if(!uid||!fname)return;
  document.getElementById('t-title').textContent=uid+' / '+fname;
  const d=await api('/api/log?user_id='+uid+'&filename='+encodeURIComponent(fname));
  const el=document.getElementById('t-out');
  el.textContent=d.log||'No log found';
  el.scrollTop=el.scrollHeight;
}
function startAR(){if(arT)return;arT=setInterval(loadLog,3000)}
function stopAR(){clearInterval(arT);arT=null}
async function saveCreds(){
  const u=document.getElementById('s-user').value.trim();
  const p=document.getElementById('s-pass').value.trim();
  if(!u||!p){document.getElementById('cm').textContent='Both required';return}
  const r=await fetch('/api/set_creds',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p})});
  const d=await r.json();
  const el=document.getElementById('cm');
  el.style.color=d.ok?'var(--ok)':'var(--danger)';
  el.textContent=d.ok?'✓ Saved':'✗ Failed';
}
async function botAct(action){
  const r=await fetch('/api/bot_action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action})});
  const d=await r.json();
  const el=document.getElementById('am');
  el.style.color='var(--ok)';el.textContent=d.msg||'Done';
}
loadDash();
setInterval(()=>{
  if(document.getElementById('pg-dashboard').classList.contains('active'))loadDash();
  if(document.getElementById('pg-processes').classList.contains('active'))loadProcs();
},10000);
</script>
</body>
</html>"""

# ══════════════════════════════════════════════════════════════════════════════
# USER PORTAL — Mobile First, Premium Design, Fixed
# ══════════════════════════════════════════════════════════════════════════════
USER_PORTAL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>CloudBot Portal</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#04060d;--surf:#080e1c;--surf2:#0c1425;--bdr:rgba(255,255,255,0.07);--acc:#6ee7ff;--acc2:#a78bfa;--acc3:#34d399;--txt:#f0f4ff;--muted:#6b7a9e;--danger:#f87171;--ok:#34d399}
html,body{height:100%}
body{background:var(--bg);color:var(--txt);font-family:'Plus Jakarta Sans',sans-serif;min-height:100vh}
body::before{content:'';position:fixed;inset:0;z-index:0;pointer-events:none;background:radial-gradient(ellipse 80% 40% at 50% 0%,rgba(110,231,255,.05) 0%,transparent 60%),radial-gradient(ellipse 60% 60% at 80% 80%,rgba(167,139,250,.04) 0%,transparent 60%)}
.hdr{position:sticky;top:0;z-index:50;background:rgba(8,14,28,.9);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border-bottom:1px solid var(--bdr);padding:13px 18px;display:flex;align-items:center;justify-content:space-between}
.logo{display:flex;align-items:center;gap:10px}
.li{width:32px;height:32px;border-radius:9px;background:linear-gradient(135deg,var(--acc),var(--acc2));display:flex;align-items:center;justify-content:center;font-size:15px;box-shadow:0 4px 12px rgba(110,231,255,.25)}
.ln{font-size:15px;font-weight:800}
.pp{font-size:10px;font-weight:700;padding:4px 10px;border-radius:20px;background:linear-gradient(135deg,rgba(110,231,255,.1),rgba(167,139,250,.1));color:var(--acc);border:1px solid rgba(110,231,255,.2);font-family:'DM Mono',monospace;letter-spacing:1px}
.wrap{position:relative;z-index:1;padding:18px 16px;max-width:560px;margin:0 auto}
.pcard{background:linear-gradient(135deg,rgba(110,231,255,.06),rgba(167,139,250,.05));border:1px solid rgba(110,231,255,.1);border-radius:18px;padding:18px;margin-bottom:18px;position:relative;overflow:hidden}
.pcard::before{content:'';position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,rgba(110,231,255,.4),rgba(167,139,250,.4),transparent)}
.pname{font-size:20px;font-weight:800;letter-spacing:-.5px;margin-bottom:3px}
.pmeta{color:var(--muted);font-size:12px;font-family:'DM Mono',monospace}
.srow{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:18px}
.st{background:var(--surf);border:1px solid var(--bdr);border-radius:13px;padding:13px;text-align:center}
.sn{font-size:24px;font-weight:800;color:var(--acc);line-height:1}
.sl{font-size:9px;color:var(--muted);letter-spacing:1.5px;text-transform:uppercase;font-family:'DM Mono',monospace;margin-top:4px}
.sch{display:flex;align-items:center;justify-content:space-between;margin-bottom:11px}
.sct{font-size:14px;font-weight:700}
.rb{width:30px;height:30px;border-radius:8px;border:1px solid var(--bdr);background:var(--surf);color:var(--muted);cursor:pointer;font-size:14px;display:flex;align-items:center;justify-content:center;transition:all .2s}
.rb:hover{border-color:rgba(110,231,255,.3);color:var(--acc);transform:rotate(180deg)}
.fc{background:var(--surf);border:1px solid var(--bdr);border-radius:13px;margin-bottom:9px;overflow:hidden;transition:all .2s;animation:fu .4s ease both}
@keyframes fu{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
.fm{padding:13px 15px;display:flex;align-items:center;justify-content:space-between;cursor:pointer;gap:10px}
.fl{}
.fn{font-size:13px;font-weight:700;display:flex;align-items:center;gap:7px}
.fext{font-size:9px;font-weight:700;padding:2px 6px;border-radius:4px;background:rgba(110,231,255,.1);color:var(--acc);font-family:'DM Mono',monospace;border:1px solid rgba(110,231,255,.15)}
.fmeta{font-size:10px;color:var(--muted);font-family:'DM Mono',monospace;margin-top:3px}
.badge{display:inline-flex;align-items:center;gap:3px;padding:3px 9px;border-radius:20px;font-size:10px;font-weight:700;white-space:nowrap}
.bok{background:rgba(52,211,153,.1);color:var(--ok);border:1px solid rgba(52,211,153,.2)}
.bmut{background:rgba(107,122,158,.1);color:var(--muted);border:1px solid rgba(107,122,158,.2)}
.fa{display:flex;border-top:1px solid var(--bdr);background:rgba(255,255,255,.01)}
.fb{flex:1;padding:10px;border:none;background:none;color:var(--muted);font-family:'Plus Jakarta Sans',sans-serif;font-size:12px;font-weight:600;cursor:pointer;transition:all .15s;border-right:1px solid var(--bdr);display:flex;align-items:center;justify-content:center;gap:4px}
.fb:last-child{border-right:none}
.fb:active{background:rgba(110,231,255,.07);color:var(--acc)}
.lp{max-height:0;overflow:hidden;transition:max-height .35s cubic-bezier(.4,0,.2,1)}
.lp.open{max-height:260px;border-top:1px solid var(--bdr)}
.lb{padding:13px;font-family:'DM Mono',monospace;font-size:11px;line-height:1.8;color:#4ade80;max-height:240px;overflow-y:auto;white-space:pre-wrap;word-break:break-all;background:#020408}
.lb::-webkit-scrollbar{width:3px}.lb::-webkit-scrollbar-thumb{background:rgba(255,255,255,.1);border-radius:2px}
.empty{text-align:center;padding:50px 20px;color:var(--muted)}
.ei{font-size:44px;margin-bottom:12px;opacity:.5}
.et{font-size:14px;font-weight:700;color:var(--txt);margin-bottom:5px}
.es{font-size:12px;line-height:1.5}
.loader{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:60px 20px;gap:12px;color:var(--muted)}
.spin{width:22px;height:22px;border:2px solid var(--bdr);border-top-color:var(--acc);border-radius:50%;animation:sp .7s linear infinite}
@keyframes sp{to{transform:rotate(360deg)}}
.errbox{background:rgba(248,113,113,.08);border:1px solid rgba(248,113,113,.2);border-radius:14px;padding:22px 18px;text-align:center;color:var(--danger);margin:16px 0}
.erri{font-size:30px;margin-bottom:8px}
.errt{font-size:14px;font-weight:700;margin-bottom:5px}
.errs{font-size:12px;opacity:.7;line-height:1.5}
</style>
</head>
<body>
<div class="hdr">
  <div class="logo"><div class="li">⚡</div><div class="ln">CloudBot</div></div>
  <div class="pp" id="pp">LOADING</div>
</div>
<div class="wrap" id="wrap">
  <div class="loader"><div class="spin"></div><div style="font-size:13px">Loading your dashboard...</div></div>
</div>
<script>
var uid=null;
try{var tg=window.Telegram&&window.Telegram.WebApp;if(tg&&tg.initDataUnsafe&&tg.initDataUnsafe.user&&tg.initDataUnsafe.user.id){uid=String(tg.initDataUnsafe.user.id);tg.ready();tg.expand();}}catch(e){}
if(!uid)uid=new URLSearchParams(location.search).get('uid');
var wrap=document.getElementById('wrap');
var ppEl=document.getElementById('pp');
var fileMap={};
var fileData=[];
if(!uid){
  wrap.innerHTML='<div class="errbox"><div class="erri">❌</div><div class="errt">No User ID</div><div class="errs">Please open this link from the Telegram bot using the portal button.</div></div>';
}else{loadPortal();}
function loadPortal(){
  fetch('/api/portal/'+uid)
  .then(function(r){return r.json();})
  .then(function(d){
    if(d.error){
      wrap.innerHTML='<div class="errbox"><div class="erri">⚠️</div><div class="errt">Error</div><div class="errs">'+d.error+'<br><br>Please start the bot with /start first.</div></div>';
      return;
    }
    var files=d.files||[];
    var running=files.filter(function(f){return f.running;}).length;
    var plan=(d.plan||'free').toUpperCase();
    ppEl.textContent=plan;
    fileData=files;
    fileMap={};
    files.forEach(function(f,i){fileMap[f.filename]=i;});
    var joinDate=d.join_date?new Date(d.join_date*1000).toLocaleDateString('en-US',{year:'numeric',month:'short',day:'numeric'}):'—';
    var filesHTML='';
    if(files.length===0){
      filesHTML='<div class="empty"><div class="ei">📭</div><div class="et">No Files Yet</div><div class="es">Send a .py or .js file to the bot to get started</div></div>';
    }else{
      files.forEach(function(f,i){
        var size=(f.size_bytes/1024).toFixed(1);
        var date=f.uploaded_at?new Date(f.uploaded_at*1000).toLocaleString():'—';
        var ext=f.filename.split('.').pop().toUpperCase();
        filesHTML+='<div class="fc" style="animation-delay:'+(i*0.05)+'s">'+
          '<div class="fm" onclick="toggleLog(\''+f.filename+'\')">'+
            '<div class="fl">'+
              '<div class="fn"><span class="fext">'+ext+'</span>'+f.filename+'</div>'+
              '<div class="fmeta">'+size+' KB &nbsp;·&nbsp; '+date+'</div>'+
            '</div>'+
            '<span class="badge '+(f.running?'bok':'bmut')+'">'+(f.running?'▶ On':'■ Off')+'</span>'+
          '</div>'+
          '<div class="fa">'+
            '<button class="fb" onclick="event.stopPropagation();toggleLog(\''+f.filename+'\')">📋 Log</button>'+
            '<button class="fb" onclick="event.stopPropagation();loadPortal()">🔄 Refresh</button>'+
          '</div>'+
          '<div class="lp" id="lp-'+i+'"><div class="lb" id="lb-'+i+'">Loading...</div></div>'+
        '</div>';
      });
    }
    wrap.innerHTML=
      '<div class="pcard">'+
        '<div class="pname">Hi, '+(d.full_name||'User')+' 👋</div>'+
        '<div class="pmeta">@'+(d.username||'unknown')+' &nbsp;·&nbsp; Joined '+joinDate+'</div>'+
      '</div>'+
      '<div class="srow">'+
        '<div class="st"><div class="sn">'+files.length+'</div><div class="sl">Files</div></div>'+
        '<div class="st"><div class="sn" style="color:var(--acc3)">'+running+'</div><div class="sl">Running</div></div>'+
        '<div class="st"><div class="sn" style="color:var(--acc2);font-size:15px;padding-top:6px">'+plan+'</div><div class="sl">Plan</div></div>'+
      '</div>'+
      '<div class="sch"><div class="sct">📁 My Files</div><button class="rb" onclick="loadPortal()">↻</button></div>'+
      '<div id="fl">'+filesHTML+'</div>';
  })
  .catch(function(e){
    wrap.innerHTML='<div class="errbox"><div class="erri">🔌</div><div class="errt">Connection Error</div><div class="errs">Failed to connect. Please try again.</div></div>';
  });
}
function toggleLog(fname){
  var idx=fileMap[fname];
  if(idx===undefined)return;
  var panel=document.getElementById('lp-'+idx);
  var body=document.getElementById('lb-'+idx);
  if(!panel)return;
  if(panel.classList.contains('open')){panel.classList.remove('open');return;}
  panel.classList.add('open');
  body.textContent='Loading...';
  fetch('/api/log?user_id='+uid+'&filename='+encodeURIComponent(fname))
  .then(function(r){return r.json();})
  .then(function(d){body.textContent=d.log||'$ No log output yet';body.scrollTop=body.scrollHeight;})
  .catch(function(){body.textContent='$ Failed to load log';});
}
</script>
</body>
</html>"""

# ══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════════════════════════════════════
@flask_app.route("/")
def index():
    return redirect("/admin")

@flask_app.route("/admin")
def admin_index():
    if not session.get("admin"):
        return redirect("/admin/login")
    return ADMIN_PAGE

@flask_app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    err = ""
    if request.method == "POST":
        if request.form.get("username","") == get_web_username() and \
           request.form.get("password","") == get_web_password():
            session["admin"] = True
            return redirect("/admin")
        err = '<div class="err">⚠️ Invalid username or password</div>'
    return LOGIN_PAGE.replace("{ERROR}", err)

@flask_app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect("/admin/login")

@flask_app.route("/portal")
def user_portal():
    return USER_PORTAL

@flask_app.route("/health")
def health():
    return jsonify({"status": "ok"})

# ══════════════════════════════════════════════════════════════════════════════
# API
# ══════════════════════════════════════════════════════════════════════════════
@flask_app.route("/api/stats")
@require_admin
def api_stats():
    s = get_global_stats()
    s["running_processes"] = get_total_process_count()
    return jsonify(s)

@flask_app.route("/api/system")
@require_admin
def api_system():
    return jsonify(get_system_stats())

@flask_app.route("/api/activity")
@require_admin
def api_activity():
    import database
    try:
        conn = database.get_conn()
        rows = conn.execute("SELECT user_id,action,detail,timestamp FROM activity_logs ORDER BY timestamp DESC LIMIT 30").fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except:
        return jsonify([])

@flask_app.route("/api/users")
@require_admin
def api_users():
    users = get_all_users()
    for u in users:
        u["file_count"] = len(get_file_list(u["user_id"]))
    return jsonify(users)

@flask_app.route("/api/user/<int:uid>")
@require_admin
def api_user_detail(uid):
    user = get_user(uid)
    if not user:
        return jsonify({"error": "Not found"}), 404
    user["files"] = get_file_list(uid)
    return jsonify(user)

@flask_app.route("/api/user/<int:uid>/ban", methods=["POST"])
@require_admin
def api_ban(uid):
    ban_user(uid, True); return jsonify({"ok": True})

@flask_app.route("/api/user/<int:uid>/unban", methods=["POST"])
@require_admin
def api_unban(uid):
    ban_user(uid, False); return jsonify({"ok": True})

@flask_app.route("/api/user/<int:uid>/premium", methods=["POST"])
@require_admin
def api_premium(uid):
    set_premium(uid, 30); return jsonify({"ok": True})

@flask_app.route("/api/files")
@require_admin
def api_files():
    result = []
    for u in get_all_users():
        for f in get_file_list(u["user_id"]):
            f["user_id"] = u["user_id"]
            result.append(f)
    return jsonify(result)

@flask_app.route("/api/processes")
@require_admin
def api_processes():
    result = []
    try:
        for (uid, fname), info in get_all_processes().items():
            pi = get_process_info(uid, fname) or {}
            result.append({"user_id":uid,"filename":fname,"pid":info.get("pid"),"started_at":info.get("started_at",0),"cpu_percent":pi.get("cpu_percent",0),"memory_mb":pi.get("memory_mb",0)})
    except:
        pass
    return jsonify(result)

@flask_app.route("/api/start", methods=["POST"])
@require_admin
def api_start():
    d = request.json
    uid = int(d["user_id"]); fname = d["filename"]
    user = get_user(uid)
    ok, msg = run_script(uid, fname, user.get("plan","free") if user else "free")
    return jsonify({"ok": ok, "msg": msg})

@flask_app.route("/api/stop", methods=["POST"])
@require_admin
def api_stop():
    d = request.json
    ok, msg = stop_script(int(d["user_id"]), d["filename"])
    return jsonify({"ok": ok, "msg": msg})

@flask_app.route("/api/log")
def api_log():
    uid = request.args.get("user_id")
    fname = request.args.get("filename")
    if not uid or not fname:
        return jsonify({"log": "Missing params"})
    try:
        return jsonify({"log": read_log(int(uid), fname, last_n=200)})
    except Exception as e:
        return jsonify({"log": "Error: " + str(e)})

@flask_app.route("/api/set_creds", methods=["POST"])
@require_admin
def api_set_creds():
    d = request.json
    set_setting("web_username", d.get("username",""))
    set_setting("web_password", d.get("password",""))
    return jsonify({"ok": True})

@flask_app.route("/api/bot_action", methods=["POST"])
@require_admin
def api_bot_action():
    action = request.json.get("action","")
    if action == "maintenance_on":   set_setting("maintenance","1"); return jsonify({"msg":"🔒 Maintenance enabled"})
    elif action == "maintenance_off": set_setting("maintenance","0"); return jsonify({"msg":"🟢 Maintenance disabled"})
    elif action == "stop_all":
        try: stop_all_scripts()
        except: pass
        return jsonify({"msg":"💀 All scripts stopped"})
    return jsonify({"msg":"Unknown"})

@flask_app.route("/api/portal/<int:uid>")
def api_portal(uid):
    try:
        user = get_user(uid)
        if not user:
            return jsonify({"error": "User not found. Please /start the bot first."})
        user["files"] = get_file_list(uid)
        return jsonify(user)
    except Exception as e:
        return jsonify({"error": str(e)})
