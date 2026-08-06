import os
import google.generativeai as genai

# 初始化配置
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

# 選擇模型 (建議使用 gemini-1.5-flash 速度最快)
model = genai.GenerativeModel('gemini-1.5-flash')

def main():
    print("--- 已進入 Gemini CLI 模式 (輸入 'quit' 離開) ---")
    while True:
        user_input = input("您：")
        if user_input.lower() in ['quit', 'exit', '離開']:
            break
            
        response = model.generate_content(user_input)
        print(f"\nGemini：\n{response.text}\n")

if __name__ == "__main__":
    main()