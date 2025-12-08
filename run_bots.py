# run_bots.py
"""
Run both:
- forwarder_bot.py  (Bot API control & commands)
- user_forwarder.py (Telethon userbot watcher)

Usage:
    python run_bots.py
"""

import os
import subprocess
import sys
import time

SCRIPTS = ["forwarder_bot.py", "user_forwarder.py"]


def main() -> None:
    print("=" * 60)
    print("🚀 run_bots.py – launching forwarder_bot.py and user_forwarder.py")
    print("=" * 60)

    processes = []

    # Start both scripts
    for script in SCRIPTS:
        if not os.path.exists(script):
            print(f"❌ {script} not found in current directory.")
            sys.exit(1)
        print(f"▶️ Starting {script} ...")
        p = subprocess.Popen([sys.executable, script])
        processes.append(p)

    try:
        while True:
            time.sleep(5)
            for idx, p in enumerate(processes):
                if p.poll() is not None:
                    script = SCRIPTS[idx]
                    code = p.returncode
                    print(f"⚠️ {script} exited with code {code}. Restarting...")
                    new_p = subprocess.Popen([sys.executable, script])
                    processes[idx] = new_p
    except KeyboardInterrupt:
        print("\n🛑 Stopping all bots...")
        for p in processes:
            try:
                p.terminate()
            except Exception:
                pass
        for p in processes:
            try:
                p.wait(timeout=5)
            except Exception:
                pass
        print("✅ All bots stopped.")


if __name__ == "__main__":
    main()
