# nomura-etf-tracker

每天自野村投信官方 API 取得 ETF 完整持股與 NAV，轉成容易讀取的 JSON，並由 GitHub Actions 保存每日快照。目前追蹤 `009821`。

## 資料位置

- 最新資料：`data/009821/latest.json`
- 歷史快照：`data/009821/history/YYYY-MM-DD.json`
- JSON Schema：`schema.json`

每份快照的 `data_date` 同時適用於 NAV 與持股。`previous_nav` 保存前一個官方 NAV，`nav.change` 與 `nav.change_percent` 則由兩日官方 NAV 計算。`portfolio_tables` 保留官方每張持股／資產表的完整欄位與列，不假設所有 ETF 都只有股票。

## 自動更新

`.github/workflows/update.yml` 會在週一至週五台灣時間 06:40 執行，也可在 GitHub 的 **Actions → Update ETF data → Run workflow** 手動觸發。GitHub 排程可能因平台負載稍晚啟動。

程式以臺灣證券交易所官方開休市日曆判定前一個台灣工作日，並只接受該日期的野村資料。若 06:40 尚未發布，會每隔 20 分鐘重試，最多重試 6 次（另加首次執行，共最多 7 次，最晚約 08:40）；成功後立即停止，全部失敗則保留原有 `latest.json` 並將 workflow 標示為失敗。

工作流程會：

1. 執行內建測試。
2. 呼叫 `GetFundNAVList` 取得近期 NAV 日期；若清單為空才使用 `GetFundNAV`。
3. 呼叫 `GetFundAssets`，取得前一個台灣工作日同日的 NAV 與完整持股。
4. 以原子方式寫入 `latest.json` 與當日歷史快照；資料有變更才 commit。

## 本機執行

需要 Python 3.10 以上，不需安裝第三方套件。

```bash
PYTHONPATH=src python -m unittest discover -s tests
PYTHONPATH=src python -m nomura_tracker
```

PowerShell：

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests
python -m nomura_tracker
```

## 加入其他 FundID

將代號加入 `funds.json` 即可；每檔 ETF 會寫入自己的 `data/<FundID>/` 目錄。

## 官方來源

- `GET https://openapi.twse.com.tw/v1/holidaySchedule/holidaySchedule`（台灣開休市日）
- `POST https://www.nomurafunds.com.tw/API/ETFAPI/api/Fund/GetFundAssets`
- `POST https://www.nomurafunds.com.tw/API/ETFAPI/api/Fund/GetFundNAVList`
- `POST https://www.nomurafunds.com.tw/API/ETFAPI/api/Fund/GetFundNAV`（備援）

本專案只整理公開資料，不構成投資建議。API 為野村投信官網使用的公開介面，若官方日後變更欄位或端點，workflow 會失敗並保留上一份有效的 `latest.json`。
