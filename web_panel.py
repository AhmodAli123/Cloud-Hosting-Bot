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

# ── Credential helpers ────────────────────────────────────────────────────────
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

# ── HTML Pages ────────────────────────────────────────────────────────────────
LOGIN_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CloudBot · Admin Login</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@700;800&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#060a10;--surf:#0d1421;--bdr:#1a2840;--acc:#00d4ff;--acc2:#7c3aed;--txt:#e2e8f0;--mut:#64748b;--err:#ef4444}
body{background:var(--bg);color:var(--txt);font-family:'Space Mono',monospace;min-height:100vh;display:flex;align-items:center;justify-content:center;overflow:hidden}
.grid{position:fixed;inset:0;background-image:linear-gradient(rgba(0,212,255,.04) 1px,transparent 1px),linear-gradient(90deg,rgba(0,212,255,.04) 1px,transparent 1px);background-size:44px 44px;animation:gridMove 25s linear infinite}
@keyframes gridMove{to{transform:translateY(44px)}}
.orb{position:fixed;border-radius:50%;filter:blur(90px);pointer-events:none}
.orb1{width:500px;height:500px;background:rgba(0,212,255,.06);top:-150px;right:-150px}
.orb2{width:350px;height:350px;background:rgba(124,58,237,.06);bottom:-100px;left:-100px}
.card{position:relative;z-index:1;background:var(--surf);border:1px solid var(--bdr);border-radius:20px;padding:48px 40px;width:420px;box-shadow:0 0 80px rgba(0,212,255,.04),0 30px 60px rgba(0,0,0,.6);animation:up .5s ease}
@keyframes up{from{opacity:0;transform:translateY(24px)}to{opacity:1;transform:translateY(0)}}
.brand{display:flex;align-items:center;gap:14px;margin-bottom:36px}
.brand-icon{width:48px;height:48px;border-radius:12px;background:linear-gradient(135deg,var(--acc),var(--acc2));display:flex;align-items:center;justify-content:center;font-size:22px}
.brand-name{font-family:'Syne',sans-serif;font-size:22px;font-weight:800;letter-spacing:-.5px}
.brand-role{font-size:10px;color:var(--mut);letter-spacing:3px;text-transform:uppercase;margin-top:2px}
.line{height:1px;background:var(--bdr);margin-bottom:28px}
.field{margin-bottom:18px}
label{display:block;font-size:10px;color:var(--mut);letter-spacing:2px;text-transform:uppercase;margin-bottom:8px}
.inp-wrap{position:relative}
.inp-icon{position:absolute;left:14px;top:50%;transform:translateY(-50%);font-size:15px}
input[type=text],input[type=password]{width:100%;padding:13px 14px 13px 42px;background:var(--bg);border:1px solid var(--bdr);border-radius:10px;color:var(--txt);font-family:'Space Mono',monospace;font-size:14px;outline:none;transition:border-color .2s,box-shadow .2s}
input:focus{border-color:var(--acc);box-shadow:0 0 0 3px rgba(0,212,255,.08)}
.btn{width:100%;padding:14px;margin-top:8px;background:linear-gradient(135deg,var(--acc),var(--acc2));border:none;border-radius:10px;color:#fff;font-family:'Syne',sans-serif;font-size:15px;font-weight:800;letter-spacing:1px;cursor:pointer;transition:opacity .2s,transform .1s}
.btn:hover{opacity:.88;transform:translateY(-1px)}
.err{background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.3);border-radius:8px;padding:10px 14px;color:var(--err);font-size:12px;margin-bottom:18px}
.portal-link{text-align:center;margin-top:18px;font-size:12px;color:var(--mut)}
.portal-link a{color:var(--acc);text-decoration:none}
</style>
</head>
<body>
<div class="grid"></div>
<div class="orb orb1"></div>
<div class="orb orb2"></div>
<div class="card">
  <div class="brand">
    <div class="brand-icon">🤖</div>
    <div>
      <div class="brand-name">CloudBot</div>
      <div class="brand-role">Admin Panel</div>
    </div>
  </div>
  <div class="line"></div>
  {ERROR}
  <form method="POST" action="/admin/login">
    <div class="field">
      <label>Username</label>
      <div class="inp-wrap"><span class="inp-icon">👤</span><input type="text" name="username" placeholder="Enter username" autocomplete="off"></div>
    </div>
    <div class="field">
      <label>Password</label>
      <div class="inp-wrap"><span class="inp-icon">🔑</span><input type="password" name="password" placeholder="Enter password"></div>
    </div>
    <button type="submit" class="btn">ACCESS PANEL →</button>
  </form>
  <div class="portal-link">User portal? <a href="/portal">Click here</a></div>
