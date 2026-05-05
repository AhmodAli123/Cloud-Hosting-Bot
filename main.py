import os
import sys
import time
import threading
import zipfile
import tempfile
from datetime import datetime, timedelta
import telebot
from telebot.types import Message, CallbackQuery
from flask import Flask

import config
from config import BOT_TOKEN, ADMIN_IDS, FLASK_PORT
from database import (
    register_user, update_last_active, get_user, get_all_users,
    ban_user, set_premium, remove_premium, check_premium_expiry,
    get_global_stats, log_activity, get_setting, set_setting,
)
from file_manager import (
    save_file, delete_file, list_user_files, read_file, write_file,
    get_user_storage_info, reset_user_files,
)
from process_manager import (
    run_script, stop_script, stop_all_user_scripts, get_user_processes,
    is_running, get_system_stats, get_process_info, kill_zombie_processes,
)
from dependency_manager import (
    auto_install_for_file, retry_install_and_run, auto_fix_missing_module,
)
from log_manager import read_log, clear_log, clear_user_logs, clear_all_logs, detect_error_in_log
from admin_panel import (
    is_admin, is_maintenance, set_maintenance, broadcast,
    run_shell_command, build_admin_stats, build_user_detail, get_bot_uptime,
    reset_start_time,
)
from keyboards import (
    main_menu_keyboard, admin_panel_keyboard, file_list_keyboard,
    file_action_keyboard, process_list_keyboard, confirm_keyboard,
    log_view_keyboard, user_list_keyboard, remove_keyboard,
)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

_pending_actions = {}

def _require_user(message: Message):
    user = message.from_user
    register_user(user.id, user.username or "", user.first_name or "")
    update_last_active(user.id)
    db_user = get_user(user.id)
    if db_user and db_user["is_banned"]:
        bot.reply_to(message, "🚫 You are banned from using this bot.")
        return None
    if is_maintenance() and not is_admin(user.id):
        bot.reply_to(message, "🔒 Bot is under maintenance. Please try again later.")
        return None
    return db_user

def _safe_send(chat_id, text, **kwargs):
    try:
        MAX = 4096
        for i in range(0, len(text), MAX):
            bot.send_message(chat_id, text[i:i+MAX], **kwargs)
    except Exception as e:
        try:
            bot.send_message(chat_id, f"❌ Send error: {e}")
        except Exception:
            pass

def _format_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024**2:
        return f"{size_bytes/1024:.1f} KB"
    return f"{size_bytes/(1024**2):.2f} MB"

@bot.message_handler(commands=["start"])
def cmd_start(message: Message):
    db_user = _require_user(message)
    if not db_user:
        return
    name = message.from_user.first_name or "User"
    plan = db_user.get("plan", "free")
    plan_icon = "💎" if plan == "premium" else "🆓"
    text = (
        f"🚀 <b>Welcome to Cloud Hosting Bot!</b>\n\n"
        f"Hello, <b>{name}</b>! {plan_icon} Plan: <b>{plan.capitalize()}</b>\n\n"
        f"Upload your Python or Node.js scripts and run them 24/7!\n\n"
        f"📋 <b>Quick Start:</b>\n"
        f"1️⃣ Upload a <code>.py</code> or <code>.js</code> file\n"
        f"2️⃣ Click ▶️ Run to start it\n"
        f"3️⃣ View logs anytime with 📜 Logs\n\n"
        f"Use the menu below to get started 👇"
    )
    bot.send_message(message.chat.id, text, reply_markup=main_menu_keyboard(is_admin(message.from_user.id)))
    log_activity(message.from_user.id, "start")

@bot.message_handler(commands=["help"])
def cmd_help(message: Message):
    db_user = _require_user(message)
    if not db_user:
        return
    text = (
        "❓ <b>HELP — Cloud Hosting Bot</b>\n\n"
        "📁 <b>File Commands:</b>\n"
        "• Upload .py / .js / .zip file → auto-saved\n"
        "• <code>/myfiles</code> — list your files\n"
        "• <code>/delete &lt;filename&gt;</code> — delete a file\n\n"
        "⚙️ <b>Run Commands:</b>\n"
        "• <code>/run &lt;filename&gt;</code> — run script\n"
        "• <code>/stop &lt;filename&gt;</code> — stop script\n"
        "• <code>/stopall</code> — stop all running scripts\n"
        "• <code>/processes</code> — list running scripts\n\n"
        "📜 <b>Log Commands:</b>\n"
        "• <code>/log &lt;filename&gt;</code> — view log (last 50 lines)\n"
        "• <code>/clearlog &lt;filename&gt;</code> — clear a log\n\n"
        "📊 <b>Info Commands:</b>\n"
        "• <code>/stats</code> — your stats\n"
        "• <code>/status</code> — bot & system status\n"
        "• <code>/ping</code> — latency check\n\n"
        "🔐 <b>Admin Commands:</b>\n"
        "• <code>/admin</code> — open admin panel\n"
        "• <code>/addpremium &lt;user_id&gt; [days]</code>\n"
        "• <code>/removepremium &lt;user_id&gt;</code>\n"
        "• <code>/ban &lt;user_id&gt;</code> / <code>/unban &lt;user_id&gt;</code>\n"
        "• <code>/broadcast &lt;msg&gt;</code>\n"
        "• <code>/shell &lt;cmd&gt;</code> — run terminal command\n"
        "• <code>/maintenance on|off</code>\n"
        "• <code>/clearlogs</code> — clear all logs\n"
    )
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=["ping"])
def cmd_ping(message: Message):
    start = time.time()
    msg = bot.reply_to(message, "🏓 Pong!")
    latency = (time.time() - start) * 1000
    bot.edit_message_text(
        f"🏓 Pong! Latency: <b>{latency:.1f}ms</b>",
        message.chat.id, msg.message_id
    )

