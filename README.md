# 新竹桃園招標中工程案

## 檔案說明
| 檔案 | 用途 |
|---|---|
| `index.html` | 瀏覽器版網頁：打開時由瀏覽器直接抓資料（備案） |
| `update_tenders.py` | GitHub 每天自動執行的抓資料程式 |
| `template.html` | 自動產生網頁用的版型 |
| `.github/workflows/daily.yml` | 每天早上 6 點自動執行的排程設定 |

執行成功後會自動產生 `docs/`（秒開版網頁）和 `data/`（快取）兩個資料夾。

## 網頁來源設定（Settings → Pages）
- GitHub 自動抓取成功 → 選 `main` + `/docs`（秒開版）
- GitHub 被擋（HTTP 403） → 選 `main` + `/ (root)`（瀏覽器版）

## 調整條件
修改 `update_tenders.py`（GitHub 版）和 `index.html`（瀏覽器版）最上方的設定區。
