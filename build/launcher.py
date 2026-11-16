"""VideoSift launcher.

The EXE built from this file only contains Python + PySide6.
The real program lives in <ROOT>\\app\\*.py and is replaced by update packages:
drop  vx.y.z_Update.zip  into  <ROOT>\\UPDATE\\  and start the EXE.
"""
import os, sys, json, shutil, zipfile, runpy, time, traceback, re
from pathlib import Path

import _deps  # noqa: F401  (forces PyInstaller to bundle every runtime dependency)

LAUNCHER_VERSION = 2          # V0.6.01：設環境變數 SC_LAUNCHER，程式才知道要不要換外殼（雲端更新）
ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
UPDATE_DIR = ROOT / "UPDATE"
BACKUP_DIR = ROOT / "app_backup"
LOG_DIR = ROOT / "LOG"


def log(msg):
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with (LOG_DIR / "update_log.txt").open("a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def msgbox(text, title="VideoSift", error=False):
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, str(text), title, 0x10 if error else 0x40)
    except Exception:
        print(title, text)


def vkey(name):
    return tuple(int(x) for x in re.findall(r"\d+", name)) or (0,)


def apply_updates():
    """Apply every UPDATE\\*.zip in version order. Returns backup path of the first applied update."""
    if not UPDATE_DIR.exists():
        return None, []
    zips = sorted(UPDATE_DIR.glob("*.zip"), key=lambda p: vkey(p.stem))
    first_backup = None; applied = []
    for z in zips:
        backup = None
        try:
            with zipfile.ZipFile(z) as zf:
                manifest = {}
                if "manifest.json" in zf.namelist():
                    manifest = json.loads(zf.read("manifest.json").decode("utf-8-sig"))
                need = int(manifest.get("requires_launcher", 1))
                if need > LAUNCHER_VERSION:
                    msgbox(f"更新檔 {z.name} 需要新版啟動器（EXE），請使用完整安裝包更新。\n\n目前程式維持原版本。", error=True)
                    log(f"SKIP {z.name}: requires launcher {need} > {LAUNCHER_VERSION}")
                    continue
                members = [m for m in zf.namelist() if m.startswith("app/") and not m.endswith("/")]
                for m in members:
                    if ".." in Path(m).parts or Path(m).is_absolute():
                        raise RuntimeError(f"unsafe path in update: {m}")
                if not members:
                    raise RuntimeError("update package has no app/ files")
                stamp = time.strftime("%Y%m%d_%H%M%S")
                backup = BACKUP_DIR / f"{stamp}_before_{z.stem}"
                if APP_DIR.exists():
                    shutil.copytree(APP_DIR, backup, ignore=shutil.ignore_patterns("__pycache__"))
                first_backup = first_backup or backup
                for m in members:
                    dest = ROOT / m
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    tmp = dest.with_suffix(dest.suffix + ".new")
                    tmp.write_bytes(zf.read(m))
                    os.replace(tmp, dest)
                shutil.rmtree(APP_DIR / "__pycache__", ignore_errors=True)
            done = UPDATE_DIR / "applied"; done.mkdir(exist_ok=True)
            os.replace(z, done / z.name)
            applied.append(manifest.get("version") or z.stem)
            log(f"APPLIED {z.name} (backup {first_backup})")
        except Exception as e:
            log(f"FAILED {z.name}: {e}")
            if backup is not None and backup.exists():
                try: restore(backup); log(f"RESTORED {backup} after failed {z.name}")
                except Exception as e2: log(f"RESTORE FAILED: {e2}")
            msgbox(f"套用更新 {z.name} 失敗：\n{e}\n\n程式維持原版本。", error=True)
    # keep only the 5 newest backups
    try:
        olds = sorted(BACKUP_DIR.iterdir(), key=lambda p: p.name)[:-5]
        for d in olds: shutil.rmtree(d, ignore_errors=True)
    except Exception:
        pass
    return first_backup, applied


def restore(backup):
    shutil.rmtree(APP_DIR, ignore_errors=True)
    shutil.copytree(backup, APP_DIR)


def run_app():
    os.environ["SC_LAUNCHER"] = str(LAUNCHER_VERSION)
    sys.path.insert(0, str(APP_DIR))
    for mod in ("app", "core"):
        sys.modules.pop(mod, None)
    runpy.run_path(str(APP_DIR / "app.py"), run_name="__main__")


def cleanup_shell():
    """上次換外殼留下的舊檔（換好之後就不需要了）."""
    for n in ("_internal_old", "UPDATE/shell_new"):
        shutil.rmtree(ROOT / n, ignore_errors=True)
    for n in ("VideoSift.exe.old",):
        try: (ROOT / n).unlink()
        except Exception: pass


def main():
    os.chdir(ROOT)
    cleanup_shell()
    backup, applied = apply_updates()
    if not (APP_DIR / "app.py").exists():
        msgbox(f"找不到程式檔：\n{APP_DIR / 'app.py'}\n\n請重新安裝或放入更新檔。", error=True)
        return 1
    if applied:
        msgbox("已更新至：" + "、".join(applied) + "\n\n你的資料（Data）未受影響。")
    try:
        run_app()
    except SystemExit as e:
        return e.code or 0
    except Exception:
        err = traceback.format_exc(); log("START FAILED\n" + err)
        if backup is not None:
            restore(backup); log(f"ROLLED BACK to {backup}")
            msgbox("新版本啟動失敗，已自動退回更新前的版本。\n\n詳細錯誤記錄在 LOG\\update_log.txt。", error=True)
            os.execv(sys.executable, [sys.executable] + sys.argv[1:]) if getattr(sys, "frozen", False) else None
        else:
            msgbox("程式啟動失敗，詳細錯誤記錄在 LOG\\update_log.txt。\n\n" + err[-800:], error=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
