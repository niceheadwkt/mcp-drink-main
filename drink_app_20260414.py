import streamlit as st
import pandas as pd
from datetime import datetime
import time
import html
# 引用 db_logic.py 中的資料庫處理函式
from db_logic import firebase_bridge, fetch_cloud_orders, add_cloud_order

# --- 1. 菜單數據 ---
menu_data = {
    "茶人系列 原味茶": {"輕香烏龍綠": 45, "糯米香茶": 45, "島韻紅茶": 40, "炭培烏龍": 40, "油切蕎麥茶": 40, "手採高山青": 40},
    "講究系列 風味茶": {
        "牡丹高山青": 60, "牡丹蕎麥茶": 60, "粉粿牡丹檸檬": 70, 
        "酸梅湯烏龍綠": 65, "輕檸烏龍綠": 65, "糯香檸檬茶": 65, 
        "粉粿桂花檸檬": 70, "粉粿黑糖檸檬": 70, "荔枝烏龍": 60, "荔枝蘆薈": 65
    },
    "香醇系列 奶茶": {
        "烏龍綠奶茶": 60, "糯香奶茶": 60, "粉粿黑糖奶茶": 70, 
        "黃金蕎麥奶茶": 55, "逮丸奶茶": 75, "極黑芝麻奶茶": 70, 
        "島韻紅奶茶": 55, "烏龍奶茶": 55, "高山青奶茶": 55
    },
    "濃韻系列 芝士奶蓋": {"奶蓋烏龍綠": 75, "奶蓋糯香茶": 75, "奶蓋島韻紅": 70, "奶蓋烏龍茶": 70, "奶蓋高山青": 70},
    "自然系列 鮮奶茶": {"烏龍綠鮮奶茶": 80, "糯香鮮奶茶": 80, "蕎麥鮮奶茶": 75, "逮丸鮮奶茶": 90}
}
toppings_data = {"招牌粉粿": 15, "草仔粿": 15, "雙粉": 15, "琥珀粉圓": 10, "蘆薈": 15, "嫩仙草": 10}

sugar_options = ["正常甜", "五分甜", "三分甜", "一分糖", "無糖"]
ice_options = ["正常冰", "少冰", "微冰", "去冰", "完全去冰", "熱飲"]

st.set_page_config(page_title="一沐日雲端點餐系統", layout="centered")
st.title("🥤 一沐日 雲端點餐系統")

# --- 2. 輔助函式 ---
def get_orders():
    """從雲端獲取資料並格式化為 UI 所需欄位"""
    raw_orders = fetch_cloud_orders()
    if not raw_orders:
        return []
    
    formatted_orders = []
    for o in raw_orders:
        formatted_orders.append({
            "id": o.get("id"),
            "姓名": o.get("name", "匿名"),
            "飲品": o.get("item", "未知"),
            "規格": o.get("spec", "三分甜/微冰"),
            "加料": o.get("toppings", "無"),
            "金額": o.get("price", 0),
            "時間": o.get("timestamp", "")
        })
    return formatted_orders

def get_index(option_list, target_value):
    if target_value in option_list:
        return option_list.index(target_value)
    return 0

# --- 3. 狀態管理 ---
if "editing_order" not in st.session_state:
    st.session_state.editing_order = None

# --- 4. 點餐介面 ---
edit_data = st.session_state.editing_order
form_id = edit_data["id"] if edit_data else "new" 

st.subheader("📝 " + ("修改訂單" if edit_data else "新增點餐"))

# 姓名輸入
name = st.text_input("👤 訂購人姓名", value=edit_data["姓名"] if edit_data else "", key=f"name_{form_id}")

c1, c2 = st.columns(2)
with c1:
    # 系列選擇
    cat_list = list(menu_data.keys())
    default_cat_idx = 0
    if edit_data:
        for i, (c_name, items) in enumerate(menu_data.items()):
            if edit_data["飲品"] in items:
                default_cat_idx = i
                break
    cat = st.selectbox("選擇系列", cat_list, index=default_cat_idx, key=f"cat_{form_id}")
    
    # 飲品連動
    current_items = menu_data[cat]
    display_list = [f"{k} (${v})" for k, v in current_items.items()]
    default_item_idx = 0
    if edit_data and edit_data["飲品"] in current_items:
        target_display = f"{edit_data['飲品']} (${current_items[edit_data['飲品']]})"
        default_item_idx = get_index(display_list, target_display)
        
    sel_display = st.selectbox("選擇飲品", display_list, index=default_item_idx, key=f"item_{form_id}")
    item_key = sel_display.split(" ($")[0]
    base_p = current_items[item_key]

with c2:
    # 甜度冰量拆解
    d_sugar, d_ice = ("三分甜", "微冰")
    if edit_data and "/" in edit_data["規格"]:
        d_sugar, d_ice = edit_data["規格"].split("/")
        
    sugar = st.selectbox("甜度", sugar_options, index=get_index(sugar_options, d_sugar), key=f"sugar_{form_id}")
    ice = st.selectbox("冰量", ice_options, index=get_index(ice_options, d_ice), key=f"ice_{form_id}")

