# 新竹桃園招標中工程案（每日自動更新）

## 設定步驟（約 10 分鐘，一次就好）
1. 註冊 / 登入 GitHub，建立新的 **Public** repository（例如 `tender-watch`）。
2. 把這個資料夾的檔案全部上傳（保留 `.github/workflows/daily.yml` 的路徑）。
3. 到 **Actions** 分頁 → 選「每日更新招標清單」→ **Run workflow**，等 2–5 分鐘跑完。
4. 到 **Settings → Pages**：Source 選 *Deploy from a branch*，Branch 選 `main`、資料夾選 `/docs` → Save。
5. 網址會是 `https://你的帳號.github.io/tender-watch/`，之後每天早上 6 點自動更新。

## 調整條件
打開 `update_tenders.py` 最上面的設定區：預算上限、掃描天數、地區關鍵字。
