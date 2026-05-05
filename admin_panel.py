import subprocess
import os
import time
import threading
from database import (
    get_all_users, ban_user, set_premium, remove_premium,
    get_setting, set_setting, get_global_stats, get_user,
)
from process_manager import (
    get_all_processes, stop_all_scripts, get_system_stats,
    get_total_process_count, kill_zombie_processes,
)
from log_manager import clear_all_logs, get_all_log_files
from file_manager import reset_user_files, get_user_dir
from config import ADMIN_IDS

def is_admin(user_id):
    return user_id in ADMIN_IDS

def is_maintenance():
    return get_setting("maintenance") == "1"

def set_maintenance(enabled: bool):
    set_setting("maintenance", "1" if enabled else "0")

def broadcast(bot, message_text, exclude_ids=None):
    if exclude_ids is None:
        exclude_ids = []
    users = get_all_users()
    success, fail = 0, 0
    for user in users:
        uid = user["user_id"]
        if uid in exclude_ids or user["is_banned"]:
            continue
        try:
            bot.send_message(uid, message_text)
            success += 1
            time.sleep(0.05)
        except Exception:
            fail += 1
    return success, fail

def run_shell_command(command, timeout=30):
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True,
            text=True, timeout=timeout
        )
        output = result.stdout + result.stderr
        return output[:3000] if output else "(no output)"
    except subprocess.TimeoutExpired:
        return "❌ Command timed out"
    except Exception as e:
        return f"❌ Error: {e}"

def build_admin_stats():
    db_stats = get_global_stats()
    sys_stats = get_system_stats()
    total_procs = get_total_process_count()
    zombie_count = len(kill_zombie_processes())
    uptime_seconds = time.time() - _start_time
    uptime_str = _format_uptime(uptime_seconds)
    all_procs = get_all_processes()
    log_files = get_all_log_files()
    total_log_size = sum(lf["size_kb"] for lf in log_files)

    text = (
        f"📊 <b>GLOBAL STATISTICS</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Total Users: <b>{db_stats['total_users']}</b>\n"
        f"💎 Premium Users: <b>{db_stats['premium_users']}</b>\n"
        f"🆓 Free Users: <b>{db_stats['total_users'] - db_stats['premium_users']}</b>\n"
        f"🚫 Banned Users: <b>{db_stats['banned_users']}</b>\n"
        f"📁 Total Files: <b>{db_stats['total_files']}</b>\n"
        f"⚙️ Running Processes: <b>{total_procs}</b>\n"
        f"🕷️ Zombie Cleaned: <b>{zombie_count}</b>\n"
        f"📜 Log Files: <b>{len(log_files)}</b> ({total_log_size:.1f} KB)\n"
        f"⏱️ Bot Uptime: <b>{uptime_str}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🖥️ <b>SYSTEM</b>\n"
        f"💻 CPU: <b>{sys_stats['cpu_percent']}%</b>\n"
        f"🧠 RAM: <b>{sys_stats['ram_used_mb']:.0f}/{sys_stats['ram_total_mb']:.0f} MB</b> ({sys_stats['ram_percent']}%)\n"
        f"💾 Disk: <b>{sys_stats['disk_used_gb']:.1f}/{sys_stats['disk_total_gb']:.1f} GB</b> ({sys_stats['disk_percent']}%)\n"
    )
    return text

def build_user_detail(user_id):
    user = get_user(user_id)
    if not user:
        return "❌ User not found"
    join_dt = time.strftime("%Y-%m-%d %H:%M", time.localtime(user["join_date"])) if user.get("join_date") else "N/A"
    last_dt = time.strftime("%Y-%m-%d %H:%M", time.localtime(user["last_active"])) if user.get("last_active") else "N/A"
    expiry_str = "N/A"
    if user.get("premium_expiry") and user["premium_expiry"] > 0:
        expiry_str = time.strftime("%Y-%m-%d", time.localtime(user["premium_expiry"]))
    text = (
        f"👤 <b>User Detail</b>\n"
        f"ID: <code>{user['user_id']}</code>\n"
        f"Username: @{user.get('username','N/A')}\n"
        f"Name: {user.get('full_name','N/A')}\n"
        f"Plan: {'💎 Premium' if user['plan']=='premium' else '🆓 Free'}\n"
        f"Banned: {'🚫 Yes' if user['is_banned'] else '✅ No'}\n"
        f"Joined: {join_dt}\n"
        f"Last Active: {last_dt}\n"
        f"Premium Expires: {expiry_str}\n"
    )
    return text

def _format_uptime(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}h {m}m {s}s"

_start_time = time.time()

def reset_start_time():
    global _start_time
    _start_time = time.time()

def get_bot_uptime():
    return _format_uptime(time.time() - _start_time)
