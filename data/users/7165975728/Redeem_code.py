#!/usr/bin/env python3
"""
Telegram Referral Bot – Full Featured (telebot library)
Fixed Force Join Verification – Fully Working
"""

import os
import sqlite3
import time
import csv
import io
import shutil
from collections import defaultdict

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ------------------- CONFIGURATION -------------------
BOT_TOKEN = "8509477318:AAE7RAPsqz-SoTvcewF2h2STS54LI0TuyzI"
ADMIN_IDS = [7165975728]
DB_FILE = "bot.db"
FORCE_JOIN_ENABLED = True   # Force join on/off

bot = telebot.TeleBot(BOT_TOKEN, threaded=True)

# ------------------- DATABASE SETUP -------------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            referrer_id INTEGER DEFAULT NULL,
            referral_count INTEGER DEFAULT 0,
            last_rewarded_ref_count INTEGER DEFAULT 0,
            banned INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER NOT NULL,
            referred_user_id INTEGER NOT NULL,
            referred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS redeem_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'unused',
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            used_by INTEGER DEFAULT NULL,
            used_at TIMESTAMP DEFAULT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS force_join_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            channel_link TEXT NOT NULL,
            added_by INTEGER,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            target_user_id INTEGER DEFAULT NULL,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# ------------------- DATABASE QUERIES -------------------
