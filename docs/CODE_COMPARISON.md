# 🔀 程式碼對比：修復前後

## 🔴 問題 1：update_order_by_name 函數簽名

### ❌ 修復前（有問題）
```python
def update_order_by_name(name: str, drink_name: str = None, spec: str = None, topping: str = None) -> str:
    """根據姓名修改訂單內容。"""
```

**問題：**
- 類型註解說 `spec: str` 但預設值是 `None`
- Pydantic 看到類型 `str` 卻收到 `None`，產生驗證錯誤
- 錯誤訊息：`spec input should be a valid string [type=string_type, input_value=None, input_type=NoneType]`

### ✅ 修復後（正確）
```python
from typing import Optional

def update_order_by_name(name: str, drink_name: Optional[str] = None, spec: Optional[str] = None, topping: Optional[str] = None) -> str:
    """根據姓名修改訂單內容。
    參數設為選填（None）以處理使用者說「其餘不變」的情況。
    """
```

**修復方式：**
- 導入 `Optional` 類型
- `Optional[str]` 表示「字串或 None」，符合預設值
- Pydantic 現在可以驗證通過

---

## 🔴 問題 2：update_drink_order 函數簽名

### ❌ 修復前（有問題）
```python
def update_drink_order(doc_id: str, name: str = None, drink_name: str = None, spec: str = None, topping: str = None):
    """修改已存在的訂單。當使用者提供訂單 ID 並要求更改內容時使用。"""
    update_data = {}
    
    # ... 驗證邏輯 ...
    # 呼叫 db_logic.py 中的 update 行為
    result = db.firebase_bridge(action="update", doc_id=doc_id, data=update_data)
```

**問題：**
- 所有選填參數都有類型不匹配的問題
- 邏輯不夠清晰：什麼時候應該計算價格？什麼時候應該更新？

### ✅ 修復後（正確且邏輯清晰）
```python
from typing import Optional

def update_drink_order(doc_id: str, name: Optional[str] = None, drink_name: Optional[str] = None, 
                       spec: Optional[str] = None, topping: Optional[str] = None):
    """修改已存在的訂單。當使用者提供訂單 ID 並要求更改內容時使用。
    - doc_id: 訂單的唯一 ID (從清單取得)。
    - 其他參數與點餐工具相同，僅輸入需要修改的部分。
    """
    update_data = {}
    
    # 1. 飲品名稱模糊比對與價格獲取
    if drink_name:  # ✅ 只在有提供時才處理
        correct_drink, _ = utils.get_drink_info(drink_name)
        if not correct_drink:
            return f"❌ 找不到品項 '{drink_name}'，請確認名稱是否正確。..."
    else:
        correct_drink = None  # ✅ 明確設為 None

    # 2. 規格字眼強制檢查
    if spec and not utils.validate_spec(spec):  # ✅ 有條件檢查
        return f"⚠️ 規格 '{spec}' 資訊不全。..."

    # 3. 加料資訊校正
    correct_topping = None  # ✅ 初始為 None
    if topping and topping != "無":
        match_t, _ = utils.get_topping_info(topping)
        correct_topping = match_t if match_t else "無"

    # 4. 只有當飲品與加料都有值時才計算 ✅ 新增的邏輯檢查
    total_price = None
    if correct_drink and correct_topping is not None:
        total_price = utils.calculate_price(correct_drink, correct_topping)

    # 5. 打包訂單資料 (只包含提供的欄位) ✅ 改進
    if name:
        update_data["name"] = name
    if correct_drink:
        update_data["item"] = correct_drink
    if spec:
        update_data["spec"] = spec
    if correct_topping is not None:
        update_data["toppings"] = correct_topping
    if total_price is not None:
        update_data["price"] = total_price
    
    update_data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 6. 透過 db_logic 更新雲端
    if not update_data:  # ✅ 檢查是否有東西要更新
        return "ℹ️ 沒有提供任何要修改的資訊。"

    result = db.firebase_bridge(action="update", doc_id=doc_id, data=update_data)
    
    if result:
        return f"✅ 訂單 {doc_id} 已成功更新。"
    else:
        return "❌ 修改失敗，請確認訂單 ID 是否正確。"
```

---

## 🔴 問題 3：update_order_by_name 邏輯優化

### ❌ 修復前（邏輯有漏洞）
```python
# 3. 準備更新資料 (若參數為 None 則沿用舊資料)
final_drink = drink_name if drink_name else existing_data.get("item")
final_spec = spec if spec else existing_data.get("spec")
final_topping = topping if topping else existing_data.get("toppings", "無")
if topping != "無":  # ❌ 問題：topping 可能為 None，不應該直接比較
    match_t, _ = utils.get_topping_info(topping)
    final_topping = match_t if match_t else "無"

# 以下省略，但存在相同的驗證與計算邏輯重複問題
```

### ✅ 修復後（邏輯完整）
```python
# 3. 準備更新資料 (若參數為 None 則沿用舊資料)
final_drink = drink_name if drink_name else existing_data.get("item")
final_spec = spec if spec else existing_data.get("spec")
final_topping = topping if topping else existing_data.get("toppings", "無")

# ✅ 改進：先檢查 topping 是否為 None，再比較
if topping and topping != "無":  # ✅ 加上 topping 的存在檢查
    match_t, _ = utils.get_topping_info(topping)
    final_topping = match_t if match_t else "無"

# 驗證飲品名稱與規格
correct_drink, _ = utils.get_drink_info(final_drink)
if not correct_drink:
    return f"❌ 找不到品項 '{final_drink}'。"

if not utils.validate_spec(final_spec):
    return f"⚠️ 規格 '{final_spec}' 格式不正確。"

# 計算新價格
new_price = utils.calculate_price(correct_drink, final_topping)

update_data = {
    "name": name,
    "item": correct_drink,
    "spec": final_spec,
    "toppings": final_topping,
    "price": new_price,
    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
}

# 4. 執行更新
result = db.firebase_bridge(action="update", doc_id=target_id, data=update_data)
```

---

## 📊 修復總結表

| 方面 | 修復前 | 修復後 |
|------|-------|--------|
| **型別註解** | `spec: str = None` ❌ | `spec: Optional[str] = None` ✅ |
| **Pydantic 驗證** | 失敗 ❌ | 通過 ✅ |
| **邏輯安全性** | 有 NoneType 比較錯誤風險 ⚠️ | 完整檢查 ✅ |
| **部分更新支持** | 不清晰 ⚠️ | 明確支持 ✅ |
| **程式碼可讀性** | 中等 | 高 ✅ |
| **錯誤訊息** | 驗證失敗 ❌ | 正常運作 ✅ |

---

## 🧠 核心概念

### 什麼是 Optional？

```python
# ❌ 錯誤：類型說 str，預設值卻是 None
def foo(x: str = None):
    pass

# ✅ 正確：明確說 str 或 None
def foo(x: Optional[str] = None):
    pass

# ✅ 也可以這樣寫（Python 3.10+）
def foo(x: str | None = None):
    pass
```

### 為什麼 Pydantic 會拒絕？

Pydantic 是一個資料驗證庫，它會檢查：
1. 參數類型是否與註解匹配
2. 如果註解只說 `str`，收到 `None` 就會報錯
3. 只有當你說 `Optional[str]` 或 `str | None`，Pydantic 才允許 `None`

這保證了類型安全和資料完整性！

---

**版本：** v2.0 修復版
**日期：** 2024
**相容性：** Python 3.8+
