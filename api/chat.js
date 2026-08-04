export default async function handler(req, res) {
    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method Not Allowed' });
    }

    const { prompt, keys } = req.body;
    
    // 獲取金鑰：優先使用前端傳過來的金鑰，次要使用 Vercel 環境變數
    const geminiKey = keys?.geminiKey || process.env.GEMINI_KEY || process.env.GOOGLE_API_KEY;
    const openaiKey = keys?.openaiKey || process.env.OPENAI_KEY;

    if (geminiKey) {
        try {
            const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${geminiKey}`;
            const systemInstruction = "你是一個專業的飲品訂單助手。請一律使用「繁體中文」回答。你可以執行點餐、修改、刪除、查詢菜單或搜尋重複訂單。";
            const tools = [
                {
                    name: "get_menu",
                    description: "查詢目前所有的飲品品項、價格以及可加料的內容。",
                    parameters: { type: "OBJECT", properties: {} }
                },
                {
                    name: "place_drink_order",
                    description: "執行飲品點餐工具。當使用者表達想喝飲料或點餐時，請呼叫此工具。參數: name, drink_name, spec, topping",
                    parameters: {
                        type: "OBJECT",
                        properties: {
                            name: { type: "STRING", description: "訂購人姓名 (務必取得)" },
                            drink_name: { type: "STRING", description: "飲料名稱" },
                            spec: { type: "STRING", description: "甜度與冰量，如: 三分甜/微冰" },
                            topping: { type: "STRING", description: "加料內容，如: 招牌粉粿，若無則預設為『無』" }
                        },
                        required: ["name", "drink_name", "spec"]
                    }
                },
                {
                    name: "list_recent_orders",
                    description: "列出最近的所有訂單資訊。",
                    parameters: { type: "OBJECT", properties: {} }
                },
                {
                    name: "find_duplicate_orders_by_name",
                    description: "搜尋特定人物的重複訂單資料。參數: name",
                    parameters: {
                        type: "OBJECT",
                        properties: {
                            name: { type: "STRING", description: "要查詢的人名" }
                        },
                        required: ["name"]
                    }
                },
                {
                    name: "search_all_duplicates",
                    description: "掃描全部訂單，找出所有有重複訂單的人物。",
                    parameters: { type: "OBJECT", properties: {} }
                },
                {
                    name: "get_duplicate_statistics",
                    description: "取得重複訂單的比例與統計建議。",
                    parameters: { type: "OBJECT", properties: {} }
                }
            ];

            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    contents: [{ parts: [{ text: prompt }] }],
                    systemInstruction: { parts: [{ text: systemInstruction }] },
                    tools: [{ functionDeclarations: tools }],
                    generationConfig: { temperature: 0.7 }
                })
            });

            if (!response.ok) {
                const errText = await response.text();
                return res.status(response.status).json({ error: `Gemini API Error: ${errText}` });
            }

            const data = await response.json();
            const parts = data.candidates?.[0]?.content?.parts || [];
            
            const functionCalls = parts.filter(p => p.functionCall);
            if (functionCalls.length > 0) {
                const toolCalls = functionCalls.map((fc, i) => ({
                    id: `call_${i}_${Date.now()}`,
                    function: {
                        name: fc.functionCall.name,
                        arguments: JSON.stringify(fc.functionCall.args)
                    }
                }));
                return res.status(200).json({ tool_calls: toolCalls });
            }

            const content = parts.map(p => p.text).join("");
            return res.status(200).json({ content });

        } catch (e) {
            return res.status(500).json({ error: e.message });
        }
    }

    if (openaiKey) {
        try {
            const response = await fetch("https://api.openai.com/v1/chat/completions", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${openaiKey}`
                },
                body: JSON.stringify({
                    model: "gpt-4o-mini",
                    messages: [
                        { role: "system", content: "你是一個專業的飲品訂單助手。請一律使用「繁體中文」回答。你可以執行點餐、修改、刪除、查詢菜單或搜尋重複訂單。" },
                        { role: "user", content: prompt }
                    ],
                    tools: [
                        {
                            type: "function",
                            function: {
                                name: "get_menu",
                                description: "查詢目前所有的飲品品項、價格以及可加料的內容。",
                                parameters: { type: "object", properties: {} }
                            }
                        },
                        {
                            type: "function",
                            function: {
                                name: "place_drink_order",
                                description: "執行飲品點餐工具。當使用者表達想喝飲料或點餐時，請呼叫此工具。參數: name, drink_name, spec, topping",
                                parameters: {
                                    type: "object",
                                    properties: {
                                        name: { type: "string", description: "訂購人姓名 (務必取得)" },
                                        drink_name: { type: "string", description: "飲料名稱" },
                                        spec: { type: "string", description: "甜度與冰量，如: 三分甜/微冰" },
                                        topping: { type: "string", description: "加料內容，如: 招牌粉粿，若無則預設為『無』" }
                                    },
                                    required: ["name", "drink_name", "spec"]
                                }
                            }
                        },
                        {
                            type: "function",
                            function: {
                                name: "list_recent_orders",
                                description: "列出最近的所有訂單資訊。",
                                parameters: { type: "object", properties: {} }
                            }
                        },
                        {
                            type: "function",
                            function: {
                                name: "find_duplicate_orders_by_name",
                                description: "搜尋特定人物的重複訂單資料。參數: name",
                                parameters: {
                                    type: "object",
                                    properties: {
                                        name: { type: "string", description: "要查詢的人名" }
                                    },
                                    required: ["name"]
                                }
                            }
                        },
                        {
                            type: "function",
                            function: {
                                name: "search_all_duplicates",
                                description: "掃描全部訂單，找出所有有重複訂單的人物。",
                                parameters: { type: "object", properties: {} }
                            }
                        },
                        {
                            type: "function",
                            function: {
                                name: "get_duplicate_statistics",
                                description: "取得重複訂單的比例與統計建議。",
                                parameters: { type: "object", properties: {} }
                            }
                        }
                    ],
                    temperature: 0.7
                })
            });

            if (!response.ok) {
                const errText = await response.text();
                return res.status(response.status).json({ error: `OpenAI API Error: ${errText}` });
            }

            const data = await response.json();
            const message = data.choices[0].message;

            if (message.tool_calls && message.tool_calls.length > 0) {
                return res.status(200).json({ tool_calls: message.tool_calls });
            }
            return res.status(200).json({ content: message.content });
        } catch (e) {
            return res.status(500).json({ error: e.message });
        }
    }

    return res.status(400).json({ error: "No API Key configured on Server or Client. Please setup GEMINI_KEY or OPENAI_KEY." });
}
