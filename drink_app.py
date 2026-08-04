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

def get_local_ollama_models():
    """發送請求取得本地 Ollama 的模型清單"""
    import requests
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=1.0)
        if response.status_code == 200:
            data = response.json()
            # 取得模型名稱，排除可能為空的名稱
            models = [m.get("name") for m in data.get("models", []) if m.get("name")]
            return models
    except Exception:
        pass
    return []

# --- 1. 宣告與掃描可用之 AI 客戶端金鑰 ---
client = None
ai_provider = None
ai_model = None

# 取得本地已下載的 Ollama 模型清單
local_models = get_local_ollama_models()

# 定義金鑰與產商/模型對照
PROVIDER_MAP = {
    "GEMINI_KEY": ("Gemini", "gemini-2.5-flash"),
    "OPENAI_KEY": ("OpenAI", "gpt-4o-mini"),
    "CLAUDE_KEY": ("Anthropic", "claude-3-5-sonnet-latest")
}

# 掃描可用雲端金鑰 (依 st.secrets 的 Key 順序優先)
available_cloud_providers = {}
try:
    for key in st.secrets.keys():
        if key in PROVIDER_MAP:
            provider_name, model_name = PROVIDER_MAP[key]
            key_val = st.secrets[key]
            if key_val:
                available_cloud_providers[provider_name] = (key_val, model_name)
except Exception:
    pass

# 掃描本地環境變數作為備用
env_keys = [
    ("GOOGLE_API_KEY", "Gemini", "gemini-2.5-flash"),
    ("GEMINI_API_KEY", "Gemini", "gemini-2.5-flash"),
    ("OPENAI_API_KEY", "OpenAI", "gpt-4o-mini"),
    ("ANTHROPIC_API_KEY", "Anthropic", "claude-3-5-sonnet-latest")
]
for env_var, provider_name, model_name in env_keys:
    if provider_name not in available_cloud_providers:
        key_val = os.environ.get(env_var)
        if key_val:
            available_cloud_providers[provider_name] = (key_val, model_name)

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

def clean_schema(d):
    """遞迴清理 Schema，移除 Gemini 不支援的欄位 (如 additionalProperties, anyOf)"""
    if not isinstance(d, dict):
        return d
        
    # 若包含 anyOf，將其簡化為第一個非 null 的單一型態以相容 Gemini
    if "anyOf" in d:
        non_null_type = None
        for option in d["anyOf"]:
            if isinstance(option, dict) and option.get("type") != "null":
                non_null_type = option.get("type")
                break
        if non_null_type:
            cleaned = {k: v for k, v in d.items() if k != "anyOf"}
            cleaned["type"] = non_null_type
            return clean_schema(cleaned)
            
    cleaned = {}
    for k, v in d.items():
        if k in ("additionalProperties", "additional_properties"):
            continue
        if isinstance(v, dict):
            cleaned[k] = clean_schema(v)
        elif isinstance(v, list):
            cleaned[k] = [clean_schema(item) if isinstance(item, dict) else item for item in v]
        else:
            cleaned[k] = v
    return cleaned