def register_user(user_id, referrer_id=None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if c.fetchone():
        conn.close()
        return False
    c.execute("INSERT INTO users (user_id, referrer_id) VALUES (?, ?)", (user_id, referrer_id))
    conn.commit()
    conn.close()
    return True

def get_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def increment_referral_count(referrer_id, referred_user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET referral_count = referral_count + 1 WHERE user_id = ?", (referrer_id,))
    c.execute("INSERT INTO referrals (referrer_id, referred_user_id) VALUES (?, ?)", (referrer_id, referred_user_id))
    conn.commit()
    c.execute("SELECT * FROM users WHERE user_id = ?", (referrer_id,))
    conn.row_factory = sqlite3.Row
    row = c.fetchone()
    conn.close()
    return row

def update_last_rewarded(user_id, new_last_rewarded):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET last_rewarded_ref_count = ? WHERE user_id = ?", (new_last_rewarded, user_id))
    conn.commit()
    conn.close()

def get_referrals_count(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT referral_count FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def get_top_referrers(limit=10):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT user_id, referral_count FROM users ORDER BY referral_count DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

def is_user_banned(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT banned FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row and row[0] == 1

def ban_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET banned = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def unban_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET banned = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def reset_user_referrals(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET referral_count = 0, last_rewarded_ref_count = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def total_users():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    count = c.fetchone()[0]
    conn.close()
    return count

def add_redeem_code(code, created_by):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO redeem_codes (code, created_by) VALUES (?, ?)", (code, created_by))
    conn.commit()
    conn.close()

def remove_redeem_code(code):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM redeem_codes WHERE code = ?", (code,))
    conn.commit()
    conn.close()

def get_unused_redeem_code():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT code FROM redeem_codes WHERE status = 'unused' LIMIT 1")
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def mark_code_used(code, user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE redeem_codes SET status = 'used', used_by = ?, used_at = CURRENT_TIMESTAMP WHERE code = ?", (user_id, code))
    conn.commit()
    conn.close()

def assign_reward_to_user(user_id, code):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO user_rewards (user_id, code) VALUES (?, ?)", (user_id, code))
    conn.commit()
    conn.close()

def get_user_rewards(user_id):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT code, assigned_at FROM user_rewards WHERE user_id = ? ORDER BY assigned_at DESC", (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_codes(status=None):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    if status:
        c.execute("SELECT code, status, created_by, used_by FROM redeem_codes WHERE status = ?", (status,))
    else:
        c.execute("SELECT code, status, created_by, used_by FROM redeem_codes")
    rows = c.fetchall()
    conn.close()
    return rows

def add_force_join_channel(chat_id, channel_link, added_by):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO force_join_channels (chat_id, channel_link, added_by) VALUES (?, ?, ?)", (chat_id, channel_link, added_by))
    conn.commit()
    conn.close()

def remove_force_join_channel(chat_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM force_join_channels WHERE chat_id = ?", (chat_id,))
    conn.commit()
    conn.close()

def get_all_force_join_channels():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT chat_id, channel_link FROM force_join_channels")
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_user_ids():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE banned = 0")
    rows = c.fetchall()
    conn.close()
    return [row[0] for row in rows]

def daily_stats():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE DATE(created_at) = DATE('now')")
    new_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM referrals WHERE DATE(referred_at) = DATE('now')")
    new_refs = c.fetchone()[0]
    conn.close()
    return {"new_users": new_users, "new_referrals": new_refs}

def export_users():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT user_id, referrer_id, referral_count, banned, created_at FROM users")
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows

def export_codes():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT code, status, created_by, used_by, created_at, used_at FROM redeem_codes")
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows

def log_admin_action(admin_id, action, target_user_id=None, details=""):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO admin_logs (admin_id, action, target_user_id, details) VALUES (?, ?, ?, ?)",
              (admin_id, action, target_user_id, details))
    conn.commit()
    conn.close()

def get_admin_logs(limit=100):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM admin_logs ORDER BY timestamp DESC LIMIT ?", (limit,))
    logs = c.fetchall()
    conn.close()
    return logs

# ------------------- ANTI-SPAM -------------------
user_last_command = defaultdict(float)

def anti_spam(user_id, cooldown=1):
    now = time.time()
    if now - user_last_command[user_id] < cooldown:
        return False
    user_last_command[user_id] = now
    return True

# ------------------- FORCE JOIN CHECK (FIXED) -------------------
def check_force_join(user_id):
    if not FORCE_JOIN_ENABLED:
        return True
    channels = get_all_force_join_channels()
    if not channels:
        return True
    for ch in channels:
        try:
            # Bot must be a member of the channel to check membership
            member = bot.get_chat_member(ch["chat_id"], user_id)
            if member.status in ("left", "kicked"):
                return False
        except Exception as e:
            print(f"Force join check error for channel {ch['chat_id']}: {e}")
            # If bot cannot check (not admin or not member), assume user not joined for safety
            return False
    return True

def send_force_join_message(chat_id):
    channels = get_all_force_join_channels()
    if not channels:
        return
    keyboard = InlineKeyboardMarkup()
    for idx, ch in enumerate(channels):
        keyboard.add(InlineKeyboardButton(text=f"📢 Join Channel {idx+1}", url=ch["channel_link"]))
    keyboard.add(InlineKeyboardButton(text="✅ Verify Join", callback_data="verify_join"))
    bot.send_message(chat_id, 
                     "🔐 *You must join the following channels to use this bot:*\n\n"
                     "After joining, click *Verify Join*.",
                     reply_markup=keyboard, parse_mode="Markdown")

# ------------------- DYNAMIC MAIN MENU (with admin button) -------------------
def get_main_menu(user_id):
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("👥 My Referrals", callback_data="my_referrals"),
        InlineKeyboardButton("🎁 My Reward", callback_data="my_reward")
    )
    keyboard.add(
        InlineKeyboardButton("🔗 Get Referral Link", callback_data="get_link"),
        InlineKeyboardButton("📜 Redeem History", callback_data="redeem_history")
    )
    keyboard.add(
        InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard"),
        InlineKeyboardButton("❓ Help", callback_data="help")
    )
    if user_id in ADMIN_IDS:
        keyboard.add(InlineKeyboardButton("🛠 Admin Panel", callback_data="admin_panel"))
    return keyboard

def admin_panel_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("➕ Add Redeem Code", callback_data="admin_add_code"),
        InlineKeyboardButton("➖ Remove Redeem Code", callback_data="admin_remove_code"),
        InlineKeyboardButton("📋 View All Codes", callback_data="admin_view_codes"),
        InlineKeyboardButton("✅ View Unused Codes", callback_data="admin_view_unused"),
        InlineKeyboardButton("❌ View Used Codes", callback_data="admin_view_used"),
        InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast"),
        InlineKeyboardButton("➕ Add Force Join Channel", callback_data="admin_add_channel"),
        InlineKeyboardButton("➖ Remove Force Join Channel", callback_data="admin_remove_channel"),
        InlineKeyboardButton("📜 List Force Join Channels", callback_data="admin_list_channels"),
        InlineKeyboardButton("👥 Total Users", callback_data="admin_total_users"),
        InlineKeyboardButton("🔗 Total Referrals", callback_data="admin_total_refs"),
        InlineKeyboardButton("🚫 Ban User", callback_data="admin_ban"),
        InlineKeyboardButton("✅ Unban User", callback_data="admin_unban"),
        InlineKeyboardButton("📄 User Details", callback_data="admin_user_details"),
        InlineKeyboardButton("🔄 Reset User Referrals", callback_data="admin_reset_refs"),
        InlineKeyboardButton("📊 Export Users", callback_data="admin_export_users"),
        InlineKeyboardButton("💾 Export Codes", callback_data="admin_export_codes"),
        InlineKeyboardButton("📈 Daily Stats", callback_data="admin_daily_stats"),
        InlineKeyboardButton("📜 Admin Logs", callback_data="admin_logs"),
        InlineKeyboardButton("🗄️ Backup Database", callback_data="admin_backup")
    )
    return keyboard

# ------------------- BOT HANDLERS -------------------

@bot.message_handler(commands=['start'])
def cmd_start(message):
    user_id = message.from_user.id
    if not anti_spam(user_id):
        bot.reply_to(message, "🐌 Please don't spam!")
        return

    # Force join check
    if FORCE_JOIN_ENABLED and not check_force_join(user_id):
        send_force_join_message(message.chat.id)
        return

    args = message.text.split()
    referrer_id = None
    if len(args) > 1:
        try:
            referrer_id = int(args[1])
            if referrer_id == user_id:
                referrer_id = None
        except:
            pass

    if register_user(user_id, referrer_id):
        if referrer_id:
            referrer = increment_referral_count(referrer_id, user_id)
            if referrer:
                current = referrer["referral_count"]
                last_rewarded = referrer["last_rewarded_ref_count"]
                while current - last_rewarded >= 5:
                    code = get_unused_redeem_code()
                    if code:
                        mark_code_used(code, referrer_id)
                        assign_reward_to_user(referrer_id, code)
                        try:
                            bot.send_message(referrer_id,
                                f"🎉 Congratulations! You completed 5 referrals and unlocked a redeem code!\n"
                                f"Your code: `{code}`",
                                parse_mode="Markdown")
                        except:
                            pass
                        update_last_rewarded(referrer_id, last_rewarded + 5)
                        last_rewarded += 5
                    else:
                        break
        bot.send_message(message.chat.id,
            f"✅ Welcome {message.from_user.first_name}!\n\nInvite friends and earn redeem codes.\nUse the menu below.",
            reply_markup=get_main_menu(user_id))
    else:
        user = get_user(user_id)
        if user:
            bot.send_message(message.chat.id,
                f"👋 Welcome back {message.from_user.first_name}!\nYou have {user['referral_count']} referrals.",
                reply_markup=get_main_menu(user_id))
        else:
            bot.send_message(message.chat.id, "Something went wrong. Try /start again.")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    if not anti_spam(user_id):
        bot.answer_callback_query(call.id, "Please wait before clicking again.", show_alert=False)
        return

    # Force join check for all callbacks except "verify_join"
    data = call.data
    if data != "verify_join" and FORCE_JOIN_ENABLED and not check_force_join(user_id):
        bot.answer_callback_query(call.id, "You need to join all required channels first.", show_alert=True)
        send_force_join_message(call.message.chat.id)
        return

    # ---- User callbacks ----
    if data == "my_referrals":
        user = get_user(user_id)
        if user:
            bot.edit_message_text(
                f"👥 Your Referrals: {user['referral_count']}\nKeep inviting to unlock more rewards!",
                call.message.chat.id, call.message.message_id,
                reply_markup=get_main_menu(user_id))
        else:
            bot.edit_message_text("User not found.", call.message.chat.id, call.message.message_id,
                                  reply_markup=get_main_menu(user_id))
        bot.answer_callback_query(call.id)

    elif data == "my_reward":
        rewards = get_user_rewards(user_id)
        if rewards:
            text = "🎁 Your earned redeem codes:\n\n" + "\n".join([f"`{r['code']}` (earned: {r['assigned_at']})" for r in rewards])
        else:
            text = "You haven't earned any redeem code yet. Invite 5 friends to get your first code!"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                              reply_markup=get_main_menu(user_id), parse_mode="Markdown")
        bot.answer_callback_query(call.id)

    elif data == "get_link":
        bot_username = bot.get_me().username
        link = f"https://t.me/{bot_username}?start={user_id}"
        bot.edit_message_text(
            f"🔗 Your personal referral link:\n`{link}`\n\nShare it with your friends!",
            call.message.chat.id, call.message.message_id,
            reply_markup=get_main_menu(user_id), parse_mode="Markdown")
        bot.answer_callback_query(call.id)

    elif data == "redeem_history":
        rewards = get_user_rewards(user_id)
        if rewards:
            text = "📜 Redeem History:\n\n" + "\n".join([f"Code: `{r['code']}` – {r['assigned_at']}" for r in rewards])
        else:
            text = "No redeem history found."
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                              reply_markup=get_main_menu(user_id), parse_mode="Markdown")
        bot.answer_callback_query(call.id)

    elif data == "leaderboard":
        top = get_top_referrers(10)
        if top:
            text = "🏆 Top Referrers:\n\n"
            for idx, user in enumerate(top, 1):
                text += f"{idx}. User `{user['user_id']}` – {user['referral_count']} referrals\n"
        else:
            text = "No referrals yet."
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                              reply_markup=get_main_menu(user_id), parse_mode="Markdown")
        bot.answer_callback_query(call.id)

    elif data == "help":
        help_text = (
            "📖 *Help Section*\n\n"
            "• *My Referrals* – See how many friends joined via your link.\n"
            "• *My Reward* – View your earned redeem codes.\n"
            "• *Get Referral Link* – Get your unique link to share.\n"
            "• *Redeem History* – All codes you received.\n"
            "• *Leaderboard* – Top referrers.\n\n"
            "For every 5 successful referrals you get 1 redeem code automatically."
        )
        bot.edit_message_text(help_text, call.message.chat.id, call.message.message_id,
                              reply_markup=get_main_menu(user_id), parse_mode="Markdown")
        bot.answer_callback_query(call.id)

    # ---- Verify Join (force join re-check) ----
    elif data == "verify_join":
        if check_force_join(user_id):
            # User has joined all channels – delete force join message and show main menu
            bot.delete_message(call.message.chat.id, call.message.message_id)
            # Send welcome menu
            user = get_user(user_id)
            if user:
                bot.send_message(call.message.chat.id,
                    f"👋 Welcome {call.from_user.first_name}! You have {user['referral_count']} referrals.",
                    reply_markup=get_main_menu(user_id))
            else:
                # If somehow not registered, register now
                register_user(user_id)
                bot.send_message(call.message.chat.id,
                    f"✅ Welcome {call.from_user.first_name}!",
                    reply_markup=get_main_menu(user_id))
            bot.answer_callback_query(call.id, "✅ Verification successful! Welcome to the bot.", show_alert=False)
        else:
            bot.answer_callback_query(call.id, "❌ You still haven't joined all channels. Please join and click Verify again.", show_alert=True)
            send_force_join_message(call.message.chat.id)

    # ---- Admin Panel button from main menu ----
    elif data == "admin_panel":
        if user_id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "Unauthorized.", show_alert=True)
            return
        bot.edit_message_text("🛠 Admin Panel", call.message.chat.id, call.message.message_id,
                              reply_markup=admin_panel_keyboard())
        bot.answer_callback_query(call.id)

    # ---- Admin callbacks (only if user is admin) ----
    elif user_id in ADMIN_IDS:
        if data == "admin_add_code":
            msg = bot.send_message(call.message.chat.id, "✏️ Send the redeem code you want to add (or /cancel to cancel).")
            bot.register_next_step_handler(msg, process_add_code, call.message.chat.id)

        elif data == "admin_remove_code":
            msg = bot.send_message(call.message.chat.id, "✏️ Send the exact redeem code you want to remove.")
            bot.register_next_step_handler(msg, process_remove_code, call.message.chat.id)

        elif data == "admin_view_codes":
            codes = get_all_codes()
            if not codes:
                text = "No redeem codes found."
            else:
                text = "📋 *All Redeem Codes*\n\n"
                for c in codes:
                    text += f"`{c['code']}` – {c['status']} (created by {c['created_by']}"
                    if c['used_by']:
                        text += f", used by {c['used_by']}"
                    text += ")\n"
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  reply_markup=admin_panel_keyboard(), parse_mode="Markdown")
            bot.answer_callback_query(call.id)

        elif data == "admin_view_unused":
            codes = get_all_codes("unused")
            text = "✅ *Unused Codes*\n\n" + "\n".join([f"`{c['code']}`" for c in codes]) if codes else "No unused codes."
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  reply_markup=admin_panel_keyboard(), parse_mode="Markdown")
            bot.answer_callback_query(call.id)

        elif data == "admin_view_used":
            codes = get_all_codes("used")
            text = "❌ *Used Codes*\n\n" + "\n".join([f"`{c['code']}` (used by {c['used_by']})" for c in codes]) if codes else "No used codes."
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  reply_markup=admin_panel_keyboard(), parse_mode="Markdown")
            bot.answer_callback_query(call.id)

        elif data == "admin_broadcast":
            msg = bot.send_message(call.message.chat.id, "📢 Send the message to broadcast to all users (text only).")
            bot.register_next_step_handler(msg, process_broadcast, call.message.chat.id)

        elif data == "admin_add_channel":
            msg = bot.send_message(call.message.chat.id, "Step 1/2: Send the **channel ID** (numeric) of the channel/group.\nExample: -100123456789")
            bot.register_next_step_handler(msg, process_add_channel_id, call.message.chat.id)

        elif data == "admin_remove_channel":
            msg = bot.send_message(call.message.chat.id, "Send the **channel ID** of the channel to remove.")
            bot.register_next_step_handler(msg, process_remove_channel, call.message.chat.id)

        elif data == "admin_list_channels":
            channels = get_all_force_join_channels()
            if channels:
                text = "📢 *Force‑Join Channels*\n\n" + "\n".join([f"ID: `{c['chat_id']}` – {c['channel_link']}" for c in channels])
                text += "\n\n⚠️ *IMPORTANT:* Bot must be added as admin/member in each channel for verification to work."
            else:
                text = "No force‑join channels configured."
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  reply_markup=admin_panel_keyboard(), parse_mode="Markdown")
            bot.answer_callback_query(call.id)

        elif data == "admin_total_users":
            total = total_users()
            bot.edit_message_text(f"👥 Total registered users: {total}", call.message.chat.id, call.message.message_id,
                                  reply_markup=admin_panel_keyboard())
            bot.answer_callback_query(call.id)

        elif data == "admin_total_refs":
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("SELECT SUM(referral_count) FROM users")
            total = c.fetchone()[0] or 0
            conn.close()
            bot.edit_message_text(f"🔗 Total referrals across all users: {total}", call.message.chat.id, call.message.message_id,
                                  reply_markup=admin_panel_keyboard())
            bot.answer_callback_query(call.id)

        elif data == "admin_ban":
            msg = bot.send_message(call.message.chat.id, "Send the **user ID** of the user to ban.")
            bot.register_next_step_handler(msg, process_ban, call.message.chat.id)

        elif data == "admin_unban":
            msg = bot.send_message(call.message.chat.id, "Send the **user ID** of the user to unban.")
            bot.register_next_step_handler(msg, process_unban, call.message.chat.id)

        elif data == "admin_user_details":
            msg = bot.send_message(call.message.chat.id, "Send the **user ID** to see details.")
            bot.register_next_step_handler(msg, process_user_details, call.message.chat.id)

        elif data == "admin_reset_refs":
            msg = bot.send_message(call.message.chat.id, "Send the **user ID** whose referral count should be reset to 0.")
            bot.register_next_step_handler(msg, process_reset_refs, call.message.chat.id)

        elif data == "admin_export_users":
            data_rows = export_users()
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=["user_id","referrer_id","referral_count","banned","created_at"])
            writer.writeheader()
            writer.writerows(data_rows)
            output.seek(0)
            bot.send_document(call.message.chat.id, document=("users_export.csv", output.getvalue().encode()), caption="Users data export")
            bot.answer_callback_query(call.id)

        elif data == "admin_export_codes":
            data_rows = export_codes()
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=["code","status","created_by","used_by","created_at","used_at"])
            writer.writeheader()
            writer.writerows(data_rows)
            output.seek(0)
            bot.send_document(call.message.chat.id, document=("codes_export.csv", output.getvalue().encode()), caption="Redeem codes export")
            bot.answer_callback_query(call.id)

        elif data == "admin_daily_stats":
            stats = daily_stats()
            text = f"📊 *Daily Statistics*\n\nNew users today: {stats['new_users']}\nNew referrals today: {stats['new_referrals']}"
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  reply_markup=admin_panel_keyboard(), parse_mode="Markdown")
            bot.answer_callback_query(call.id)

        elif data == "admin_logs":
            logs = get_admin_logs(50)
            if not logs:
                text = "No admin logs found."
            else:
                text = "📜 *Recent Admin Actions*\n\n"
                for log in logs:
                    text += f"`{log['timestamp']}` – {log['action']} by {log['admin_id']}"
                    if log['target_user_id']:
                        text += f" (target: {log['target_user_id']})"
                    text += "\n"
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  reply_markup=admin_panel_keyboard(), parse_mode="Markdown")
            bot.answer_callback_query(call.id)

        elif data == "admin_backup":
            backup_path = "bot_backup.db"
            shutil.copy(DB_FILE, backup_path)
            with open(backup_path, 'rb') as f:
                bot.send_document(call.message.chat.id, f, caption="Database backup")
            os.remove(backup_path)
            bot.answer_callback_query(call.id)

        else:
            bot.answer_callback_query(call.id, "Unknown command.", show_alert=False)

    else:
        bot.answer_callback_query(call.id, "Unauthorized.", show_alert=True)

