# ============================================================
# 修改指南：只要同一個人有多筆訂單，都算重複
# ============================================================
# 
# 原理：改變重複檢測的邏輯
# 
# 【原始邏輯】
# 重複訂單 = 同一個人 + 飲品相同 + 規格相同 + 加料相同
# 例：小媚媚的兩筆「烏龍綠鮮奶茶 + 一分甜去冰 + 無」= 重複
# 
# 【新邏輯】
# 重複訂單 = 同一個人 + 任何飲品 (2筆或以上)
# 例：小媚媚的兩筆訂單，無論飲品是什麼 = 重複

# ============================================================
# 修改位置 1：find_duplicate_orders_by_name() 函數
# ============================================================
# 
# 【原始代碼】第 105-168 行
# 
# @mcp.tool()
# def find_duplicate_orders_by_name(name: str) -> str:
#     """..."""
#     # 1. 從資料庫獲取所有訂單
#     all_orders = db.firebase_bridge(action="fetch")
#     if not all_orders:
#         return "📭 目前沒有任何訂單。"
#     
#     # 2. 篩選該人名的所有訂單
#     person_orders = []
#     if isinstance(all_orders, list):
#         person_orders = [o for o in all_orders if o.get("name") == name]
#     elif isinstance(all_orders, dict):
#         person_orders = [o for o in all_orders.values() if o.get("name") == name]
#     
#     if not person_orders:
#         return f"❌ 找不到名為 '{name}' 的訂單。"
#     
#     # 3. 分析重複訂單 - 按「飲品+規格+加料」組合分組
#     order_groups = defaultdict(list)
#     for order in person_orders:
#         # 建立訂單簽名（用於判斷是否重複）
#         signature = f"{order.get('item', '')}|{order.get('spec', '')}|{order.get('toppings', '')}"
#         order_groups[signature].append(order)
#     
#     # 4. 篩選出重複訂單（相同簽名的超過 1 筆）
#     duplicate_groups = {sig: orders for sig, orders in order_groups.items() if len(orders) > 1}
#     
#     if not duplicate_groups:
#         return f"✅ {name} 沒有重複的訂單。所有訂單都是獨立的。"
#     
#     # 5. 生成詳細報告
#     output = f"🔍 {name} 的重複訂單報告\n"
#     output += "="*40 + "\n\n"
#     
#     total_duplicates = sum(len(orders) - 1 for orders in duplicate_groups.values())
#     output += f"⚠️ 發現 {len(duplicate_groups)} 組重複訂單，共 {total_duplicates} 筆重複\n\n"
#     
#     for idx, (signature, orders) in enumerate(duplicate_groups.items(), 1):
#         item, spec, toppings = signature.split("|")
#         output += f"【第 {idx} 組】重複 {len(orders)} 次\n"
#         output += f"  🥤 飲品：{item}\n"
#         output += f"  🌡️ 規格：{spec}\n"
#         output += f"  💎 加料：{toppings}\n"
#         output += f"  💰 單杯價格：${orders[0].get('price', 0)} 元\n"
#         output += f"  📅 訂單時間：\n"
#         
#         for i, order in enumerate(orders, 1):
#             output += f"     {i}. {order.get('timestamp', '時間未記錄')} (ID: {order.get('id', 'N/A')})\n"
#         
#         output += "\n"
#     
#     return output
#
# ============================================================
# 【修改為】
# ============================================================

@mcp.tool()
def find_duplicate_orders_by_name(name: str) -> str:
    """
    🔍 搜尋特定人物的重複訂單資料。
    【修改版】只要同一個人有 2+ 筆訂單，都算重複（不管飲品是否相同）
    當使用者詢問「搜尋個人有重複的資料」、「某人有重複訂單」時，請呼叫此工具。
    
    參數說明：
    - name: 要查詢的人名
    
    功能：
    - 找出該人名下所有訂單
    - 只要有 2+ 筆訂單，都算重複
    - 顯示所有訂單詳細資訊和統計
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


# ============================================================
# 修改位置 2：search_all_duplicates() 函數
# ============================================================
#
# 【原始代碼】第 170-227 行
# 
# 原始邏輯：先按飲品分組，然後找出有重複的人
# 
# 【修改為】直接檢查訂單數量

@mcp.tool()
def search_all_duplicates() -> str:
    """
    🔍 掃描全部訂單，找出所有有重複訂單的人物。
    【修改版】只要某人有 2+ 筆訂單，就算重複（不管飲品是否相同）
    當使用者詢問「全局搜尋重複」、「誰有重複訂單」時，請呼叫此工具。
    
    功能：
    - 分析所有訂單
    - 找出所有有 2+ 筆訂單的人物
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
    
    # 3. 【關鍵改動】只檢查訂單數量，2+ 就算重複
    people_with_duplicates = {}
    for name, orders in person_orders.items():
        if len(orders) > 1:  # 只要 2+ 筆就算重複
            people_with_duplicates[name] = {
                "total_orders": len(orders),
                "duplicate_count": len(orders) - 1,  # 重複筆數 = 總筆數 - 1
                "total_price": sum(o.get('price', 0) for o in orders)
            }
    
    if not people_with_duplicates:
        return "✅ 全部訂單都是獨立的，沒有人有重複訂單。"
    
    # 4. 生成全局報告
    output = "🔍 全局重複訂單掃描報告\n"
    output += "="*50 + "\n\n"
    output += f"共找到 {len(people_with_duplicates)} 個人有重複訂單\n\n"
    
    sorted_people = sorted(people_with_duplicates.items(), 
                          key=lambda x: x[1]["total_orders"], 
                          reverse=True)
    
    for idx, (name, stats) in enumerate(sorted_people, 1):
        output += f"{idx}. 👤 {name}\n"
        output += f"   📊 訂單數：{stats['total_orders']} 筆\n"
        output += f"   ⚠️ 重複筆數：{stats['duplicate_count']} 筆\n"
        output += f"   💰 總金額：${stats['total_price']} 元\n"
        output += f"   💡 詢問「搜尋 {name} 的重複訂單」可看詳細資訊\n\n"
    
    return output