@bot.message_handler(commands=["status"])
def cmd_status(message: Message):
    db_user = _require_user(message)
    if not db_user:
        return
    sys_stats = get_system_stats()
    uptime = get_bot_uptime()
    maintenance_str = "🔒 Maintenance Mode" if is_maintenance() else "🟢 Operational"
    text = (
        f"📡 <b>BOT STATUS</b>\n"
        f"Status: {maintenance_str}\n"
        f"⏱️ Uptime: <b>{uptime}</b>\n\n"
        f"🖥️ <b>SYSTEM</b>\n"
        f"💻 CPU: <b>{sys_stats['cpu_percent']}%</b>\n"
        f"🧠 RAM: <b>{sys_stats['ram_used_mb']:.0f}/{sys_stats['ram_total_mb']:.0f} MB</b> ({sys_stats['ram_percent']}%)\n"
        f"💾 Disk: <b>{sys_stats['disk_used_gb']:.1f}/{sys_stats['disk_total_gb']:.1f} GB</b>\n"
    )
    bot.reply_to(message, text)

@bot.message_handler(commands=["stats"])
def cmd_stats(message: Message):
    db_user = _require_user(message)
    if not db_user:
        return
    uid = message.from_user.id
    files = list_user_files(uid)
    procs = get_user_processes(uid)
    used_mb, limit_mb = get_user_storage_info(uid, db_user["plan"])
    plan = db_user.get("plan", "free")
    premium_expiry = db_user.get("premium_expiry", 0)
    expiry_str = "N/A"
    if plan == "premium" and premium_expiry:
        expiry_str = time.strftime("%Y-%m-%d", time.localtime(premium_expiry))
    join_dt = time.strftime("%Y-%m-%d", time.localtime(db_user.get("join_date", time.time())))
    text = (
        f"📊 <b>YOUR STATS</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🆔 ID: <code>{uid}</code>\n"
        f"📅 Joined: {join_dt}\n"
        f"{'💎' if plan=='premium' else '🆓'} Plan: <b>{plan.capitalize()}</b>\n"
        f"⏰ Plan Expires: {expiry_str}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📁 Files: <b>{len(files)}</b>\n"
        f"💾 Storage: <b>{used_mb:.2f}/{limit_mb} MB</b>\n"
        f"⚙️ Running Processes: <b>{len(procs)}</b>\n"
    )
    bot.reply_to(message, text)

@bot.message_handler(commands=["myfiles"])
def cmd_myfiles(message: Message):
    db_user = _require_user(message)
    if not db_user:
        return
    uid = message.from_user.id
    files = list_user_files(uid)
    if not files:
        bot.reply_to(message, "📭 You have no uploaded files.")
        return
    procs = get_user_processes(uid)
    running_set = set(procs.keys())
    markup = file_list_keyboard(files, running_set)
    bot.send_message(message.chat.id, f"📁 <b>Your Files</b> ({len(files)} total):", reply_markup=markup)

@bot.message_handler(commands=["processes"])
def cmd_processes(message: Message):
    db_user = _require_user(message)
    if not db_user:
        return
    uid = message.from_user.id
    procs = get_user_processes(uid)
    if not procs:
        bot.reply_to(message, "⚙️ No running processes.")
        return
    markup = process_list_keyboard(procs)
    bot.send_message(message.chat.id, f"⚙️ <b>Running Processes</b> ({len(procs)}):", reply_markup=markup)

@bot.message_handler(commands=["run"])
def cmd_run(message: Message):
    db_user = _require_user(message)
    if not db_user:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /run <filename>")
        return
    filename = parts[1].strip()
    uid = message.from_user.id
    ok, msg = run_script(uid, filename, db_user.get("plan", "free"))
    bot.reply_to(message, msg)

@bot.message_handler(commands=["stop"])
def cmd_stop(message: Message):
    db_user = _require_user(message)
    if not db_user:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /stop <filename>")
        return
    filename = parts[1].strip()
    ok, msg = stop_script(message.from_user.id, filename)
    bot.reply_to(message, msg)

