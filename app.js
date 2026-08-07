// app.js

// --- 1. 一沐日菜單與價格數據 ---
const NESTED_MENU = {
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
};

const TOPPINGS_MENU = {
    "無": 0, "招牌粉粿": 15, "草仔粿": 15, "雙粉": 15, "琥珀粉圓": 10, "蘆薈": 15, "嫩仙草": 10
};

// 扁平化菜單
const DRINK_MENU = {};
for (const category in NESTED_MENU) {
    for (const item in NESTED_MENU[category]) {
        DRINK_MENU[item] = NESTED_MENU[category][item];
    }
}

// --- 2. 初始化 Firebase (對接 myfinanceapp-f08ae) ---
const firebaseConfig = {
    projectId: "myfinanceapp-f08ae"
};
firebase.initializeApp(firebaseConfig);
const db = firebase.firestore();
const collectionRef = db.collection("drink_orders");

// --- 3. 全局變數與狀態管理 ---
let ordersList = [];
let isEditing = false;
let activeCloudProvider = null;
let chatHistory = [
    { role: "assistant", content: "想喝什麼？我可以幫您點餐、修改或查重複訂單。" }
];

// --- 4. DOM 載入與初始化 ---
document.addEventListener("DOMContentLoaded", () => {
    initFormSelects();
    initEventListeners();
    loadSettings();
    syncOrdersFromFirestore();
    detectActiveAIConfig();
    checkOllamaStatus();
    registerServiceWorker();
});

function registerServiceWorker() {
    if ("serviceWorker" in navigator) {
        navigator.serviceWorker.register("./sw.js")
            .then(reg => console.log("PWA Service Worker registered:", reg.scope))
            .catch(err => console.warn("PWA Service Worker registration failed:", err));
    }
}

// 初始化表單選單
function initFormSelects() {
    const categorySelect = document.getElementById("category");
    const itemSelect = document.getElementById("item");
    const toppingsSelect = document.getElementById("toppings");

    // 1. 系列選單
    categorySelect.innerHTML = "";
    Object.keys(NESTED_MENU).forEach(cat => {
        const opt = document.createElement("option");
        opt.value = cat;
        opt.textContent = cat;
        categorySelect.appendChild(opt);
    });

    // 2. 飲品選單連動
    const updateItems = () => {
        const selectedCat = categorySelect.value;
        itemSelect.innerHTML = "";
        const items = NESTED_MENU[selectedCat];
        Object.keys(items).forEach(itm => {
            const opt = document.createElement("option");
            opt.value = itm;
            opt.textContent = `${itm} ($${items[itm]}元)`;
            itemSelect.appendChild(opt);
        });
        calculateFormPrice();
    };
    categorySelect.addEventListener("change", updateItems);
    updateItems();

    // 3. 加料選單
    toppingsSelect.innerHTML = "";
    Object.keys(TOPPINGS_MENU).forEach(top => {
        const opt = document.createElement("option");
        opt.value = top;
        opt.textContent = top === "無" ? "無" : `${top} (+$${TOPPINGS_MENU[top]}元)`;
        if (top === "無") opt.selected = true;
        toppingsSelect.appendChild(opt);
    });

    // 監聽加料與飲品變更重新計價
    itemSelect.addEventListener("change", calculateFormPrice);
    toppingsSelect.addEventListener("change", calculateFormPrice);
}

// 計算當前表單價格
function calculateFormPrice() {
    const categorySelect = document.getElementById("category");
    const itemSelect = document.getElementById("item");
    const toppingsSelect = document.getElementById("toppings");
    const totalPriceEl = document.getElementById("total-price");

    if (!itemSelect.value) return;

    const basePrice = NESTED_MENU[categorySelect.value][itemSelect.value];
    let toppingsPrice = 0;
    
    // 獲取所有選取的加料價格
    Array.from(toppingsSelect.selectedOptions).forEach(opt => {
        toppingsPrice += TOPPINGS_MENU[opt.value];
    });

    totalPriceEl.textContent = `$${basePrice + toppingsPrice}`;
}

// 監聽所有按鈕與 UI 事件
function initEventListeners() {
    // 側邊欄開關
    document.getElementById("toggle-sidebar").addEventListener("click", () => {
        document.getElementById("sidebar").classList.toggle("active");
        document.getElementById("sidebar-backdrop").classList.toggle("active");
    });
    document.getElementById("close-sidebar").addEventListener("click", () => {
        document.getElementById("sidebar").classList.remove("active");
        document.getElementById("sidebar-backdrop").classList.remove("active");
    });
    document.getElementById("sidebar-backdrop").addEventListener("click", () => {
        document.getElementById("sidebar").classList.remove("active");
        document.getElementById("sidebar-backdrop").classList.remove("active");
    });

    // 設定面板開關
    document.getElementById("toggle-settings").addEventListener("click", () => {
        document.getElementById("settings-panel").classList.add("active");
        updateCacheManagerUI();
    });
    document.getElementById("close-settings").addEventListener("click", () => {
        document.getElementById("settings-panel").classList.remove("active");
    });

    // 儲存設定按鈕
    document.getElementById("save-settings").addEventListener("click", saveSettings);

    // AI 模式切換顯示連動
    const modeRadios = document.getElementsByName("ai-mode");
    modeRadios.forEach(radio => {
        radio.addEventListener("change", (e) => {
            const val = e.target.value;
            localStorage.setItem("ai-mode", val);
            const localModelRow = document.getElementById("local-model-row");
            const webllmModelRow = document.getElementById("webllm-model-row");
            const webllmProgressRow = document.getElementById("webllm-progress-row");
            
            // 隱藏進度條
            if (webllmProgressRow) webllmProgressRow.classList.add("hidden");

            if (val === "cloud") {
                localModelRow.classList.add("hidden");
                webllmModelRow.classList.add("hidden");
            } else if (val === "local") {
                localModelRow.classList.remove("hidden");
                webllmModelRow.classList.add("hidden");
                checkOllamaStatus();
            } else if (val === "webllm") {
                localModelRow.classList.add("hidden");
                webllmModelRow.classList.remove("hidden");
            }
            detectActiveAIConfig();
        });
    });

    // 當選取本地模型變更時，立即儲存並更新狀態
    document.getElementById("local-model-select").addEventListener("change", (e) => {
        localStorage.setItem("local-model", e.target.value);
        detectActiveAIConfig();
    });

    // 當選取網頁內置模型變更時，立即儲存並更新狀態
    document.getElementById("webllm-model-select").addEventListener("change", (e) => {
        const val = e.target.value;
        localStorage.setItem("webllm-model", val);
        const customRow = document.getElementById("webllm-custom-model-row");
        if (val === "custom") {
            customRow.classList.remove("hidden");
        } else {
            customRow.classList.add("hidden");
        }
        detectActiveAIConfig();
    });

    // 監聽自訂模型輸入變更
    document.getElementById("webllm-custom-model-input").addEventListener("input", (e) => {
        localStorage.setItem("webllm-custom-model", e.target.value.trim());
        detectActiveAIConfig();
    });


    // 重整本地模型按鈕
    document.getElementById("refresh-local-models").addEventListener("click", checkOllamaStatus);


    // 表單送出 (新增/修改)
    document.getElementById("order-form").addEventListener("submit", handleOrderSubmit);
    document.getElementById("cancel-edit-btn").addEventListener("click", cancelEditMode);

    // 重複檢查按鈕
    document.getElementById("btn-scan-all").addEventListener("click", runGlobalDuplicateScan);
    document.getElementById("btn-stats").addEventListener("click", runDuplicateStatistics);
    document.getElementById("btn-search-single").addEventListener("click", runSinglePersonScan);

    // 下載 CSV 按鈕
    document.getElementById("btn-download-csv").addEventListener("click", downloadOrdersCSV);

    // AI 聊天傳送按鈕
    document.getElementById("send-chat").addEventListener("click", handleChatSend);
    document.getElementById("chat-input").addEventListener("keypress", (e) => {
        if (e.key === "Enter") handleChatSend();
    });
}

