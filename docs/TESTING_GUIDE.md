# 🧪 測試指南：驗證 MCP Server 修復

## 📋 目錄
1. [環境檢查](#環境檢查)
2. [單元測試](#單元測試)
3. [集成測試](#集成測試)
4. [UI 測試](#ui-測試)
5. [故障排除](#故障排除)

---

## 環境檢查

### 1️⃣ 驗證 Python 版本
```bash
python --version
# 預期輸出：Python 3.8 或更高版本
```

### 2️⃣ 驗證必要套件
```bash
pip list | grep -E "fastmcp|pydantic|openai"

# 預期輸出類似：
# fastmcp            0.x.x
# pydantic           2.x.x
# openai             1.x.x
```

### 3️⃣ 檢查檔案位置
```bash
# 確認以下檔案存在
ls -l /path/to/mcp_server.py
ls -l /path/to/db_logic.py
ls -l /path/to/order_utils.py
ls -l /path/to/drink_app.py
```

---

## 單元測試

### 測試 1：型別註解正確性

**目的：** 驗證 Pydantic 能夠正確驗證函數簽名

**測試指令：**
```python
from pydantic import BaseModel, ValidationError
from typing import Optional

# 模擬 FastMCP 的驗證行為
class UpdateOrderByNameRequest(BaseModel):
    name: str
    drink_name: Optional[str] = None
    spec: Optional[str] = None
    topping: Optional[str] = None

# ✅ 應該通過：完整資訊
try:
    req = UpdateOrderByNameRequest(
        name="國童哥",
        drink_name="烏龍綠鮮奶茶",
        spec="五分甜/少冰",
        topping="粉粿"
    )
    print("✅ 完整資訊測試通過")
except ValidationError as e:
    print(f"❌ 測試失敗：{e}")

# ✅ 應該通過：部分資訊（新增的關鍵修復）
try:
    req = UpdateOrderByNameRequest(
        name="國童哥",
        drink_name="烏龍綠鮮奶茶",
        spec=None,      # ← 關鍵：之前會失敗，現在應該通過
        topping=None    # ← 關鍵：之前會失敗，現在應該通過
    )
    print("✅ 部分資訊測試通過（修復驗證！）")
except ValidationError as e:
    print(f"❌ 測試失敗：{e}")

# ✅ 應該通過：最小資訊
try:
    req = UpdateOrderByNameRequest(
        name="國童哥"
    )
    print("✅ 最小資訊測試通過")
except ValidationError as e:
    print(f"❌ 測試失敗：{e}")

# ❌ 應該失敗：缺少必要欄位
try:
    req = UpdateOrderByNameRequest(
        drink_name="烏龍綠鮮奶茶"
        # 缺少 name，這是必要的
    )
    print("❌ 缺少必要欄位卻通過了，測試失敗")
except ValidationError as e:
    print("✅ 正確拒絕缺少必要欄位的請求")
```

**預期結果：**
```
✅ 完整資訊測試通過
✅ 部分資訊測試通過（修復驗證！）
✅ 最小資訊測試通過
✅ 正確拒絕缺少必要欄位的請求
```

---

### 測試 2：None 值處理邏輯

**目的：** 驗證函數正確處理 `None` 值和「其餘不變」邏輯

**測試指令（僅邏輯驗證）：**
```python
# 模擬現有訂單資料
existing_order = {
    "name": "國童哥",
    "item": "檸檬綠茶",
    "spec": "三分甜/微冰",
    "toppings": "無",
    "price": 50
}

# 模擬修改請求
modification = {
    "name": "國童哥",
    "drink_name": "烏龍綠鮮奶茶",  # 只改飲料
    "spec": None,                      # 保持原樣
    "topping": None                    # 保持原樣
}

# 驗證邏輯
def test_partial_update(existing, mods):
    final_drink = mods["drink_name"] if mods["drink_name"] else existing.get("item")
    final_spec = mods["spec"] if mods["spec"] else existing.get("spec")
    final_topping = mods["topping"] if mods["topping"] else existing.get("toppings", "無")
    
    return {
        "item": final_drink,
        "spec": final_spec,
        "toppings": final_topping
    }

result = test_partial_update(existing_order, modification)

# 驗證：只有飲料改變，其他保持原樣
assert result["item"] == "烏龍綠鮮奶茶", "✅ 飲料正確更新"
assert result["spec"] == "三分甜/微冰", "✅ 規格保持原樣"
assert result["toppings"] == "無", "✅ 加料保持原樣"

print("✅ None 值邏輯測試通過：其餘不變功能正常")
```

**預期結果：**
```
✅ None 值邏輯測試通過：其餘不變功能正常
```

---

## 集成測試

### 測試 3：MCP 伺服器啟動

**目的：** 驗證修復的代碼能正確啟動

**測試步驟：**

1. **在新終端啟動伺服器：**
```bash
cd /path/to/project
python mcp_server.py
```

2. **檢查輸出（應該看到類似內容）：**
```
Starting Drink-Assistant MCP Server...
[INFO] FastMCP Server initialized
[INFO] Listening on stdio...
```

3. **預期行為：**
   - ✅ 沒有 import 錯誤
   - ✅ 沒有 type validation 錯誤
   - ✅ 伺服器保持運行狀態

4. **如果有錯誤，檢查：**
   - 是否導入了 `Optional` 類型？
   - 所有函數簽名是否都用了 `Optional[str]`？

---

### 測試 4：工具方法呼叫模擬

**目的：** 驗證 Streamlit 可以正確呼叫 MCP 工具

**測試代碼（在 Streamlit 環境中）：**

```python
# 在 drink_app.py 中添加測試代碼
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_mcp_tools():
    """測試所有修復的工具"""
    
    mcp_server_params = StdioServerParameters(
        command=r"C:\aiTest\mcp-drink-main\.venv\Scripts\python.exe",
        args=[r"C:\aiTest\mcp-drink-main\mcp_server.py"],
        env=None
    )
    
    async with stdio_client(mcp_server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # 測試 1：查看菜單
            print("\n📋 測試 1：查看菜單")
            try:
                result = await session.call_tool("get_menu", arguments={})
                print("✅ get_menu 工具成功呼叫")
                print(result.content[0].text[:100])  # 印出前 100 字
            except Exception as e:
                print(f"❌ 失敗：{e}")
            
            # 測試 2：修改訂單（關鍵測試）
            print("\n📝 測試 2：修改訂單（部分欄位）")
            try:
                result = await session.call_tool("update_order_by_name", arguments={
                    "name": "國童哥",
                    "drink_name": "烏龍綠鮮奶茶",
                    "spec": None,        # ← 關鍵修復：應該接受 None
                    "topping": None      # ← 關鍵修復：應該接受 None
                })
                print("✅ update_order_by_name 工具成功呼叫")
                print(result.content[0].text)
            except Exception as e:
                print(f"❌ 失敗：{e}")
                print("⚠️ 這表示型別註解修復可能沒有正確應用")

# 在終端運行
asyncio.run(test_mcp_tools())
```

**預期結果：**
```
📋 測試 1：查看菜單
✅ get_menu 工具成功呼叫
📋 一沐日 完整飲品菜單：

【茶飲系列】
...

📝 測試 2：修改訂單（部分欄位）
✅ update_order_by_name 工具成功呼叫
✅ 已成功修改 國童哥 的訂單內容。
```

---

## UI 測試

### 測試 5：Streamlit 修改訂單流程

**目的：** 在實際 UI 中測試修改訂單功能

**步驟：**

1. **啟動 Streamlit 應用：**
```bash
streamlit run drink_app.py
```

2. **測試場景 A：查看現有訂單**
   - ✅ 應該在「已訂購清冊匯總」看到訂單列表
   - ✅ 每筆訂單都有「🛠️ 修改」按鈕

3. **測試場景 B：修改訂單（只改飲料）**
   - 點擊「🛠️ 修改」按鈕
   - 更改「飲品」
   - 保持「甜度」和「冰量」不變
   - 點擊「💾 儲存修改」
   - ✅ 應該看到 `✅ 同步完成！` 消息
   - ✅ 訂單應該更新，其他欄位保持原樣

4. **測試場景 C：AI 助手修改訂單**
   - 在側邊欄「🤖 飲品小助手」輸入：
     ```
     國童哥要把飲料改為烏龍綠鮮奶茶，其餘不變
     ```
   - ✅ 應該看到：`✅ 已成功修改 國童哥 的訂單內容。`
   - ✅ 沒有驗證錯誤訊息

5. **測試場景 D：刪除訂單**
   - 點擊「🗑️ 刪除」按鈕
   - ✅ 訂單應該被刪除

### 預期結果檢查清單

```
[ ] get_menu 呼叫正常
[ ] place_drink_order 呼叫正常
[ ] update_order_by_name 呼叫正常（之前會失敗）
[ ] delete_order_by_name 呼叫正常
[ ] 沒有「validation error」訊息
[ ] 修改訂單「其餘不變」功能正常
[ ] Streamlit UI 更新順暢
[ ] Firebase 資料同步正確
```

---

## 故障排除

### ❌ 仍然收到驗證錯誤

**症狀：**
```
2 validation errors for call[update_order_by_name]
spec input should be a valid string
```

**診斷步驟：**

1. **檢查檔案是否真的被更新了：**
```bash
grep -n "from typing import Optional" mcp_server.py
# 應該看到有一行這樣的導入
```

2. **檢查函數簽名：**
```bash
grep -n "def update_order_by_name" mcp_server.py
# 應該看到：
# def update_order_by_name(name: str, drink_name: Optional[str] = None, ...
```

3. **確認 MCP 伺服器已重啟：**
   - 關閉 Streamlit 應用
   - 終止 MCP 伺服器進程（如果正在運行）
   - 重新啟動應用

4. **檢查是否有快取問題：**
```bash
# 清除 Python 快取
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type f -name "*.pyc" -delete

# 重新啟動應用
streamlit run drink_app.py
```

---

### ❌ 模組導入失敗

**症狀：**
```
ModuleNotFoundError: No module named 'db_logic'
```

**解決步驟：**

1. **確認所有必要檔案在同一目錄：**
```bash
ls -la
# 應該看到：
# mcp_server.py
# db_logic.py
# order_utils.py
# drink_app.py
```

2. **檢查 Python 路徑：**
```bash
python -c "import sys; print('\n'.join(sys.path))"
# 確認當前目錄在路徑中
```

---

### ❌ Ollama 連線失敗

**症狀：**
```
本地模型調用失敗: Connection refused
```

**解決步驟：**

1. **檢查 Ollama 是否運行：**
```bash
curl http://localhost:11434/api/tags
# 應該返回可用模型列表
```

2. **如果 Ollama 沒運行，啟動它：**
```bash
# Windows
ollama serve

# 或用 WSL2
wsl ollama serve
```

---

## ✅ 成功驗證清單

使用這個清單確認修復成功：

```
基本檢查
[ ] Python 版本 >= 3.8
[ ] 安裝了 fastmcp, pydantic, openai
[ ] 所有必要的 .py 檔案都存在

型別註解修復
[ ] mcp_server.py 導入了 Optional
[ ] update_order_by_name 使用 Optional[str]
[ ] update_drink_order 使用 Optional[str]

單元測試
[ ] Pydantic 驗證測試通過
[ ] None 值邏輯測試通過

集成測試
[ ] MCP 伺服器成功啟動
[ ] update_order_by_name 工具呼叫成功
[ ] 沒有驗證錯誤

UI 測試
[ ] 修改訂單功能正常
[ ] 其餘不變邏輯正確
[ ] AI 助手修改訂單成功
[ ] 沒有「validation error」訊息出現

資料驗證
[ ] Firebase 正確同步修改
[ ] CSV 匯出資料正確
[ ] 所有欄位都完整
```

---

## 📞 如需幫助

如果測試失敗，請提供：

1. **完整的錯誤訊息：**
```bash
python mcp_server.py 2>&1 | tee error.log
```

2. **Python 和套件版本：**
```bash
python --version
pip list
```

3. **檔案內容驗證：**
```bash
head -20 mcp_server.py
grep "Optional" mcp_server.py
```

---

**最後更新：** 2024
**修復版本：** v2.0
**測試涵蓋率：** 核心功能 ✅