@bot.message_handler(commands=["stopall"])
def cmd_stopall(message: Message):
    db_user = _require_user(message)
    if not db_user:
        return
    stopped = stop_all_user_scripts(message.from_user.id)
    if stopped:
        bot.reply_to(message, f"🛑 Stopped: {', '.join(stopped)}")
    else:
        bot.reply_to(message, "⚙️ No running processes.")

@bot.message_handler(commands=["log"])
def cmd_log(message: Message):
    db_user = _require_user(message)
    if not db_user:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /log <filename>")
        return
    filename = parts[1].strip()
    uid = message.from_user.id
    log_content = read_log(uid, filename, last_n=50)
    error = detect_error_in_log(uid, filename)
    text = f"📜 <b>Log: {filename}</b>\n<pre>{log_content[-3000:]}</pre>"
    if error:
        text += f"\n\n⚠️ <b>Error Detected:</b>\n<pre>{error[:500]}</pre>"
    markup = log_view_keyboard(filename)
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.message_handler(commands=["clearlog"])
def cmd_clearlog(message: Message):
    db_user = _require_user(message)
    if not db_user:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /clearlog <filename>")
        return
    filename = parts[1].strip()
    clear_log(message.from_user.id, filename)
    bot.reply_to(message, f"🗑️ Log cleared for `{filename}`")

@bot.message_handler(commands=["delete"])
def cmd_delete(message: Message):
    db_user = _require_user(message)
    if not db_user:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /delete <filename>")
        return
    filename = parts[1].strip()
    uid = message.from_user.id
    if is_running(uid, filename):
        stop_script(uid, filename)
    ok, msg = delete_file(uid, filename)
    bot.reply_to(message, msg)

@bot.message_handler(commands=["admin"])
def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "🚫 Admin only.")
        return
    text = f"🔐 <b>ADMIN PANEL</b>\nBot Uptime: {get_bot_uptime()}\nMaintenance: {'🔒 ON' if is_maintenance() else '🟢 OFF'}"
    bot.send_message(message.chat.id, text, reply_markup=admin_panel_keyboard())

@bot.message_handler(commands=["addpremium"])
def cmd_addpremium(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "🚫 Admin only.")
        return
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /addpremium <user_id> [days]")
        return
    try:
        target_id = int(parts[1])
        days = int(parts[2]) if len(parts) > 2 else 30
        set_premium(target_id, days)
        bot.reply_to(message, f"💎 Premium added to <code>{target_id}</code> for {days} days.")
        try:
            bot.send_message(target_id, f"🎉 You've been upgraded to <b>Premium</b> for {days} days!")
        except Exception:
            pass
    except ValueError:
        bot.reply_to(message, "❌ Invalid user ID or days.")

@bot.message_handler(commands=["removepremium"])
def cmd_removepremium(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "🚫 Admin only.")
        return
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /removepremium <user_id>")
        return
    try:
        target_id = int(parts[1])
        remove_premium(target_id)
        bot.reply_to(message, f"🆓 Premium removed from <code>{target_id}</code>.")
        try:
            bot.send_message(target_id, "⚠️ Your premium subscription has ended.")
        except Exception:
            pass
    except ValueError:
        bot.reply_to(message, "❌ Invalid user ID.")

@bot.message_handler(commands=["ban"])
def cmd_ban(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "🚫 Admin only.")
        return
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /ban <user_id>")
        return
    try:
        target_id = int(parts[1])
        ban_user(target_id, True)
        stop_all_user_scripts(target_id)
        bot.reply_to(message, f"🚫 User <code>{target_id}</code> has been banned.")
    except ValueError:
        bot.reply_to(message, "❌ Invalid user ID.")

@bot.message_handler(commands=["unban"])
def cmd_unban(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "🚫 Admin only.")
        return
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /unban <user_id>")
        return
    try:
        target_id = int(parts[1])
        ban_user(target_id, False)
        bot.reply_to(message, f"✅ User <code>{target_id}</code> has been unbanned.")
        try:
            bot.send_message(target_id, "✅ You have been unbanned. You can use the bot again.")
        except Exception:
            pass
    except ValueError:
        bot.reply_to(message, "❌ Invalid user ID.")

@bot.message_handler(commands=["broadcast"])
def cmd_broadcast(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "🚫 Admin only.")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /broadcast <message>")
        return
    text = parts[1]
    msg = bot.reply_to(message, "📢 Broadcasting...")
    success, fail = broadcast(bot, f"📢 <b>Broadcast Message:</b>\n\n{text}", exclude_ids=[message.from_user.id])
    bot.edit_message_text(
        f"📢 Broadcast done!\n✅ Sent: {success}\n❌ Failed: {fail}",
        message.chat.id, msg.message_id
    )

@bot.message_handler(commands=["shell"])
def cmd_shell(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "🚫 Admin only.")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /shell <command>")
        return
    cmd = parts[1]
    msg = bot.reply_to(message, "🖥️ Running...")
    output = run_shell_command(cmd)
    bot.edit_message_text(
        f"🖥️ <b>$ {cmd}</b>\n<pre>{output}</pre>",
        message.chat.id, msg.message_id
    )

