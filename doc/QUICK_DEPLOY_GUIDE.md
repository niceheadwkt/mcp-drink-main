# ⚡ 快速部署指南：修改重複訂單檢測邏輯

## 📋 修改概述

**原來的邏輯：**
```
重複訂單 = 同一個人 + 飲品相同 + 規格相同 + 加料相同
例：小媚媚的兩筆「烏龍綠鮮奶茶 + 一分甜去冰 + 無」才算重複
```

**新的邏輯：**
```
重複訂單 = 同一個人 + 2筆或以上訂單（不管飲品是否相同）
例：小媚媚、林進源只要有 2 筆訂單，不管喝什麼，都算重複 ✅
```

---

## 🚀 部署方式（選一個）

### 方式 1：直接替換（最簡單，30 秒）⚡

```bash
# 步驟 1：備份原檔案
cp mcp_server.py mcp_server.py.backup

# 步驟 2：用新檔案替換
# 將 mcp_server_FINAL.py 的內容完全複製到 mcp_server.py

# 步驟 3：重啟應用
streamlit run drink_app.py
```

### 方式 2：手動修改（10 分鐘）

如果你只想修改特定函數，按以下步驟操作：

#### 修改點 1：find_duplicate_orders_by_name() 函數

**找到這個函數（第 105 行左右）**

```python
@mcp.tool()
def find_duplicate_orders_by_name(name: str) -> str:
    """..."""
    # 篩選該人名的所有訂單
    person_orders = [...]
    
    # 分析重複訂單 - 按「飲品+規格+加料」組合分組
    order_groups = defaultdict(list)  # ← 刪除這行開始的 5 行
    for order in person_orders:
        signature = f"{order.get('item', '')}|..."
        order_groups[signature].append(order)
    
    # 篩選出重複訂單（相同簽名的超過 1 筆）
    duplicate_groups = {...}  # ← 刪除這行
    
    if not duplicate_groups:  # ← 改為
        return f"✅ {name} 沒有重複訂單，只有 {len(person_orders)} 筆訂單。"
```

**替換為：**

```python
@mcp.tool()
def find_duplicate_orders_by_name(name: str) -> str:
    """
    🔍 搜尋特定人物的重複訂單資料。
    【修改版】只要同一個人有 2+ 筆訂單，都算重複（不管飲品是否相同）
    """
    # 1. 從資料庫獲取所有訂單
    all_orders = db.firebase_bridge(action="fetch")
    if not all_orders:
        return "📭 目前沒有任何訂單。"
    
    # 2. 篩選該人名的所有訂單
    person_orders = []
    if isinstance(all_orders, list):
        person_orders = [o for o in all_orders if o.get("name") == name]
    elif isinstance(all_orders, dict):
        person_orders = [o for o in all_orders.values() if o.get("name") == name]
    
    if not person_orders:
        return f"❌ 找不到名為 '{name}' 的訂單。"
    
    # 3. 【關鍵改動】只檢查訂單數量，不按飲品分組
    if len(person_orders) < 2:
        return f"✅ {name} 沒有重複訂單，只有 {len(person_orders)} 筆訂單。"
    
    # 4. 生成詳細報告
    output = f"🔍 {name} 的重複訂單報告\n"
    output += "="*50 + "\n\n"
    output += f"⚠️ 發現重複！{name} 共有 {len(person_orders)} 筆訂單\n"
    output += f"   其中有 {len(person_orders) - 1} 筆算重複訂單\n\n"
    
    # 5. 列出所有訂單
    output += "📋 所有訂單明細：\n"
    for idx, order in enumerate(person_orders, 1):
        output += f"\n【訂單 {idx}】\n"
        output += f"  🥤 飲品：{order.get('item', '未知')}\n"
        output += f"  🌡️ 規格：{order.get('spec', '未知')}\n"
        output += f"  💎 加料：{order.get('toppings', '無')}\n"
        output += f"  💰 價格：${order.get('price', 0)} 元\n"
        output += f"  📅 時間：{order.get('timestamp', '時間未記錄')} (ID: {order.get('id', 'N/A')})\n"
    
    # 6. 統計信息
    total_price = sum(o.get('price', 0) for o in person_orders)
    output += f"\n📊 統計資訊：\n"
    output += f"  總訂單數：{len(person_orders)} 筆\n"
    output += f"  總金額：${total_price} 元\n"
    output += f"  平均單杯價格：${total_price // len(person_orders)} 元\n"
    
    return output
```

