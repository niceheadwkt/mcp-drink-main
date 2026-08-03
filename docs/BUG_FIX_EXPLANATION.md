# 🔧 MCP Server 驗證錯誤修復說明

## 📋 問題診斷

**錯誤訊息：**
```
2 validation errors for call[update_order_by_name]
- spec input should be a valid string [type=string_type, input_value=None, input_type=NoneType]
- topping input should be a valid string [type=string_type, input_value=None, input_type=NoneType]
```

## 🎯 根本原因

在原始的 `mcp_server.py` 中，`update_order_by_name` 函數的參數定義如下：

```python
def update_order_by_name(name: str, drink_name: str = None, spec: str = None, topping: str = None) -> str:
```

**問題所在：**
- Pydantic（FastMCP 使用的驗證庫）檢查到參數類型為 `str`
- 但預設值為 `None`，這在類型檢查上產生矛盾
- 當 AI 傳送 `null` 值時（表示「該欄位不變」），驗證失敗

## ✅ 修復方案

### 1. **導入 Optional 類型**
```python
from typing import Optional
```

### 2. **修正所有選填參數的類型註解**

**修復前：**
```python
def update_order_by_name(name: str, drink_name: str = None, spec: str = None, topping: str = None) -> str:
```

**修復後：**
```python
def update_order_by_name(name: str, drink_name: Optional[str] = None, spec: Optional[str] = None, topping: Optional[str] = None) -> str:
```

### 3. **對所有包含選填參數的函數應用修復**

修復的函數：
- ✅ `update_drink_order()` - 所有參數除了 `doc_id` 都改為 `Optional[str]`
- ✅ `update_order_by_name()` - 所有參數除了 `name` 都改為 `Optional[str]`

## 🔍 核心邏輯改進

除了類型註解外，還優化了邏輯以正確處理 `None` 值：

### update_order_by_name 的改進
```python
# 準備更新資料 (若參數為 None 則沿用舊資料)
final_drink = drink_name if drink_name else existing_data.get("item")
final_spec = spec if spec else existing_data.get("spec")
final_topping = topping if topping else existing_data.get("toppings", "無")
```

這確保了：
1. 當使用者只修改某個欄位時（其他傳 `None`），該欄位使用舊資料
2. 支持 `"其餘不變"` 的使用者需求

### update_drink_order 的改進
```python
# 只有當飲品與加料都有值時才計算總價
if correct_drink and correct_topping is not None:
    total_price = utils.calculate_price(correct_drink, correct_topping)

# 只包含提供的欄位
if name:
    update_data["name"] = name
if correct_drink:
    update_data["item"] = correct_drink
# ... 其他欄位
```

這使得：
1. 部分更新不會影響未修改的欄位
2. 邏輯更加清晰和健壯

## 🧪 測試案例

修復後應能成功處理以下情況：

### 案例 1：只修改飲品
```json
{
  "action": "update",
  "name": "國童哥",
  "drink": "烏龍綠鮮奶茶",
  "spec": null,
  "topping": null
}
```
✅ 飲品會更新，規格和加料保持原樣

### 案例 2：只修改規格
```json
{
  "action": "update",
  "name": "國童哥",
  "drink": null,
  "spec": "五分甜/少冰",
  "topping": null
}
```
✅ 規格會更新，其他欄位不變

### 案例 3：完整修改
```json
{
  "action": "update",
  "name": "國童哥",
  "drink": "烏龍綠鮮奶茶",
  "spec": "五分甜/少冰",
  "topping": "粉粿"
}
```
✅ 所有欄位都會更新

## 📝 部署步驟

1. **備份原始檔案**
   ```bash
   cp mcp_server.py mcp_server.py.backup
   ```

2. **使用修復版本覆蓋**
   - 將提供的 `mcp_server.py` 複製到你的專案目錄
   - 確保檔案位置正確

3. **重啟 MCP 伺服器**
   ```bash
   # 關閉現有的 MCP 伺服器程序
   # 重新啟動 Streamlit app 或直接執行
   python mcp_server.py
   ```

4. **驗證修復**
   - 在 Streamlit 側邊欄嘗試修改訂單
   - 測試「其餘不變」的情況
   - 檢查是否還有驗證錯誤

## 🚀 額外建議

### 1. 添加更多日誌
在 `mcp_server.py` 中添加：
```python
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
```

### 2. 驗證函數的防禦性程式設計
```python
if not orders:
    return "📭 目前沒有任何訂單。"

if not target_id:
    return f"❌ 找不到名為 {name} 的訂單。"
```

### 3. 單元測試建議
```python
# 測試 update_order_by_name 處理 None 值
def test_update_with_none_values():
    result = update_order_by_name(
        name="test_user",
        drink_name=None,
        spec=None,
        topping=None
    )
    assert "✅" in result
```

## 📚 相關資源

- **Pydantic 文檔**: https://docs.pydantic.dev/
- **FastMCP 文檔**: 查看你的 FastMCP 版本的官方文檔
- **Python typing 模組**: https://docs.python.org/3/library/typing.html

---

**修復版本：** v2.0
**修改日期：** 2024
**相容性：** Python 3.8+
