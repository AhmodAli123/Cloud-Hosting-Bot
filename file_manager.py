import os
import shutil
import zipfile
import tempfile
import subprocess
import sys
import re
from config import (
    USERS_DIR,
    MAX_FILE_SIZE_MB,
    MAX_FILES_PER_USER,
    MAX_STORAGE_MB_FREE,
    MAX_STORAGE_MB_PREMIUM,
)
from database import (
    add_file_record,
    delete_file_record,
    get_user_files,
    get_user_file_count,
    get_user_storage_mb,
)

# hosting_bot.py থেকে আনা মডিউল ম্যাপ
TELEGRAM_MODULES = {
    'telebot': 'pyTelegramBotAPI',
    'telegram': 'python-telegram-bot',
    'aiogram': 'aiogram',
    'pyrogram': 'pyrogram',
    'telethon': 'telethon',
    'bs4': 'beautifulsoup4',
    'requests': 'requests',
    'pillow': 'Pillow',
    'cv2': 'opencv-python',
    'yaml': 'PyYAML',
    'dotenv': 'python-dotenv',
}

ALLOWED_EXTENSIONS = {".py", ".js", ".zip"}

def get_user_dir(user_id):
    user_dir = os.path.join(USERS_DIR, str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    return user_dir

# --- File Handling Features from hosting_bot.py ---

def handle_zip_file(user_id, zip_bytes, file_name_zip, plan="free"):
    """ZIP ফাইল এক্সট্রাকশন, ডিপেন্ডেন্সি ইনস্টলেশন এবং মেইন ফাইল ডিটেকশন লজিক"""
    user_dir = get_user_dir(user_id)
    temp_dir = tempfile.mkdtemp(prefix=f"user_{user_id}_zip_")
    status_messages = []

    try:
        zip_path = os.path.join(temp_dir, file_name_zip)
        with open(zip_path, 'wb') as f:
            f.write(zip_bytes)

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # আনসেফ পাথ চেক
            for member in zip_ref.infolist():
                if member.filename.startswith('/') or '..' in member.filename:
                    return False, "❌ Unsafe ZIP file detected."
            zip_ref.extractall(temp_dir)

        extracted_items = os.listdir(temp_dir)
        py_files = [f for f in extracted_items if f.endswith('.py')]
        js_files = [f for f in extracted_items if f.endswith('.js')]
        
        # Python Requirements Install
        if 'requirements.txt' in extracted_items:
            req_path = os.path.join(temp_dir, 'requirements.txt')
            try:
                subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', req_path], 
                               capture_output=True, check=True)
                status_messages.append("✅ Python requirements installed.")
            except:
                status_messages.append("⚠️ Failed to install Python requirements.")

        # Node.js Package Install
        if 'package.json' in extracted_items:
            try:
                subprocess.run(['npm', 'install'], cwd=temp_dir, capture_output=True, check=True)
                status_messages.append("✅ Node.js dependencies installed.")
            except:
                status_messages.append("⚠️ Failed to install Node.js dependencies (npm not found or error).")

        # মেইন স্ক্রিপ্ট ডিটেকশন লজিক (hosting_bot.py থেকে)
        main_script = None
        file_type = None
        preferred_py = ['main.py', 'bot.py', 'app.py']
        preferred_js = ['index.js', 'main.js', 'bot.js', 'app.js']

        for p in preferred_py:
            if p in py_files: main_script = p; file_type = 'py'; break
        if not main_script:
            for p in preferred_js:
                if p in js_files: main_script = p; file_type = 'js'; break
        
        if not main_script:
            if py_files: main_script = py_files[0]; file_type = 'py'
            elif js_files: main_script = js_files[0]; file_type = 'js'

        if not main_script:
            return False, "❌ No .py or .js file found in ZIP."

        # ফাইলগুলো ইউজার ডিরেক্টরিতে মুভ করা
        for item in os.listdir(temp_dir):
            if item == file_name_zip: continue
            s = os.path.join(temp_dir, item)
            d = os.path.join(user_dir, item)
            if os.path.isdir(s):
                if os.path.exists(d): shutil.rmtree(d)
                shutil.move(s, d)
            else:
                shutil.move(s, d)
                size = os.path.getsize(d)
                add_file_record(user_id, item, d, size)

        status_messages.append(f"🚀 Detected main script: `{main_script}`")
        return True, "\n".join(status_messages)

    except Exception as e:
        return False, f"❌ ZIP Error: {str(e)}"
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

def save_file(user_id, filename, file_bytes, plan="free"):
    """hosting_bot.py এর ফিচার অনুযায়ী আপডেট করা ফাইল সেভার"""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"❌ Unsupported type `{ext}`. Allowed: .py, .js, .zip"

    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        return False, f"❌ File too large. Max: {MAX_FILE_SIZE_MB}MB"

    if ext == '.zip':
        return handle_zip_file(user_id, file_bytes, filename, plan)

    user_dir = get_user_dir(user_id)
    filepath = os.path.join(user_dir, filename)

    with open(filepath, "wb") as f:
        f.write(file_bytes)

    add_file_record(user_id, filename, filepath, len(file_bytes))
    return True, f"✅ Uploaded `{filename}` ({size_mb:.2f} MB)"

# --- End File Handling Features ---

def delete_file(user_id, filename):
    user_dir = get_user_dir(user_id)
    filepath = os.path.join(user_dir, filename)
    if not os.path.exists(filepath):
        return False, "❌ File not found"
    os.remove(filepath)
    delete_file_record(user_id, filename)
    return True, f"🗑️ Deleted `{filename}`"

def list_user_files(user_id):
    user_dir = get_user_dir(user_id)
    on_disk = [
        f for f in os.listdir(user_dir)
        if os.path.isfile(os.path.join(user_dir, f))
        and os.path.splitext(f)[1].lower() in {".py", ".js"}
    ]
    result = []
    for fname in on_disk:
        fpath = os.path.join(user_dir, fname)
        size = os.path.getsize(fpath)
        result.append({
            "filename": fname,
            "size_bytes": size,
            "size_kb": round(size / 1024, 2),
        })
    return result

def read_file(user_id, filename):
    user_dir = get_user_dir(user_id)
    filepath = os.path.join(user_dir, filename)
    if not os.path.exists(filepath):
        return None
    with open(filepath, "r", errors="replace") as f:
        return f.read()

def write_file(user_id, filename, content):
    user_dir = get_user_dir(user_id)
    filepath = os.path.join(user_dir, filename)
    with open(filepath, "w") as f:
        f.write(content)
    size = os.path.getsize(filepath)
    add_file_record(user_id, filename, filepath, size)
    return True, f"✏️ Saved `{filename}`"

def reset_user_files(user_id):
    user_dir = get_user_dir(user_id)
    count = 0
    for fname in os.listdir(user_dir):
        fpath = os.path.join(user_dir, fname)
        if os.path.isfile(fpath):
            os.remove(fpath)
            delete_file_record(user_id, fname)
            count += 1
    return count

def get_user_storage_info(user_id, plan="free"):
    used = get_user_storage_mb(user_id)
    limit = MAX_STORAGE_MB_PREMIUM if plan == "premium" else MAX_STORAGE_MB_FREE
    return used, limit