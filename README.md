# 🥤 一沐日雲端點餐與 MCP 系統 (mcp-drink-main)

本專案是一個整合 **Streamlit 網頁介面**、**Google Cloud Firestore (Firebase)** 與 **Model Context Protocol (MCP)** 的智能點餐助理系統。透過本系統，使用者不僅可以使用傳統的網頁 UI 進行點餐與訂單管理，更能直接與 AI 點餐助手進行對話，由 AI 自動解析口語需求並呼叫 MCP 工具完成點餐、修改、刪除或進行重複訂單的篩選與統計。

---

## 🏗️ 核心架構與元件

專案由多個功能模組相互協作而成，主要元件如下：

### 1. 🖥️ Streamlit 網頁應用 - [drink_app.py](file:///c:/aiTest/mcp-drink-main/drink_app.py)
* **角色**：系統的前端視覺化操作介面。
* **功能**：
  - 提供直覺的點餐表單（選擇人名、飲品、甜度冰量、加料）。
  - 即時從雲端 Firestore 載入訂單列表，並支援在網頁上直接「修改」或「刪除」訂單。
  - **多 AI 廠商與雙模式切換側邊欄**：
    - 支援雲端模型（如 Gemini, OpenAI, Claude）與本地 Ollama 模型（如 Gemma 4, Qwen 等）雙模式。
    - **雲端模式**下會自動顯示目前採用的 API 與模型版本。
    - **本地模式**下會自動偵測本地已下載的 Ollama 模型清單並提供下拉選單切換，並優先建議 `gemma4`。
    - 無論雲端或本地，皆可透過 OpenAI 相容協定或 Native SDK 發送對話並在背景安全解析 MCP 工具。

### 2. 🤖 FastMCP 伺服器 - [mcp_server.py](file:///c:/aiTest/mcp-drink-main/mcp_server.py)
* **角色**：基於 Model Context Protocol (MCP) 標準的後端服務。
* **功能**：
  - 註冊並暴露多個點餐工具（Tools）給支援 MCP 的大語言模型（如 Claude Desktop 或內置的 Streamlit AI 助手）。
  - **支援工具清單**：
    - `get_menu`：查詢目前的完整飲品菜單與加料選項。
    - `place_drink_order`：為特定人名點購飲品（會自動驗證甜度冰量與計算金額）。
    - `list_recent_orders`：列出最近的 10 筆訂單。
    - `find_duplicate_orders_by_name`：查詢特定人名的重複訂單。
    - `search_all_duplicates`：搜尋資料庫中所有重複的訂單。
    - `get_duplicate_statistics`：獲取重複點單的統計分析數據。
    - `update_drink_order` / `update_order_by_name`：修改現有訂單資訊。
    - `delete_drink_order` / `delete_order_by_name`：刪除指定訂單。

