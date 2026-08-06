# 🥤 一沐日雲端點餐與 MCP 系統 (mcp-drink-main) - 專案規則與規格

本檔案為 AI 助理 (Agent) 的開發規格指南與工作規則。在進行任何開發、修復與功能新增前，AI 務必詳閱並遵守本規格。

---

## 🏗️ 專案簡介
本專案是一個整合 **Streamlit 網頁應用**、**Google Cloud Firestore (Firebase)** 與 **Model Context Protocol (MCP)** 的一沐日雲端點餐與訂單管理助理系統。
提供傳統的網頁 UI 與 AI 對話雙重點餐模式，能自動比對口語輸入的品項、進行規格與金額驗證，並提供訂單重複篩選與統計。

---

## 🎨 語系與風格
1. **語系限制**：
   - 與使用者的所有溝通對話、程式檔案中的命名、註解或日誌，均使用 **繁體中文**。
2. **設計美學**：
   - **PWA 前端介面**：使用極致現代的 **毛玻璃美學** (Glassmorphism)，強調精緻、簡潔與高質感的 UI。
   - **Streamlit 管理介面**：維持簡潔、直覺的純文字與表格報表排版，並於側邊欄提供模型與金鑰控制。

---

## ⚙️ 技術架構
1. **後端與 MCP 協定** (基於 FastMCP 框架 - [mcp_server.py](file:///c:/aiTest/mcp-drink-main/mcp_server.py))：
   - 提供 `get_menu` (菜單查詢)、`place_drink_order` (執行點餐)、`list_recent_orders` (列出最新 10 筆訂單)、`find_duplicate_orders_by_name` (查詢個人重複訂單)、`search_all_duplicates` (掃描所有重複訂單)、`update_drink_order` / `delete_drink_order` (修刪訂單) 等工具。
2. **資料庫橋樑** ([db_logic.py](file:///c:/aiTest/mcp-drink-main/db_logic.py))：
   - 以單例模式 (Singleton) 封裝 Firestore Client 避免連線過載。
   - 透過讀取專案根目錄下的 [firebase-adminsdk.json](file:///c:/aiTest/mcp-drink-main/firebase-adminsdk.json) 進行安全性憑證登入。
3. **驗證與比對邏輯** ([order_utils.py](file:///c:/aiTest/mcp-drink-main/order_utils.py))：
   - 採用 **RapidFuzz 模糊比對演算法** 來自動匹配口語輸入的飲品名稱（例如：「粉粿檸檬」比對出「粉粿桂花檸檬」）。
   - 嚴格校驗甜度與冰量規範 (`validate_spec`)，點餐時若規格資訊不足須主動詢問。
4. **前端介面**：
   - PWA 極致毛玻璃美學版 (Port 8000)：由 [index.html](file:///c:/aiTest/mcp-drink-main/index.html)、[app.js](file:///c:/aiTest/mcp-drink-main/app.js) 及 [style.css](file:///c:/aiTest/mcp-drink-main/style.css) 組成，以 `python -m http.server 8000` 執行。
   - Streamlit 後端管理版 (Port 8501)：由 [drink_app.py](file:///c:/aiTest/mcp-drink-main/drink_app.py) 提供，以 `streamlit run drink_app.py` 執行。

---

## 🔑 金鑰與環境配置
* **依賴工具**：使用 `uv` 進行 Python 套件與虛擬環境管理（建議使用 Python 3.13 以上）。
* **API 金鑰**：AI 助理的金鑰設定於 [.streamlit/secrets.toml](file:///c:/aiTest/mcp-drink-main/.streamlit/secrets.toml)。本地 Ollama 模式則免金鑰，優先建議使用 `gemma4` 模型。

---

## 📈 開發進度
- [x] 基於 FastMCP 點餐伺服器工具開發 ([mcp_server.py](file:///c:/aiTest/mcp-drink-main/mcp_server.py))
- [x] Firestore 單例資料庫與橋樑串接 ([db_logic.py](file:///c:/aiTest/mcp-drink-main/db_logic.py))
- [x] RapidFuzz 模糊比對菜單與規格驗證 ([order_utils.py](file:///c:/aiTest/mcp-drink-main/order_utils.py))
- [x] 修正 MCP 修改功能因 Pydantic 類型不相容導致之 Crash (改以 `Optional` 宣告)
- [x] 精緻毛玻璃視覺 PWA 點餐前端頁面 ([index.html](file:///c:/aiTest/mcp-drink-main/index.html), [app.js](file:///c:/aiTest/mcp-drink-main/app.js), [style.css](file:///c:/aiTest/mcp-drink-main/style.css))
- [x] Streamlit 多 AI/本地雙模式控制後端 APP ([drink_app.py](file:///c:/aiTest/mcp-drink-main/drink_app.py))

---

## ⚠️ 開發守則與注意事項
1. **憑證安全規範**：
   - 嚴禁將 `firebase-adminsdk.json` 金鑰檔或任何含有明文 API Key 的設定檔提交至 Git 遠端倉庫。
2. **Pydantic 參數相容性**：
   - 在修改 [mcp_server.py](file:///c:/aiTest/mcp-drink-main/mcp_server.py) 中的工具參數時，任何非必填或可為空之欄位，必須顯式標記為 `Optional[type] = None`（如 `spec: Optional[str] = None`），否則會觸發 Pydantic 驗證錯誤。
3. **驗證優先**：
   - 所有點餐修改均應通過 [order_utils.py](file:///c:/aiTest/mcp-drink-main/order_utils.py) 的 `validate_spec` 驗證與 `calculate_price` 計價，確保與一沐日官方菜單數據一致。

---

## 🔄 開工與收工自動檢核
* **開工自動檢核**：
  當使用者說「開工」或進行類似工作啟動的宣告時，AI 助理應自動：
  1. 執行 `git fetch` 檢查遠端倉庫是否有更新。
  2. 執行 `git status` 檢查本地與遠端的分支同步狀態。
  3. 報告檢核結果給使用者。如果有更新，詢問使用者是否要下載（進行 `git pull`）。
* **收工自動檢查**：
  當使用者說「收工」或進行工作結束的宣告時，AI 助理應自動：
  1. 執行 `git status` 檢查本地是否有尚未提交 (uncommitted) 的修改或未追蹤的檔案。
  2. 報告檢查結果給使用者。如果有變更，詢問使用者是否需要為其進行 `git add`、`git commit` 與 `git push` 上傳至 GitHub。
