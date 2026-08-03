# db_logic.py(Firestore 版本)
import logging
import os
from google.cloud import firestore
from datetime import datetime

# 設定日誌，方便在 MCP Log 中追蹤連線與寫入狀態
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 全域客戶端變數
_db_client = None

def get_firestore_client():
    """
    獲取並初始化 Firestore 客戶端。
    採用單例模式避免重複初始化與 NoneType 錯誤。
    支援本地讀取金鑰檔，或在雲端讀取 Streamlit Secrets 的 gcp_service_account 設定。
    """
    global _db_client
    if _db_client is None:
        try:
            # 優先從 Streamlit Secrets 讀取 (適合部署到 Streamlit Community Cloud)
            import streamlit as st
            if "gcp_service_account" in st.secrets:
                logger.info("Attempting to load credentials from Streamlit Secrets.")
                from google.oauth2 import service_account
                creds_info = dict(st.secrets["gcp_service_account"])
                # 確保 private_key 中換行符號正確
                if "private_key" in creds_info:
                    creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
                creds = service_account.Credentials.from_service_account_info(creds_info)
                _db_client = firestore.Client(credentials=creds, project=creds_info.get("project_id"))
                logger.info("Firestore client initialized successfully via Streamlit Secrets.")
                return _db_client
        except Exception as e:
            logger.warning(f"Failed to load credentials from Streamlit Secrets: {e}. Trying local file...")

        try:
            # 備用方案：從本地金鑰檔載入 (適合本地開發)
            current_dir = os.path.dirname(os.path.abspath(__file__))
            key_filename = "firebase-adminsdk.json"
            key_path = os.path.join(current_dir, key_filename)
            
            if not os.path.exists(key_path):
                logger.error(f"FATAL: Key file NOT FOUND at {key_path} and no Secrets found.")
                return None

            logger.info(f"Attempting to load key from: {key_path}")
            _db_client = firestore.Client.from_service_account_json(key_path)            
            logger.info("Firestore client initialized successfully via local JSON key.")
        except Exception as e:
            logger.error(f"Failed to initialize Firestore Client: {e}")
            return None
    return _db_client

def firebase_bridge(action, data=None, doc_id=None):
    """
    通用 Firebase Firestore 溝通橋樑
    :param action: 操作行為 ("push", "fetch", "update", "delete")
    :param data: 要寫入或更新的字典資料
    :param doc_id: 指定的文件 ID
    """
    db = get_firestore_client()
    
    if db is None:
        logger.error("Firestore database connection is not available.")
        return None

    try:
        # 指向您控制台中的集合名稱：drink_orders
        collection_ref = db.collection("drink_orders")

        if action == "push" and data:
            # 增加時間戳記以利排序
            data["timestamp"] = datetime.now().isoformat()
            # 執行 Firestore 寫入
            update_time, doc_ref = collection_ref.add(data)
            logger.info(f"Successfully added document ID: {doc_ref.id}")
            return {"id": doc_ref.id}

        elif action == "fetch":
            # 讀取所有訂單，並按時間倒序排列
            docs = collection_ref.order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
            return [{"id": doc.id, **doc.to_dict()} for doc in docs]

        elif action == "update" and doc_id and data:
            # 更新指定 ID 的文件
            doc_ref = collection_ref.document(doc_id)
            doc_ref.update(data)
            logger.info(f"Successfully updated document: {doc_id}")
            return True

        elif action == "delete" and doc_id:
            # 刪除指定 ID 的文件
            collection_ref.document(doc_id).delete()
            logger.info(f"Successfully deleted document: {doc_id}")
            return True

    except Exception as e:
        logger.error(f"Firestore Operation Error: {e}")
        return None

def fetch_cloud_orders():
    """便捷函式：獲取雲端所有點餐資料"""
    return firebase_bridge("fetch")

def add_cloud_order(order_data):
    """便捷函式：新增一筆點餐資料到 Firestore"""
    return firebase_bridge("push", data=order_data)