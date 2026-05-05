import telebot
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)

def main_menu_keyboard(is_admin=False):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("📁 My Files"),
        KeyboardButton("⚙️ My Processes"),
        KeyboardButton("📤 Upload File"),
        KeyboardButton("📊 My Stats"),
        KeyboardButton("📜 Logs"),
        KeyboardButton("ℹ️ Status"),
    )
    if is_admin:
        markup.add(KeyboardButton("🔐 Admin Panel"))
    markup.add(KeyboardButton("❓ Help"))
    return markup

def admin_panel_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("👥 All Users", callback_data="admin_users"),
        InlineKeyboardButton("📊 Global Stats", callback_data="admin_stats"),
        InlineKeyboardButton("➕ Add Premium", callback_data="admin_add_premium"),
        InlineKeyboardButton("➖ Remove Premium", callback_data="admin_remove_premium"),
        InlineKeyboardButton("🚫 Ban User", callback_data="admin_ban"),
        InlineKeyboardButton("✅ Unban User", callback_data="admin_unban"),
        InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
        InlineKeyboardButton("🔒 Maintenance ON", callback_data="admin_maintenance_on"),
        InlineKeyboardButton("🔓 Maintenance OFF", callback_data="admin_maintenance_off"),
        InlineKeyboardButton("🧹 Clear All Logs", callback_data="admin_clear_logs"),
        InlineKeyboardButton("💀 Stop All Scripts", callback_data="admin_stop_all"),
        InlineKeyboardButton("🖥️ Shell Command", callback_data="admin_shell"),
        InlineKeyboardButton("🔄 Restart Bot", callback_data="admin_restart"),
        InlineKeyboardButton("📦 System Info", callback_data="admin_sysinfo"),
    )
    return markup

def file_list_keyboard(files, running_files=None, page=0, page_size=5):
    markup = InlineKeyboardMarkup(row_width=1)
    if running_files is None:
        running_files = set()
    start = page * page_size
    end = start + page_size
    current_page = files[start:end]
    for f in current_page:
        fname = f["filename"]
        status = "🟢" if fname in running_files else "🔴"
        markup.add(InlineKeyboardButton(
            f"{status} {fname} ({f['size_kb']} KB)",
            callback_data=f"file_menu:{fname}"
        ))
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"files_page:{page-1}"))
    if end < len(files):
        nav_buttons.append(InlineKeyboardButton("➡️ Next", callback_data=f"files_page:{page+1}"))
    if nav_buttons:
        markup.row(*nav_buttons)
    markup.add(InlineKeyboardButton("🔙 Back", callback_data="back_main"))
    return markup

def file_action_keyboard(filename, is_running=False):
    markup = InlineKeyboardMarkup(row_width=2)
    if is_running:
        markup.add(
            InlineKeyboardButton("🛑 Stop", callback_data=f"stop:{filename}"),
            InlineKeyboardButton("📜 View Log", callback_data=f"viewlog:{filename}"),
            InlineKeyboardButton("🔁 Auto Restart ON", callback_data=f"autorestart:{filename}"),
        )
    else:
        markup.add(
            InlineKeyboardButton("▶️ Run", callback_data=f"run:{filename}"),
            InlineKeyboardButton("🔁 Retry Run", callback_data=f"retryrun:{filename}"),
            InlineKeyboardButton("📜 View Log", callback_data=f"viewlog:{filename}"),
            InlineKeyboardButton("✏️ Edit", callback_data=f"edit:{filename}"),
            InlineKeyboardButton("🗑️ Delete", callback_data=f"delete:{filename}"),
        )
    markup.add(InlineKeyboardButton("🔙 Back", callback_data="back_files"))
    return markup

def process_list_keyboard(processes, page=0, page_size=5):
    markup = InlineKeyboardMarkup(row_width=1)
    items = list(processes.items())
    start = page * page_size
    end = start + page_size
    current = items[start:end]
    for fname, info in current:
        pid = info.get("pid", "?")
        markup.add(InlineKeyboardButton(
            f"🟢 {fname} (PID: {pid})",
            callback_data=f"proc_menu:{fname}"
        ))
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"proc_page:{page-1}"))
    if end < len(items):
        nav_buttons.append(InlineKeyboardButton("➡️ Next", callback_data=f"proc_page:{page+1}"))
    if nav_buttons:
        markup.row(*nav_buttons)
    markup.add(InlineKeyboardButton("🛑 Stop All", callback_data="stop_all_procs"))
    markup.add(InlineKeyboardButton("🔙 Back", callback_data="back_main"))
    return markup

def confirm_keyboard(action, data=""):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("✅ Confirm", callback_data=f"confirm:{action}:{data}"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
    )
    return markup

def log_view_keyboard(filename, offset=0):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔄 Refresh", callback_data=f"viewlog:{filename}:{offset}"),
        InlineKeyboardButton("🔙 Back", callback_data=f"file_menu:{filename}"),
        InlineKeyboardButton("🗑️ Clear Log", callback_data=f"clearlog:{filename}"),
    )
    return markup

def user_list_keyboard(users, page=0, page_size=8):
    markup = InlineKeyboardMarkup(row_width=1)
    start = page * page_size
    end = start + page_size
    current = users[start:end]
    for u in current:
        plan_icon = "💎" if u["plan"] == "premium" else "🆓"
        ban_icon = "🚫" if u["is_banned"] else ""
        name = u.get("username") or u.get("full_name") or str(u["user_id"])
        markup.add(InlineKeyboardButton(
            f"{plan_icon}{ban_icon} {name} ({u['user_id']})",
            callback_data=f"admin_user_detail:{u['user_id']}"
        ))
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_users_page:{page-1}"))
    if end < len(users):
        nav_buttons.append(InlineKeyboardButton("➡️ Next", callback_data=f"admin_users_page:{page+1}"))
    if nav_buttons:
        markup.row(*nav_buttons)
    markup.add(InlineKeyboardButton("🔙 Admin Panel", callback_data="back_admin"))
    return markup

def remove_keyboard():
    return ReplyKeyboardRemove()