# ------------------- ADMIN STEP PROCESSORS -------------------
def process_add_code(message, original_chat_id):
    if message.text == "/cancel":
        bot.send_message(message.chat.id, "Operation cancelled.")
        return
    code = message.text.strip()
    if not code:
        bot.send_message(message.chat.id, "Invalid code.")
        return
    add_redeem_code(code, message.from_user.id)
    log_admin_action(message.from_user.id, "add_redeem_code", details=f"Code: {code}")
    bot.send_message(message.chat.id, f"✅ Redeem code `{code}` added successfully.", parse_mode="Markdown")
    bot.send_message(original_chat_id, "🛠 Admin Panel", reply_markup=admin_panel_keyboard())

def process_remove_code(message, original_chat_id):
    code = message.text.strip()
    remove_redeem_code(code)
    log_admin_action(message.from_user.id, "remove_redeem_code", details=f"Code: {code}")
    bot.send_message(message.chat.id, f"✅ Redeem code `{code}` removed (if it existed).", parse_mode="Markdown")
    bot.send_message(original_chat_id, "🛠 Admin Panel", reply_markup=admin_panel_keyboard())

def process_broadcast(message, original_chat_id):
    text = message.text
    users = get_all_user_ids()
    sent = 0
    for uid in users:
        try:
            bot.send_message(uid, text)
            sent += 1
            time.sleep(0.05)
        except:
            pass
    log_admin_action(message.from_user.id, "broadcast", details=f"Sent to {sent} users")
    bot.send_message(message.chat.id, f"✅ Broadcast complete. Sent to {sent} users.")
    bot.send_message(original_chat_id, "🛠 Admin Panel", reply_markup=admin_panel_keyboard())