// --- 5. Firebase 雲端資料同步 ---
function syncOrdersFromFirestore() {
    const tbody = document.getElementById("orders-tbody");
    
    // 即時監聽 Firestore
    collectionRef.orderBy("timestamp", "desc").onSnapshot(snapshot => {
        ordersList = [];
        tbody.innerHTML = "";
        
        if (snapshot.empty) {
            tbody.innerHTML = `<tr><td colspan="6" class="text-center">目前無任何訂單資料。</td></tr>`;
            updateSummaryFooter();
            return;
        }

        snapshot.forEach(doc => {
            const data = doc.data();
            data.id = doc.id;
            ordersList.push(data);
            
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td>${escapeHTML(data.name || "匿名")}</td>
                <td>${escapeHTML(data.item || "未知")}</td>
                <td>${escapeHTML(data.spec || "三分甜/微冰")}</td>
                <td>${escapeHTML(data.toppings || "無")}</td>
                <td>$${data.price || 0}</td>
                <td>
                    <button class="btn btn-secondary btn-sm" onclick="enterEditMode('${data.id}')"><i class="fa-solid fa-edit"></i> 修改</button>
                    <button class="btn btn-secondary btn-sm" style="color: #ef4444;" onclick="deleteOrder('${data.id}')"><i class="fa-solid fa-trash"></i> 刪除</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
        
        updateSummaryFooter();
    }, error => {
        console.error("Firestore sync error: ", error);
        tbody.innerHTML = `<tr><td colspan="6" class="text-center text-danger">雲端載入錯誤：${error.message}</td></tr>`;
    });
}

// 更新底部金額與總杯數匯總
function updateSummaryFooter() {
    const infoEl = document.getElementById("summary-info");
    const totalCup = ordersList.length;
    const totalAmount = ordersList.reduce((sum, o) => sum + (o.price || 0), 0);
    infoEl.textContent = `📊 總計：${totalCup} 杯 | 總金額：$${totalAmount} 元`;
}

// 處理新增/修改點餐提交
function handleOrderSubmit(e) {
    e.preventDefault();

    const editId = document.getElementById("edit-id").value;
    const name = document.getElementById("name").value.trim();
    const categorySelect = document.getElementById("category");
    const itemSelect = document.getElementById("item");
    const sugar = document.getElementById("sugar").value;
    const ice = document.getElementById("ice").value;
    const toppingsSelect = document.getElementById("toppings");

    if (!name) {
        alert("請輸入訂購人姓名！");
        return;
    }

    // 整理加料
    const selectedToppings = Array.from(toppingsSelect.selectedOptions)
        .map(opt => opt.value)
        .filter(val => val !== "無");
    const toppingsStr = selectedToppings.length > 0 ? selectedToppings.join("、") : "無";

    // 計算價格
    const basePrice = NESTED_MENU[categorySelect.value][itemSelect.value];
    const toppingsPrice = selectedToppings.reduce((sum, t) => sum + TOPPINGS_MENU[t], 0);
    const totalPrice = basePrice + toppingsPrice;

    const payload = {
        name: name,
        item: itemSelect.value,
        spec: `${sugar}/${ice}`,
        toppings: toppingsStr,
        price: totalPrice,
        timestamp: new Date().toISOString()
    };

    if (isEditing && editId) {
        // 更新資料
        collectionRef.doc(editId).update(payload)
            .then(() => {
                cancelEditMode();
                showBotMessage("✅ 成功為您儲存修改點餐！");
            })
            .catch(err => alert("修改失敗: " + err.message));
    } else {
        // 新增資料
        collectionRef.add(payload)
            .then(() => {
                document.getElementById("order-form").reset();
                initFormSelects();
                showBotMessage("🚀 成功將訂單同步寫入雲端！");
            })
            .catch(err => alert("新增失敗: " + err.message));
    }
}

// 進入修改模式
window.enterEditMode = function(id) {
    const order = ordersList.find(o => o.id === id);
    if (!order) return;

    isEditing = true;
    document.getElementById("form-title").innerHTML = `<i class="fa-solid fa-edit"></i> 修改訂單`;
    document.getElementById("edit-id").value = id;
    document.getElementById("name").value = order.name;

    // 尋找品項系列
    let foundCat = Object.keys(NESTED_MENU)[0];
    for (const cat in NESTED_MENU) {
        if (order.item in NESTED_MENU[cat]) {
            foundCat = cat;
            break;
        }
    }
    document.getElementById("category").value = foundCat;
    
    // 連動更新飲品清單
    const itemSelect = document.getElementById("item");
    itemSelect.innerHTML = "";
    Object.keys(NESTED_MENU[foundCat]).forEach(itm => {
        const opt = document.createElement("option");
        opt.value = itm;
        opt.textContent = `${itm} ($${NESTED_MENU[foundCat][itm]}元)`;
        itemSelect.appendChild(opt);
    });
    itemSelect.value = order.item;

    // 甜度冰量拆解
    if (order.spec && order.spec.includes("/")) {
        const [sugar, ice] = order.spec.split("/");
        document.getElementById("sugar").value = sugar;
        document.getElementById("ice").value = ice;
    }

    // 處理加料
    const toppingsSelect = document.getElementById("toppings");
    Array.from(toppingsSelect.options).forEach(opt => {
        opt.selected = false;
    });

    if (order.toppings && order.toppings !== "無") {
        const activeTops = order.toppings.split("、");
        Array.from(toppingsSelect.options).forEach(opt => {
            if (activeTops.includes(opt.value)) {
                opt.selected = true;
            }
        });
    } else {
        Array.from(toppingsSelect.options).forEach(opt => {
            if (opt.value === "無") opt.selected = true;
        });
    }

    calculateFormPrice();
    document.getElementById("submit-btn").innerHTML = `<i class="fa-solid fa-save"></i> 儲存修改`;
    document.getElementById("cancel-edit-btn").classList.remove("hidden");
    
    // 滾動到表單
    document.getElementById("order-form").scrollIntoView({ behavior: "smooth" });
};

// 取消修改模式
function cancelEditMode() {
    isEditing = false;
    document.getElementById("form-title").innerHTML = `<i class="fa-solid fa-edit"></i> 新增點餐`;
    document.getElementById("edit-id").value = "";
    document.getElementById("order-form").reset();
    document.getElementById("submit-btn").innerHTML = `<i class="fa-solid fa-cloud-arrow-up"></i> 同步至雲端`;
    document.getElementById("cancel-edit-btn").classList.add("hidden");
    initFormSelects();
}

// 刪除點餐
window.deleteOrder = function(id) {
    if (confirm("您確定要刪除這筆訂單嗎？")) {
        collectionRef.doc(id).delete()
            .then(() => {
                showBotMessage("🗑️ 訂單已成功自雲端刪除！");
            })
            .catch(err => alert("刪除失敗: " + err.message));
    }
};

// --- 6. 系統與 AI 設定儲存 ---
function saveSettings() {
    // 儲存金鑰
    localStorage.setItem("key-gemini", document.getElementById("key-gemini").value.trim());
    localStorage.setItem("key-openai", document.getElementById("key-openai").value.trim());
    localStorage.setItem("key-anthropic", document.getElementById("key-anthropic").value.trim());
    localStorage.setItem("proxy-endpoint", document.getElementById("proxy-endpoint").value.trim());
    localStorage.setItem("local-api-url", document.getElementById("local-api-url").value.trim());

    document.getElementById("settings-panel").classList.remove("active");
    detectActiveAIConfig();
}

function loadSettings() {
    const aiMode = localStorage.getItem("ai-mode") || "cloud";
    document.querySelector(`input[name="ai-mode"][value="${aiMode}"]`).checked = true;

    const localModelRow = document.getElementById("local-model-row");
    const webllmModelRow = document.getElementById("webllm-model-row");
    if (aiMode === "cloud") {
        localModelRow.classList.add("hidden");
        webllmModelRow.classList.add("hidden");
    } else if (aiMode === "local") {
        localModelRow.classList.remove("hidden");
        webllmModelRow.classList.add("hidden");
    } else if (aiMode === "webllm") {
        localModelRow.classList.add("hidden");
        webllmModelRow.classList.remove("hidden");
    }

    document.getElementById("key-gemini").value = localStorage.getItem("key-gemini") || "";
    document.getElementById("key-openai").value = localStorage.getItem("key-openai") || "";
    document.getElementById("key-anthropic").value = localStorage.getItem("key-anthropic") || "";
    document.getElementById("proxy-endpoint").value = localStorage.getItem("proxy-endpoint") || "/api/chat";
    document.getElementById("local-api-url").value = localStorage.getItem("local-api-url") || "http://localhost:11434";

    const savedWebLLMModel = localStorage.getItem("webllm-model") || "Qwen2.5-1.5B-Instruct-q4f16_1-MLC";
    document.getElementById("webllm-model-select").value = savedWebLLMModel;

    const savedCustomModel = localStorage.getItem("webllm-custom-model") || "";
    document.getElementById("webllm-custom-model-input").value = savedCustomModel;

    const customRow = document.getElementById("webllm-custom-model-row");
    if (savedWebLLMModel === "custom") {
        customRow.classList.remove("hidden");
    } else {
        customRow.classList.add("hidden");
    }
}


// 偵測目前啟用的 AI 客戶端
function detectActiveAIConfig() {
    const aiMode = localStorage.getItem("ai-mode") || "cloud";
    const statusEl = document.getElementById("active-model-status");

    if (aiMode === "local") {
        const localModel = localStorage.getItem("local-model") || "載入中...";
        statusEl.innerHTML = `🟢 模式: 🏠 本地 Ollama | 模型: <code>${localModel}</code>`;
        activeCloudProvider = "Ollama";
        return;
    }

    if (aiMode === "webllm") {
        let webllmModel = localStorage.getItem("webllm-model") || "Qwen2.5-1.5B-Instruct-q4f16_1-MLC";
        if (webllmModel === "custom") {
            const customModel = localStorage.getItem("webllm-custom-model") || "";
            webllmModel = customModel ? `自訂: ${customModel}` : "請輸入自訂模型 ID";
        }
        statusEl.innerHTML = `🟢 模式: 🌐 內置 AI | 模型: <code>${webllmModel.split("-q4f")[0]}</code>`;
        activeCloudProvider = "WebLLM";
        return;
    }

    // 雲端模式
    const gemini = localStorage.getItem("key-gemini");
    const openai = localStorage.getItem("key-openai");
    const anthropic = localStorage.getItem("key-anthropic");

    if (gemini) {
        statusEl.innerHTML = `🟢 模式: ☁️ 雲端 Gemini | 模型: <code>gemini-2.5-flash</code>`;
        activeCloudProvider = "Gemini";
    } else if (openai) {
        statusEl.innerHTML = `🟢 模式: ☁️ 雲端 OpenAI | 模型: <code>gpt-4o-mini</code>`;
        activeCloudProvider = "OpenAI";
    } else if (anthropic) {
        statusEl.innerHTML = `🟢 模式: ☁️ 雲端 Anthropic | 模型: <code>claude-3-5-sonnet</code>`;
        activeCloudProvider = "Anthropic";
    } else {
        // 未輸入金鑰，走預設雲端 Proxy (由伺服器端環境變數決定)
        statusEl.innerHTML = `🟡 模式: ☁️ 雲端 Proxy 中轉 | 依託管平台預設模型為主`;
        activeCloudProvider = "Proxy";
    }
}

// 檢查本地 Ollama 服務狀態與拉取模型
async function checkOllamaStatus() {
    const select = document.getElementById("local-model-select");
    const refBtn = document.getElementById("refresh-local-models");
    
    select.innerHTML = "<option>偵測連線中...</option>";
    refBtn.disabled = true;

    // 取得自訂的 API 網址，去掉尾端斜線
    let localApiUrl = (localStorage.getItem("local-api-url") || "http://localhost:11434").replace(/\/+$/, "");

    try {
        let models = [];
        let connected = false;
        
        // 嘗試 1：Ollama API 格式 (/api/tags)
        let res = await fetch(`${localApiUrl}/api/tags`).catch(() => null);
        if (res) {
            connected = true;
            if (res.ok) {
                const data = await res.json();
                const rawModels = data.models || [];
                models = rawModels.map(m => ({ name: m.name, size: m.size || 0 }));
            }
        }
        
        // 如果第一個嘗試連不上或者沒有模型，嘗試第二個
        if (!connected || models.length === 0) {
            // 嘗試 2：OpenAI / PocketPal 格式 (/v1/models)
            const res2 = await fetch(`${localApiUrl}/v1/models`).catch(() => null);
            if (res2) {
                connected = true;
                if (res2.ok) {
                    const data = await res2.json();
                    const rawModels = data.data || [];
                    models = rawModels.map(m => ({ name: m.id, size: 0 }));
                }
            }
        }

        if (!connected) {
            throw new Error("無法連線至該端點");
        }

        if (models.length > 0) {
            select.innerHTML = "";
            let defaultIdx = 0;
            models.forEach((m, idx) => {
                const opt = document.createElement("option");
                opt.value = m.name;
                const sizeText = m.size ? ` (${(m.size / (1024*1024*1024)).toFixed(1)}GB)` : "";
                opt.textContent = `${m.name}${sizeText}`;
                if (m.name.toLowerCase().includes("gemma") || m.name.toLowerCase().includes("qwen")) defaultIdx = idx;
                select.appendChild(opt);
            });
            
            // 讀取先前儲存的模型設定
            const savedModel = localStorage.getItem("local-model");
            if (savedModel && Array.from(select.options).some(o => o.value === savedModel)) {
                select.value = savedModel;
            } else {
                select.selectedIndex = defaultIdx;
                localStorage.setItem("local-model", select.value);
            }
            
            detectActiveAIConfig();
        } else {
            select.innerHTML = "<option value=''>已連線，但服務端未下載或載入任何模型</option>";
        }
    } catch (e) {
        select.innerHTML = `<option value=''>無法連線至本地 API (${localApiUrl.replace(/^https?:\/\//, "")})</option>`;
    } finally {
        refBtn.disabled = false;
    }
}



// --- 7. 重複訂單檢查核心邏輯 (客戶端極速處理) ---
function analyzeDuplicates() {
    if (ordersList.length === 0) return { groups: {}, people: {} };

    const personGroups = {};
    ordersList.forEach(o => {
        const name = o.name || "匿名";
        if (!personGroups[name]) personGroups[name] = [];
        personGroups[name].push(o);
    });

    const dupPeople = {};
    const detailedGroups = {};

    for (const name in personGroups) {
        const list = personGroups[name];
        const comboGroups = {};
        
        list.forEach(o => {
            const signature = `${o.item}|${o.spec}|${o.toppings || "無"}`;
            if (!comboGroups[signature]) comboGroups[signature] = [];
            comboGroups[signature].push(o);
        });

        const duplicates = Object.keys(comboGroups)
            .filter(sig => comboGroups[sig].length > 1)
            .map(sig => comboGroups[sig]);

        if (duplicates.length > 0) {
            detailedGroups[name] = duplicates;
            dupPeople[name] = {
                totalOrders: list.length,
                dupCount: duplicates.reduce((sum, g) => sum + (g.length - 1), 0),
                groupsCount: duplicates.length
            };
        }
    }

    return { groups: detailedGroups, people: dupPeople };
}

function runGlobalDuplicateScan() {
    const resultsEl = document.getElementById("dup-results");
    resultsEl.classList.remove("hidden");
    
    const analysis = analyzeDuplicates();
    const sortedPeople = Object.keys(analysis.people).map(name => ({
        name, ...analysis.people[name]
    })).sort((a, b) => b.dupCount - a.dupCount);

    if (sortedPeople.length === 0) {
        resultsEl.textContent = "🔍 全局重複訂單掃描\n========================================\n\n✅ 掃描完成：全部訂單皆為獨立，沒有重複情況。";
        return;
    }

    let report = `🔍 全局重複訂單掃描報告\n========================================\n\n共找到 ${sortedPeople.length} 個人有重複點餐：\n\n`;
    sortedPeople.forEach((p, idx) => {
        report += `${idx + 1}. 👤 ${p.name}\n`;
        report += `   📊 總點單：${p.totalOrders} 杯\n`;
        report += `   ⚠️ 重複組：${p.groupsCount} 組\n`;
        report += `   🔁 重複筆：${p.dupCount} 筆\n`;
        report += `   💡 輸入「${p.name}」進行單人查詢可看詳細時間\n\n`;
    });

    resultsEl.textContent = report;
}

function runDuplicateStatistics() {
    const resultsEl = document.getElementById("dup-results");
    resultsEl.classList.remove("hidden");

    if (ordersList.length === 0) {
        resultsEl.textContent = "📊 重複訂單統計報告\n========================================\n\n📭 目前尚無點餐資料，無法統計。";
        return;
    }

    const analysis = analyzeDuplicates();
    const totalCup = ordersList.length;
    const totalDups = Object.values(analysis.people).reduce((sum, p) => sum + p.dupCount, 0);
    const dupRate = ((totalDups / totalCup) * 100).toFixed(1);

    // 統計熱門重複品項
    const itemCounts = {};
    Object.values(analysis.groups).forEach(personDups => {
        personDups.forEach(group => {
            const item = group[0].item;
            itemCounts[item] = (itemCounts[item] || 0) + (group.length - 1);
        });
    });

    const sortedItems = Object.keys(itemCounts).map(item => ({
        item, count: itemCounts[item]
    })).sort((a,b) => b.count - a.count);

    let report = `📊 全局重複訂單統計報告\n========================================\n\n`;
    report += `📈 總訂單杯數：${totalCup} 杯\n`;
    report += `⚠️ 重複總杯數：${totalDups} 杯\n`;
    report += `🔂 訂單重複率：${dupRate}%\n\n`;
    report += `🔥 最熱門的「重複點餐」品項排名：\n`;

    if (sortedItems.length === 0) {
        report += `   （目前無任何重複品項）\n`;
    } else {
        sortedItems.forEach((i, idx) => {
            report += `   ${idx + 1}. ${i.item} (重複 ${i.count} 次)\n`;
        });
    }

    resultsEl.textContent = report;
}

function runSinglePersonScan() {
    const name = document.getElementById("search-name").value.trim();
    const resultsEl = document.getElementById("dup-results");

    if (!name) {
        alert("請輸入要查詢的姓名！");
        return;
    }

    resultsEl.classList.remove("hidden");
    const analysis = analyzeDuplicates();
    const personDups = analysis.groups[name];

    if (!personDups) {
        const hasOrder = ordersList.some(o => o.name === name);
        if (hasOrder) {
            resultsEl.textContent = `🔍 ${name} 的個人重複檢查\n========================================\n\n✅ 該使用者有訂餐，但皆為獨立規格，沒有重複訂購。`;
        } else {
            resultsEl.textContent = `🔍 ${name} 的個人重複檢查\n========================================\n\n❌ 找不到名為「${name}」的點餐紀錄。`;
        }
        return;
    }

    let report = `🔍 ${name} 的個人重複點單詳細報告\n========================================\n\n`;
    report += `⚠️ 發現共 ${personDups.length} 組重複訂餐：\n\n`;

    personDups.forEach((group, idx) => {
        const first = group[0];
        report += `【第 ${idx + 1} 組】重複 ${group.length} 次\n`;
        report += `   🥤 飲品：${first.item}\n`;
        report += `   🌡️ 規格：${first.spec}\n`;
        report += `   💎 加料：${first.toppings || "無"}\n`;
        report += `   💰 單杯金額：$${first.price} 元\n`;
        report += `   📅 訂購詳細時間與 ID：\n`;
        group.forEach((o, i) => {
            const timeStr = o.timestamp ? new Date(o.timestamp).toLocaleString("zh-TW") : "無時間記錄";
            report += `      ${i + 1}. ${timeStr} (ID: ${o.id.substring(0,6)}...)\n`;
        });
        report += "\n";
    });

    resultsEl.textContent = report;
}

// 匯出訂單為 CSV 檔案
function downloadOrdersCSV() {
    if (ordersList.length === 0) {
        alert("目前尚無資料可供下載！");
        return;
    }

    // 欄位定義
    const headers = ["姓名", "飲品", "規格", "加料", "金額", "時間"];
    const rows = ordersList.map(o => [
        o.name || "匿名",
        o.item || "未知",
        o.spec || "三分甜/微冰",
        o.toppings || "無",
        o.price || 0,
        o.timestamp ? new Date(o.timestamp).toLocaleString("zh-TW") : ""
    ]);

    // 加入 BOM 確保 Excel 開啟不亂碼
    let csvContent = "\uFEFF";
    csvContent += headers.join(",") + "\n";
    rows.forEach(row => {
        csvContent += row.map(val => `"${String(val).replace(/"/g, '""')}"`).join(",") + "\n";
    });

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    const url = URL.createObjectURL(blob);
    link.setAttribute("href", url);
    link.setAttribute("download", `drink_orders_${new Date().toISOString().substring(5,10).replace("-","")}.csv`);
    link.style.visibility = "hidden";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// --- 8. AI 聊天對話與工具對接核心 ---
async function handleChatSend() {
    const inputEl = document.getElementById("chat-input");
    const text = inputEl.value.trim();
    if (!text) return;

    // 清空輸入
    inputEl.value = "";

    // 顯示使用者對話
    showUserMessage(text);
    chatHistory.push({ role: "user", content: text });
    
    // 顯示 Bot 載入中
    const loadingMessageId = showLoadingMessage();

    try {
        const aiMode = localStorage.getItem("ai-mode") || "cloud";
        let responseText = "";

        if (aiMode === "local") {
            responseText = await callLocalOllama(chatHistory);
        } else if (aiMode === "webllm") {
            responseText = await callWebLLM(chatHistory);
        } else {
            responseText = await callCloudAI(chatHistory);
        }


        // 移除載入中訊息並顯示回覆
        removeMessage(loadingMessageId);
        showBotMessage(responseText);
        chatHistory.push({ role: "assistant", content: responseText });

        // 如果回覆中包含 "✅" 符號，代表有成功的寫入/刪除操作，自動在 UI 提示刷新
        if (responseText.includes("✅")) {
            setTimeout(() => {
                // 部分指令可即時更新，Firebase 自帶 OnSnapshot 會自動渲染
            }, 800);
        }

    } catch (err) {
        removeMessage(loadingMessageId);
        showBotMessage(`❌ 執行錯誤: ${err.message}`);
    }
}

// --- 9. 呼叫 AI 服務 API ---
// A. 本地 Ollama 呼叫 (模擬 OpenAI 介面)
// A. 本地 Ollama 呼叫 (模擬 OpenAI 介面)
async function callLocalOllama(history) {
    const model = localStorage.getItem("local-model");
    if (!model) throw new Error("尚未選擇任何本地 Ollama 模型！");

    const systemPrompt = `你是一個專業的飲品訂單助手。請一律使用「繁體中文」回答。你擁有並可隨時調用點餐、修改、刪除、查詢菜單與重複檢查的工具。

🚨 核心行為準則：
1. 【修改與加料】：當使用者要求「修改規格」或「幫某人加/換料」（例如：「幫國炯加琥珀粉圓」、「把小甜甜改成去冰」）時，不論使用者有沒有提供飲料名稱，請【立即直接調用】 "update_order_by_name" 工具。工具會自動在雲端資料庫中搜尋該使用者是否有既有訂單並進行修改。不要事先詢問使用者飲料名稱或規格，先調用工具就對了！
2. 【刪除與取消】：當使用者要求刪除或取消點餐時，請【立即直接調用】 "delete_order_by_name" 工具。
3. 任何工具呼叫執行後，請將工具回傳的結果直接呈現給使用者。`;

    // 為 Ollama 構造 Tools Schema
    const tools = getBrowserToolSchemas();

    // 將 history 中的 role: assistant 改成 role: assistant (相容)
    const messages = [
        { role: "system", content: systemPrompt },
        ...history
    ];

    // 取得自訂的 API 網址，去掉尾端斜線
    let localApiUrl = (localStorage.getItem("local-api-url") || "http://localhost:11434").replace(/\/+$/, "");

    try {
        const res = await fetch(`${localApiUrl}/v1/chat/completions`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                model: model,
                messages: messages,
                tools: tools,
                temperature: 0.7
            })
        });

        if (!res.ok) throw new Error(`本地 API 回傳錯誤: ${res.statusText}`);
        const data = await res.json();
        const message = data.choices[0].message;

        // 處理本地 tool call
        if (message.tool_calls && message.tool_calls.length > 0) {
            return await executeBrowserToolCalls(message.tool_calls);
        }
        return message.content || "（本地模型未傳回文字）";
    } catch (e) {
        throw new Error(`無法連線至本地 API (${localApiUrl.replace(/^https?:\/\//, "")})，請確認服務已啟動且無 CORS 限制。詳細錯誤: ${e.message}`);
    }
}


