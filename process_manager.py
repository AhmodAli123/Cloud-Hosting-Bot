import subprocess
import os
import time
import signal
import threading
import psutil
from collections import defaultdict
from config import (
    MAX_PROCESSES_PER_USER_FREE,
    MAX_PROCESSES_PER_USER_PREMIUM,
    SCRIPT_TIMEOUT,
    LOGS_DIR,
    USERS_DIR,
)
from log_manager import write_log, append_log

_processes = {}
_process_lock = threading.Lock()
_auto_restart_flags = {}

def _get_max_processes(plan):
    return MAX_PROCESSES_PER_USER_PREMIUM if plan == "premium" else MAX_PROCESSES_PER_USER_FREE

def get_user_process_count(user_id):
    with _process_lock:
        return sum(1 for (uid, _) in _processes if uid == user_id)

def get_user_processes(user_id):
    with _process_lock:
        result = {}
        for (uid, filename), info in _processes.items():
            if uid == user_id:
                result[filename] = info
        return result

def get_all_processes():
    with _process_lock:
        return dict(_processes)

def get_total_process_count():
    with _process_lock:
        return len(_processes)

def is_running(user_id, filename):
    with _process_lock:
        key = (user_id, filename)
        if key not in _processes:
            return False
        proc = _processes[key].get("proc")
        return proc is not None and proc.poll() is None

def run_script(user_id, filename, plan="free", auto_restart=False):
    if get_user_process_count(user_id) >= _get_max_processes(plan):
        return False, f"❌ Process limit reached ({_get_max_processes(plan)} max for {plan} plan)"

    if is_running(user_id, filename):
        return False, "⚠️ Script is already running"

    user_dir = os.path.join(USERS_DIR, str(user_id))
    filepath = os.path.join(user_dir, filename)
    if not os.path.exists(filepath):
        return False, "❌ File not found"

    log_path = os.path.join(LOGS_DIR, f"{user_id}_{filename}.log")
    write_log(log_path, f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting {filename}\n")

    if filename.endswith(".py"):
        cmd = ["python3", "-u", filepath]
    elif filename.endswith(".js"):
        cmd = ["node", filepath]
    else:
        return False, "❌ Unsupported file type"

    try:
        log_file = open(log_path, "a")
        proc = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=log_file,
            cwd=user_dir,
            preexec_fn=os.setsid,
        )
        with _process_lock:
            _processes[(user_id, filename)] = {
                "proc": proc,
                "pid": proc.pid,
                "started_at": time.time(),
                "log_path": log_path,
                "log_file": log_file,
                "filename": filename,
                "auto_restart": auto_restart,
            }
        _auto_restart_flags[(user_id, filename)] = auto_restart

        t = threading.Thread(target=_monitor_process, args=(user_id, filename, plan), daemon=True)
        t.start()

        return True, f"✅ Started `{filename}` (PID: {proc.pid})"
    except Exception as e:
        return False, f"❌ Error: {e}"

def _monitor_process(user_id, filename, plan):
    key = (user_id, filename)
    start = time.time()
    while True:
        time.sleep(3)
        with _process_lock:
            if key not in _processes:
                break
            proc = _processes[key]["proc"]
            log_file = _processes[key]["log_file"]
        if proc.poll() is not None:
            log_file.close()
            auto_restart = _auto_restart_flags.get(key, False)
            with _process_lock:
                _processes.pop(key, None)
            if auto_restart:
                time.sleep(5)
                run_script(user_id, filename, plan, auto_restart=True)
            break
        elapsed = time.time() - start
        if elapsed > SCRIPT_TIMEOUT:
            stop_script(user_id, filename)
            append_log(os.path.join(LOGS_DIR, f"{user_id}_{filename}.log"),
                       f"\n[TIMEOUT] Script exceeded {SCRIPT_TIMEOUT}s limit\n")
            break

def stop_script(user_id, filename):
    key = (user_id, filename)
    with _process_lock:
        if key not in _processes:
            return False, "⚠️ Script is not running"
        info = _processes[key]
        proc = info["proc"]
        log_file = info["log_file"]

    try:
        pgid = os.getpgid(proc.pid)
        os.killpg(pgid, signal.SIGTERM)
        time.sleep(1)
        if proc.poll() is None:
            os.killpg(pgid, signal.SIGKILL)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass

    try:
        log_file.close()
    except Exception:
        pass

    with _process_lock:
        _processes.pop(key, None)
    _auto_restart_flags.pop(key, None)
    return True, f"🛑 Stopped `{filename}`"

def stop_all_user_scripts(user_id):
    with _process_lock:
        keys = [k for k in _processes if k[0] == user_id]
    stopped = []
    for key in keys:
        ok, msg = stop_script(key[0], key[1])
        if ok:
            stopped.append(key[1])
    return stopped

def stop_all_scripts():
    with _process_lock:
        keys = list(_processes.keys())
    for key in keys:
        stop_script(key[0], key[1])

def kill_zombie_processes():
    removed = []
    with _process_lock:
        dead_keys = []
        for key, info in _processes.items():
            proc = info["proc"]
            if proc.poll() is not None:
                dead_keys.append(key)
        for key in dead_keys:
            try:
                _processes[key]["log_file"].close()
            except Exception:
                pass
            _processes.pop(key)
            removed.append(key)
    return removed

def get_process_info(user_id, filename):
    key = (user_id, filename)
    with _process_lock:
        if key not in _processes:
            return None
        info = _processes[key]
        pid = info["pid"]
    try:
        p = psutil.Process(pid)
        return {
            "pid": pid,
            "status": p.status(),
            "cpu_percent": p.cpu_percent(interval=0.1),
            "memory_mb": p.memory_info().rss / (1024 * 1024),
            "started_at": info["started_at"],
        }
    except Exception:
        return {"pid": pid, "status": "unknown", "started_at": info["started_at"]}

def get_system_stats():
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return {
        "cpu_percent": cpu,
        "ram_used_mb": ram.used / (1024 * 1024),
        "ram_total_mb": ram.total / (1024 * 1024),
        "ram_percent": ram.percent,
        "disk_used_gb": disk.used / (1024 ** 3),
        "disk_total_gb": disk.total / (1024 ** 3),
        "disk_percent": disk.percent,
    }
