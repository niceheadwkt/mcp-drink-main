import warnings
# 1. 放在最上方，徹底消除截圖中的 Future廣告警告
warnings.filterwarnings("ignore", category=FutureWarning)

from fastmcp.prompts import prompt
from requests import exceptions
import streamlit as st
import pandas as pd
from datetime import datetime
import time
import html
# 引用 db_logic.py 中的資料庫處理函式
from db_logic import firebase_bridge, fetch_cloud_orders, add_cloud_order
# 引用 order_utils.py 中的菜單數據
import order_utils as utils

# --- 1. 配置改用本地端 Gemma 4 (透過 Ollama) ---
from openai import OpenAI
import json
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 不需要 API KEY，Base URL 指向 Ollama 預設位址
client = OpenAI(
    base_url='http://localhost:11434/v1',
    api_key='ollama', # 隨便填一個字串即可
)
model_name = "gemma4"
 
# --- 2. 配置 MCP 啟動參數 ---
mcp_server_params = StdioServerParameters(
    command=r"C:\aiTest\mcp-drink-main\.venv\Scripts\python.exe", # 修改這裡，指向虛擬環境的 python
    #args=["mcp_server.py"],  # 請確保檔案路徑正確
    # 修改後（請將路徑改為您電腦上的真實絕對路徑）
    args=[r"C:\aiTest\mcp-drink-main\mcp_server.py"],
    env=None
)

async def call_mcp_and_local_llm(user_input):
    # 1. 整理對話歷史，讓 local_llm 知道之前聊過什麼
    history_context = ""
    for msg in st.session_state.messages[-5:]:
        role_name = "助理" if msg["role"] == "Drink-Assistant" else "使用者"
        history_context += f"{role_name}: {msg['content']}\n"

    # 2. 將歷史與當前輸入組合
    prompt = f"""
    你是一個專業的飲品點餐助手。
    請一律使用「繁體中文」進行回覆與生成 JSON。
    請分析「對話歷史」與「最新輸入」來判斷行動。

    📜 對話歷史：
    {history_context}

    最新輸入："{user_input}"

    ⚠️ 點餐限制：
    - 必須從歷史或最新輸入中湊齊「姓名」、「品項」、「糖冰規格」。
    - **如果目前資訊仍缺少姓名**，請詢問姓名。
    - **如果缺少糖度或冰量**，請詢問規格。

    判斷邏輯：
    1. 資訊齊全：回傳 JSON: {{"action": "order", "name": "姓名", "drink": "品項", "spec": "糖冰", "topping": "加料"}}
    2. 資訊不全：回覆詢問文字（不要 JSON）。
    3. 看菜單：回傳 JSON: {{"action": "menu"}}
    """

    try:
        # 改用 OpenAI SDK 呼叫 Ollama 的 Gemma 4
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0  # 設定為 0 增加 JSON 生成的穩定性
        )
        raw_text = response.choices[0].message.content.strip()
    except Exception as e:
        raw_text = f"本地模型調用失敗: {str(e)}"

    # 嘗試解析 JSON
    try:
        # 簡單處理可能的 Markdown 標籤
        clean_json = raw_text.replace("```json", "").replace("```", "").strip()

        # 檢查是否真的是 JSON (避免 AI 回覆一般對話文字)
        if not (clean_json.startswith('{') and clean_json.endswith('}')):
             return raw_text
        
        data = json.loads(clean_json)
        
        # B. 根據解析結果，透過 MCP 執行動作
        async with stdio_client(mcp_server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                if data.get("action") == "order":
                    # 呼叫 mcp_server.py 的點餐工具
                    mcp_result = await session.call_tool("place_drink_order", arguments={
                        "name": data.get("name"),
                        "drink_name": data.get("drink"),
                        "spec": data.get("spec"),
                        "topping": data.get("topping", "無")
                    })
                    return mcp_result.content[0].text
                
                elif data.get("action") == "menu":
                    # 呼叫 mcp_server.py 的菜單工具
                    mcp_result = await session.call_tool("get_menu", arguments={})
                    return mcp_result.content[0].text
                    
    except json.JSONDecodeError:
        # 如果 AI 回傳的是純文字對話，則直接回傳
        return raw_text
    except Exception as e:
        return f"系統執行錯誤: {str(e)}"
            
def drink_ai_agent(prompt):
    """供 Streamlit 呼叫的入口"""
    return asyncio.run(call_mcp_and_local_llm(prompt))

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

# --- 主畫面：手動操作區 ---
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
    cat_list = list(utils.NESTED_MENU.keys())
    default_cat_idx = 0
    if edit_data:
        for i, (c_name, items) in enumerate(utils.NESTED_MENU.items()):
            if edit_data["飲品"] in items:
                default_cat_idx = i
                break
    cat = st.selectbox("選擇系列", cat_list, index=default_cat_idx, key=f"cat_{form_id}")
    
    # 飲品連動
    current_items = utils.NESTED_MENU[cat]
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
        if t in utils.TOPPINGS_MENU:
            default_tops.append(f"{t} (+${utils.TOPPINGS_MENU[t]})")

tops = st.multiselect("加好料 (可多選)", [f"{k} (+${v})" for k, v in utils.TOPPINGS_MENU.items()], default=default_tops, key=f"tops_{form_id}")
top_p = sum([utils.TOPPINGS_MENU[t.split(" (+")[0]] for t in tops])
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
st.subheader("📋 已訂購清冊匯總")

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

# --- 側邊欄：AI 對話介面 ---
with st.sidebar:
    st.title("🤖 飲品小助手")
    
    # 確保訊息容器先存在
    chat_placeholder = st.container()
    
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "Drink-Assistant", "content": "想喝什麼？"}]

    with chat_placeholder:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # 將輸入框獨立出來
    if user_input := st.chat_input("想喝什麼？", key="ai_chat_input"):
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        # 立即更新顯示而不重啟
        response = drink_ai_agent(user_input)
        st.session_state.messages.append({"role": "Drink-Assistant", "content": response})
        
        if "✅" in response:
            time.sleep(0.5) 
            st.rerun()
        else:
            # 僅更新聊天內容
            st.rerun()

# 加入在側邊欄最底部
    st.divider()
    st.subheader("🛠️ 本地模型狀態")
    if st.button("🔍 檢查 Ollama 可用模型"):
        try:
            # 這裡會列出 Ollama 已經下載的所有模型
            models = client.models.list()
            st.write("目前本地可選用的模型 ID：")
            for m in models.data:
                st.code(m.id)
        except Exception as e:
            st.error(f"無法連線至 Ollama: {e}")