</div>
</body>
</html>"""

ADMIN_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CloudBot · Admin Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#060a10;--surf:#0d1421;--surf2:#111927;--bdr:#1a2840;--acc:#00d4ff;--acc2:#7c3aed;--txt:#e2e8f0;--mut:#64748b;--ok:#10b981;--err:#ef4444;--warn:#f59e0b}
body{background:var(--bg);color:var(--txt);font-family:'Space Mono',monospace;min-height:100vh;display:flex}
/* SIDEBAR */
.sidebar{width:240px;min-height:100vh;background:var(--surf);border-right:1px solid var(--bdr);display:flex;flex-direction:column;position:fixed;top:0;left:0;bottom:0;z-index:50}
.s-logo{padding:22px 18px;border-bottom:1px solid var(--bdr);display:flex;align-items:center;gap:12px}
.s-icon{width:38px;height:38px;border-radius:10px;background:linear-gradient(135deg,var(--acc),var(--acc2));display:flex;align-items:center;justify-content:center;font-size:17px}
.s-name{font-family:'Syne',sans-serif;font-weight:800;font-size:15px}
.s-role{font-size:9px;color:var(--mut);letter-spacing:2px;text-transform:uppercase}
nav{flex:1;padding:14px 10px;overflow-y:auto}
.nav-sec{font-size:9px;color:var(--mut);letter-spacing:2px;padding:14px 10px 6px;text-transform:uppercase}
.nav-btn{display:flex;align-items:center;gap:10px;width:100%;padding:10px 12px;border-radius:8px;border:none;background:none;color:var(--mut);font-family:'Space Mono',monospace;font-size:12px;cursor:pointer;transition:all .15s;text-align:left;margin-bottom:2px}
.nav-btn:hover{background:var(--bdr);color:var(--txt)}
.nav-btn.active{background:rgba(0,212,255,.1);color:var(--acc);border:1px solid rgba(0,212,255,.2)}
.s-footer{padding:14px 10px;border-top:1px solid var(--bdr)}
.logout-btn{display:flex;align-items:center;gap:10px;width:100%;padding:10px 12px;border-radius:8px;border:1px solid rgba(239,68,68,.25);background:rgba(239,68,68,.05);color:var(--err);font-size:12px;cursor:pointer;font-family:'Space Mono',monospace;transition:all .15s;text-decoration:none}
.logout-btn:hover{background:rgba(239,68,68,.12)}
/* MAIN */
.main{margin-left:240px;padding:30px;flex:1;min-height:100vh}
.page{display:none}.page.active{display:block}
.ph{margin-bottom:26px;display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:12px}
.pt{font-family:'Syne',sans-serif;font-size:22px;font-weight:800}
.ps{color:var(--mut);font-size:12px;margin-top:3px}
/* STATS */
.sg{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:24px}
.sc{background:var(--surf);border:1px solid var(--bdr);border-radius:12px;padding:18px;transition:border-color .2s}
.sc:hover{border-color:var(--acc)}
.sl{font-size:10px;color:var(--mut);letter-spacing:1px;text-transform:uppercase;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center}
.sv{font-family:'Syne',sans-serif;font-size:30px;font-weight:800}
/* SYS */
.sysg{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:24px}
.sysc{background:var(--surf);border:1px solid var(--bdr);border-radius:12px;padding:16px}
.syl{font-size:10px;color:var(--mut);letter-spacing:1px;margin-bottom:6px}
.syv{font-family:'Syne',sans-serif;font-size:22px;font-weight:700}
.pb{height:5px;background:var(--bdr);border-radius:3px;margin-top:10px;overflow:hidden}
.pf{height:100%;border-radius:3px;background:linear-gradient(90deg,var(--acc),var(--acc2));transition:width .6s}
/* CARD TABLE */
.card{background:var(--surf);border:1px solid var(--bdr);border-radius:12px;overflow:hidden;margin-bottom:18px}
.ch{padding:14px 18px;border-bottom:1px solid var(--bdr);display:flex;align-items:center;justify-content:space-between}
.ct{font-family:'Syne',sans-serif;font-weight:700;font-size:14px}
table{width:100%;border-collapse:collapse}
th{padding:11px 14px;text-align:left;font-size:10px;color:var(--mut);letter-spacing:1px;text-transform:uppercase;border-bottom:1px solid var(--bdr)}
td{padding:11px 14px;font-size:12px;border-bottom:1px solid rgba(26,40,64,.4);vertical-align:middle}
tr:last-child td{border-bottom:none}
tr:hover td{background:rgba(255,255,255,.015)}
/* BADGES */
.badge{display:inline-block;padding:3px 9px;border-radius:20px;font-size:10px}
.b-ok{background:rgba(16,185,129,.12);color:var(--ok);border:1px solid rgba(16,185,129,.25)}
.b-err{background:rgba(239,68,68,.12);color:var(--err);border:1px solid rgba(239,68,68,.25)}
.b-warn{background:rgba(245,158,11,.12);color:var(--warn);border:1px solid rgba(245,158,11,.25)}
.b-acc{background:rgba(0,212,255,.12);color:var(--acc);border:1px solid rgba(0,212,255,.25)}
.b-mut{background:rgba(100,116,139,.12);color:var(--mut);border:1px solid rgba(100,116,139,.25)}
/* BUTTONS */
.btn{padding:6px 12px;border-radius:6px;border:none;cursor:pointer;font-size:11px;font-family:'Space Mono',monospace;transition:all .15s}
.btn-p{background:rgba(0,212,255,.12);color:var(--acc);border:1px solid rgba(0,212,255,.25)}.btn-p:hover{background:rgba(0,212,255,.22)}
.btn-d{background:rgba(239,68,68,.12);color:var(--err);border:1px solid rgba(239,68,68,.25)}.btn-d:hover{background:rgba(239,68,68,.22)}
.btn-s{background:rgba(16,185,129,.12);color:var(--ok);border:1px solid rgba(16,185,129,.25)}.btn-s:hover{background:rgba(16,185,129,.22)}
.btn-lg{padding:12px 20px;font-size:13px;width:100%;margin-bottom:8px;border-radius:8px}
/* SEARCH */
.srch{padding:8px 14px;background:var(--bg);border:1px solid var(--bdr);border-radius:8px;color:var(--txt);font-family:'Space Mono',monospace;font-size:12px;outline:none;width:220px}
.srch:focus{border-color:var(--acc)}
/* TERMINAL */
.term{background:#020508;border:1px solid var(--bdr);border-radius:12px;overflow:hidden}
.th{background:var(--surf);padding:10px 14px;display:flex;align-items:center;gap:8px;border-bottom:1px solid var(--bdr)}
.dot{width:11px;height:11px;border-radius:50%}
.tb{padding:16px;font-size:12px;line-height:1.75;color:#00ff7f;min-height:320px;max-height:520px;overflow-y:auto;white-space:pre-wrap;word-break:break-all}
.tb::-webkit-scrollbar{width:5px}.tb::-webkit-scrollbar-thumb{background:var(--bdr);border-radius:3px}
/* MODAL */
.overlay{display:none;position:fixed;inset:0;z-index:200;background:rgba(0,0,0,.75);backdrop-filter:blur(4px);align-items:center;justify-content:center}
.overlay.open{display:flex}
.modal{background:var(--surf);border:1px solid var(--bdr);border-radius:16px;padding:26px;width:580px;max-width:95vw;max-height:85vh;overflow-y:auto;animation:up .2s ease}
@keyframes up{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
.mh{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px}
.mt{font-family:'Syne',sans-serif;font-weight:700;font-size:17px}
.mc{background:none;border:none;color:var(--mut);font-size:20px;cursor:pointer}
.fr{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;background:var(--surf2);border:1px solid var(--bdr);border-radius:8px;margin-bottom:8px}
/* SETTINGS INPUT */
.set-inp{width:100%;padding:11px 14px;background:var(--bg);border:1px solid var(--bdr);border-radius:8px;color:var(--txt);font-family:'Space Mono',monospace;font-size:13px;outline:none;margin-bottom:12px}
.set-inp:focus{border-color:var(--acc)}
</style>
</head>
<body>
<div class="sidebar">
  <div class="s-logo">
    <div class="s-icon">🤖</div>
    <div><div class="s-name">CloudBot</div><div class="s-role">Admin Panel</div></div>
  </div>
  <nav>
    <div class="nav-sec">Main</div>
    <button class="nav-btn active" onclick="go('dashboard',this)">📊 Dashboard</button>
    <button class="nav-btn" onclick="go('users',this)">👥 Users</button>
    <button class="nav-btn" onclick="go('files',this)">📁 All Files</button>
    <div class="nav-sec">Monitor</div>
    <button class="nav-btn" onclick="go('processes',this)">⚙️ Processes</button>
    <button class="nav-btn" onclick="go('terminal',this)">💻 Terminal</button>
    <div class="nav-sec">Config</div>
    <button class="nav-btn" onclick="go('settings',this)">🔧 Settings</button>
  </nav>
  <div class="s-footer">
    <a href="/admin/logout" class="logout-btn">🚪 Logout</a>
  </div>
</div>

<div class="main">
  <!-- DASHBOARD -->
  <div class="page active" id="pg-dashboard">
    <div class="ph">
      <div><div class="pt">Dashboard</div><div class="ps">System overview · <span id="clock"></span></div></div>
    </div>
    <div class="sg">
      <div class="sc"><div class="sl">Total Users <span>👥</span></div><div class="sv" id="d-users">—</div></div>
      <div class="sc"><div class="sl">Premium <span>⭐</span></div><div class="sv" id="d-premium">—</div></div>
      <div class="sc"><div class="sl">Total Files <span>📁</span></div><div class="sv" id="d-files">—</div></div>
      <div class="sc"><div class="sl">Running <span>⚙️</span></div><div class="sv" id="d-procs">—</div></div>
    </div>
    <div class="sysg">
      <div class="sysc"><div class="syl">CPU</div><div class="syv" id="cpu-v">—</div><div class="pb"><div class="pf" id="cpu-b" style="width:0"></div></div></div>
      <div class="sysc"><div class="syl">RAM</div><div class="syv" id="ram-v">—</div><div class="pb"><div class="pf" id="ram-b" style="width:0"></div></div></div>
      <div class="sysc"><div class="syl">Disk</div><div class="syv" id="dsk-v">—</div><div class="pb"><div class="pf" id="dsk-b" style="width:0"></div></div></div>
    </div>
    <div class="card">
      <div class="ch"><div class="ct">Recent Activity</div></div>
      <table><thead><tr><th>User ID</th><th>Action</th><th>Detail</th><th>Time</th></tr></thead>
      <tbody id="act-tb"><tr><td colspan="4" style="text-align:center;color:var(--mut);padding:20px">Loading...</td></tr></tbody></table>
    </div>
  </div>

  <!-- USERS -->
  <div class="page" id="pg-users">
    <div class="ph">
      <div><div class="pt">Users</div><div class="ps">Manage all registered users</div></div>
      <input class="srch" id="u-search" placeholder="🔍 Search..." oninput="filterU()">
    </div>
    <div class="card">
      <table><thead><tr><th>User</th><th>ID</th><th>Plan</th><th>Status</th><th>Files</th><th>Joined</th><th>Actions</th></tr></thead>
      <tbody id="u-tb"><tr><td colspan="7" style="text-align:center;color:var(--mut);padding:20px">Loading...</td></tr></tbody></table>
    </div>
  </div>

  <!-- FILES -->
  <div class="page" id="pg-files">
    <div class="ph"><div><div class="pt">All Files</div><div class="ps">Every uploaded file</div></div></div>
    <div class="card">
      <table><thead><tr><th>Filename</th><th>Owner</th><th>Status</th><th>Size</th><th>Uploaded</th><th>Actions</th></tr></thead>
      <tbody id="f-tb"><tr><td colspan="6" style="text-align:center;color:var(--mut);padding:20px">Loading...</td></tr></tbody></table>
    </div>
  </div>

  <!-- PROCESSES -->
  <div class="page" id="pg-processes">
    <div class="ph"><div><div class="pt">Processes</div><div class="ps">Live running scripts</div></div></div>
    <div class="card">
      <table><thead><tr><th>User</th><th>File</th><th>PID</th><th>CPU</th><th>RAM</th><th>Uptime</th><th>Action</th></tr></thead>
      <tbody id="p-tb"><tr><td colspan="7" style="text-align:center;color:var(--mut);padding:20px">Loading...</td></tr></tbody></table>
    </div>
  </div>

  <!-- TERMINAL -->
  <div class="page" id="pg-terminal">
    <div class="ph"><div><div class="pt">Live Terminal</div><div class="ps">View script logs in real time</div></div></div>
    <div style="display:flex;gap:10px;margin-bottom:16px;flex-wrap:wrap">
      <input class="srch" id="t-uid" placeholder="User ID" style="width:140px">
      <input class="srch" id="t-file" placeholder="filename.py" style="width:180px">
      <button class="btn btn-p" onclick="loadLog()">Load Log</button>
      <button class="btn btn-s" onclick="startAR()">▶ Auto Refresh</button>
      <button class="btn btn-d" onclick="stopAR()">■ Stop</button>
    </div>
    <div class="term">
      <div class="th">
        <div class="dot" style="background:#ef4444"></div>
        <div class="dot" style="background:#f59e0b"></div>
        <div class="dot" style="background:#10b981"></div>
        <span style="font-size:11px;color:var(--mut);margin-left:8px" id="t-title">No log loaded</span>
      </div>
      <div class="tb" id="t-out">$ Waiting...\n</div>
    </div>
  </div>

  <!-- SETTINGS -->
  <div class="page" id="pg-settings">
    <div class="ph"><div><div class="pt">Settings</div><div class="ps">Panel & bot configuration</div></div></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;max-width:780px">
      <div class="card">
        <div class="ch"><div class="ct">🔐 Web Credentials</div></div>
        <div style="padding:18px">
          <label style="font-size:10px;color:var(--mut);letter-spacing:1px;text-transform:uppercase;display:block;margin-bottom:6px">New Username</label>
          <input class="set-inp" id="s-user" placeholder="Enter new username">
          <label style="font-size:10px;color:var(--mut);letter-spacing:1px;text-transform:uppercase;display:block;margin-bottom:6px">New Password</label>
          <input class="set-inp" id="s-pass" type="password" placeholder="Enter new password">
          <button class="btn btn-p btn-lg" onclick="saveCreds()">💾 Save Credentials</button>
          <div id="creds-msg" style="font-size:11px;text-align:center;margin-top:6px"></div>
        </div>
      </div>
      <div class="card">
        <div class="ch"><div class="ct">🔧 Bot Controls</div></div>
        <div style="padding:18px">
          <button class="btn btn-d btn-lg" onclick="botAct('maintenance_on')">🔒 Enable Maintenance</button>
          <button class="btn btn-s btn-lg" onclick="botAct('maintenance_off')">🟢 Disable Maintenance</button>
          <button class="btn btn-d btn-lg" onclick="botAct('stop_all')">💀 Stop All Scripts</button>
          <div id="act-msg" style="font-size:11px;text-align:center;margin-top:6px"></div>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- USER MODAL -->
<div class="overlay" id="u-modal">
  <div class="modal">
    <div class="mh">
      <div class="mt" id="m-title">User Details</div>
      <button class="mc" onclick="closeM()">✕</button>
    </div>
    <div id="m-body">Loading...</div>
  </div>
</div>

<script>
let allU=[], arTimer=null;

function go(name,el){
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById('pg-'+name).classList.add('active');
  if(el)el.classList.add('active');
  if(name==='dashboard')loadDash();
  if(name==='users')loadUsers();
  if(name==='files')loadFiles();
  if(name==='processes')loadProcs();
}

setInterval(()=>{document.getElementById('clock').textContent=new Date().toLocaleTimeString()},1000);
document.getElementById('clock').textContent=new Date().toLocaleTimeString();

const api=async u=>{const r=await fetch(u);return r.json()};

async function loadDash(){
  const[s,sys]=await Promise.all([api('/api/stats'),api('/api/system')]);
  document.getElementById('d-users').textContent=s.total_users;
  document.getElementById('d-premium').textContent=s.premium_users;
  document.getElementById('d-files').textContent=s.total_files;
  document.getElementById('d-procs').textContent=s.running_processes;
  document.getElementById('cpu-v').textContent=sys.cpu_percent.toFixed(1)+'%';
  document.getElementById('ram-v').textContent=sys.ram_percent.toFixed(1)+'%';
  document.getElementById('dsk-v').textContent=sys.disk_percent.toFixed(1)+'%';
  document.getElementById('cpu-b').style.width=sys.cpu_percent+'%';
  document.getElementById('ram-b').style.width=sys.ram_percent+'%';
  document.getElementById('dsk-b').style.width=sys.disk_percent+'%';
  const acts=await api('/api/activity');
  document.getElementById('act-tb').innerHTML=acts.map(a=>`<tr>
    <td>${a.user_id}</td>
    <td><span class="badge b-acc">${a.action}</span></td>
    <td style="color:var(--mut)">${a.detail||'—'}</td>
    <td style="color:var(--mut);font-size:10px">${new Date(a.timestamp*1000).toLocaleString()}</td>
  </tr>`).join('')||'<tr><td colspan="4" style="text-align:center;color:var(--mut);padding:20px">No activity</td></tr>';
}

async function loadUsers(){
  allU=await api('/api/users');
  renderU(allU);
}
function renderU(data){
  document.getElementById('u-tb').innerHTML=data.map(u=>`<tr>
    <td><b style="font-size:13px">${u.full_name||'—'}</b><div style="color:var(--mut);font-size:10px">@${u.username||'unknown'}</div></td>
    <td style="color:var(--mut);font-size:11px">${u.user_id}</td>
    <td><span class="badge ${u.plan==='premium'?'b-warn':'b-mut'}">${u.plan}</span></td>
    <td><span class="badge ${u.is_banned?'b-err':'b-ok'}">${u.is_banned?'Banned':'Active'}</span></td>
    <td>${u.file_count||0}</td>
    <td style="color:var(--mut);font-size:10px">${new Date(u.join_date*1000).toLocaleDateString()}</td>
    <td style="display:flex;gap:5px;flex-wrap:wrap">
      <button class="btn btn-p" onclick="viewU(${u.user_id})">👁</button>
      <button class="btn ${u.is_banned?'btn-s':'btn-d'}" onclick="toggleBan(${u.user_id},${u.is_banned})">${u.is_banned?'Unban':'Ban'}</button>
      <button class="btn btn-s" onclick="setPrem(${u.user_id})">⭐</button>
    </td>
  </tr>`).join('')||'<tr><td colspan="7" style="text-align:center;color:var(--mut);padding:20px">No users</td></tr>';
}
function filterU(){
  const q=document.getElementById('u-search').value.toLowerCase();
  renderU(allU.filter(u=>(u.full_name||'').toLowerCase().includes(q)||(u.username||'').toLowerCase().includes(q)||String(u.user_id).includes(q)));
}

async function loadFiles(){
  const data=await api('/api/files');
  document.getElementById('f-tb').innerHTML=data.map(f=>`<tr>
    <td>📄 ${f.filename}</td>
    <td style="color:var(--mut);font-size:11px">${f.user_id}</td>
    <td><span class="badge ${f.running?'b-ok':'b-mut'}">${f.running?'▶ Running':'■ Stopped'}</span></td>
    <td style="color:var(--mut);font-size:11px">${(f.size_bytes/1024).toFixed(1)} KB</td>
    <td style="color:var(--mut);font-size:10px">${new Date(f.uploaded_at*1000).toLocaleString()}</td>
    <td style="display:flex;gap:5px">
      <button class="btn btn-p" onclick="loadLogD(${f.user_id},'${f.filename}')">📋</button>
      <button class="btn ${f.running?'btn-d':'btn-s'}" onclick="toggleScript(${f.user_id},'${f.filename}',${f.running})">${f.running?'Stop':'Start'}</button>
    </td>
  </tr>`).join('')||'<tr><td colspan="6" style="text-align:center;color:var(--mut);padding:20px">No files</td></tr>';
}

async function loadProcs(){
  const data=await api('/api/processes');
  document.getElementById('p-tb').innerHTML=data.map(p=>`<tr>
    <td style="font-size:11px">${p.user_id}</td>
    <td>📄 ${p.filename}</td>
    <td style="color:var(--acc)">${p.pid}</td>
    <td>${(p.cpu_percent||0).toFixed(1)}%</td>
    <td>${(p.memory_mb||0).toFixed(1)} MB</td>
    <td style="color:var(--mut);font-size:10px">${Math.floor((Date.now()/1000-p.started_at)/60)}m ago</td>
    <td><button class="btn btn-d" onclick="stopS(${p.user_id},'${p.filename}')">Stop</button></td>
  </tr>`).join('')||'<tr><td colspan="7" style="text-align:center;color:var(--mut);padding:20px">No running processes</td></tr>';
}

async function viewU(uid){
  document.getElementById('u-modal').classList.add('open');
  document.getElementById('m-body').innerHTML='<div style="text-align:center;padding:30px;color:var(--mut)">Loading...</div>';
  const d=await api('/api/user/'+uid);
  document.getElementById('m-title').textContent=(d.full_name||'User')+' (@'+(d.username||'unknown')+')';
  const fh=(d.files||[]).map(f=>`<div class="fr">
    <div><div style="font-size:13px">📄 ${f.filename}</div><div style="font-size:10px;color:var(--mut)">${(f.size_bytes/1024).toFixed(1)} KB</div></div>
    <span class="badge ${f.running?'b-ok':'b-mut'}">${f.running?'▶ Running':'■ Stopped'}</span>
  </div>`).join('')||'<div style="color:var(--mut);font-size:12px;text-align:center;padding:20px">No files uploaded</div>';
  document.getElementById('m-body').innerHTML=`
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:18px">
      <div style="background:var(--surf2);border:1px solid var(--bdr);border-radius:8px;padding:12px"><div style="font-size:10px;color:var(--mut);margin-bottom:4px">USER ID</div><div style="font-weight:700">${d.user_id}</div></div>
      <div style="background:var(--surf2);border:1px solid var(--bdr);border-radius:8px;padding:12px"><div style="font-size:10px;color:var(--mut);margin-bottom:4px">PLAN</div><span class="badge ${d.plan==='premium'?'b-warn':'b-mut'}">${d.plan}</span></div>
      <div style="background:var(--surf2);border:1px solid var(--bdr);border-radius:8px;padding:12px"><div style="font-size:10px;color:var(--mut);margin-bottom:4px">STATUS</div><span class="badge ${d.is_banned?'b-err':'b-ok'}">${d.is_banned?'Banned':'Active'}</span></div>
    </div>
    <div style="font-family:'Syne',sans-serif;font-weight:700;margin-bottom:12px">Files (${(d.files||[]).length})</div>${fh}`;
}
function closeM(){document.getElementById('u-modal').classList.remove('open')}

async function toggleBan(uid,banned){await fetch('/api/user/'+uid+(banned?'/unban':'/ban'),{method:'POST'});loadUsers()}
async function setPrem(uid){await fetch('/api/user/'+uid+'/premium',{method:'POST'});loadUsers()}
async function toggleScript(uid,fname,running){
  await fetch(running?'/api/stop':'/api/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:uid,filename:fname})});
  loadFiles();
}
async function stopS(uid,fname){
  await fetch('/api/stop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:uid,filename:fname})});
  loadProcs();
}

function loadLogD(uid,fname){
  document.getElementById('t-uid').value=uid;
  document.getElementById('t-file').value=fname;
  go('terminal',null);
  document.querySelectorAll('.nav-btn').forEach(b=>b.classList.remove('active'));
  loadLog();
}
async function loadLog(){
  const uid=document.getElementById('t-uid').value.trim();
  const fname=document.getElementById('t-file').value.trim();
  if(!uid||!fname){alert('Enter User ID and filename');return}
  document.getElementById('t-title').textContent=uid+' / '+fname;
  const d=await api('/api/log?user_id='+uid+'&filename='+encodeURIComponent(fname));
  const el=document.getElementById('t-out');
  el.textContent=d.log||'No log found';
  el.scrollTop=el.scrollHeight;
}
function startAR(){if(arTimer)return;arTimer=setInterval(loadLog,3000)}
function stopAR(){clearInterval(arTimer);arTimer=null}

async function saveCreds(){
  const u=document.getElementById('s-user').value.trim();
  const p=document.getElementById('s-pass').value.trim();
  if(!u||!p){document.getElementById('creds-msg').textContent='⚠️ Both fields required';return}
  const r=await fetch('/api/set_creds',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p})});
  const d=await r.json();
  document.getElementById('creds-msg').style.color=d.ok?'var(--ok)':'var(--err)';
  document.getElementById('creds-msg').textContent=d.ok?'✅ Saved!':'❌ Failed';
}
async function botAct(action){
  const r=await fetch('/api/bot_action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action})});
  const d=await r.json();
  document.getElementById('act-msg').textContent=d.msg||'✅ Done';
}

loadDash();
setInterval(()=>{
  if(document.getElementById('pg-dashboard').classList.contains('active'))loadDash();
  if(document.getElementById('pg-processes').classList.contains('active'))loadProcs();
},10000);
</script>
</body></html>"""

