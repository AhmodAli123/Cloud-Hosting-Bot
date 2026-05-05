import subprocess
import os
import re
import json
import threading
from config import PACKAGE_MAP, USERS_DIR
from log_manager import append_log, extract_missing_module, detect_error_in_log

_install_lock = threading.Lock()

def scan_imports(filepath):
    imports = set()
    try:
        with open(filepath, "r", errors="replace") as f:
            content = f.read()
        patterns = [
            r"^import\s+([\w.]+)",
            r"^from\s+([\w.]+)\s+import",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, content, re.MULTILINE):
                top_level = match.group(1).split(".")[0]
                imports.add(top_level)
    except Exception:
        pass
    return imports

def map_package(import_name):
    return PACKAGE_MAP.get(import_name, import_name)

def pip_install(package, log_path=None):
    mapped = map_package(package)
    cmd = ["pip", "install", "--quiet", mapped]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120
        )
        msg = f"[DEP] pip install {mapped}: {'OK' if result.returncode == 0 else 'FAILED'}\n"
        if result.stderr:
            msg += result.stderr[:500]
        if log_path:
            append_log(log_path, msg)
        return result.returncode == 0, msg
    except subprocess.TimeoutExpired:
        msg = f"[DEP] pip install {mapped}: TIMEOUT\n"
        if log_path:
            append_log(log_path, msg)
        return False, msg
    except Exception as e:
        msg = f"[DEP] pip install {mapped}: ERROR {e}\n"
        if log_path:
            append_log(log_path, msg)
        return False, msg

def npm_install(user_dir, log_path=None):
    pkg_json = os.path.join(user_dir, "package.json")
    if not os.path.exists(pkg_json):
        return False, "No package.json found"
    cmd = ["npm", "install", "--prefix", user_dir]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=user_dir)
        msg = f"[NPM] npm install: {'OK' if result.returncode == 0 else 'FAILED'}\n"
        if result.stderr:
            msg += result.stderr[:500]
        if log_path:
            append_log(log_path, msg)
        return result.returncode == 0, msg
    except Exception as e:
        msg = f"[NPM] ERROR: {e}\n"
        if log_path:
            append_log(log_path, msg)
        return False, msg

def install_requirements_txt(user_dir, log_path=None):
    req_path = os.path.join(user_dir, "requirements.txt")
    if not os.path.exists(req_path):
        return False, "No requirements.txt found"
    cmd = ["pip", "install", "-r", req_path, "--quiet"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        msg = f"[REQ] requirements.txt install: {'OK' if result.returncode == 0 else 'FAILED'}\n"
        if result.returncode != 0:
            msg += result.stderr[:500]
        if log_path:
            append_log(log_path, msg)
        return result.returncode == 0, msg
    except Exception as e:
        msg = f"[REQ] ERROR: {e}\n"
        if log_path:
            append_log(log_path, msg)
        return False, msg

def auto_install_for_file(filepath, user_dir, log_path=None):
    results = []
    if filepath.endswith(".py"):
        imports = scan_imports(filepath)
        stdlib_modules = {
            "os", "sys", "re", "json", "time", "datetime", "math", "random",
            "threading", "subprocess", "pathlib", "shutil", "hashlib", "base64",
            "urllib", "http", "socket", "io", "collections", "itertools",
            "functools", "typing", "abc", "copy", "struct", "pickle",
            "logging", "traceback", "signal", "enum", "dataclasses",
            "contextlib", "weakref", "gc", "inspect", "ast", "dis", "types",
            "string", "textwrap", "csv", "configparser", "argparse", "getopt",
            "uuid", "secrets", "hmac", "sqlite3", "queue", "heapq",
            "bisect", "array", "statistics", "decimal", "fractions",
            "asyncio", "concurrent", "multiprocessing", "platform", "glob",
            "fnmatch", "tempfile", "zipfile", "tarfile", "gzip", "bz2",
            "pprint", "unittest", "doctest",
        }
        for imp in imports:
            if imp in stdlib_modules:
                continue
            ok, msg = pip_install(imp, log_path)
            results.append(msg.strip())

        req_path = os.path.join(user_dir, "requirements.txt")
        if os.path.exists(req_path):
            ok, msg = install_requirements_txt(user_dir, log_path)
            results.append(msg.strip())

    elif filepath.endswith(".js"):
        pkg_json = os.path.join(user_dir, "package.json")
        if os.path.exists(pkg_json):
            ok, msg = npm_install(user_dir, log_path)
            results.append(msg.strip())

    return results

def auto_fix_missing_module(user_id, filename, log_path):
    error_detail = detect_error_in_log(user_id, filename)
    if not error_detail:
        return None
    missing = extract_missing_module(error_detail)
    if not missing:
        return None
    ok, msg = pip_install(missing, log_path)
    return msg

def retry_install_and_run(user_id, filename, plan, process_manager, max_retries=3):
    import time as t
    from log_manager import _log_path
    log_path = _log_path(user_id, filename)
    user_dir = os.path.join(USERS_DIR, str(user_id))
    filepath = os.path.join(user_dir, filename)

    for attempt in range(1, max_retries + 1):
        append_log(log_path, f"\n[RETRY {attempt}/{max_retries}] Attempting run...\n")
        ok, msg = process_manager.run_script(user_id, filename, plan)
        if ok:
            return True, f"✅ Started on retry {attempt}"
        t.sleep(3)
        fixed = auto_fix_missing_module(user_id, filename, log_path)
        if fixed:
            append_log(log_path, f"\n[AUTO-FIX] {fixed}\n")
        else:
            auto_install_for_file(filepath, user_dir, log_path)

    return False, f"❌ Failed after {max_retries} retries"