// WebLLM Engine 實例與狀態
let webllmEngine = null;
let currentWebLLMModel = "";

async function callWebLLM(history) {
    let model = localStorage.getItem("webllm-model") || "Qwen2.5-1.5B-Instruct-q4f16_1-MLC";
    if (model === "custom") {
        model = localStorage.getItem("webllm-custom-model") || "";
        if (!model) {
            throw new Error("請先在側邊欄輸入您想使用的自訂 WebLLM 模型 ID！");
        }
    }
    
    // 如果引擎未初始化，或者選擇的模型改變了，則需要重新載入
    if (!webllmEngine || currentWebLLMModel !== model) {
        // 顯示進度條 UI
        const progressRow = document.getElementById("webllm-progress-row");
        const progressLabel = document.getElementById("webllm-progress-label");
        const progressPercent = document.getElementById("webllm-progress-percent");
        const progressBar = document.getElementById("webllm-progress-bar");
        
        if (progressRow) progressRow.classList.remove("hidden");
        
        try {
            if (progressLabel) progressLabel.textContent = "正在載入 WebLLM 模組...";
            // 動態匯入 WebLLM
            const { CreateMLCEngine } = await import("https://esm.run/@mlc-ai/web-llm");
            
            if (progressLabel) progressLabel.textContent = `載入大模型中 (${model.split("-q4f")[0]})...`;
            
            webllmEngine = await CreateMLCEngine(model, {
                initProgressCallback: (progress) => {
                    const pct = Math.round(progress.progress * 100);
                    if (progressPercent) progressPercent.textContent = `${pct}%`;
                    if (progressBar) progressBar.style.width = `${pct}%`;
                    if (progressLabel) {
                        progressLabel.textContent = progress.text.length > 30 ? progress.text.substring(0, 30) + "..." : progress.text;
                    }
                }
            });
            currentWebLLMModel = model;
            
            // 下載載入完成後隱藏進度條
            if (progressRow) progressRow.classList.add("hidden");
        } catch (err) {
            if (progressRow) progressRow.classList.add("hidden");
            throw new Error(`初始化網頁內置 AI 失敗。可能因為您的瀏覽器不支援 WebGPU。詳細錯誤: ${err.message}`);
        }
    }

    const systemPrompt = `你是一個只會以 JSON 呼叫工具的飲品訂單管理助手。請一律使用「繁體中文」回答。

🚨 核心規則（極重要）：
1. 當用戶提出任何點餐、修改、刪除、查詢要求時，你【絕對禁止】直接以文字問候或回答。
2. 你【必須且只能】輸出以下格式的純 JSON 物件來進行工具呼叫（不要添加 \`\`\`json 等 Markdown 外框，直接輸出開頭為 { 結尾為 } 的純文字）：
{
  "tool_call": {
    "name": "工具名稱",
    "arguments": {
      "參數名": "參數值"
    }
  }
}
3. 只有當你獲得「[系統工具執行結果]」之後，你才能使用流暢的繁體中文文字總結並回覆給用戶。

🚨 呼叫範例（Few-Shot）：
使用者輸入：「小圓圓點一杯荔枝烏龍去冰半糖加蘆薈」
你的 JSON 輸出：
{
  "tool_call": {
    "name": "place_drink_order",
    "arguments": {
      "name": "小圓圓",
      "drink_name": "荔枝烏龍",
      "spec": "半糖/去冰",
      "topping": "蘆薈"
    }
  }
}

使用者輸入：「幫小胖胖修改，改成少冰無糖」
你的 JSON 輸出：
{
  "tool_call": {
    "name": "update_order_by_name",
    "arguments": {
      "name": "小胖胖",
      "spec": "無糖/少冰"
    }
  }
}

可用的工具清單與參數說明：
1. "place_drink_order": 點餐。參數:
   - "name": 訂購人姓名 (必要，如："小圓圓")
   - "drink_name": 飲料名稱 (必要)
   - "spec": 甜度與冰量，如: "三分甜/微冰" (必要)
   - "topping": 加料，無加料則填 "無"
2. "update_order_by_name": 修改點餐。當使用者要求「修改規格」或「加/換料」時，請直接呼叫此工具。參數:
   - "name": 訂購人姓名 (必要)
   - "drink_name": 新飲料名稱 (選填)
   - "spec": 新規格，如 "去冰無糖" (選填)
   - "topping": 新加料，取消加料傳 "無" (選填)
3. "delete_order_by_name": 刪除點餐。參數:
   - "name": 姓名 (必要)
4. "get_menu": 查詢菜單。無參數。
5. "list_recent_orders": 列出最近訂單。無參數。
6. "find_duplicate_orders_by_name": 查詢個人重複點餐。參數: "name"
7. "search_all_duplicates": 掃描全部重複。無參數.
8. "get_duplicate_statistics": 重複統計報告。無參數。`;

    let localMessages = [
        { role: "system", content: systemPrompt },
        ...history
    ];

    try {
        let maxLoops = 3;
        for (let loop = 0; loop < maxLoops; loop++) {
            const reply = await webllmEngine.chat.completions.create({
                messages: localMessages,
                temperature: 0.3
            });

            const content = reply.choices[0].message.content || "";
            
            // 嘗試解析是否包含 JSON 工具呼叫
            let jsonText = content.trim();
            if (jsonText.includes("```")) {
                const match = jsonText.match(/```(?:json)?\s*([\s\S]+?)\s*```/);
                if (match) jsonText = match[1].trim();
            }
            
            if (jsonText.startsWith("{") && jsonText.endsWith("}")) {
                try {
                    const parsed = JSON.parse(jsonText);
                    if (parsed.tool_call) {
                        const toolName = parsed.tool_call.name;
                        const toolArgs = parsed.tool_call.arguments || {};
                        
                        console.log(`[WebLLM Prompt-based Tool Call]: ${toolName}`, toolArgs);
                        
                        // 執行本地工具模擬
                        const toolCallResult = await executeBrowserToolCalls([{
                            id: `webllm_call_${Date.now()}`,
                            function: {
                                name: toolName,
                                arguments: JSON.stringify(toolArgs)
                            }
                        }]);
                        
                        // 將工具執行結果加入對話歷史，並讓模型進行下一輪推理
                        localMessages.push({ role: "assistant", content: content });
                        localMessages.push({ role: "user", content: `[系統工具執行結果]:\n${toolCallResult}` });
                        continue;
                    }
                } catch (jsonErr) {
                    console.warn("Failed to parse tool call JSON from WebLLM response:", jsonText, jsonErr);
                }
            }
            
            return content;
        }
        
        throw new Error("模型工具呼叫超出最大限制次數。");
    } catch (e) {
        throw new Error(`網頁內置 AI 推理失敗：${e.message}`);
    }
}
// 取得已下載快取的模型列表
async function getCachedModels() {
    const cachedModels = new Set();
    const allModels = [
        { id: "Qwen2.5-1.5B-Instruct-q4f16_1-MLC", name: "Qwen 2.5 1.5B" },
        { id: "Qwen2.5-3B-Instruct-q4f16_1-MLC", name: "Qwen 2.5 3B" },
        { id: "Llama-3.2-1B-Instruct-q4f16_1-MLC", name: "Llama 3.2 1B" },
        { id: "Llama-3.2-3B-Instruct-q4f16_1-MLC", name: "Llama 3.2 3B" },
        { id: "Gemma-2-2B-it-q4f16_1-MLC", name: "Gemma 2 2B" }
    ];
    
    // 1. 檢測 Cache Storage
    try {
        const cacheNames = await caches.keys();
        for (let cacheName of cacheNames) {
            if (cacheName.toLowerCase().includes("webllm") || cacheName.toLowerCase().includes("mlc")) {
                const cache = await caches.open(cacheName);
                const requests = await cache.keys();
                for (let request of requests) {
                    const url = request.url;
                    let matched = false;
                    const urlLower = url.toLowerCase().replace(/[-_]/g, "");
                    for (let m of allModels) {
                        const targetKey = m.id.split("-MLC")[0].toLowerCase().replace(/[-_]/g, "");
                        if (urlLower.includes(targetKey)) {
                            cachedModels.add(m.id);
                            matched = true;
                        }
                    }
                    // 自訂模型的 Hugging Face 解析
                    if (!matched && url.includes("/resolve/main/")) {
                        const parts = url.split("/resolve/main/")[0].split("/");
                        const modelId = parts[parts.length - 1];
                        if (modelId && modelId.toLowerCase().includes("mlc")) {
                            cachedModels.add(modelId);
                        }
                    }
                }
            }
        }
    } catch (e) {
        console.warn("getCachedModels cache check error:", e);
    }
    
    // 2. 檢測 OPFS
    try {
        if (navigator.storage && navigator.storage.getDirectory) {
            const root = await navigator.storage.getDirectory();
            for await (const [name, handle] of root.entries()) {
                if (name.toLowerCase().includes("mlc")) {
                    cachedModels.add(name);
                }
            }
        }
    } catch (e) {
        console.warn("getCachedModels OPFS check error:", e);
    }
    
    return Array.from(cachedModels);
}

