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
import os
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
# --- 新增：讀取 Claude Desktop 配置的函式 ---
def get_mcp_params_from_claude_config(server_name="drink-server"):
    # 自動取得當前電腦的 Local AppData 路徑 (例如 C:\Users\xxx\AppData\Local)
    local_appdata = os.environ.get('LOCALAPPDATA')
    if not local_appdata:
        return None
   
    # 動態拼接路徑，避開寫死使用者名稱
    config_path = os.path.join(
        local_appdata, 
        r"Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json"
    )
    
    try:
        if not os.path.exists(config_path):
            return None
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        server_config = config.get("mcpServers", {}).get(server_name)
        
        if not server_config:
            st.error(f"在 Claude 配置中找不到伺服器: {server_name}")
            return None
            
        return StdioServerParameters(
            command=server_config.get("command"),
            args=server_config.get("args"),
            env=server_config.get("env")
        )
    except Exception as e:
        st.error(f"讀取 Claude 配置失敗: {e}")
        return None
# --- 修改後的配置區 ---
# 假設你在 Claude Desktop 設定檔中給它的名稱是 "drink-server"
mcp_server_params = get_mcp_params_from_claude_config("drink-server")

# 如果讀取失敗的備案（原本的寫法）
if mcp_server_params is None:
    mcp_server_params = StdioServerParameters(
        command=r"C:\aiTest\mcp-drink-main\.venv\Scripts\python.exe",
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
    你是一個專門處理飲品訂單的機器人。請根據對話判斷意圖並「嚴格」輸出 JSON。
    請一律使用「繁體中文」進行回覆與生成 JSON。
    請分析「對話歷史」與「最新輸入」來判斷行動。

    📜 對話歷史：
    {history_context}

    最新輸入："{user_input}"

    ⚠️ 點餐限制：
    1. **修改訂單**：只要使用者提到「修改」、「調整」或「其餘不變」，即便只提到其中一項（如：品項），也請「立即」執行 update 動作。
       - 對於使用者沒提到的欄位，在 JSON 中填入 null。
       - 範例：{{"action": "update", "name": "國童哥", "drink": "烏龍綠鮮奶茶", "spec": null}}
    2. **新點餐意圖**：
       - 必須包含姓名、品項、規格（糖冰）。
       - 若資訊不足，才使用文字詢問。
       輸出格式範例（僅輸出 JSON，不要解釋）：
       {{"action": "update", "name": "姓名", "drink": "品項或null", "spec": "規格或null", "topping": "加料或null"}}
    3. **搜尋重複訂單**：當使用者提到「搜尋重複」、「有沒有重複」時：
       - 特定人名：{{"action": "find_duplicate", "name": "人名"}}
       - 全局搜尋：{{"action": "search_all_duplicates"}}
       - 看統計：{{"action": "get_statistics"}}

    ⚠️ 行動判斷規則：
    1. 點餐：若使用者想訂購，且具備姓名、品項、規格，回傳 JSON: {{"action": "order", "name": "姓名", "drink": "品項", "spec": "糖冰", "topping": "加料"}}
    2. 修改：修改：若使用者想更改部分內容（例如：把飲料改為去冰，其餘不變），
       請務必回傳 JSON。對於「不變」的欄位，請在 JSON 中填入 null。
       例如：{{"action": "update", "name": "國童哥", "drink": "烏龍綠鮮奶茶", "spec": null, "topping": null}}
    3. 刪除：若要取消訂單，回傳 JSON: {{"action": "delete", "name": "姓名"}}
    4. 看菜單：回傳 JSON: {{"action": "menu"}}
    5. 搜尋重複：若使用者詢問重複訂單，回傳 JSON: {{"action": "find_duplicate", "name": "人名"}} 或 {{"action": "search_all_duplicates"}} 或 {{"action": "get_statistics"}}    
    6. 資訊不足：請直接文字詢問，不要生成 JSON。
    """

    try:
        # 改用 OpenAI SDK 呼叫 Ollama 的 Gemma 4
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,  # 設定為 0 增加 JSON 生成的穩定性，不需要 AI 太有創意
            top_p=0.1  #進一步限縮生成範圍，讓 JSON 格式更穩定
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
                        "topping": data.get("topping") or "無"
                    })
                    return mcp_result.content[0].text
                
                elif data.get("action") == "menu":
                    # 呼叫 mcp_server.py 的菜單工具
                    mcp_result = await session.call_tool("get_menu", arguments={})
                    return mcp_result.content[0].text

                # --- 新增：處理修改訂單 ---
                elif data.get("action") == "update":
                    mcp_result = await session.call_tool("update_order_by_name", arguments={
                        "name": data.get("name"),
                        "drink_name": data.get("drink"),
                        "spec": data.get("spec"),
                        "topping": data.get("topping") or "無"
                    })
                    return mcp_result.content[0].text

                # --- 新增：處理刪除訂單 ---
                elif data.get("action") == "delete":
                    # 請確保你的 mcp_server.py 裡面有定義 delete_order_by_name 這個工具
                    mcp_result = await session.call_tool("delete_order_by_name", arguments={
                        "name": data.get("name")
                    })
                    return mcp_result.content[0].text
                    
                # ===== 新增：搜尋特定人物的重複訂單 =====
                elif data.get("action") == "find_duplicate":
                    mcp_result = await session.call_tool("find_duplicate_orders_by_name", arguments={
                        "name": data.get("name")
                    })
                    return mcp_result.content[0].text

                # ===== 新增：全局搜尋重複訂單 =====
                elif data.get("action") == "search_all_duplicates":
                    mcp_result = await session.call_tool("search_all_duplicates", arguments={})
                    return mcp_result.content[0].text

                # ===== 新增：取得重複訂單統計 =====
                elif data.get("action") == "get_statistics":
                    mcp_result = await session.call_tool("get_duplicate_statistics", arguments={})
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
# 新增：重複訂單檢查面板
st.subheader("🔍 重複訂單檢查")
col_dup1, col_dup2 = st.columns(2)

with col_dup1:
    if st.button("🔍 全局掃描重複訂單"):
        try:
            result = asyncio.run(call_mcp_and_local_llm("搜尋全部有重複的訂單"))
            st.info(result)
        except Exception as e:
            st.error(f"掃描失敗: {e}")

with col_dup2:
    if st.button("📊 查看重複訂單統計"):
        try:
            result = asyncio.run(call_mcp_and_local_llm("顯示重複訂單的統計資訊"))
            st.info(result)
        except Exception as e:
            st.error(f"統計失敗: {e}")

# 單人查詢
st.write("**單人重複訂單查詢：**")
search_name = st.text_input("輸入姓名查詢該人的重複訂單")
if search_name and st.button("🔎 查詢此人的重複訂單"):
    try:
        result = asyncio.run(call_mcp_and_local_llm(f"搜尋 {search_name} 有沒有重複的訂單"))
        st.info(result)
    except Exception as e:
        st.error(f"查詢失敗: {e}")

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
            
    st.divider()
    st.subheader("💡 快速幫助")
    st.markdown("""
    **重複訂單查詢示例：**
    - "搜尋國童哥有沒有重複的訂單"
    - "查一下誰有重複訂單"
    - "顯示全部重複訂單"
    - "有什麼訂單重複了嗎"
    """)

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