# ============================================================
# 修改位置 3：get_duplicate_statistics() 函數
# ============================================================
#
# 【原始代碼】第 229-312 行
# 
# 原始邏輯：統計相同飲品的重複
# 
# 【修改為】統計有多筆訂單的人物佔比

@mcp.tool()
def get_duplicate_statistics() -> str:
    """
    📊 取得重複訂單的統計資訊。
    【修改版】統計有 2+ 筆訂單的人物佔比
    當使用者詢問「重複訂單統計」、「重複率」時，請呼叫此工具。
    
    功能：
    - 計算有重複的人物比例
    - 顯示人均訂單數
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
    
    # 2. 按人名分組
    person_orders = defaultdict(list)
    for order in orders_list:
        name = order.get("name", "匿名")
        person_orders[name].append(order)
    
    # 3. 統計數據
    total_orders = len(orders_list)
    total_people = len(person_orders)
    
    # 【關鍵改動】只要 2+ 筆訂單就算重複
    people_with_duplicates = {name: orders for name, orders in person_orders.items() if len(orders) > 1}
    people_without_duplicates = {name: orders for name, orders in person_orders.items() if len(orders) == 1}
    
    total_duplicate_orders = sum(len(orders) - 1 for orders in people_with_duplicates.values())
    
    # 計算人均訂單數
    avg_orders_per_person = total_orders / total_people if total_people > 0 else 0
    
    # 4. 找出訂單最多的人
    if people_with_duplicates:
        top_person = max(people_with_duplicates.items(), 
                        key=lambda x: x[1])
    else:
        top_person = None
    
    # 5. 生成統計報告
    duplicate_rate = (len(people_with_duplicates) / total_people * 100) if total_people > 0 else 0
    
    output = "📊 重複訂單統計報告\n"
    output += "="*50 + "\n\n"
    output += f"📈 訂單總數：{total_orders} 筆\n"
    output += f"👥 不同客戶：{total_people} 人\n"
    output += f"⚠️ 有重複訂單的客戶：{len(people_with_duplicates)} 人\n"
    output += f"✅ 只訂過一次的客戶：{len(people_without_duplicates)} 人\n"
    output += f"📊 有重複客戶佔比：{duplicate_rate:.1f}%\n"
    output += f"🔁 總重複筆數：{total_duplicate_orders} 筆\n"
    output += f"📋 人均訂單數：{avg_orders_per_person:.1f} 筆\n\n"
    
    if top_person:
        name, orders = top_person
        output += f"🏆 訂單最多的客戶：\n"
        output += f"   👤 {name}\n"
        output += f"   📊 訂單數：{len(orders)} 筆\n"
        output += f"   💰 總消費：${sum(o.get('price', 0) for o in orders)} 元\n\n"
    
    # 6. 分析和建議
    output += f"💡 分析與建議：\n"
    if duplicate_rate > 50:
        output += f"   • 大部分客戶都是重複訂購者，這很好！(重複率 {duplicate_rate:.0f}%)\n"
        output += f"   • 建議：推出會員卡或折扣方案吸引重複購買\n"
    elif duplicate_rate > 25:
        output += f"   • 有相當比例的重複客戶 ({duplicate_rate:.0f}%)\n"
        output += f"   • 建議：加強與常客的互動，提高回購率\n"
    else:
        output += f"   • 重複客戶較少 ({duplicate_rate:.0f}%)\n"
        output += f"   • 建議：改進產品和服務，提高客戶滿意度\n"
    
    return output


# ============================================================
# 完整修改總結
# ============================================================
# 
# 需要修改的函數：3 個
# 1. find_duplicate_orders_by_name()
#    - 移除簽名組合邏輯
#    - 直接檢查訂單數量（< 2 = 沒重複）
#    - 改為列出所有訂單而不是分組
# 
# 2. search_all_duplicates()
#    - 移除簽名分組邏輯
#    - 改為直接檢查訂單數量（> 1 = 有重複）
# 
# 3. get_duplicate_statistics()
#    - 改為計算有多筆訂單的人物比例
#    - 不再統計飲品相同的情況
# 
# ============================================================
# 如何應用這個修改？
# ============================================================
# 
# 方法 1：直接替換三個函數
# 將上面的代碼複製到你的 mcp_server.py 中，
# 替換原有的同名函數即可
# 
# 方法 2：逐個修改
# 找到原始代碼的相應位置，進行上述修改
# 
# 關鍵改動點：
# 1. 移除所有 defaultdict(list) 和簽名組合邏輯
# 2. 改為直接檢查 len(person_orders) 或 len(orders)
# 3. 條件從「相同簽名的超過 1 筆」改為「訂單數超過 1 筆」
# 
# ============================================================