def process_add_channel_id(message, original_chat_id):
    try:
        chat_id = int(message.text.strip())
        msg = bot.send_message(message.chat.id, "Step 2/2: Send the **invite link** for that channel (e.g., https://t.me/joinchat/...).")
        bot.register_next_step_handler(msg, process_add_channel_link, original_chat_id, chat_id)
    except:
        bot.send_message(message.chat.id, "Invalid channel ID. Must be an integer.")
        bot.send_message(original_chat_id, "🛠 Admin Panel", reply_markup=admin_panel_keyboard())

def process_add_channel_link(message, original_chat_id, chat_id):
    link = message.text.strip()
    add_force_join_channel(chat_id, link, message.from_user.id)
    log_admin_action(message.from_user.id, "add_force_join", details=f"Chat {chat_id}")
    bot.send_message(message.chat.id, f"✅ Channel added successfully.\nID: {chat_id}\nLink: {link}\n\n⚠️ Make sure the bot is added as admin/member in this channel for verification to work.")
    bot.send_message(original_chat_id, "🛠 Admin Panel", reply_markup=admin_panel_keyboard())

def process_remove_channel(message, original_chat_id):
    try:
        chat_id = int(message.text.strip())
        remove_force_join_channel(chat_id)
        log_admin_action(message.from_user.id, "remove_force_join", details=f"Removed chat {chat_id}")
        bot.send_message(message.chat.id, f"✅ Channel with ID {chat_id} removed (if existed).")
    except:
        bot.send_message(message.chat.id, "Invalid chat ID.")
    bot.send_message(original_chat_id, "🛠 Admin Panel", reply_markup=admin_panel_keyboard())