@bot.message_handler(commands=["maintenance"])
def cmd_maintenance(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "🚫 Admin only.")
        return
    parts = message.text.split()
    if len(parts) < 2 or parts[1] not in ("on", "off"):
        bot.reply_to(message, "Usage: /maintenance on|off")
        return
    enabled = parts[1] == "on"
    set_maintenance(enabled)
    bot.reply_to(message, f"🔒 Maintenance mode {'enabled' if enabled else 'disabled'}.")

@bot.message_handler(commands=["clearlogs"])
def cmd_clearlogs(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "🚫 Admin only.")
        return
    count = clear_all_logs()
    bot.reply_to(message, f"🧹 Cleared {count} log files.")

@bot.message_handler(commands=["globalstats"])
def cmd_globalstats(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "🚫 Admin only.")
        return
    text = build_admin_stats()
    bot.reply_to(message, text)

@bot.message_handler(content_types=["document"])
def handle_document(message: Message):
    db_user = _require_user(message)
    if not db_user:
        return
    doc = message.document
    filename = doc.file_name or "upload"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in {".py", ".js", ".zip"}:
        bot.reply_to(message, "❌ Only .py, .js, and .zip files are supported.")
        return
    msg = bot.reply_to(message, f"⬇️ Downloading `{filename}`...")
    try:
        file_info = bot.get_file(doc.file_id)
        file_bytes = bot.download_file(file_info.file_path)
    except Exception as e:
        bot.edit_message_text(f"❌ Download failed: {e}", message.chat.id, msg.message_id)
        return
    uid = message.from_user.id
    ok, result = save_file(uid, filename, file_bytes, db_user.get("plan", "free"))
    log_activity(uid, "upload", filename)
    if ok:
        markup = file_action_keyboard(filename, is_running(uid, filename))
        bot.edit_message_text(
            f"✅ {result}\n\nWhat do you want to do with <code>{filename}</code>?",
            message.chat.id, msg.message_id, reply_markup=markup
        )
    else:
        bot.edit_message_text(result, message.chat.id, msg.message_id)

@bot.message_handler(func=lambda m: m.text == "📁 My Files")
def menu_myfiles(message: Message):
    cmd_myfiles(message)

@bot.message_handler(func=lambda m: m.text == "⚙️ My Processes")
def menu_processes(message: Message):
    cmd_processes(message)

@bot.message_handler(func=lambda m: m.text == "📤 Upload File")
def menu_upload(message: Message):
    db_user = _require_user(message)
    if not db_user:
        return
    bot.reply_to(message, "📤 Send your <b>.py</b>, <b>.js</b>, or <b>.zip</b> file now:")

@bot.message_handler(func=lambda m: m.text == "📊 My Stats")
def menu_stats(message: Message):
    cmd_stats(message)

@bot.message_handler(func=lambda m: m.text == "📜 Logs")
def menu_logs(message: Message):
    db_user = _require_user(message)
    if not db_user:
        return
    uid = message.from_user.id
    files = list_user_files(uid)
    if not files:
        bot.reply_to(message, "📭 No files found.")
        return
    text = "📜 <b>Select a file to view logs:</b>"
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    markup = InlineKeyboardMarkup(row_width=1)
    for f in files[:10]:
        fname = f["filename"]
        markup.add(InlineKeyboardButton(fname, callback_data=f"viewlog:{fname}"))
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "ℹ️ Status")
def menu_status(message: Message):
    cmd_status(message)

@bot.message_handler(func=lambda m: m.text == "🔐 Admin Panel")
def menu_admin(message: Message):
    cmd_admin(message)