### 3. 📦 資料庫橋樑 - [db_logic.py](file:///c:/aiTest/mcp-drink-main/db_logic.py)
* **角色**：負責與 Google Cloud Firestore 連線與執行 CRUD 操作。
* **功能**：
  - 以單例模式（Singleton）管理 Firestore Client，避免重複連線。
  - 透過讀取金鑰檔 [firebase-adminsdk.json](file:///c:/aiTest/mcp-drink-main/firebase-adminsdk.json) 進行身份驗證。
  - 提供統一的 `firebase_bridge` 介面，支援 `push` (新增)、`fetch` (讀取)、`update` (修改)、`delete` (刪除) 等底層操作。
  - *備份說明*：專案中亦包含一個備份版本 [db_logic_google.genai.py](file:///c:/aiTest/mcp-drink-main/db_logic_google.genai.py)。

### 4. ⚙️ 點餐工具與數據庫 - [order_utils.py](file:///c:/aiTest/mcp-drink-main/order_utils.py)
* **角色**：管理菜單與驗證逻辑。
* **功能**：
  - 定義「一沐日」官方的飲品菜單數據 `NESTED_MENU` 與加料價格 `TOPPINGS_MENU`。
  - 實作 `get_drink_info` 與 `get_topping_info`：使用 **RapidFuzz 模糊比對演算法**，自動比對口語輸入的飲品名稱（例如：「烏龍綠鮮奶茶」比對出「烏龍綠鮮奶茶」），提升 AI 點單時的精確度與容錯率。
  - 實作 `validate_spec`：嚴格驗證規格是否同時包含「糖度」與「冰量」資訊。
  - 實作 `calculate_price`：依據飲品基本價與加料價格計算總金額。

---

## 🔑 環境準備與設定

本專案需要 Python 3.13 以上環境。在執行本專案前，請務必完成以下設定：

### 1. 安裝套件依賴
建議使用 `uv` 進行依賴管理與執行：
```bash
# 安裝 pyproject.toml 中定義的依賴
uv pip install -r pyproject.toml
```
主要的 Python 套件包括：`fastmcp`、`google-cloud-firestore`、`google-genai`、`rapidfuzz`、`streamlit`、`anthropic` 等。

### 2. Firebase Firestore 金鑰配置
* 請前往 Firebase 控制台下載您的服務帳戶金鑰 JSON 檔案。
* 將其重新命名為 `firebase-adminsdk.json` 並放置於專案根目錄下（即 `c:/aiTest/mcp-drink-main/firebase-adminsdk.json`）。
* 本專案的 [db_logic.py](file:///c:/aiTest/mcp-drink-main/db_logic.py) 將會自動偵測並載入該金鑰。

### 3. API 金鑰配置 (用於 Streamlit UI 內置 AI 助手)
* 請在專案根目錄下建立 `.streamlit` 資料夾，並於其中建立 [secrets.toml](file:///c:/aiTest/mcp-drink-main/.streamlit/secrets.toml) 檔案：
  ```toml
  # 支援配置多個 AI 廠商金鑰，系統會自動依照您在 secrets.toml 中撰寫的 Key 順序來決定預設使用的雲端 AI！
  GEMINI_KEY = "您的_GEMINI_API_KEY"     # 啟用 Gemini
  OPENAI_KEY = "您的_OPENAI_API_KEY"     # 啟用 OpenAI (ChatGPT)
  CLAUDE_KEY = "您的_ANTHROPIC_API_KEY"   # 啟用 Anthropic (Claude)
  ```
* **環境變數支援**：亦支援自動讀取系統環境變數（如 `GOOGLE_API_KEY`、`OPENAI_API_KEY`、`ANTHROPIC_API_KEY`），本地 NB 執行時免填設定檔。
* **本地 Ollama 免金鑰**：若選擇本地 Ollama 模式，則無需配置任何 API 金鑰，只需在本地執行 Ollama (`ollama serve`) 即可。

---

## 🚀 執行與使用指南

### 方式 A：啟動 Streamlit 網頁 UI (推薦)
這是最完整的點餐系統介面。您可以使用以下任一指令啟動：
```powershell
# 透過當前虛擬環境執行 Streamlit (推薦)
.\.venv\Scripts\python.exe -m streamlit run drink_app.py

# 或透過 uv 執行
uv run streamlit run drink_app.py
```
啟動後，瀏覽器會自動開啟 `http://localhost:8501`。您可以在左側或上方看到訂單列表、新增訂單的表單，以及最下方的 **簡易 AI 對話框**。

### 方式 B：將 MCP 伺服器掛載至 Claude Desktop
您可以將 [mcp_server.py](file:///c:/aiTest/mcp-drink-main/mcp_server.py) 設定到 Claude Desktop 的設定檔中，讓您的 Claude 桌面應用程式直接獲得一沐日點餐的能力：

1. 開啟 Claude Desktop 設定檔：
   `C:\Users\ch26788\AppData\Roaming\Claude\claude_desktop_config.json`
2. 在 `mcpServers` 下加入 `drink-server`：
   ```json
   {
     "mcpServers": {
       "drink-server": {
         "command": "C:\\aiTest\\mcp-drink-main\\.venv\\Scripts\\python.exe",
         "args": [
           "C:\\aiTest\\mcp-drink-main\\mcp_server.py"
         ],
         "env": {
           "PYTHONPATH": "C:\\aiTest\\mcp-drink-main"
         }
       }
     }
   }
   ```
3. 重啟 Claude Desktop。在對話框中您應該可以看到 🔧 工具圖標，這代表 Claude 已成功載入一沐日的點餐工具。您可以嘗試輸入：
   - *「透過 drink-server，幫林進源訂一杯粉粿桂花檸檬 無糖去冰 加招牌粉粿」*
   - *「幫我看看最近的訂單」*

---

## 🔧 已知修復與技術細節

在之前的版本中，當透過 MCP 呼叫 `update_order_by_name` 或 `update_drink_order` 時，可能會遇到以下 Pydantic 類型驗證錯誤：
```text
2 validation errors for call[update_order_by_name]
spec input should be a valid string [type=string_type, input_value=None, input_type=NoneType]
```
這是因為參數宣告為 `str`，但預設值為 `None`，導致 Pydantic 在解析引數時產生衝突。目前已全面修復，在 [mcp_server.py](file:///c:/aiTest/mcp-drink-main/mcp_server.py) 中：
* 導入了 `from typing import Optional`。
* 將可能為空之參數型別標記為 `Optional[str]`（例如 `spec: Optional[str] = None`）。
* 對 None 值的傳遞進行了安全過濾，確保資料庫更新時不會以 Null 覆蓋原有欄位。
* 詳細的修復日誌與程式碼對比請參閱 [docs/EXECUTIVE_SUMMARY.md](file:///c:/aiTest/mcp-drink-main/docs/EXECUTIVE_SUMMARY.md) 與 [docs/BUG_FIX_EXPLANATION.md](file:///c:/aiTest/mcp-drink-main/docs/BUG_FIX_EXPLANATION.md)。

---

## 📈 其他實驗性腳本

本工作區亦包含非點餐系統核心的股票爬蟲與繪圖工具：
* **[stockChart.py](file:///c:/aiTest/mcp-drink-main/stockChart.py)**：自 Yahoo 奇摩股市抓取個股（以聯電 2303 為例）的歷史 K 線數據，使用 `matplotlib` 進行中文化折線圖繪製。
* **[stock_crawler_advanced.py](file:///c:/aiTest/mcp-drink-main/stock_crawler_advanced.py)**：進階股票數據爬蟲與分析腳本。