# --- 3. AI 邏輯核心 (Gemini + MCP Tool Use) ---
async def process_with_ai(user_input):
    """根據偵測到的 AI 服務提供者處理對話與 MCP 工具調用"""
    global client, ai_provider, ai_model
    if not client:
        return "❌ 錯誤：未初始化 AI 客戶端。請檢查 API 金鑰配置。"

    try:
        async with stdio_client(mcp_server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # 獲取 MCP 伺服器提供的所有工具
                tools_response = await session.list_tools()
                
                # 根據不同廠商格式化工具列表
                formatted_tools = []
                gemini_tools = None
                
                if ai_provider == "Gemini":
                    for tool in tools_response.tools:
                        # 清理 schema，防止 Gemini 丟出 400 錯誤
                        cleaned_schema = clean_schema(tool.inputSchema)
                        formatted_tools.append(types.FunctionDeclaration(
                            name=tool.name,
                            description=tool.description,
                            parameters=cleaned_schema
                        ))
                    gemini_tools = [types.Tool(function_declarations=formatted_tools)] if formatted_tools else None
                elif ai_provider == "OpenAI":
                    for tool in tools_response.tools:
                        formatted_tools.append({
                            "type": "function",
                            "function": {
                                "name": tool.name,
                                "description": tool.description,
                                "parameters": tool.inputSchema
                            }
                        })
                elif ai_provider == "Anthropic":
                    for tool in tools_response.tools:
                        formatted_tools.append({
                            "name": tool.name,
                            "description": tool.description,
                            "input_schema": tool.inputSchema
                        })

                # A. Gemini 請求與 Tool Call 處理
                if ai_provider == "Gemini":
                    config = types.GenerateContentConfig(
                        system_instruction="你是一個專業的飲品訂單助手。請一律使用「繁體中文」回答。你可以執行點餐、修改、刪除、查詢菜單或搜尋重複訂單。",
                        tools=gemini_tools,
                        temperature=0.7
                    )
                    response = client.models.generate_content(
                        model=ai_model,
                        contents=user_input,
                        config=config
                    )
                    if response.function_calls:
                        final_content = []
                        for call in response.function_calls:
                            mcp_result = await session.call_tool(call.name, call.args)
                            final_content.append(mcp_result.content[0].text)
                        return "\n".join(final_content)
                    else:
                        return response.text or ""

                # B. OpenAI 請求與 Tool Call 處理
                elif ai_provider == "OpenAI":
                    messages = [
                        {"role": "system", "content": "你是一個專業的飲品訂單助手。請一律使用「繁體中文」回答。你可以執行點餐、修改、刪除、查詢菜單或搜尋重複訂單。"},
                        {"role": "user", "content": user_input}
                    ]
                    response = client.chat.completions.create(
                        model=ai_model,
                        messages=messages,
                        tools=formatted_tools if formatted_tools else None,
                        temperature=0.7
                    )
                    message = response.choices[0].message
                    if message.tool_calls:
                        final_content = []
                        for tool_call in message.tool_calls:
                            func_args = json.loads(tool_call.function.arguments)
                            mcp_result = await session.call_tool(tool_call.function.name, func_args)
                            final_content.append(mcp_result.content[0].text)
                        return "\n".join(final_content)
                    else:
                        return message.content

                # C. Anthropic 請求與 Tool Call 處理
                elif ai_provider == "Anthropic":
                    response = client.messages.create(
                        model=ai_model,
                        max_tokens=1024,
                        system="你是一個專業的飲品訂單助手。請一律使用「繁體中文」回答。你可以執行點餐、修改、刪除、查詢菜單或搜尋重複訂單。",
                        messages=[
                            {"role": "user", "content": user_input}
                        ],
                        tools=formatted_tools if formatted_tools else None,
                        temperature=0.7
                    )
                    tool_calls = [content for content in response.content if content.type == "tool_use"]
                    if tool_calls:
                        final_content = []
                        for call in tool_calls:
                            mcp_result = await session.call_tool(call.name, call.input)
                            final_content.append(mcp_result.content[0].text)
                        return "\n".join(final_content)
                    else:
                        text_blocks = [content for content in response.content if content.type == "text"]
                        return "\n".join([b.text for b in text_blocks])

                else:
                    return f"❌ 錯誤：未知的 AI 服務提供者: {ai_provider}"

    except BaseException as e:
            full_error = traceback.format_exc()
            err_str = str(e)
            print(f"DEBUG 詳細錯誤內容:\n{full_error}")
            # 針對額度不足錯誤提供友善的提示
            if "credit balance is too low" in err_str or "balance" in err_str.lower():
                return "❌ AI 服務商額度不足，請前往該平台後台儲值，或在左側邊欄切換成其他 AI (如 Gemini) 或本地 Ollama 模式。"
            return f"❌ 系統錯誤: {err_str}\n\n詳細資訊:\n```\n{full_error}\n```"
            
def drink_ai_agent(user_message: str) -> str:
    """Streamlit 介面呼叫入口 (相容 Streamlit Community Cloud 與 Python 3.13 的事件迴圈)"""
    try:
        import anyio
        return anyio.run(process_with_ai, user_message)
    except BaseException as e:
        # 降級方案：使用普通 asyncio
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(process_with_ai(user_message))
        except BaseException as ex:
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
    
    # ⚙️ 助手模式配置區
    st.subheader("⚙️ 助手模式配置")
    modes = []
    if available_cloud_providers:
        modes.append("☁️ 雲端 AI 模式")
    if local_models:
        modes.append("🏠 本地 Ollama 模式")
        
    if not modes:
        st.warning("⚠️ 未偵測到任何可用模型 (無雲端金鑰且本地 Ollama 未啟動)")
        selected_mode = None
    else:
        # 使用者選擇模式
        selected_mode = st.radio("選擇 AI 運行模式", modes, index=0)
        
    if selected_mode == "☁️ 雲端 AI 模式":
        # 取得預設的雲端服務商
        cloud_p = list(available_cloud_providers.keys())[0]
        key_val, model_name = available_cloud_providers[cloud_p]
        
        ai_provider = cloud_p
        ai_model = model_name
        
        if cloud_p == "Gemini":
            client = genai.Client(api_key=key_val)
        elif cloud_p == "OpenAI":
            from openai import OpenAI
            client = OpenAI(api_key=key_val)
        elif cloud_p == "Anthropic":
            from anthropic import Anthropic
            client = Anthropic(api_key=key_val)
            
        st.success(f"目前使用雲端模型：`{ai_provider} ({ai_model})`")
        
    elif selected_mode == "🏠 本地 Ollama 模式":
        default_local_idx = 0
        # 優先尋找含有 gemma4 的本地模型
        for idx, m in enumerate(local_models):
            if "gemma4" in m.lower():
                default_local_idx = idx
                break
                
        selected_local_model = st.selectbox(
            "選擇本地模型", 
            local_models, 
            index=default_local_idx
        )
        
        ai_provider = "OpenAI"  # Ollama 可相容於 OpenAI 接口格式
        ai_model = selected_local_model
        
        from openai import OpenAI
        # 初始化指向本地 Ollama 的客戶端
        client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
        st.success(f"目前使用本地模型：`{ai_model}`")

    st.divider()
    
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
        
        if response and "✅" in response:
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