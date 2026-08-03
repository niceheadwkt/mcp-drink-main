# order_utils.py
from rapidfuzz import process

# --- 核心菜單數據 (唯一來源) ---
NESTED_MENU = {
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

# 自動扁平化為原本 MCP 用的格式: {"飲品名": 價格}
DRINK_MENU = {item: price for category in NESTED_MENU.values() for item, price in category.items()}

# --- 加料數據 ---
TOPPINGS_MENU = {
    "無": 0, "招牌粉粿": 15, "草仔粿": 15, "雙粉": 15, "琥珀粉圓": 10, "蘆薈": 15, "嫩仙草": 10
}

def get_drink_info(user_input):
    """
    透過模糊比對找到最正確的品項名稱與價格
    回傳範例: ("輕香烏龍綠", 45)
    """
    choices = list(DRINK_MENU.keys())
    # extractOne 會回傳 (名稱, 分數)
    best_match, score, _ = process.extractOne(user_input, choices)
    
    if score >= 75:  # 設定門檻，避免完全無關的也比對成功
        return best_match, DRINK_MENU[best_match]
    return None, 0
    
def get_topping_info(user_input):
    """
    透過模糊比對找到最正確的品項名稱與價格
    回傳範例: ("招牌粉粿", 15)
    """
    choices = list(TOPPINGS_MENU.keys())
    # extractOne 會回傳 (名稱, 分數)
    best_match, score, _ = process.extractOne(user_input, choices)
    
    if score >= 75:  # 設定門檻，避免完全無關的也比對成功
        return best_match, TOPPINGS_MENU[best_match]
    return None, 0
    
def validate_spec(spec_text):
    """檢查規格是否同時包含糖度與冰量關鍵字"""
    sugar_keywords = ["糖", "甜", "原味"] # 原味有時代表固定甜度
    ice_keywords = ["冰", "溫", "熱", "常溫"]
    
    has_sugar = any(k in spec_text for k in sugar_keywords)
    has_ice = any(k in spec_text for k in ice_keywords)
    
    return has_sugar and has_ice
    
def calculate_price(drink_name, topping_name="無"):
    """
    計算單杯總金額
    """
    if topping_name is None:
        topping_name = "無"
    base_price = DRINK_MENU.get(drink_name, 0)
    topping_price = TOPPINGS_MENU.get(topping_name, 0)
    return base_price + topping_price