// 動態更新快取管理 UI
async function updateCacheManagerUI() {
    const container = document.getElementById("cache-manager-container");
    const select = document.getElementById("cache-model-select");
    if (!container || !select) return;
    
    const cachedModelIds = await getCachedModels();
    
    const allModels = [
        { id: "Qwen2.5-1.5B-Instruct-q4f16_1-MLC", name: "Qwen 2.5 1.5B" },
        { id: "Qwen2.5-3B-Instruct-q4f16_1-MLC", name: "Qwen 2.5 3B" },
        { id: "Llama-3.2-1B-Instruct-q4f16_1-MLC", name: "Llama 3.2 1B" },
        { id: "Llama-3.2-3B-Instruct-q4f16_1-MLC", name: "Llama 3.2 3B" },
        { id: "Gemma-2-2B-it-q4f16_1-MLC", name: "Gemma 2 2B" }
    ];
    
    if (cachedModelIds.length === 0) {
        container.style.display = "none";
    } else {
        container.style.display = "block";
        select.innerHTML = "";
        
        cachedModelIds.forEach(id => {
            const opt = document.createElement("option");
            opt.value = id;
            const staticMatch = allModels.find(m => m.id === id);
            opt.textContent = staticMatch ? staticMatch.name : `自訂: ${id.split("-q4f")[0]}`;
            select.appendChild(opt);
        });
    }
}