USER_PORTAL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CloudBot · My Files</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@700;800&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#060a10;--surf:#0d1421;--surf2:#111927;--bdr:#1a2840;--acc:#00d4ff;--acc2:#7c3aed;--txt:#e2e8f0;--mut:#64748b;--ok:#10b981;--err:#ef4444}
body{background:var(--bg);color:var(--txt);font-family:'Space Mono',monospace;min-height:100vh}
.hdr{background:var(--surf);border-bottom:1px solid var(--bdr);padding:14px 28px;display:flex;align-items:center;justify-content:space-between}
.logo{font-family:'Syne',sans-serif;font-weight:800;font-size:18px;display:flex;align-items:center;gap:10px}
.logo span{width:32px;height:32px;border-radius:8px;background:linear-gradient(135deg,var(--acc),var(--acc2));display:flex;align-items:center;justify-content:center;font-size:14px}
.uid{font-size:11px;color:var(--mut)}
.wrap{max-width:860px;margin:36px auto;padding:0 20px}
.name{font-family:'Syne',sans-serif;font-size:26px;font-weight:800;margin-bottom:4px}
.sub{color:var(--mut);font-size:12px;margin-bottom:28px}
.sg{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:28px}
.sc{background:var(--surf);border:1px solid var(--bdr);border-radius:12px;padding:18px;text-align:center}
.sv{font-family:'Syne',sans-serif;font-size:30px;font-weight:800;color:var(--acc)}
.sl{font-size:10px;color:var(--mut);letter-spacing:1px;margin-top:4px}
.card{background:var(--surf);border:1px solid var(--bdr);border-radius:12px;overflow:hidden;margin-bottom:18px}
.ch{padding:14px 18px;border-bottom:1px solid var(--bdr);font-family:'Syne',sans-serif;font-weight:700;font-size:14px}
.fi{display:flex;align-items:center;justify-content:space-between;padding:14px 18px;border-bottom:1px solid rgba(26,40,64,.4)}
.fi:last-child{border-bottom:none}
.fn{font-size:13px}
.fm{font-size:10px;color:var(--mut);margin-top:3px}
.badge{display:inline-block;padding:3px 9px;border-radius:20px;font-size:10px}
.b-ok{background:rgba(16,185,129,.12);color:var(--ok);border:1px solid rgba(16,185,129,.25)}
.b-mut{background:rgba(100,116,139,.12);color:var(--mut);border:1px solid rgba(100,116,139,.25)}
.log-btn{background:rgba(0,212,255,.1);border:1px solid rgba(0,212,255,.25);color:var(--acc);padding:4px 10px;border-radius:6px;font-size:10px;cursor:pointer;font-family:'Space Mono',monospace}
.term{background:#020508;border:1px solid var(--bdr);border-radius:12px;overflow:hidden;margin-top:18px}
.th{background:var(--surf);padding:9px 14px;display:flex;align-items:center;gap:7px;border-bottom:1px solid var(--bdr)}
.dot{width:10px;height:10px;border-radius:50%}
.tb{padding:14px;font-size:11px;line-height:1.75;color:#00ff7f;min-height:200px;max-height:360px;overflow-y:auto;white-space:pre-wrap;word-break:break-all}
.empty{padding:40px;text-align:center;color:var(--mut);font-size:12px}
</style>
</head>
<body>
<div class="hdr">
  <div class="logo"><span>🤖</span> CloudBot</div>
  <div class="uid" id="uid-lbl">Loading...</div>
</div>
<div class="wrap">
  <div class="name" id="p-name">My Dashboard</div>
  <div class="sub" id="p-sub">Loading...</div>
  <div class="sg">
    <div class="sc"><div class="sv" id="p-fc">—</div><div class="sl">FILES</div></div>
    <div class="sc"><div class="sv" id="p-rc">—</div><div class="sl">RUNNING</div></div>
    <div class="sc"><div class="sv" id="p-pl">—</div><div class="sl">PLAN</div></div>
  </div>
  <div class="card">
    <div class="ch">📁 My Files</div>
    <div id="fl"><div class="empty">Loading your files...</div></div>
  </div>
  <div class="term" id="log-box" style="display:none">
    <div class="th">
      <div class="dot" style="background:#ef4444"></div>
      <div class="dot" style="background:#f59e0b"></div>
      <div class="dot" style="background:#10b981"></div>
      <span style="font-size:11px;color:var(--mut);margin-left:8px" id="log-ttl">Log</span>
    </div>
    <div class="tb" id="log-c">No log</div>
  </div>
</div>
<script>
const uid=new URLSearchParams(location.search).get('uid');
if(!uid){document.body.innerHTML='<div style="padding:40px;color:#ef4444;font-family:monospace">❌ No user ID. Open from Telegram bot.</div>'}
else{
  document.getElementById('uid-lbl').textContent='ID: '+uid;
  fetch('/api/portal/'+uid).then(r=>r.json()).then(d=>{
    if(d.error){document.getElementById('p-sub').textContent='❌ '+d.error;return}
    document.getElementById('p-name').textContent='Welcome, '+(d.full_name||'User');
    document.getElementById('p-sub').textContent='@'+(d.username||'unknown')+' · Joined '+new Date(d.join_date*1000).toLocaleDateString();
    document.getElementById('p-fc').textContent=(d.files||[]).length;
    document.getElementById('p-rc').textContent=(d.files||[]).filter(f=>f.running).length;
    document.getElementById('p-pl').textContent=(d.plan||'free').toUpperCase();
    const fl=document.getElementById('fl');
    if(!d.files||!d.files.length){fl.innerHTML='<div class="empty">📭 No files uploaded yet</div>';return}
    fl.innerHTML=d.files.map(f=>`<div class="fi">
      <div><div class="fn">📄 ${f.filename}</div><div class="fm">${(f.size_bytes/1024).toFixed(1)} KB · ${new Date(f.uploaded_at*1000).toLocaleString()}</div></div>
      <div style="display:flex;align-items:center;gap:8px">
        <span class="badge ${f.running?'b-ok':'b-mut'}">${f.running?'▶ Running':'■ Stopped'}</span>
        <button class="log-btn" onclick="viewLog('${f.filename}')">Log</button>
      </div>
    </div>`).join('');
  });
}
async function viewLog(fname){
  document.getElementById('log-box').style.display='block';
  document.getElementById('log-ttl').textContent=fname;
  document.getElementById('log-c').textContent='Loading...';
  const d=await fetch('/api/log?user_id='+uid+'&filename='+encodeURIComponent(fname)).then(r=>r.json());
  const el=document.getElementById('log-c');
  el.textContent=d.log||'No log found';
  el.scrollTop=el.scrollHeight;
}
</script>
</body></html>"""

# ── Routes ────────────────────────────────────────────────────────────────────
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
        if request.form.get("username","") == get_web_username() and request.form.get("password","") == get_web_password():
            session["admin"] = True
            return redirect("/admin")
        err = '<div style="background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.3);border-radius:8px;padding:10px 14px;color:#ef4444;font-size:12px;margin-bottom:18px">❌ Invalid username or password</div>'
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

# ── API ───────────────────────────────────────────────────────────────────────
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
    conn = database.get_conn()
    rows = conn.execute("SELECT user_id,action,detail,timestamp FROM activity_logs ORDER BY timestamp DESC LIMIT 30").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@flask_app.route("/api/users")
@require_admin
def api_users():
    users = get_all_users()
    for u in users:
        u["file_count"] = len(list_user_files(u["user_id"]))
    return jsonify(users)

@flask_app.route("/api/user/<int:uid>")
@require_admin
def api_user_detail(uid):
    user = get_user(uid)
    if not user:
        return jsonify({"error": "Not found"}), 404
    files = []
    for fname in list_user_files(uid):
        fp = os.path.join(config.USERS_DIR, str(uid), fname)
        files.append({
            "filename": fname,
            "size_bytes": os.path.getsize(fp) if os.path.exists(fp) else 0,
            "uploaded_at": os.path.getmtime(fp) if os.path.exists(fp) else 0,
            "running": is_running(uid, fname),
        })
    user["files"] = files
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
        uid = u["user_id"]
        for fname in list_user_files(uid):
            fp = os.path.join(config.USERS_DIR, str(uid), fname)
            result.append({
                "user_id": uid, "filename": fname,
                "size_bytes": os.path.getsize(fp) if os.path.exists(fp) else 0,
                "uploaded_at": os.path.getmtime(fp) if os.path.exists(fp) else 0,
                "running": is_running(uid, fname),
            })
    return jsonify(result)

@flask_app.route("/api/processes")
@require_admin
def api_processes():
    result = []
    for (uid, fname), info in get_all_processes().items():
        pi = get_process_info(uid, fname) or {}
        result.append({"user_id": uid, "filename": fname, "pid": info.get("pid"),
                        "started_at": info.get("started_at", 0),
                        "cpu_percent": pi.get("cpu_percent", 0),
                        "memory_mb": pi.get("memory_mb", 0)})
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
@require_admin
def api_log():
    uid = request.args.get("user_id")
    fname = request.args.get("filename")
    if not uid or not fname:
        return jsonify({"log": "Missing params"})
    return jsonify({"log": read_log(int(uid), fname, last_n=200)})

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
    elif action == "stop_all":        stop_all_scripts(); return jsonify({"msg":"💀 All scripts stopped"})
    return jsonify({"msg":"Unknown"})

@flask_app.route("/api/portal/<int:uid>")
def api_portal(uid):
    user = get_user(uid)
    if not user:
        return jsonify({"error": "User not found"})
    files = []
    for fname in list_user_files(uid):
        fp = os.path.join(config.USERS_DIR, str(uid), fname)
        files.append({
            "filename": fname,
            "size_bytes": os.path.getsize(fp) if os.path.exists(fp) else 0,
            "uploaded_at": os.path.getmtime(fp) if os.path.exists(fp) else 0,
            "running": is_running(uid, fname),
        })
    user["files"] = files
    return jsonify(user)