@bot.message_handler(func=lambda m: m.text == "❓ Help")
def menu_help(message: Message):
    cmd_help(message)

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call: CallbackQuery):
    uid = call.from_user.id
    data = call.data
    db_user = get_user(uid)
    if not db_user:
        bot.answer_callback_query(call.id, "Please /start first")
        return
    if db_user["is_banned"] and not is_admin(uid):
        bot.answer_callback_query(call.id, "🚫 You are banned")
        return
    plan = db_user.get("plan", "free")

    try:
        if data == "back_main":
            bot.answer_callback_query(call.id)
            bot.send_message(uid, "🏠 Main Menu", reply_markup=main_menu_keyboard(is_admin(uid)))

        elif data == "back_files":
            bot.answer_callback_query(call.id)
            files = list_user_files(uid)
            procs = get_user_processes(uid)
            running_set = set(procs.keys())
            markup = file_list_keyboard(files, running_set)
            bot.edit_message_text(f"📁 <b>Your Files</b> ({len(files)} total):", call.message.chat.id, call.message.message_id, reply_markup=markup)

        elif data.startswith("files_page:"):
            page = int(data.split(":")[1])
            files = list_user_files(uid)
            procs = get_user_processes(uid)
            running_set = set(procs.keys())
            markup = file_list_keyboard(files, running_set, page=page)
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
            bot.answer_callback_query(call.id)

        elif data.startswith("file_menu:"):
            filename = data.split(":", 1)[1]
            running = is_running(uid, filename)
            markup = file_action_keyboard(filename, running)
            status = "🟢 Running" if running else "🔴 Stopped"
            bot.edit_message_text(
                f"📄 <b>{filename}</b>\nStatus: {status}",
                call.message.chat.id, call.message.message_id, reply_markup=markup
            )
            bot.answer_callback_query(call.id)

        elif data.startswith("run:"):
            filename = data.split(":", 1)[1]
            bot.answer_callback_query(call.id, "▶️ Starting...")
            ok, msg = run_script(uid, filename, plan)
            markup = file_action_keyboard(filename, ok)
            bot.edit_message_text(
                f"📄 <b>{filename}</b>\n{msg}",
                call.message.chat.id, call.message.message_id, reply_markup=markup
            )
            log_activity(uid, "run", filename)

        elif data.startswith("retryrun:"):
            filename = data.split(":", 1)[1]
            bot.answer_callback_query(call.id, "🔁 Retrying...")

            def _retry():
                import process_manager as pm
                ok, msg = retry_install_and_run(uid, filename, plan, pm)
                try:
                    bot.send_message(uid, f"🔁 <b>Retry Result:</b> {msg}")
                except Exception:
                    pass
            threading.Thread(target=_retry, daemon=True).start()

        elif data.startswith("autorestart:"):
            filename = data.split(":", 1)[1]
            stop_script(uid, filename)
            ok, msg = run_script(uid, filename, plan, auto_restart=True)
            bot.answer_callback_query(call.id, "🔁 Auto-restart enabled")
            markup = file_action_keyboard(filename, ok)
            bot.edit_message_text(
                f"📄 <b>{filename}</b>\n{msg}\n♻️ Auto-restart: ON",
                call.message.chat.id, call.message.message_id, reply_markup=markup
            )

        elif data.startswith("stop:"):
            filename = data.split(":", 1)[1]
            ok, msg = stop_script(uid, filename)
            bot.answer_callback_query(call.id, "🛑 Stopped")
            markup = file_action_keyboard(filename, False)
            bot.edit_message_text(
                f"📄 <b>{filename}</b>\n{msg}",
                call.message.chat.id, call.message.message_id, reply_markup=markup
            )
            log_activity(uid, "stop", filename)

        elif data == "stop_all_procs":
            stopped = stop_all_user_scripts(uid)
            bot.answer_callback_query(call.id, f"🛑 Stopped {len(stopped)}")
            bot.edit_message_text(
                f"🛑 Stopped {len(stopped)} process(es): {', '.join(stopped) if stopped else 'none'}",
                call.message.chat.id, call.message.message_id
            )

        elif data.startswith("viewlog:"):
            parts = data.split(":")
            filename = parts[1]
            bot.answer_callback_query(call.id, "📜 Loading log...")
            log_content = read_log(uid, filename, last_n=50)
            error = detect_error_in_log(uid, filename)
            text = f"📜 <b>Log: {filename}</b>\n<pre>{log_content[-3000:]}</pre>"
            if error:
                text += f"\n\n⚠️ <b>Error:</b>\n<pre>{error[:300]}</pre>"
            markup = log_view_keyboard(filename)
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

        elif data.startswith("clearlog:"):
            filename = data.split(":", 1)[1]
            clear_log(uid, filename)
            bot.answer_callback_query(call.id, "🗑️ Log cleared")
            markup = log_view_keyboard(filename)
            bot.edit_message_text(f"🗑️ Log for <code>{filename}</code> cleared.", call.message.chat.id, call.message.message_id, reply_markup=markup)

        elif data.startswith("delete:"):
            filename = data.split(":", 1)[1]
            if is_running(uid, filename):
                stop_script(uid, filename)
            ok, msg = delete_file(uid, filename)
            bot.answer_callback_query(call.id, "🗑️ Deleted")
            files = list_user_files(uid)
            if files:
                procs = get_user_processes(uid)
                markup = file_list_keyboard(files, set(procs.keys()))
                bot.edit_message_text(f"{msg}\n\n📁 <b>Your Files</b> ({len(files)} total):", call.message.chat.id, call.message.message_id, reply_markup=markup)
            else:
                bot.edit_message_text(f"{msg}\n\n📭 No files remaining.", call.message.chat.id, call.message.message_id)
            log_activity(uid, "delete", filename)

        elif data.startswith("edit:"):
            filename = data.split(":", 1)[1]
            content = read_file(uid, filename)
            if content is None:
                bot.answer_callback_query(call.id, "❌ File not found")
                return
            _pending_actions[uid] = {"action": "edit_file", "filename": filename}
            bot.answer_callback_query(call.id)
            bot.send_message(
                uid,
                f"✏️ <b>Editing: {filename}</b>\n\nCurrent content:\n<pre>{content[:2000]}</pre>\n\nSend the new content now:",
                reply_markup=remove_keyboard()
            )

        elif data.startswith("proc_menu:"):
            filename = data.split(":", 1)[1]
            info = get_process_info(uid, filename)
            if info:
                text = (
                    f"⚙️ <b>Process: {filename}</b>\n"
                    f"PID: <code>{info.get('pid')}</code>\n"
                    f"Status: {info.get('status', 'N/A')}\n"
                    f"CPU: {info.get('cpu_percent', 0):.1f}%\n"
                    f"RAM: {info.get('memory_mb', 0):.1f} MB\n"
                    f"Running since: {time.strftime('%H:%M:%S', time.localtime(info.get('started_at', 0)))}\n"
                )
            else:
                text = f"⚙️ <b>Process: {filename}</b>\nStatus: Stopped"
            from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
            markup = InlineKeyboardMarkup(row_width=2)
            markup.add(
                InlineKeyboardButton("🛑 Stop", callback_data=f"stop:{filename}"),
                InlineKeyboardButton("📜 Log", callback_data=f"viewlog:{filename}"),
                InlineKeyboardButton("🔙 Back", callback_data="back_main"),
            )
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
            bot.answer_callback_query(call.id)

        elif data == "admin_stats":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "🚫 Admin only")
                return
            text = build_admin_stats()
            from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🔙 Admin Panel", callback_data="back_admin"))
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
            bot.answer_callback_query(call.id)

        elif data == "back_admin":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "🚫 Admin only")
                return
            bot.edit_message_text(
                f"🔐 <b>ADMIN PANEL</b>\nBot Uptime: {get_bot_uptime()}",
                call.message.chat.id, call.message.message_id,
                reply_markup=admin_panel_keyboard()
            )
            bot.answer_callback_query(call.id)

        elif data == "admin_users":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "🚫 Admin only")
                return
            users = get_all_users()
            markup = user_list_keyboard(users)
            bot.edit_message_text(
                f"👥 <b>All Users</b> ({len(users)} total):",
                call.message.chat.id, call.message.message_id, reply_markup=markup
            )
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_users_page:"):
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "🚫 Admin only")
                return
            page = int(data.split(":")[1])
            users = get_all_users()
            markup = user_list_keyboard(users, page=page)
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_user_detail:"):
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "🚫 Admin only")
                return
            target_id = int(data.split(":")[1])
            text = build_user_detail(target_id)
            from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
            markup = InlineKeyboardMarkup(row_width=2)
            markup.add(
                InlineKeyboardButton("💎 Add Premium", callback_data=f"confirm:add_premium:{target_id}"),
                InlineKeyboardButton("🆓 Remove Premium", callback_data=f"confirm:remove_premium:{target_id}"),
                InlineKeyboardButton("🚫 Ban", callback_data=f"confirm:ban:{target_id}"),
                InlineKeyboardButton("✅ Unban", callback_data=f"confirm:unban:{target_id}"),
                InlineKeyboardButton("🗑️ Reset Files", callback_data=f"confirm:reset_files:{target_id}"),
                InlineKeyboardButton("🔙 Back", callback_data="admin_users"),
            )
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
            bot.answer_callback_query(call.id)

        elif data.startswith("confirm:"):
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "🚫 Admin only")
                return
            _, action, target_id_str = data.split(":", 2)
            target_id = int(target_id_str)
            if action == "add_premium":
                set_premium(target_id, 30)
                bot.answer_callback_query(call.id, "💎 Premium added (30 days)")
                try:
                    bot.send_message(target_id, "🎉 You've been upgraded to <b>Premium</b> for 30 days!")
                except Exception:
                    pass
            elif action == "remove_premium":
                remove_premium(target_id)
                bot.answer_callback_query(call.id, "🆓 Premium removed")
                try:
                    bot.send_message(target_id, "⚠️ Your premium subscription has ended.")
                except Exception:
                    pass
            elif action == "ban":
                ban_user(target_id, True)
                stop_all_user_scripts(target_id)
                bot.answer_callback_query(call.id, "🚫 User banned")
            elif action == "unban":
                ban_user(target_id, False)
                bot.answer_callback_query(call.id, "✅ User unbanned")
                try:
                    bot.send_message(target_id, "✅ You have been unbanned!")
                except Exception:
                    pass
            elif action == "reset_files":
                stop_all_user_scripts(target_id)
                count = reset_user_files(target_id)
                clear_user_logs(target_id)
                bot.answer_callback_query(call.id, f"🗑️ Deleted {count} files")
            text = build_user_detail(target_id)
            from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
            markup = InlineKeyboardMarkup(row_width=2)
            markup.add(
                InlineKeyboardButton("💎 Add Premium", callback_data=f"confirm:add_premium:{target_id}"),
                InlineKeyboardButton("🆓 Remove Premium", callback_data=f"confirm:remove_premium:{target_id}"),
                InlineKeyboardButton("🚫 Ban", callback_data=f"confirm:ban:{target_id}"),
                InlineKeyboardButton("✅ Unban", callback_data=f"confirm:unban:{target_id}"),
                InlineKeyboardButton("🗑️ Reset Files", callback_data=f"confirm:reset_files:{target_id}"),
                InlineKeyboardButton("🔙 Back", callback_data="admin_users"),
            )
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

        elif data == "admin_broadcast":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "🚫 Admin only")
                return
            _pending_actions[uid] = {"action": "broadcast"}
            bot.answer_callback_query(call.id)
            bot.send_message(uid, "📢 Send the broadcast message now:")

        elif data == "admin_shell":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "🚫 Admin only")
                return
            _pending_actions[uid] = {"action": "shell"}
            bot.answer_callback_query(call.id)
            bot.send_message(uid, "🖥️ Send the shell command to execute:")

        elif data == "admin_add_premium":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "🚫 Admin only")
                return
            _pending_actions[uid] = {"action": "add_premium_input"}
            bot.answer_callback_query(call.id)
            bot.send_message(uid, "💎 Send user ID to add premium (format: <code>user_id days</code>):")

        elif data == "admin_remove_premium":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "🚫 Admin only")
                return
            _pending_actions[uid] = {"action": "remove_premium_input"}
            bot.answer_callback_query(call.id)
            bot.send_message(uid, "🆓 Send user ID to remove premium:")

        elif data == "admin_ban":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "🚫 Admin only")
                return
            _pending_actions[uid] = {"action": "ban_input"}
            bot.answer_callback_query(call.id)
            bot.send_message(uid, "🚫 Send user ID to ban:")

        elif data == "admin_unban":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "🚫 Admin only")
                return
            _pending_actions[uid] = {"action": "unban_input"}
            bot.answer_callback_query(call.id)
            bot.send_message(uid, "✅ Send user ID to unban:")

        elif data == "admin_maintenance_on":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "🚫 Admin only")
                return
            set_maintenance(True)
            bot.answer_callback_query(call.id, "🔒 Maintenance ON")
            bot.edit_message_text("🔒 Maintenance mode enabled.", call.message.chat.id, call.message.message_id, reply_markup=admin_panel_keyboard())

        elif data == "admin_maintenance_off":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "🚫 Admin only")
                return
            set_maintenance(False)
            bot.answer_callback_query(call.id, "🟢 Maintenance OFF")
            bot.edit_message_text("🟢 Maintenance mode disabled.", call.message.chat.id, call.message.message_id, reply_markup=admin_panel_keyboard())

        elif data == "admin_clear_logs":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "🚫 Admin only")
                return
            count = clear_all_logs()
            bot.answer_callback_query(call.id, f"🧹 {count} logs cleared")
            bot.edit_message_text(f"🧹 Cleared {count} log files.", call.message.chat.id, call.message.message_id, reply_markup=admin_panel_keyboard())

        elif data == "admin_stop_all":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "🚫 Admin only")
                return
            stop_all_scripts()
            bot.answer_callback_query(call.id, "💀 All scripts stopped")
            bot.edit_message_text("💀 All running scripts stopped.", call.message.chat.id, call.message.message_id, reply_markup=admin_panel_keyboard())

        elif data == "admin_sysinfo":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "🚫 Admin only")
                return
            text = build_admin_stats()
            from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🔙 Back", callback_data="back_admin"))
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
            bot.answer_callback_query(call.id)

        elif data == "admin_restart":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "🚫 Admin only")
                return
            bot.answer_callback_query(call.id, "🔄 Restarting...")
            bot.send_message(uid, "🔄 Bot is restarting...")
            reset_start_time()
            os.execv(sys.executable, [sys.executable] + sys.argv)

        elif data == "cancel":
            _pending_actions.pop(uid, None)
            bot.answer_callback_query(call.id, "❌ Cancelled")

    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ Error: {str(e)[:50]}")
        try:
            bot.send_message(uid, f"❌ Callback error: {e}")
        except Exception:
            pass

