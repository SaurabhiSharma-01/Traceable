#!/usr/bin/env python3
"""
setup.py — One-shot setup script for Traceable.
Run this from the project root (the folder containing this file).

Usage:
    python setup.py
"""
import subprocess
import sys
import os
from pathlib import Path

ROOT = Path(__file__).parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"

def run(cmd, cwd=None, check=True):
    print(f"\n>>> {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    return subprocess.run(cmd, cwd=cwd or ROOT, check=check, shell=isinstance(cmd, str))

# ── 1. Git init ──────────────────────────────────────────────────────────────
if not (ROOT / ".git").exists():
    run(["git", "init"])
    run(["git", "add", "."])
    run(["git", "commit", "-m", "chore: project scaffold"])
    print("\n[git] Initial commit done.")
else:
    print("\n[git] Repository already initialised.")

# ── 2. Python venv ───────────────────────────────────────────────────────────
venv = BACKEND / ".venv"
if not venv.exists():
    run([sys.executable, "-m", "venv", str(venv)])
    print("\n[venv] Created.")
else:
    print("\n[venv] Already exists.")

pip = str(venv / ("Scripts/pip" if sys.platform == "win32" else "bin/pip"))
run([pip, "install", "-r", str(BACKEND / "requirements.txt")])

# ── 3. Frontend dependencies ──────────────────────────────────────────────────
run(["npm", "install"], cwd=FRONTEND)

print("\n\n✅ Setup complete.")
print("\nTo start the backend:")
if sys.platform == "win32":
    print(f"  cd backend && .venv\\Scripts\\activate && uvicorn app.main:app --reload")
else:
    print(f"  cd backend && source .venv/bin/activate && uvicorn app.main:app --reload")
print("\nTo start the frontend:")
print("  cd frontend && npm run dev")
print("\nTo check your API keys:")
if sys.platform == "win32":
    print("  cd backend && .venv\\Scripts\\activate && python scripts/check_keys.py")
else:
    print("  cd backend && source .venv/bin/activate && python scripts/check_keys.py")