def process_ban(message, original_chat_id):
    try:
        uid = int(message.text.strip())
        ban_user(uid)
        log_admin_action(message.from_user.id, "ban_user", target_user_id=uid)
        bot.send_message(message.chat.id, f"✅ User {uid} has been banned.")
    except:
        bot.send_message(message.chat.id, "Invalid user ID.")
    bot.send_message(original_chat_id, "🛠 Admin Panel", reply_markup=admin_panel_keyboard())

def process_unban(message, original_chat_id):
    try:
        uid = int(message.text.strip())
        unban_user(uid)
        log_admin_action(message.from_user.id, "unban_user", target_user_id=uid)
        bot.send_message(message.chat.id, f"✅ User {uid} has been unbanned.")
    except:
        bot.send_message(message.chat.id, "Invalid user ID.")
    bot.send_message(original_chat_id, "🛠 Admin Panel", reply_markup=admin_panel_keyboard())

def process_user_details(message, original_chat_id):
    try:
        uid = int(message.text.strip())
        user = get_user(uid)
        if user:
            text = f"📄 *User Details*\n\nID: `{user['user_id']}`\nReferrals: {user['referral_count']}\nBanned: {'Yes' if user['banned'] else 'No'}\nJoined: {user['created_at']}"
            if user['referrer_id']:
                text += f"\nReferred by: `{user['referrer_id']}`"
        else:
            text = "User not found."
        bot.send_message(message.chat.id, text, parse_mode="Markdown")
    except:
        bot.send_message(message.chat.id, "Invalid user ID.")
    bot.send_message(original_chat_id, "🛠 Admin Panel", reply_markup=admin_panel_keyboard())

