# mcp_server.py
from fastmcp import FastMCP
import db_logic as db
import order_utils as utils
from datetime import datetime
import logging
from typing import Optional, List, Dict, Any
from collections import defaultdict

# 初始化 FastMCP
mcp = FastMCP("Drink-Assistant")

@mcp.tool()
def get_menu() -> str:
    """
    查詢目前所有的飲品品項、價格以及可加料的內容。
    當使用者詢問有賣什麼、價格為何、想看菜單或想知道加料選項時，請呼叫此工具。
    """
    output = "📋 一沐日 完整飲品菜單：\n"
    
    # 1. 顯示飲品分類與品項
    for category, items in utils.NESTED_MENU.items():
        output += f"\n【{category}】\n"
        for item, price in items.items():
            output += f"- {item}: ${price}元\n"
    
    output += "\n" + "="*20 + "\n"
    
    # 2. 顯示加料數據
    output += "✨ 可額外加料選項：\n"
    for topping, price in utils.TOPPINGS_MENU.items():
        output += f"- {topping}: +${price}元\n"
        
    return output

@mcp.tool()
def place_drink_order(name: str, drink_name: str, spec: str, topping: str = "無"):
    """
    執行飲品點餐工具。當使用者表達想喝飲料或點餐時，請呼叫此工具。
    
    參數說明：
    - name: 訂購人的姓名 (請務必取得姓名)。
    - drink_name: 飲料名稱 (AI 會自動比對最接近的品項)。
    - spec: 甜度與冰量。必須包含糖度與冰量資訊 (例如：微糖少冰)。
            如果使用者資訊不足，請主動追問。
    - topping: 加料內容 (如：粉粿、寒天)，若無則預設為『無』。
    """
    
    # 1. 飲品名稱模糊比對與價格獲取
    correct_drink, _ = utils.get_drink_info(drink_name)
    if not correct_drink:
        return f"❌ 找不到品項 '{drink_name}'，請確認名稱是否正確。目前的推薦品項可在選單中查看。"

    # 2. 規格字眼強制檢查 (糖/冰 控制)
    if not utils.validate_spec(spec):
        return f"⚠️ 規格 '{spec}' 資訊不全。請明確告知『糖度』與『冰量』（例如：半糖少冰）。"

    # 3. 加料資訊校正
    correct_topping = "無"
    if topping != "無":
        match_t, _ = utils.get_topping_info(topping)
        correct_topping = match_t if match_t else "無"

    # 4. 計算總金額
    total_price = utils.calculate_price(correct_drink, correct_topping)

    # 5. 打包訂單資料 (符合 Firebase 結構)
    order_data = {
        "name": name,
        "item": correct_drink,
        "spec": spec,
        "toppings": correct_topping,
        "price": total_price,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    # 6. 透過 db_logic 寫入雲端
    result = db.firebase_bridge(action="push", data=order_data)

    if result:
        return (f"✅ 成功為 {name} 錄入訂單！\n"
                f"🥤 品項：{correct_drink}\n"
                f"🌡️ 規格：{spec}\n"
                f"💎 加料：{correct_topping}\n"
                f"💰 金額：${total_price}\n"
                f"✨ 資料已同步至雲端表格與 Streamlit APP。")
    else:
        return "❌ 寫入資料庫時發生錯誤，請稍後再試。"

@mcp.tool()
def list_recent_orders():
    """
    列出最近的所有訂單資訊，包含 ID、姓名與品項。
    刪除或修改訂單前，請先呼叫此工具確認 ID。
    """
    orders = db.firebase_bridge(action="fetch")
    if not orders:
        return "📭 目前沒有任何訂單。"
    
    summary = "📋 最新訂單清單：\n"
    for o in orders[:10]: # 只列出最近 10 筆
        summary += f"- ID: {o['id']} | 姓名: {o.get('name')} | 品項: {o.get('item')}\n"
    return summary

@mcp.tool()
def find_duplicate_orders_by_name(name: str) -> str:
    """
    🔍 搜尋特定人物的重複訂單資料。
    當使用者詢問「搜尋個人有重複的資料」、「某人有重複訂單」時，請呼叫此工具。
    
    參數說明：
    - name: 要查詢的人名
    
    功能：
    - 找出該人名下所有訂單
    - 識別重複的訂單（相同飲品、規格、加料）
    - 顯示重複次數和時間戳記
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
    
    # 3. 分析重複訂單 - 按「飲品+規格+加料」組合分組
    order_groups = defaultdict(list)
    for order in person_orders:
        # 建立訂單簽名（用於判斷是否重複）
        signature = f"{order.get('item', '')}|{order.get('spec', '')}|{order.get('toppings', '')}"
        order_groups[signature].append(order)
    
    # 4. 篩選出重複訂單（相同簽名的超過 1 筆）
    duplicate_groups = {sig: orders for sig, orders in order_groups.items() if len(orders) > 1}
    
    if not duplicate_groups:
        return f"✅ {name} 沒有重複的訂單。所有訂單都是獨立的。"
    
    # 5. 生成詳細報告
    output = f"🔍 {name} 的重複訂單報告\n"
    output += "="*40 + "\n\n"
    
    total_duplicates = sum(len(orders) - 1 for orders in duplicate_groups.values())
    output += f"⚠️ 發現 {len(duplicate_groups)} 組重複訂單，共 {total_duplicates} 筆重複\n\n"
    
    for idx, (signature, orders) in enumerate(duplicate_groups.items(), 1):
        item, spec, toppings = signature.split("|")
        output += f"【第 {idx} 組】重複 {len(orders)} 次\n"
        output += f"  🥤 飲品：{item}\n"
        output += f"  🌡️ 規格：{spec}\n"
        output += f"  💎 加料：{toppings}\n"
        output += f"  💰 單杯價格：${orders[0].get('price', 0)} 元\n"
        output += f"  📅 訂單時間：\n"
        
        for i, order in enumerate(orders, 1):
            output += f"     {i}. {order.get('timestamp', '時間未記錄')} (ID: {order.get('id', 'N/A')})\n"
        
        output += "\n"
    
    return output

@mcp.tool()
def search_all_duplicates() -> str:
    """
    🔍 掃描全部訂單，找出所有有重複訂單的人物。
    當使用者詢問「全局搜尋重複」、「誰有重複訂單」時，請呼叫此工具。
    
    功能：
    - 分析所有訂單
    - 找出所有有重複的人物
    - 顯示重複數量統計
    """
    # 1. 從資料庫獲取所有訂單
    all_orders = db.firebase_bridge(action="fetch")
    if not all_orders:
        return "📭 目前沒有任何訂單。"
    
    # 2. 按人名分組
    person_orders = defaultdict(list)
    if isinstance(all_orders, list):
        for order in all_orders:
            name = order.get("name", "匿名")
            person_orders[name].append(order)
    elif isinstance(all_orders, dict):
        for order in all_orders.values():
            name = order.get("name", "匿名")
            person_orders[name].append(order)
    
    # 3. 找出有重複訂單的人物
    people_with_duplicates = {}
    for name, orders in person_orders.items():
        # 按簽名分組
        order_groups = defaultdict(list)
        for order in orders:
            signature = f"{order.get('item', '')}|{order.get('spec', '')}|{order.get('toppings', '')}"
            order_groups[signature].append(order)
        
        # 統計重複次數
        duplicate_count = sum(len(group) - 1 for group in order_groups.values() if len(group) > 1)
        if duplicate_count > 0:
            people_with_duplicates[name] = {
                "total_orders": len(orders),
                "duplicate_count": duplicate_count,
                "duplicate_groups": len([g for g in order_groups.values() if len(g) > 1])
            }
    
    if not people_with_duplicates:
        return "✅ 全部訂單都是獨立的，沒有重複情況。"
    
    # 4. 生成全局報告
    output = "🔍 全局重複訂單掃描報告\n"
    output += "="*40 + "\n\n"
    output += f"共找到 {len(people_with_duplicates)} 個人有重複訂單\n\n"
    
    sorted_people = sorted(people_with_duplicates.items(), 
                          key=lambda x: x[1]["duplicate_count"], 
                          reverse=True)
    
    for idx, (name, stats) in enumerate(sorted_people, 1):
        output += f"{idx}. 👤 {name}\n"
        output += f"   📊 訂單數：{stats['total_orders']} 筆\n"
        output += f"   ⚠️ 重複組數：{stats['duplicate_groups']} 組\n"
        output += f"   🔁 重複筆數：{stats['duplicate_count']} 筆\n"
        output += f"   💡 詢問「搜尋 {name} 的重複訂單」可看詳細資訊\n\n"
    
    return output

@mcp.tool()
def get_duplicate_statistics() -> str:
    """
    📊 取得重複訂單的統計資訊。
    當使用者詢問「重複訂單統計」、「重複率」時，請呼叫此工具。
    
    功能：
    - 計算重複訂單的比例
    - 顯示熱門的重複商品
    - 提供改進建議
    """
    # 1. 獲取所有訂單
    all_orders = db.firebase_bridge(action="fetch")
    if not all_orders:
        return "📭 目前沒有任何訂單。"
    
    # 轉換為列表格式
    orders_list = []
    if isinstance(all_orders, list):
        orders_list = all_orders
    elif isinstance(all_orders, dict):
        orders_list = list(all_orders.values())
    
    # 2. 按人名和簽名分組
    person_signatures = defaultdict(lambda: defaultdict(list))
    for order in orders_list:
        name = order.get("name", "匿名")
        signature = f"{order.get('item', '')}|{order.get('spec', '')}|{order.get('toppings', '')}"
        person_signatures[name][signature].append(order)
    
    # 3. 計算統計數據
    total_orders = len(orders_list)
    total_unique_orders = 0
    total_duplicate_orders = 0
    duplicate_signatures = defaultdict(int)  # 追蹤哪個組合最常重複
    
    for name, sigs in person_signatures.items():
        for sig, orders in sigs.items():
            if len(orders) == 1:
                total_unique_orders += 1
            else:
                total_duplicate_orders += len(orders) - 1
                duplicate_signatures[sig] += len(orders) - 1
    
    # 4. 找出最常見的重複商品
    if duplicate_signatures:
        top_duplicates = sorted(duplicate_signatures.items(), 
                               key=lambda x: x[1], 
                               reverse=True)[:5]
    else:
        top_duplicates = []
    
    # 5. 生成統計報告
    duplicate_rate = (total_duplicate_orders / total_orders * 100) if total_orders > 0 else 0
    
    output = "📊 重複訂單統計報告\n"
    output += "="*40 + "\n\n"
    output += f"📈 訂單總數：{total_orders} 筆\n"
    output += f"✅ 獨立訂單：{total_unique_orders} 筆\n"
    output += f"⚠️ 重複訂單：{total_duplicate_orders} 筆\n"
    output += f"📊 重複率：{duplicate_rate:.1f}%\n\n"
    
    if top_duplicates:
        output += "🔥 最常見的重複商品：\n"
        for idx, (sig, count) in enumerate(top_duplicates, 1):
            item, spec, toppings = sig.split("|")
            output += f"{idx}. {item} ({spec}) 加 {toppings} - 重複 {count} 筆\n"
    else:
        output += "✅ 沒有重複的訂單。\n"
    
    return output

@mcp.tool()
def update_drink_order(doc_id: str, name: Optional[str] = None, drink_name: Optional[str] = None, spec: Optional[str] = None, topping: Optional[str] = None):
    """
    修改已存在的訂單。當使用者提供訂單 ID 並要求更改內容時使用。
    - doc_id: 訂單的唯一 ID (從清單取得)。
    - 其他參數與點餐工具相同，僅輸入需要修改的部分。
    """
    update_data = {}
    
    # 1. 飲品名稱模糊比對與價格獲取
    if drink_name:
        correct_drink, _ = utils.get_drink_info(drink_name)
        if not correct_drink:
            return f"❌ 找不到品項 '{drink_name}'，請確認名稱是否正確。目前的推薦品項可在選單中查看。"
    else:
        correct_drink = None

    # 2. 規格字眼強制檢查 (糖/冰 控制)
    if spec and not utils.validate_spec(spec):
        return f"⚠️ 規格 '{spec}' 資訊不全。請明確告知『糖度』與『冰量』（例如：半糖少冰）。"

    # 3. 加料資訊校正
    correct_topping = None
    if topping and topping != "無":
        match_t, _ = utils.get_topping_info(topping)
        correct_topping = match_t if match_t else "無"

    # 4. 計算總金額 (只有當飲品與加料都有值時才計算)
    total_price = None
    if correct_drink and correct_topping is not None:
        total_price = utils.calculate_price(correct_drink, correct_topping)

    # 5. 打包訂單資料 (符合 Firebase 結構，只包含提供的欄位)
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
    if not update_data:
        return "ℹ️ 沒有提供任何要修改的資訊。"

    # 呼叫 db_logic.py 中的 update 行為
    result = db.firebase_bridge(action="update", doc_id=doc_id, data=update_data)
    
    if result:
        return f"✅ 訂單 {doc_id} 已成功更新。"
    else:
        return "❌ 修改失敗，請確認訂單 ID 是否正確。"
        
@mcp.tool()
def update_order_by_name(name: str, drink_name: Optional[str] = None, spec: Optional[str] = None, topping: Optional[str] = None) -> str:
    """
    根據姓名修改訂單內容。
    參數設為選填（None）以處理使用者說「其餘不變」的情況。
    """
    # 1. 先從資料庫抓取所有訂單
    orders = db.firebase_bridge("fetch") 
    target_id = None
    existing_data = None

    # 2. 尋找匹配該姓名的訂單
    if isinstance(orders, list):
        for o in orders:
            if o.get("name") == name:
                target_id = o.get("id")
                existing_data = o
                break
    elif isinstance(orders, dict):
        for doc_id, data in orders.items():
            if data.get("name") == name:
                target_id = doc_id
                existing_data = data
                break
            
    if not target_id:
        return f"❌ 找不到名為 {name} 的訂單。"

    # 3. 準備更新資料 (若參數為 None 則沿用舊資料)
    final_drink = drink_name if drink_name else existing_data.get("item")
    final_spec = spec if spec else existing_data.get("spec")
    final_topping = topping if topping else existing_data.get("toppings", "無")
    
    # 加料資訊校正
    if topping and topping != "無":
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
    
    if result:
        return f"✅ 已成功修改 {name} 的訂單內容。"
    else:
        return f"❌ 修改 {name} 的訂單時發生錯誤。"
        
@mcp.tool()
def delete_drink_order(doc_id: str):
    """
    刪除指定的點餐訂單。
    - doc_id: 要刪除的訂單 ID。
    """
    # 呼叫 db_logic.py 中的 delete 行為
    result = db.firebase_bridge(action="delete", doc_id=doc_id)
    
    if result:
        return f"🗑️ 訂單 {doc_id} 已成功刪除。"
    else:
        return "❌ 刪除失敗，找不到該 ID。"
        
@mcp.tool()
def delete_order_by_name(name: str) -> str:
    """根據姓名刪除訂單。"""
    # 1. 先從 Firebase/資料庫 抓取所有訂單
    orders = db.firebase_bridge("fetch") 
    
    # 2. 尋找匹配該姓名的訂單 ID
    target_id = None
    
    if isinstance(orders, list):
        for o in orders:
            if o.get("name") == name:
                target_id = o.get("id")
                break
    elif isinstance(orders, dict):
        for doc_id, data in orders.items():
            if data.get("name") == name:
                target_id = doc_id
                break            
    if target_id:
        # 3. 執行刪除
        db.firebase_bridge("delete", doc_id=target_id)
        return f"✅ 已成功刪除 {name} 的訂單。"
    else:
        return f"❌ 找不到名為 {name} 的訂單。" 
        
@mcp.resource("drink://menu")
def get_menu_resource() -> str:
    """提供完整的飲品清單作為 AI 參考資源"""
    return get_menu()

if __name__ == "__main__":
    try:
        logging.info("Starting Drink-Assistant MCP Server...")
        mcp.run()
    except Exception as e:
        logging.error(f"MCP Server crashed: {e}")
