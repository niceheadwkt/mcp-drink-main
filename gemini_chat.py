import os
from google import genai  # 注意：這裡是 from google import genai，不是 generativeai

# 初始化 Client（新版語法）
# 指定 api_version='v1beta' 以確保模型路徑正確
client = genai.Client(
    api_key=os.environ.get("GOOGLE_API_KEY"),
    http_options={'api_version': 'v1beta'}
)

def main():
    # 加入這行來偵查
    print("可用模型清單：", [m.name for m in client.models.list()])

    print("--- 已進入 2026 最新版 Gemini CLI (v1beta) ---")
    while True:
        user_input = input("您：")
        if user_input.lower() in ['quit', 'exit', '離開']:
            break
            
        try:
            # 新版 SDK 的呼叫方式是 client.models.generate_content
            response = client.models.generate_content(
                model="models/gemini-2.5-flash",
                contents=user_input
            )
            print(f"\nGemini：\n{response.text}\n")
        except Exception as e:
            print(f"\n發生錯誤：{e}\n")

if __name__ == "__main__":
    main()