# db_logic.py(requests (Realtime Database 專用))
import requests
from google.cloud import firestore
import json
import logging

# 設定日誌，方便除錯
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Firebase 即時資料庫 URL 
FIREBASE_URL = "https://myfinanceapp-f08ae-default-rtdb.firebaseio.com/drink_orders"

def firebase_bridge(action, data=None, doc_id=None):
    """
    通用 Firebase 溝通橋樑
    :param action: 操作行為 ("push", "fetch", "update", "delete")
    :param data: 要寫入或更新的字典資料
    :param doc_id: 指定的 Firebase 文件 ID (用於更新或刪除)
    :return: 根據 action 回傳資料或布林值
    """
    try:
        if action == "push" and data:
            # 寫入新訂單
            response = requests.post(f"{FIREBASE_URL}.json", json=data)
            response.raise_for_status()
            logger.info("Successfully pushed data to Firebase.")
            return response.json()

        elif action == "fetch":
            # 讀取所有訂單
            response = requests.get(f"{FIREBASE_URL}.json")
            response.raise_for_status()
            data_dict = response.json() or {}
            # 將 Firebase 的字典格式轉換為清單，並注入 ID
            return [{"id": k, **v} for k, v in data_dict.items()]

        elif action == "update" and doc_id and data:
            # 更新指定訂單
            response = requests.patch(f"{FIREBASE_URL}/{doc_id}.json", json=data)
            response.raise_for_status()
            logger.info(f"Successfully updated document: {doc_id}")
            return True

        elif action == "delete" and doc_id:
            # 刪除指定訂單
            response = requests.delete(f"{FIREBASE_URL}/{doc_id}.json")
            response.raise_for_status()
            logger.info(f"Successfully deleted document: {doc_id}")
            return True

    except requests.exceptions.RequestException as e:
        logger.error(f"Firebase API Error: {e}")
        return None

def fetch_cloud_orders():
    """便捷函式：獲取雲端訂單"""
    return firebase_bridge("fetch")

def add_cloud_order(order_data):
    """
    便捷函式：新增訂單
    order_data 格式範例: 
    {
        "姓名": "阿明", "飲品": "輕香烏龍綠", "規格": "微糖/少冰", 
        "加料": "粉粿", "金額": 60, "時間": "2026-04-13 14:00:00"
    }
    """
    return firebase_bridge("push", data=order_data)
    