@bot.message_handler(func=lambda m: m.from_user.id in _pending_actions)
def handle_pending_action(message: Message):
    uid = message.from_user.id
    action_data = _pending_actions.pop(uid, None)
    if not action_data:
        return
    action = action_data.get("action")

    if action == "edit_file":
        filename = action_data.get("filename")
        content = message.text
        ok, msg = write_file(uid, filename, content)
        bot.reply_to(message, msg)
        markup = file_action_keyboard(filename, is_running(uid, filename))
        bot.send_message(uid, f"📄 <b>{filename}</b>", reply_markup=markup)

    elif action == "broadcast":
        if not is_admin(uid):
            return
        text = message.text
        msg = bot.reply_to(message, "📢 Broadcasting...")
        success, fail = broadcast(bot, f"📢 <b>Broadcast:</b>\n\n{text}", exclude_ids=[uid])
        bot.edit_message_text(f"📢 Done! ✅ {success} sent, ❌ {fail} failed.", message.chat.id, msg.message_id)

    elif action == "shell":
        if not is_admin(uid):
            return
        cmd = message.text
        msg = bot.reply_to(message, "🖥️ Running...")
        output = run_shell_command(cmd)
        bot.edit_message_text(f"🖥️ <b>$ {cmd}</b>\n<pre>{output}</pre>", message.chat.id, msg.message_id)

    elif action == "add_premium_input":
        if not is_admin(uid):
            return
        parts = message.text.split()
        try:
            target_id = int(parts[0])
            days = int(parts[1]) if len(parts) > 1 else 30
            set_premium(target_id, days)
            bot.reply_to(message, f"💎 Premium added to <code>{target_id}</code> for {days} days.")
            try:
                bot.send_message(target_id, f"🎉 You've been upgraded to <b>Premium</b> for {days} days!")
            except Exception:
                pass
        except (ValueError, IndexError):
            bot.reply_to(message, "❌ Invalid format. Use: user_id [days]")

    elif action == "remove_premium_input":
        if not is_admin(uid):
            return
        try:
            target_id = int(message.text.strip())
            remove_premium(target_id)
            bot.reply_to(message, f"🆓 Premium removed from <code>{target_id}</code>.")
        except ValueError:
            bot.reply_to(message, "❌ Invalid user ID.")

    elif action == "ban_input":
        if not is_admin(uid):
            return
        try:
            target_id = int(message.text.strip())
            ban_user(target_id, True)
            stop_all_user_scripts(target_id)
            bot.reply_to(message, f"🚫 User <code>{target_id}</code> banned.")
        except ValueError:
            bot.reply_to(message, "❌ Invalid user ID.")

    elif action == "unban_input":
        if not is_admin(uid):
            return
        try:
            target_id = int(message.text.strip())
            ban_user(target_id, False)
            bot.reply_to(message, f"✅ User <code>{target_id}</code> unbanned.")
            try:
                bot.send_message(target_id, "✅ You have been unbanned!")
            except Exception:
                pass
        except ValueError:
            bot.reply_to(message, "❌ Invalid user ID.")