#### 修改點 2：search_all_duplicates() 函數

**找到這個函數（第 170 行左右）**

在 `# 3. 找出有重複訂單的人物` 部分，改為：

```python
# 3. 【關鍵改動】只檢查訂單數量，2+ 就算重複
people_with_duplicates = {}
for name, orders in person_orders.items():
    if len(orders) > 1:  # 只要 2+ 筆就算重複
        people_with_duplicates[name] = {
            "total_orders": len(orders),
            "duplicate_count": len(orders) - 1,  # 重複筆數 = 總筆數 - 1
            "total_price": sum(o.get('price', 0) for o in orders)
        }
```

#### 修改點 3：get_duplicate_statistics() 函數

**找到這個函數（第 229 行左右）**

在 `# 3. 統計數據` 部分，改為：

```python
# 3. 統計數據
total_orders = len(orders_list)
total_people = len(person_orders)

# 【關鍵改動】只要 2+ 筆訂單就算重複
people_with_duplicates = {name: orders for name, orders in person_orders.items() if len(orders) > 1}
people_without_duplicates = {name: orders for name, orders in person_orders.items() if len(orders) == 1}

total_duplicate_orders = sum(len(orders) - 1 for orders in people_with_duplicates.values())
```

---

## ✅ 驗證修改成功

### 測試 1：查詢單人重複訂單

**在 Streamlit 側邊欄試試看：**

```
你說：「搜尋小媚媚有沒有重複訂單」

預期結果：
🔍 小媚媚的重複訂單報告
==================================================
⚠️ 發現重複！小媚媚 共有 2 筆訂單
   其中有 1 筆算重複訂單

📋 所有訂單明細：

【訂單 1】
  🥤 飲品：烏龍綠鮮奶茶
  🌡️ 規格：一分甜去冰
  💎 加料：無
  💰 價格：$60 元
  📅 時間：2024-01-15 14:30:45 (ID: order_123)

【訂單 2】
  🥤 飲品：烏龍綠鮮奶茶
  🌡️ 規格：一分甜去冰
  💎 加料：無
  💰 價格：$60 元
  📅 時間：2024-01-15 14:35:12 (ID: order_124)

📊 統計資訊：
  總訂單數：2 筆
  總金額：$120 元
  平均單杯價格：$60 元
```

### 測試 2：全局掃描重複訂單

**在側邊欄試試看：**

```
你說：「查一下誰有重複訂單」

預期結果：
🔍 全局重複訂單掃描報告
==================================================
共找到 2 個人有重複訂單

1. 👤 小媚媚
   📊 訂單數：2 筆
   ⚠️ 重複筆數：1 筆
   💰 總金額：$120 元
   💡 詢問「搜尋 小媚媚 的重複訂單」可看詳細資訊

2. 👤 林進源
   📊 訂單數：2 筆
   ⚠️ 重複筆數：1 筆
   💰 總金額：$160 元
   💡 詢問「搜尋 林進源 的重複訂單」可看詳細資訊
```

### 測試 3：統計分析

**在側邊欄試試看：**

```
你說：「顯示重複訂單統計」

預期結果：
📊 重複訂單統計報告
==================================================
📈 訂單總數：5 筆
👥 不同客戶：3 人
⚠️ 有重複訂單的客戶：2 人
✅ 只訂過一次的客戶：1 人
📊 有重複客戶佔比：66.7%
🔁 總重複筆數：2 筆
📋 人均訂單數：1.7 筆

🏆 訂單最多的客戶：
   👤 林進源
   📊 訂單數：2 筆
   💰 總消費：$160 元

💡 分析與建議：
   • 大部分客戶都是重複訂購者，這很好！(重複率 67%)
   • 建議：推出會員卡或折扣方案吸引重複購買
```

---

## 🔍 修改前後對比

