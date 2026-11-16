# SortCut

影片分級／轉 H.265／整理（FileCompare）／HotZone 工具（Windows，Python 3.11 + PySide6）。

- `app/`：真正的程式（.py），更新包 `SC_V<版本>.zip` 就是這個資料夾。
- `build/`：啟動器（PyInstaller 打包成 `VideoSift.exe`）＋本機一鍵安裝 `build.ps1`。
- `tools/make_release.py`：做 Release 檔案（程式更新包、外殼、完整安裝包、update.json）。
- `.github/workflows/build.yml`：推到 main 就在雲端 Windows 打包、發到 Releases。

## 發新版
1. 改 `app/app.py` 的 `APP_VERSION`，在 `app/CHANGELOG.json` 最上面加這版的說明。
2. 推到 main → Actions 自動打包 → Releases 出現 `v<版本>`。
3. 使用者的 SortCut 會自己看到（開程式 1 分鐘後、之後每 6 小時），按「⬇ 更新」。

啟動器（`build/launcher.py`）有改時，把 `LAUNCHER_VERSION` 加 1，程式就會連 EXE 一起換。
