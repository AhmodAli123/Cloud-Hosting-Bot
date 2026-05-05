import os
import time
from config import LOGS_DIR, LOG_MAX_LINES

def _log_path(user_id, filename):
    return os.path.join(LOGS_DIR, f"{user_id}_{filename}.log")

def write_log(path_or_uid, content, filename=None):
    if filename:
        path = _log_path(path_or_uid, filename)
    else:
        path = path_or_uid
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)

def append_log(path_or_uid, content, filename=None):
    if filename:
        path = _log_path(path_or_uid, filename)
    else:
        path = path_or_uid
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        f.write(content)

def read_log(user_id, filename, last_n=50):
    path = _log_path(user_id, filename)
    if not os.path.exists(path):
        return "📭 No log found"
    with open(path, "r", errors="replace") as f:
        lines = f.readlines()
    if not lines:
        return "📭 Log is empty"
    tail = lines[-last_n:]
    return "".join(tail)

def clear_log(user_id, filename):
    path = _log_path(user_id, filename)
    if os.path.exists(path):
        os.remove(path)

def clear_all_logs():
    count = 0
    for fname in os.listdir(LOGS_DIR):
        fpath = os.path.join(LOGS_DIR, fname)
        if os.path.isfile(fpath):
            os.remove(fpath)
            count += 1
    return count

def clear_user_logs(user_id):
    count = 0
    prefix = f"{user_id}_"
    for fname in os.listdir(LOGS_DIR):
        if fname.startswith(prefix):
            os.remove(os.path.join(LOGS_DIR, fname))
            count += 1
    return count

def get_all_log_files():
    logs = []
    for fname in os.listdir(LOGS_DIR):
        fpath = os.path.join(LOGS_DIR, fname)
        if os.path.isfile(fpath):
            size = os.path.getsize(fpath)
            logs.append({"name": fname, "size_kb": size / 1024})
    return logs

def detect_error_in_log(user_id, filename):
    path = _log_path(user_id, filename)
    if not os.path.exists(path):
        return None
    error_keywords = [
        "Traceback", "Error:", "Exception:", "ModuleNotFoundError",
        "ImportError", "SyntaxError", "NameError", "TypeError",
        "ValueError", "AttributeError", "KeyError", "IndexError",
        "ZeroDivisionError", "RuntimeError", "ConnectionError",
        "FileNotFoundError", "PermissionError", "OSError",
    ]
    with open(path, "r", errors="replace") as f:
        content = f.read()
    for kw in error_keywords:
        if kw in content:
            lines = content.split("\n")
            relevant = [l for l in lines if any(k in l for k in error_keywords)]
            return "\n".join(relevant[-10:])
    return None

def extract_missing_module(log_content):
    import re
    match = re.search(r"No module named '([^']+)'", log_content)
    if match:
        return match.group(1)
    match = re.search(r"ModuleNotFoundError: No module named '([^']+)'", log_content)
    if match:
        return match.group(1)
    return None