def process_reset_refs(message, original_chat_id):
    try:
        uid = int(message.text.strip())
        reset_user_referrals(uid)
        log_admin_action(message.from_user.id, "reset_referrals", target_user_id=uid)
        bot.send_message(message.chat.id, f"✅ Referral count for user {uid} reset to 0.")
    except:
        bot.send_message(message.chat.id, "Invalid user ID.")
    bot.send_message(original_chat_id, "🛠 Admin Panel", reply_markup=admin_panel_keyboard())

# ------------------- ADDITIONAL COMMANDS -------------------
@bot.message_handler(commands=['admin'])
def admin_cmd(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "Unauthorized.")
        return
    bot.send_message(message.chat.id, "🛠 Admin Panel", reply_markup=admin_panel_keyboard())

@bot.message_handler(commands=['help'])
def help_cmd(message):
    bot.reply_to(message, "Use /start to see the main menu.")

@bot.message_handler(func=lambda msg: True)
def anti_spam_all(msg):
    if not anti_spam(msg.from_user.id, cooldown=1):
        bot.reply_to(msg, "🐌 Slow down!")
        return
    if FORCE_JOIN_ENABLED and not check_force_join(msg.from_user.id):
        send_force_join_message(msg.chat.id)
        return

# ------------------- MAIN -------------------
if __name__ == "__main__":
    init_db()
    print("✅ Bot started. Admin ID:", ADMIN_IDS)
    print("⚠️ Force join channels: Make sure bot is added as admin/member in each channel!")
    bot.infinity_polling()