# 加料選擇
default_tops = []
if edit_data and edit_data["加料"] != "無":
    raw_tops = edit_data["加料"].split("、")
    for t in raw_tops:
        if t in toppings_data:
            default_tops.append(f"{t} (+${toppings_data[t]})")

tops = st.multiselect("加好料 (可多選)", [f"{k} (+${v})" for k, v in toppings_data.items()], default=default_tops, key=f"tops_{form_id}")
top_p = sum([toppings_data[t.split(" (+")[0]] for t in tops])
total = base_p + top_p

st.info(f"💰 杯單價：**${total}** 元")

cb1, cb2 = st.columns([1, 4])
submit_btn_text = "💾 儲存修改" if edit_data else "🚀 同步至雲端"

if cb1.button(submit_btn_text, type="primary"):
    if name:
        payload = {
            "name": name, 
            "item": item_key, 
            "spec": f"{sugar}/{ice}",
            "toppings": "、".join([t.split(" (+")[0] for t in tops]) if tops else "無",
            "price": total
        }
        if edit_data:
            # 修改邏輯
            firebase_bridge("update", data=payload, doc_id=edit_data["id"])
            st.session_state.editing_order = None 
        else:
            # 新增邏輯
            add_cloud_order(payload)
        
        st.success("同步完成！")
        time.sleep(1)
        st.rerun()
    else:
        st.error("⚠️ 請輸入姓名")

if edit_data:
    if cb2.button("❌ 取消修改"):
        st.session_state.editing_order = None
        st.rerun()

# --- 5. 顯示清單 ---
st.divider()
st.subheader("📋 已訂購清冊匯總XXX")

# 處理操作動作
params = st.query_params
if "action" in params:
    act, o_id = params["action"], params.get("id")
    st.query_params.clear() 
    if act == "edit":
        all_data = get_orders()
        st.session_state.editing_order = next((o for o in all_data if o['id'] == o_id), None)
        st.rerun()
    elif act == "delete" and o_id:
        firebase_bridge("delete", doc_id=o_id)
        st.warning("訂單已刪除")
        time.sleep(1)
        st.rerun()

orders = get_orders()

if orders:
    # 注入 CSS
    st.markdown("""
    <style>
        .calc-table { width:100%; border-collapse: collapse; font-family: sans-serif; font-size: 15px; }
        .calc-table th { background: #f8f9fa; border-bottom: 2px solid #dee2e6; padding: 12px 8px; text-align: left; }
        .calc-table td { border-bottom: 1px solid #eee; padding: 8px; vertical-align: middle; height: 48px; }
        .act-btn { 
            text-decoration: none; padding: 5px 10px; border: 1px solid #ccc; 
            border-radius: 4px; background: #fff; color: #333 !important; font-size: 13px; 
            display: inline-block; margin-right: 5px; line-height: 1.2;
        }
        .act-btn:hover { background: #f4f4f4; border-color: #888; }
    </style>
    """, unsafe_allow_html=True)
    
    # 構建表格
    table_parts = ['<table class="calc-table"><thead><tr><th>訂購人</th><th>飲品項目</th><th>規格</th><th>加料</th><th>金額</th><th>操作</th></tr></thead><tbody>']
    for row in orders:
        n, i, s, a, p, rid = html.escape(str(row['姓名'])), html.escape(str(row['飲品'])), html.escape(str(row['規格'])), html.escape(str(row['加料'])), html.escape(str(row['金額'])), row['id']
        r_html = f'<tr><td>{n}</td><td>{i}</td><td>{s}</td><td>{a}</td><td>${p}</td><td>'
        r_html += f'<a href="/?action=edit&id={rid}" target="_self" class="act-btn">🛠️ 修改</a>'
        r_html += f'<a href="/?action=delete&id={rid}" target="_self" class="act-btn">🗑️ 刪除</a></td></tr>'
        table_parts.append(r_html)
    table_parts.append('</tbody></table>')
    st.markdown("".join(table_parts), unsafe_allow_html=True)

    # 匯總資訊
    total_m = sum(o['金額'] for o in orders)
    st.markdown(f"<div style='margin-top:20px; font-weight:bold;'>📊 總計：{len(orders)} 杯 | 總金額：${total_m} 元</div>", unsafe_allow_html=True)
    
    # CSV 下載
    df_export = pd.DataFrame(orders)[['姓名', '飲品', '規格', '加料', '金額', '時間']]
    csv_data = df_export.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 下載訂單 CSV",
        data=csv_data,
        file_name=f"drink_orders_{datetime.now().strftime('%m%d_%H%M')}.csv",
        mime='text/csv'
    )
else:
    st.info("目前尚無雲端資料。")

if st.button("🔄 重新整理"):
    st.rerun()