@bot.message_handler(commands=["setwebuser"])
def cmd_setwebuser(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /setwebuser <username>")
        return
    from database import set_setting
    set_setting("web_username", parts[1].strip())
    bot.reply_to(message, f"✅ Web username updated to: <code>{parts[1].strip()}</code>", parse_mode="HTML")

@bot.message_handler(commands=["setwebpass"])
def cmd_setwebpass(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /setwebpass <password>")
        return
    from database import set_setting
    set_setting("web_password", parts[1].strip())
    bot.reply_to(message, f"✅ Web password updated to: <code>{parts[1].strip()}</code>", parse_mode="HTML")

@bot.message_handler(commands=["webcreds"])
def cmd_webcreds(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    lines = [
        '🔐 <b>Web Panel Credentials</b>',
        '👤 Username: <code>' + get_web_username() + '</code>',
        '🔑 Password: <code>' + get_web_password() + '</code>',
        '🌐 URL: https://cloud-hosting-bot.onrender.com/admin'
    ]
    bot.reply_to(message, chr(10).join(lines), parse_mode='HTML')

def _background_tasks():
    while True:
        try:
            expired = check_premium_expiry()
            for uid in expired:
                try:
                    bot.send_message(uid, "⚠️ Your premium subscription has expired. You've been downgraded to free plan.")
                except Exception:
                    pass
            kill_zombie_processes()
        except Exception:
            pass
        time.sleep(3600)

from web_panel import flask_app, get_web_username, get_web_password

def run_flask():
    flask_app.run(host="0.0.0.0", port=FLASK_PORT, debug=False)

def send_daily_backup():
    try:
        backup_filename = f"backup_{datetime.now().strftime('%Y-%m-%d')}.zip"
        backup_path = os.path.join(tempfile.gettempdir(), backup_filename)

        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk("data"):
                for file in files:
                    file_path = os.path.join(root, file)
                    zipf.write(file_path)

        for admin_id in ADMIN_IDS:
            try:
                bot.send_message(admin_id, f"📦 <b>Daily Backup</b>\n📅 Date: <code>{datetime.now().strftime('%d %B %Y')}</code>\n✅ data/ folder attached below.")
                with open(backup_path, 'rb') as f:
                    bot.send_document(admin_id, f, visible_file_name=backup_filename)
            except Exception:
                pass

        os.remove(backup_path)
    except Exception as e:
        print(f"Backup error: {e}")

def run_daily_backup_scheduler():
    while True:
        now = datetime.now()
        next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        wait_seconds = (next_midnight - now).total_seconds()
        time.sleep(wait_seconds)
        send_daily_backup()

if __name__ == "__main__":
    print(f"🤖 Bot starting... Token: {BOT_TOKEN[:10]}...")
    print(f"🔐 Admin IDs: {ADMIN_IDS}")
    print(f"🌐 Keep-alive server on port {FLASK_PORT}")

    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=_background_tasks, daemon=True).start()
    threading.Thread(target=run_daily_backup_scheduler, daemon=True).start()
    print("📦 Daily backup scheduler started (sends at midnight)")

    print("✅ Bot is polling...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30, skip_pending=True)