// 單個模型快取清除函數
window.clearWebLLMCache = async function() {
    const model = document.getElementById("cache-model-select").value;
    if (!model) {
        alert("請先選擇要刪除的內置 AI 模型！");
        return;
    }
    
    const displayName = model.split("-q4f")[0];
    if (!confirm(`您確定要清除瀏覽器中「${displayName}」的快取模型嗎？\n這將釋放該模型佔用的裝置儲存空間（約數百 MB 至 2 GB），但下次選用該模型時需要重新下載。`)) {
        return;
    }
    
    let deletedCount = 0;
    
    // 1. 清除 Cache Storage 中屬於該模型的檔案
    try {
        const cacheNames = await caches.keys();
        for (let cacheName of cacheNames) {
            if (cacheName.toLowerCase().includes("webllm") || cacheName.toLowerCase().includes("mlc")) {
                const cache = await caches.open(cacheName);
                const requests = await cache.keys();
                // 找出該模型的特徵字根
                const rawKey = model.toLowerCase().replace(/[-_]/g, "");
                const targetKey = model.includes("-MLC") ? model.split("-MLC")[0].toLowerCase().replace(/[-_]/g, "") : rawKey;
                for (let request of requests) {
                    const url = request.url.toLowerCase().replace(/[-_]/g, "");
                    if (url.includes(targetKey) || url.includes(targetKey.replace("instruct", ""))) {
                        await cache.delete(request);
                        deletedCount++;
                    }
                }
            }
        }
    } catch (e) {
        console.warn("Cache API clear failed:", e);
    }
    
    // 2. 清除 OPFS 中對應的模型資料夾
    try {
        if (navigator.storage && navigator.storage.getDirectory) {
            const root = await navigator.storage.getDirectory();
            const targetDirKey = model.includes("-MLC") ? model.toLowerCase().split("-mlc")[0] : model.toLowerCase();
            for await (const [name, handle] of root.entries()) {
                if (name.toLowerCase().includes(targetDirKey) || targetDirKey.includes(name.toLowerCase())) {
                    await root.removeEntry(name, { recursive: true });
                    deletedCount++;
                }
            }
        }
    } catch (e) {
        console.warn("OPFS clear failed:", e);
    }
    
    // 如果當前引擎正在運行該模型，釋放引擎
    if (webllmEngine && currentWebLLMModel === model) {
        try {
            await webllmEngine.unload();
        } catch(e) {}
        webllmEngine = null;
        currentWebLLMModel = "";
    }
    
    // 重新檢查與更新 UI，若無模型快取則隱藏區塊
    await updateCacheManagerUI();
    
    alert(`🧹 內置 AI 模型「${displayName}」的快取已清除完成！`);
};

