# db_logic.py(Firestore 版本)
import logging
from google.cloud import firestore
from datetime import datetime

# 1. 確保 db 在全域範圍內先被宣告為 None
db = None
# 設定日誌，方便在 MCP Log 中查看狀態
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 初始化 Firestore 客戶端
# 專案 ID 根據您的截圖：myfinanceapp-f08ae
try:
    db = firestore.Client(project="myfinanceapp-f08ae")
    logger.info("Firestore client initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize Firestore: {e}")

def firebase_bridge(action, data=None, doc_id=None):
    """
    通用 Firebase Firestore 溝通橋樑
    :param action: 操作行為 ("push", "fetch", "update", "delete")
    :param data: 要寫入或更新的字典資料
    :param doc_id: 指定的文件 ID
    """
    try:
        # 指向您截圖中的集合名稱：drink_orders
        collection_ref = db.collection("drink_orders")

        if action == "push" and data:
            # 寫入新訂單，Firestore 會自動生成唯一 ID
            # 增加時間戳記確保排序正確
            data["timestamp"] = datetime.now().isoformat()
            update_time, doc_ref = collection_ref.add(data)
            logger.info(f"Successfully added document ID: {doc_ref.id} at {update_time}")
            return {"id": doc_ref.id}

        elif action == "fetch":
            # 讀取所有訂單，並按時間排序
            docs = collection_ref.order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
            return [{"id": doc.id, **doc.to_dict()} for doc in docs]

        elif action == "update" and doc_id and data:
            # 更新指定文件
            doc_ref = collection_ref.document(doc_id)
            doc_ref.update(data)
            logger.info(f"Successfully updated document: {doc_id}")
            return True

        elif action == "delete" and doc_id:
            # 刪除指定文件
            collection_ref.document(doc_id).delete()
            logger.info(f"Successfully deleted document: {doc_id}")
            return True

    except Exception as e:
        logger.error(f"Firestore API Error: {e}")
        return None

def fetch_cloud_orders():
    """便捷函式：獲取雲端訂單"""
    return firebase_bridge("fetch")

def add_cloud_order(order_data):
    """便捷函式：新增訂單"""
    return firebase_bridge("push", data=order_data) 