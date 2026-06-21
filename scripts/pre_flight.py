#!/usr/bin/env python3
"""Counta deployment pre-flight / update contract.

Run this before every deploy or after any non-trivial change. It checks:

1. Python syntax for all src/ files.
2. Unit tests pass.
3. i18n linter is green.
4. Inline JavaScript in app.html parses without syntax errors.
5. (Optional) Local Counta server responds on /healthz.

Exit code 0 = safe to deploy. Anything else = stop and fix.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "counta"
APP_HTML = ROOT / "src" / "counta" / "web" / "templates" / "app.html"


def run(cmd: list[str], *, cwd: Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    print(f"\n>>> {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True)


def check_python_syntax() -> bool:
    """Compile every .py under src/counta."""
    ok = True
    for path in SRC.rglob("*.py"):
        if path.name.startswith("."):
            continue
        r = run([sys.executable, "-m", "py_compile", str(path)], cwd=ROOT)
        if r.returncode != 0:
            print(f"FAIL syntax: {path}\n{r.stderr}")
            ok = False
    if ok:
        print("OK Python syntax")
    return ok


def _pytest_cmd() -> list[str]:
    """Prefer the project's own venv (uv) so dependencies are present."""
    if (ROOT / ".venv").exists() and \
       subprocess.run(["which", "uv"], capture_output=True).returncode == 0:
        return ["uv", "run", "pytest", "-q"]
    return [sys.executable, "-m", "pytest", "-q"]


def check_tests() -> bool:
    r = run(_pytest_cmd(), cwd=ROOT)
    print(r.stdout)
    if r.returncode != 0:
        print(r.stderr)
        return False
    print("OK tests")
    return True


def check_i18n() -> bool:
    r = run([sys.executable, "scripts/check_i18n.py"], cwd=ROOT)
    print(r.stdout)
    if r.returncode != 0:
        print(r.stderr)
        return False
    print("OK i18n")
    return True


def check_js_syntax() -> bool:
    """Extract inline <script> tags from app.html and parse them with bun/node."""
    html = APP_HTML.read_text(encoding="utf-8")
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    if not scripts:
        print("WARN no inline scripts found")
        return True

    combined = "\n".join(scripts)
    tmp = ROOT / ".tmp_app_inline.js"
    tmp.write_text(combined, encoding="utf-8")

    interpreter: str | None = None
    for candidate in ("bun", "node"):
        if subprocess.run(["which", candidate], capture_output=True).returncode == 0:
            interpreter = candidate
            break

    if interpreter is None:
        print("WARN bun/node not found; skipping JS syntax check")
        tmp.unlink(missing_ok=True)
        return True

    try:
        r = run([interpreter, str(tmp)], cwd=ROOT)
        # bun/node will fail with SyntaxError at parse time even though it
        # cannot run browser APIs like document. We only care about syntax.
        err = r.stderr or ""
        if "SyntaxError" in err or "Unexpected" in err or "ParseError" in err:
            print(f"FAIL JS syntax:\n{err}")
            return False
        print("OK JS syntax (runtime errors ignored — no browser APIs in headless run)")
        return True
    finally:
        tmp.unlink(missing_ok=True)


def check_healthz() -> bool:
    """Best-effort: if a server is running locally, /healthz must respond."""
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:8810/healthz", timeout=2) as resp:
            body = resp.read().decode()
            if resp.status == 200 and '"ok":true' in body:
                print("OK local healthz")
                return True
    except Exception as e:
        print(f"SKIP healthz (server not running locally): {e}")
        return True  # not a hard failure when developing offline
    return False


def main() -> int:
    print("=" * 60)
    print("Counta pre-flight / update contract")
    print("=" * 60)

    checks = [
        ("Python syntax", check_python_syntax),
        ("Unit tests", check_tests),
        ("i18n linter", check_i18n),
        ("JS syntax", check_js_syntax),
        ("Local healthz", check_healthz),
    ]

    failed: list[str] = []
    for name, fn in checks:
        try:
            if not fn():
                failed.append(name)
        except Exception as e:
            print(f"EXCEPTION in {name}: {e}")
            failed.append(name)

    print("\n" + "=" * 60)
    if failed:
        print(f"FAIL: {', '.join(failed)}")
        print("Deploy / push is NOT allowed until fixed.")
        return 1
    print("PASS — all checks green.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