// B. 雲端 AI 呼叫 (三向金鑰路由 + Proxy)
async function callCloudAI(history) {
    const geminiKey = localStorage.getItem("key-gemini");
    const openaiKey = localStorage.getItem("key-openai");
    const anthropicKey = localStorage.getItem("key-anthropic");
    const proxyEndpoint = localStorage.getItem("proxy-endpoint") || "/api/chat";

    // 優先權 1: 瀏覽器本地直連 Gemini (免 CORS 限制)
    if (geminiKey) {
        return await callGeminiDirectly(history, geminiKey);
    }

    // 優先權 2: 瀏覽器本地直連 OpenAI (可能受限於 CORS)
    if (openaiKey) {
        return await callOpenAIDirectly(history, openaiKey);
    }

    // 優先權 3: 無金鑰，或者是 Anthropic 走中轉 Serverless Proxy
    return await callVercelProxy(history, proxyEndpoint, {
        geminiKey, openaiKey, anthropicKey
    });
}

// 直連 Gemini
async function callGeminiDirectly(history, apiKey) {
    const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${apiKey}`;
    const systemInstruction = `你是一個專業的飲品訂單助手。請一律使用「繁體中文」回答。你擁有並可隨時調用點餐、修改、刪除、查詢菜單與重複檢查的工具。

🚨 核心行為準則：
1. 【修改與加料】：當使用者要求「修改規格」或「幫某人加/換料」（例如：「幫國炯加琥珀粉圓」、「把小甜甜改成去冰」）時，不論使用者有沒有提供飲料名稱，請【立即直接調用】 "update_order_by_name" 工具。工具會自動在雲端資料庫中搜尋該使用者是否有既有訂單並進行修改。不要事先詢問使用者飲料名稱或規格，先調用工具！
2. 【刪除與取消】：當使用者要求刪除或取消點餐時，請【立即直接調用】 "delete_order_by_name" 工具。
3. 任何工具呼叫執行後，請將工具回傳的結果直接呈現給使用者。`;
    
    // 整理符合 Gemini 格式的 tools
    const geminiTools = getBrowserToolSchemas().map(t => {
        // 清理 schema 防止 Gemini 400
        const cleaned = cleanSchemaForGemini(t.function.parameters);
        return {
            name: t.function.name,
            description: t.function.description,
            parameters: cleaned
        };
    });

    // 將 history 對應為 Gemini API 的 contents (role 為 user / model)
    const contents = history.map(msg => ({
        role: msg.role === "assistant" ? "model" : "user",
        parts: [{ text: msg.content }]
    }));

    const payload = {
        contents: contents,
        systemInstruction: { parts: [{ text: systemInstruction }] },
        tools: [{ functionDeclarations: geminiTools }],
        generationConfig: { temperature: 0.7 }
    };

    let res;
    let retries = 3;
    let delay = 1000;
    for (let i = 0; i < retries; i++) {
        res = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        
        if (res.ok) break;
        
        // 解析錯誤訊息決定是否重試
        const errData = await res.clone().json().catch(() => ({}));
        const errMsg = errData.error?.message || "";
        
        if (res.status === 503 || res.status === 429 || errMsg.includes("high demand") || errMsg.includes("quota")) {
            if (i < retries - 1) {
                console.warn(`Gemini API 忙碌或超出限制，${delay}ms 後進行第 ${i+1} 次重試...`);
                await new Promise(r => setTimeout(r, delay));
                delay *= 2; // 兩倍延遲
                continue;
            }
        }
        break;
    }

    if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        const errMsg = errData.error?.message || res.statusText;
        if (errMsg.includes("API key not valid")) {
            throw new Error("您的 Gemini API 金鑰無效，請至設定中確認。");
        }
        throw new Error(`Gemini API 錯誤: ${errMsg}`);
    }

    const data = await res.json();
    const candidate = data.candidates?.[0];
    const parts = candidate?.content?.parts || [];

    // 檢查是否有 functionCalls
    const functionCalls = parts.filter(p => p.functionCall);
    if (functionCalls.length > 0) {
        // 轉換為通用格式執行
        const toolCalls = functionCalls.map((fc, i) => ({
            id: `call_${i}_${Date.now()}`,
            function: {
                name: fc.functionCall.name,
                arguments: JSON.stringify(fc.functionCall.args)
            }
        }));
        return await executeBrowserToolCalls(toolCalls);
    }

    return parts.map(p => p.text).join("") || "（AI 未傳回文字）";
}

// 直連 OpenAI
async function callOpenAIDirectly(history, apiKey) {
    const url = "https://api.openai.com/v1/chat/completions";
    const tools = getBrowserToolSchemas();

    const systemPrompt = `你是一個專業的飲品訂單助手。請一律使用「繁體中文」回答。你擁有並可隨時調用點餐、修改、刪除、查詢菜單與重複檢查的工具。

🚨 核心行為準則：
1. 【修改與加料】：當使用者要求「修改規格」或「幫某人加/換料」（例如：「幫國炯加琥珀粉圓」、「把小甜甜改成去冰」）時，不論使用者有沒有提供飲料名稱，請【立即直接調用】 "update_order_by_name" 工具。工具會自動在雲端資料庫中搜尋該使用者是否有既有訂單並進行修改。不要事先詢問使用者飲料名稱或規格，先調用工具！
2. 【刪除與取消】：當使用者要求刪除或取消點餐時，請【立即直接調用】 "delete_order_by_name" 工具。
3. 任何工具呼叫執行後，請將工具回傳的結果直接呈現給使用者。`;

    const messages = [
        { role: "system", content: systemPrompt },
        ...history
    ];

    const res = await fetch(url, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${apiKey}`
        },
        body: JSON.stringify({
            model: "gpt-4o-mini",
            messages: messages,
            tools: tools,
            temperature: 0.7
        })
    });

    if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(`OpenAI API 錯誤: ${errData.error?.message || res.statusText}`);
    }

    const data = await res.json();
    const message = data.choices[0].message;

    if (message.tool_calls && message.tool_calls.length > 0) {
        return await executeBrowserToolCalls(message.tool_calls);
    }
    return message.content || "（OpenAI 未傳回文字）";
}

