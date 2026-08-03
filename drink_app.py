import sys
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
import json
import os
import asyncio
import concurrent.futures
from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import traceback

# 引用自定義模組 (請確保 db_logic.py 與 order_utils.py 在同目錄)
try:
    from db_logic import firebase_bridge, fetch_cloud_orders, add_cloud_order
    import order_utils as utils
except ImportError:
    st.error("找不到 db_logic.py 或 order_utils.py，請確認檔案是否存在。")

# --- 1. 配置 Gemini ---
if "GEMINI_KEY" in st.secrets:
    client = genai.Client(api_key=st.secrets["GEMINI_KEY"])
else:
    st.warning("請在 secrets 中配置 GEMINI_KEY 以啟動 AI 助手。")

# --- 2. MCP 伺服器配置 ---
def get_mcp_params_from_claude_config(server_name="drink-server"):
    """讀取 Claude Desktop 設定檔以取得 MCP 啟動參數"""
    local_appdata = os.environ.get('LOCALAPPDATA')
    if not local_appdata:
        return None
   
    config_path = os.path.join(
        local_appdata, 
        r"Roaming\Claude\claude_desktop_config.json"
    )
    
    try:
        if not os.path.exists(config_path):
            return None
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        server_config = config.get("mcpServers", {}).get(server_name)
        if not server_config:
            return None
            
        return StdioServerParameters(
            command=server_config.get("command"),
            args=server_config.get("args"),
            env=server_config.get("env")
        )
    except Exception:
        return None

# 優先讀取設定檔，否則使用預設路徑
mcp_server_params = get_mcp_params_from_claude_config("drink-server")
if mcp_server_params is None:
    # 改用 __file__ 定位，確保路徑正確
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    mcp_server_params = StdioServerParameters(
        command=sys.executable, # 自動指向當前的 python.exe (含虛擬環境)
        args=[os.path.join(BASE_DIR, "mcp_server.py")],
        env={**os.environ, "PYTHONPATH": BASE_DIR} # 強制加入當前路徑到搜尋路徑
    )

# --- 3. AI 邏輯核心 (Gemini + MCP Tool Use) ---
async def process_with_ai(user_input):
    """使用 Gemini SDK 處理對話與 MCP 工具調用"""
    try:
        async with stdio_client(mcp_server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # 獲取 MCP 伺服器提供的所有工具並轉換為 Gemini 可識別的 Function Declarations
                tools_response = await session.list_tools()
                gemini_tools = []
                for tool in tools_response.tools:
                    gemini_tools.append(types.FunctionDeclaration(
                        name=tool.name,
                        description=tool.description,
                        parameters=tool.inputSchema
                    ))

                # 向 Gemini 發送請求 (使用 gemini-2.5-flash)
                config = types.GenerateContentConfig(
                    system_instruction="你是一個專業的飲品訂單助手。請一律使用「繁體中文」回答。你可以執行點餐、修改、刪除、查詢菜單或搜尋重複訂單。",
                    tools=[types.Tool(function_declarations=gemini_tools)] if gemini_tools else None,
                    temperature=0.7
                )
                
                # 發送對話
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=user_input,
                    config=config
                )

                # 處理 Gemini 返回的 Tool Call
                if response.function_calls:
                    final_content = []
                    # 執行所有 Tool Call
                    for call in response.function_calls:
                        mcp_result = await session.call_tool(call.name, call.args)
                        final_content.append(mcp_result.content[0].text)
                    return "\n".join(final_content)
                else:
                    return response.text
                    
    except Exception as e:
            # 關鍵：這會印出整個 ExceptionGroup 的詳細內容
            full_error = traceback.format_exc()
            print(f"DEBUG 詳細錯誤內容:\n{full_error}") # 印在終端機
            return f"❌ 系統錯誤: {str(e)}\n\n詳細資訊:\n```\n{full_error}\n```"
            
def drink_ai_agent(user_message: str) -> str:
    """Streamlit 介面呼叫入口 (相容 Streamlit Community Cloud 與 Python 3.13 的事件迴圈)"""
    try:
        import anyio
        return anyio.run(process_with_ai, user_message)
    except Exception as e:
        # 降級方案：使用普通 asyncio
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(process_with_ai(user_message))
        except Exception as ex:
            return f"❌ AI 執行錯誤: {str(ex)}"
                
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
            result = drink_ai_agent("搜尋全部有重複的訂單")
            st.info(result)
        except Exception as e:
            st.error(f"掃描失敗: {e}")

with col_dup2:
    if st.button("📊 查看重複訂單統計"):
        try:
            result = drink_ai_agent("顯示重複訂單的統計資訊")
            st.info(result)
        except Exception as e:
            st.error(f"統計失敗: {e}")

# 單人查詢
st.write("**單人重複訂單查詢：**")
search_name = st.text_input("輸入姓名查詢該人的重複訂單")
if search_name and st.button("🔎 查詢此人的重複訂單"):
    try:
        result = drink_ai_agent(f"搜尋 {search_name} 有沒有重複的訂單")
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