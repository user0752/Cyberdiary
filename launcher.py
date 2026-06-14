#!/usr/bin/env python3
"""
CyberNote Service Launcher v2
Interactive dashboard to start/stop/monitor frontend & backend.

Controls:  Q=Quit  R=Restart Backend  F=Restart Frontend
"""
import subprocess
import sys
import os
import time
import threading
from pathlib import Path

# ── Colors ──────────────────────────────────────────────────
GREEN = "\033[92m"; BLUE = "\033[94m"; YELLOW = "\033[93m"
RED = "\033[91m"; CYAN = "\033[96m"; RESET = "\033[0m"; BOLD = "\033[1m"

ROOT = Path(__file__).parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"

running = True
backend_proc = None
frontend_proc = None


def log(tag, color, msg):
    ts = time.strftime("%H:%M:%S")
    print(f"{color}[{ts} {tag}]{RESET} {msg}", flush=True)


def _start(proc_var_name, cmd, cwd, tag, color):
    """Generic process starter — sets the global variable and starts output thread."""
    global backend_proc, frontend_proc
    proc = subprocess.Popen(
        cmd, cwd=str(cwd),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
        shell=isinstance(cmd, str),
    )
    if proc_var_name == "backend":
        backend_proc = proc
    else:
        frontend_proc = proc

    def reader():
        for line in proc.stdout:
            if not running:
                break
            line = line.rstrip()
            if line:
                c = RED if any(k in line for k in ("ERROR", "Traceback", "exception")) else (
                    YELLOW if "WARNING" in line else color)
                log(tag, c, line)

    threading.Thread(target=reader, daemon=True).start()
    return proc


def start_backend():
    global backend_proc
    if backend_proc and backend_proc.poll() is None:
        log("BACKEND", YELLOW, "Already running")
        return
    log("BACKEND", CYAN, "Starting...")
    venv_python = str(BACKEND_DIR / "venv" / "Scripts" / "python.exe")
    if not os.path.exists(venv_python):
        venv_python = sys.executable
    _start("backend",
           [venv_python, "-m", "uvicorn", "app.main:app",
            "--host", "0.0.0.0", "--port", "8000"],
           BACKEND_DIR, "BACKEND", GREEN)


def start_frontend():
    global frontend_proc
    if frontend_proc and frontend_proc.poll() is None:
        log("FRONTEND", YELLOW, "Already running")
        return
    log("FRONTEND", CYAN, "Starting...")
    _start("frontend", "npm run dev", FRONTEND_DIR, "FRONTEND", BLUE)


def stop(proc, tag):
    if proc and proc.poll() is None:
        log(tag, YELLOW, "Stopping...")
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        log(tag, RED, "Stopped")


def stop_backend():
    global backend_proc
    stop(backend_proc, "BACKEND")
    backend_proc = None


def stop_frontend():
    global frontend_proc
    stop(frontend_proc, "FRONTEND")
    frontend_proc = None


def check(port):
    import urllib.request
    try:
        urllib.request.urlopen(f"http://localhost:{port}/api/health" if port == 8000 else f"http://localhost:{port}", timeout=2)
        return True
    except Exception:
        return False


def dashboard():
    be_ok = check(8000)
    fe_ok = check(5173)
    bs = f"{GREEN}✓ RUNNING{RESET}" if be_ok else f"{RED}✗ DOWN{RESET}"
    fs = f"{GREEN}✓ RUNNING{RESET}" if fe_ok else f"{RED}✗ DOWN{RESET}"
    print(f"""
{BOLD}{CYAN}╔══════════════════════════════════════════════╗
║       CyberNote Service Dashboard          ║
╠══════════════════════════════════════════════╣
║  Backend  : {bs:<36}║
║  Frontend : {fs:<36}║
╠══════════════════════════════════════════════╣
║  [R] Restart Backend   [F] Restart Frontend ║
║  [Q] Quit                                    ║
╚══════════════════════════════════════════════╝{RESET}""")
    if be_ok and fe_ok:
        print(f"\n  {GREEN}Open {CYAN}http://localhost:5173{GREEN} in browser{RESET}\n")


def cmd_loop():
    """Simple non-blocking command input thread."""
    global running
    while running:
        try:
            cmd = input().strip().lower()
        except (EOFError, OSError):
            break
        if cmd == 'q':
            running = False
            print(f"\n{YELLOW}Shutting down...{RESET}")
            stop_backend()
            stop_frontend()
            return
        elif cmd == 'r':
            log("SYSTEM", CYAN, "Restarting backend...")
            stop_backend()
            time.sleep(1)
            start_backend()
            time.sleep(2)
            dashboard()
        elif cmd == 'f':
            log("SYSTEM", CYAN, "Restarting frontend...")
            stop_frontend()
            time.sleep(1)
            start_frontend()
            time.sleep(2)
            dashboard()
        elif cmd == '':
            dashboard()


def main():
    global running
    print(f"{CYAN}{BOLD}")
    print("  ┌─────────────────────────────────────┐")
    print("  │   CyberNote Interactive Launcher    │")
    print("  │   Q=Quit  R=Restart BE  F=Restart FE│")
    print("  └─────────────────────────────────────┘")
    print(f"{RESET}")

    start_backend()
    start_frontend()

    print(f"{YELLOW}Waiting for services...{RESET}")
    for i in range(30):
        time.sleep(1)
        if check(8000) and check(5173):
            break
        if i % 5 == 0 and i > 0:
            print(f"  ... waiting ({30 - i}s timeout)")

    dashboard()

    # Auto-open browser
    if check(5173):
        import webbrowser
        webbrowser.open("http://localhost:5173")
        log("SYSTEM", GREEN, "Browser opened")

    # Start command input thread
    t = threading.Thread(target=cmd_loop, daemon=True)
    t.start()

    try:
        while running:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        running = False
        stop_backend()
        stop_frontend()
        print(f"\n{GREEN}Goodbye!{RESET}")


if __name__ == "__main__":
    main()