// 呼叫 Vercel 中轉 Proxy
async function callVercelProxy(history, endpoint, localKeys) {
    try {
        res = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                history: history, // 改傳送整個 history
                keys: localKeys
            })
        });

        if (!res.ok) {
            const errText = await res.text();
            throw new Error(`雲端中轉失敗: ${errText || res.statusText}`);
        }

        const data = await res.json();
        
        // 如果 Proxy 返回需要執行 Tool Call
        if (data.tool_calls && data.tool_calls.length > 0) {
            return await executeBrowserToolCalls(data.tool_calls);
        }
        return data.content || "（雲端 AI 未傳回文字）";
    } catch (e) {
        throw new Error(`雲端中轉 API 發生錯誤。請確認中轉路徑與金鑰配置是否正確。詳細錯誤: ${e.message}`);
    }
}

// --- 10. 瀏覽器端本地工具模擬執行 (取代 Python mcp_server.py) ---
function getBrowserToolSchemas() {
    return [
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
                        topping: { type: "string", description: "加料內容，如: 招招粉粿，若無則預設為『無』" }
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
        },
        {
            type: "function",
            function: {
                name: "update_order_by_name",
                description: "依訂購人姓名修改其最新的點餐資訊。參數: name, drink_name, spec, topping",
                parameters: {
                    type: "object",
                    properties: {
                        name: { type: "string", description: "訂購人姓名" },
                        drink_name: { type: "string", description: "新的飲料名稱 (選填)" },
                        spec: { type: "string", description: "新的規格，如: 無糖/去冰 (選填)" },
                        topping: { type: "string", description: "新的加料內容，若要取消加料請傳入『無』 (選填)" }
                    },
                    required: ["name"]
                }
            }
        },
        {
            type: "function",
            function: {
                name: "delete_order_by_name",
                description: "依訂購人姓名刪除其最新的點餐紀錄。參數: name",
                parameters: {
                    type: "object",
                    properties: {
                        name: { type: "string", description: "要刪除點餐紀錄的訂購人姓名" }
                    },
                    required: ["name"]
                }
            }
        }
    ];
}

// 執行 AI 調用的 Tool Call 並回傳結果字串
async function executeBrowserToolCalls(toolCalls) {
    const results = [];
    for (const call of toolCalls) {
        const name = call.function.name;
        const args = JSON.parse(call.function.arguments);
        
        let resText = "";
        try {
            if (name === "get_menu") {
                resText = executeGetMenu();
            } else if (name === "place_drink_order") {
                resText = await executePlaceOrder(args.name, args.drink_name, args.spec, args.topping || "無");
            } else if (name === "list_recent_orders") {
                resText = executeListRecent();
            } else if (name === "find_duplicate_orders_by_name") {
                resText = executeFindDuplicates(args.name);
            } else if (name === "search_all_duplicates") {
                resText = executeSearchAllDuplicates();
            } else if (name === "get_duplicate_statistics") {
                resText = executeGetDuplicateStats();
            } else if (name === "update_order_by_name") {
                resText = await executeUpdateOrderByName(args.name, args.drink_name || null, args.spec || null, args.topping || null);
            } else if (name === "delete_order_by_name") {
                resText = await executeDeleteOrderByName(args.name);
            } else {
                resText = `❌ 找不到對應的工具: ${name}`;
            }
        } catch (err) {
            resText = `❌ 執行工具 ${name} 失敗: ${err.message}`;
        }
        results.push(resText);
    }
    return results.join("\n\n");
}

// 1. 取得菜單工具
function executeGetMenu() {
    let output = "📋 一沐日 完整飲品菜單：\n";
    for (const category in NESTED_MENU) {
        output += `\n【${category}】\n`;
        for (const item in NESTED_MENU[category]) {
            output += `- ${item}: $${NESTED_MENU[category][item]}元\n`;
        }
    }
    output += "\n====================\n✨ 可額外加料選項：\n";
    for (const topping in TOPPINGS_MENU) {
        if (topping !== "無") {
            output += `- ${topping}: +$${TOPPINGS_MENU[topping]}元\n`;
        }
    }
    return output;
}

// 2. 進行點餐工具 (寫入 Firestore)
async function executePlaceOrder(name, drinkName, spec, topping) {
    // 模糊比對飲料
    const matchedDrink = fuzzyMatch(drinkName, Object.keys(DRINK_MENU));
    if (!matchedDrink) {
        return `❌ 找不到品項「${drinkName}」，請檢查名稱是否正確。`;
    }

    // 模糊比對配料
    let matchedTopping = "無";
    if (topping && topping !== "無") {
        const match = fuzzyMatch(topping, Object.keys(TOPPINGS_MENU));
        if (match) matchedTopping = match;
    }

    // 驗證規格
    if (!spec || !spec.includes("/")) {
        // 如果沒有 /，嘗試自動修復或加上預設
        spec = spec ? `${spec}/微冰` : "三分甜/微冰";
    }

    // 計算價格
    const basePrice = DRINK_MENU[matchedDrink];
    const toppingPrice = TOPPINGS_MENU[matchedTopping];
    const total = basePrice + toppingPrice;

    const payload = {
        name: name,
        item: matchedDrink,
        spec: spec,
        toppings: matchedTopping,
        price: total,
        timestamp: new Date().toISOString()
    };

    // 寫入雲端 Firestore
    await collectionRef.add(payload);

    return `✅ 成功為 ${name} 錄入訂單！\n🥤 品項：${matchedDrink}\n🌡️ 規格：${spec}\n💎 加料：${matchedTopping}\n💰 金額：$${total} 元\n✨ 資料已即時同步至雲端點餐網頁。`;
}

// 3. 列出最近點餐
function executeListRecent() {
    if (ordersList.length === 0) return "📭 目前雲端沒有任何訂單。";
    let summary = "📋 最新 10 筆訂單清單：\n";
    ordersList.slice(0, 10).forEach(o => {
        summary += `- ID: ${o.id.substring(0, 6)}... | 姓名: ${o.name} | 品項: ${o.item} (${o.spec})\n`;
    });
    return summary;
}

// 4. 查詢個人重複
function executeFindDuplicates(name) {
    document.getElementById("search-name").value = name;
    runSinglePersonScan();
    return document.getElementById("dup-results").textContent;
}