### 修改前的行為

| 場景 | 結果 |
|------|------|
| 小媚媚訂 2 杯「烏龍綠鮮奶茶」| ✅ 算重複 |
| 小媚媚訂「烏龍綠」+ 「檸檬綠」| ❌ 不算重複 |
| 林進源訂 2 杯不同飲品| ❌ 不算重複 |

### 修改後的行為 ✅

| 場景 | 結果 |
|------|------|
| 小媚媚訂 2 杯「烏龍綠鮮奶茶」| ✅ 算重複 |
| 小媚媚訂「烏龍綠」+ 「檸檬綠」| ✅ 算重複（新！） |
| 林進源訂 2 杯不同飲品| ✅ 算重複（新！） |

---

## 📊 修改的代碼位置

### 三個函數的改動概要

| 函數 | 原始邏輯 | 修改後邏輯 |
|------|--------|----------|
| `find_duplicate_orders_by_name()` | 按飲品簽名分組，找相同簽名的 | 直接檢查 `len(person_orders) < 2` |
| `search_all_duplicates()` | 對每個人按飲品分組統計 | 直接檢查 `len(orders) > 1` |
| `get_duplicate_statistics()` | 統計相同飲品的重複情況 | 統計有多筆訂單的人物佔比 |

---

## 🎯 核心改動

### 移除的代碼片段

```python
# ❌ 被移除的邏輯
signature = f"{order.get('item', '')}|{order.get('spec', '')}|{order.get('toppings', '')}"
order_groups[signature].append(order)
duplicate_groups = {sig: orders for sig, orders in order_groups.items() if len(orders) > 1}
```

### 新增的代碼片段

```python
# ✅ 新邏輯：直接檢查訂單數量
if len(person_orders) < 2:
    return f"✅ {name} 沒有重複訂單..."

if len(orders) > 1:  # 只要 2+ 筆就算重複
    people_with_duplicates[name] = {...}
```

---

## ✨ 修改後的好處

```
✅ 邏輯更簡潔：不再需要複雜的簽名組合
✅ 效能更好：直接檢查訂單數量，無需遍歷
✅ 結果更直觀：一目瞭然地看到「同一個人有多少筆訂單」
✅ 業務邏輯更清晰：「重複客戶」就是「有多筆訂單的客戶」
```

---

## 🐛 常見問題

### Q1：修改後查詢結果會改變嗎？

**A：** 是的，會改變！

- **修改前**：小媚媚訂不同飲品 → 不算重複
- **修改後**：小媚媚訂不同飲品 → 算重複

### Q2：歷史訂單會受影響嗎？

**A：** 不會。只是檢測邏輯改變，歷史資料不變。

### Q3：可以回復到原來的邏輯嗎？

**A：** 可以。用備份檔案 `mcp_server.py.backup` 即可。

---

## 📝 部署清單

```
[ ] 步驟 1：備份原檔案
    cp mcp_server.py mcp_server.py.backup

[ ] 步驟 2：複製新代碼
    將 mcp_server_FINAL.py 的內容複製到 mcp_server.py
    或手動修改三個函數

[ ] 步驟 3：清除快取
    rm -rf __pycache__
    find . -name "*.pyc" -delete

[ ] 步驟 4：重啟應用
    streamlit run drink_app.py

[ ] 步驟 5：測試驗證
    在側邊欄試試「搜尋小媚媚」、「全局掃描」、「統計」

[ ] 步驟 6：確認成功
    結果符合新邏輯（2+ 筆訂單 = 重複）
```

---

## 🎉 完成！

你的飲品點餐系統現在已經按照新的邏輯運作了！

**關鍵改動：**
- ✅ 只要同一個人有 2 筆或以上訂單，都算「重複」
- ✅ 不再區分飲品是否相同
- ✅ 邏輯更簡單、效果更直觀

**測試建議：**
按照上面的「驗證修改成功」部分，在 Streamlit 中試試新功能！

---

**預計部署時間：** 1-10 分鐘（取決於選擇的方式）
**難度等級：** ⭐ 簡單
**風險等級：** 🟢 低（可隨時用備份回復）