// 5. 查詢全局重複
function executeSearchAllDuplicates() {
    runGlobalDuplicateScan();
    return document.getElementById("dup-results").textContent;
}

// 6. 查詢重複統計
function executeGetDuplicateStats() {
    runDuplicateStatistics();
    return document.getElementById("dup-results").textContent;
}

// 7. 修改點餐紀錄工具
// 7. 修改點餐紀錄工具
async function executeUpdateOrderByName(name, drinkName, spec, topping) {
    // 獲取目前資料庫中所有的訂購人姓名列表
    const allNames = Array.from(new Set(ordersList.map(o => o.name).filter(Boolean)));
    const matchedName = fuzzyMatchName(name, allNames) || name; // 模糊匹配姓名，找不到則用原名

    const userOrders = ordersList.filter(o => o.name === matchedName);
    if (userOrders.length === 0) {
        return `❌ 找不到訂購人為 ${name} 的點餐紀錄，無法修改。`;
    }
    const targetOrder = userOrders[0]; // 取得最新的那一筆
    
    const updatedDrink = drinkName ? fuzzyMatch(drinkName, Object.keys(DRINK_MENU)) : targetOrder.item;
    if (drinkName && !updatedDrink) {
        return `❌ 找不到品項「${drinkName}」，請檢查名稱是否正確。`;
    }
    
    let updatedTopping = targetOrder.toppings;
    if (topping) {
        if (topping === "無") {
            updatedTopping = "無";
        } else {
            const match = fuzzyMatch(topping, Object.keys(TOPPINGS_MENU));
            if (match) updatedTopping = match;
        }
    }
    
    let updatedSpec = targetOrder.spec;
    if (spec) {
        updatedSpec = spec.includes("/") ? spec : `${spec}/微冰`;
    }
    
    // 計算價格
    const basePrice = DRINK_MENU[updatedDrink];
    const toppingList = updatedTopping && updatedTopping !== "無" ? updatedTopping.split("、") : [];
    const toppingPrice = toppingList.reduce((sum, t) => sum + TOPPINGS_MENU[t], 0);
    const total = basePrice + toppingPrice;
    
    const payload = {
        item: updatedDrink,
        spec: updatedSpec,
        toppings: updatedTopping,
        price: total,
        timestamp: new Date().toISOString()
    };
    
    await collectionRef.doc(targetOrder.id).update(payload);
    return `✅ 成功為 ${matchedName} 修改訂單！\n🥤 新飲品：${updatedDrink}\n🌡️ 新規格：${updatedSpec}\n💎 新加料：${updatedTopping}\n💰 新金額：$${total} 元\n✨ 資料已即時更新至雲端。`;
}

// 8. 刪除點餐紀錄工具
async function executeDeleteOrderByName(name) {
    const allNames = Array.from(new Set(ordersList.map(o => o.name).filter(Boolean)));
    const matchedName = fuzzyMatchName(name, allNames) || name;

    const userOrders = ordersList.filter(o => o.name === matchedName);
    if (userOrders.length === 0) {
        return `❌ 找不到訂購人為 ${name} 的點餐紀錄，無法刪除。`;
    }
    const targetOrder = userOrders[0];
    
    await collectionRef.doc(targetOrder.id).delete();
    return `✅ 已成功為 ${matchedName} 刪除最新的點餐紀錄 (原品項: ${targetOrder.item})！\n✨ 雲端資料庫已即時同步。`;
}

// 專屬姓名的模糊匹配，防同音字/錯別字 (如 國炯 -> 國烔)
function fuzzyMatchName(input, choices) {
    if (!input) return null;
    input = input.trim().toLowerCase();
    
    // 1. 完全一致
    if (choices.includes(input)) return input;
    const exactChoice = choices.find(c => c.toLowerCase() === input);
    if (exactChoice) return exactChoice;

    // 2. 相似度計算
    let bestMatch = null;
    let bestScore = 0;
    
    choices.forEach(choice => {
        const score = getSimilarity(input, choice.toLowerCase());
        if (score > bestScore && score >= 0.45) { // 相似度高於 45% 始匹配 (相容 2 字名錯 1 字的 50% 相似度)
            bestScore = score;
            bestMatch = choice;
        }
    });

    return bestMatch; // 若皆不吻合，回傳 null 進行精確配對降級
}

// --- 11. 輔助工具函式 ---
// 模糊比對簡易實作 (Levenshtein Distance 概念)
function fuzzyMatch(input, choices) {
    if (!input) return null;
    input = input.trim().toLowerCase();
    
    // 1. 完全一致
    if (choices.includes(input)) return input;

    // 2. 包含關係
    const contains = choices.filter(c => c.toLowerCase().includes(input) || input.includes(c.toLowerCase()));
    if (contains.length > 0) {
        // 回傳最短的那個
        return contains.sort((a,b) => a.length - b.length)[0];
    }

    // 3. 相似度計算
    let bestMatch = null;
    let bestScore = 0;
    
    choices.forEach(choice => {
        const score = getSimilarity(input, choice.toLowerCase());
        if (score > bestScore && score > 0.4) {
            bestScore = score;
            bestMatch = choice;
        }
    });

    return bestMatch || choices[0]; // fallback
}

function getSimilarity(s1, s2) {
    let longer = s1;
    let shorter = s2;
    if (s1.length < s2.length) {
        longer = s2;
        shorter = s1;
    }
    const longerLength = longer.length;
    if (longerLength === 0) return 1.0;
    return (longerLength - editDistance(longer, shorter)) / parseFloat(longerLength);
}

function editDistance(s1, s2) {
    s1 = s1.toLowerCase();
    s2 = s2.toLowerCase();
    const costs = [];
    for (let i = 0; i <= s1.length; i++) {
        let lastValue = i;
        for (let j = 0; j <= s2.length; j++) {
            if (i === 0) {
                costs[j] = j;
            } else {
                if (j > 0) {
                    let newValue = costs[j - 1];
                    if (s1.charAt(i - 1) !== s2.charAt(j - 1)) {
                        newValue = Math.min(Math.min(newValue, lastValue), costs[j]) + 1;
                    }
                    costs[j - 1] = lastValue;
                    lastValue = newValue;
                }
            }
        }
        if (i > 0) costs[s2.length] = lastValue;
    }
    return costs[s2.length];
}

// 清理 Gemini Schema (防 400 錯誤)
function cleanSchemaForGemini(d) {
    if (typeof d !== 'object' || d === null) return d;
    if (Array.isArray(d)) {
        return d.map(item => cleanSchemaForGemini(item));
    }
    const cleaned = {};
    for (const k in d) {
        if (k === 'additionalProperties' || k === 'additional_properties') continue;
        cleaned[k] = cleanSchemaForGemini(d[k]);
    }
    return cleaned;
}

// HTML 安全編碼
function escapeHTML(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// --- 12. 聊天介面渲染輔助 ---
function showUserMessage(text) {
    const history = document.getElementById("chat-history");
    const msg = document.createElement("div");
    msg.className = "chat-message user";
    msg.innerHTML = `
        <div class="sender-name"><i class="fa-solid fa-user"></i> 您</div>
        <div class="message-content">${escapeHTML(text)}</div>
    `;
    history.appendChild(msg);
    history.scrollTop = history.scrollHeight;
}

function showBotMessage(text) {
    const history = document.getElementById("chat-history");
    const msg = document.createElement("div");
    msg.className = "chat-message bot";
    // 支援換行符號
    const formatted = escapeHTML(text).replace(/\n/g, "<br>");
    msg.innerHTML = `
        <div class="sender-name"><i class="fa-solid fa-robot"></i> 飲品小助手</div>
        <div class="message-content">${formatted}</div>
    `;
    history.appendChild(msg);
    history.scrollTop = history.scrollHeight;
}

function showLoadingMessage() {
    const id = `loading_${Date.now()}`;
    const history = document.getElementById("chat-history");
    const msg = document.createElement("div");
    msg.className = "chat-message bot";
    msg.id = id;
    msg.innerHTML = `
        <div class="sender-name"><i class="fa-solid fa-robot"></i> 飲品小助手</div>
        <div class="message-content"><i class="fa-solid fa-circle-notch fa-spin"></i> AI 正在思考中...</div>
    `;
    history.appendChild(msg);
    history.scrollTop = history.scrollHeight;
    return id;
}

function removeMessage(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}
