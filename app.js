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
    });
    document.getElementById("close-sidebar").addEventListener("click", () => {
        document.getElementById("sidebar").classList.remove("active");
    });

    // 設定面板開關
    document.getElementById("toggle-settings").addEventListener("click", () => {
        document.getElementById("settings-panel").classList.add("active");
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
            if (e.target.value === "cloud") {
                document.getElementById("cloud-settings-section").classList.remove("hidden");
                document.getElementById("local-settings-section").classList.add("hidden");
            } else {
                document.getElementById("cloud-settings-section").classList.add("hidden");
                document.getElementById("local-settings-section").classList.remove("hidden");
                checkOllamaStatus();
            }
        });
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
    const aiMode = document.querySelector('input[name="ai-mode"]:checked').value;
    localStorage.setItem("ai-mode", aiMode);
    
    // 儲存金鑰
    localStorage.setItem("key-gemini", document.getElementById("key-gemini").value.trim());
    localStorage.setItem("key-openai", document.getElementById("key-openai").value.trim());
    localStorage.setItem("key-anthropic", document.getElementById("key-anthropic").value.trim());
    localStorage.setItem("proxy-endpoint", document.getElementById("proxy-endpoint").value.trim());

    // 儲存選取的本地模型
    localStorage.setItem("local-model", document.getElementById("local-model-select").value);

    document.getElementById("settings-panel").classList.remove("active");
    detectActiveAIConfig();
}

function loadSettings() {
    const aiMode = localStorage.getItem("ai-mode") || "cloud";
    document.querySelector(`input[name="ai-mode"][value="${aiMode}"]`).checked = true;

    if (aiMode === "cloud") {
        document.getElementById("cloud-settings-section").classList.remove("hidden");
        document.getElementById("local-settings-section").classList.add("hidden");
    } else {
        document.getElementById("cloud-settings-section").classList.add("hidden");
        document.getElementById("local-settings-section").classList.remove("hidden");
    }

    document.getElementById("key-gemini").value = localStorage.getItem("key-gemini") || "";
    document.getElementById("key-openai").value = localStorage.getItem("key-openai") || "";
    document.getElementById("key-anthropic").value = localStorage.getItem("key-anthropic") || "";
    document.getElementById("proxy-endpoint").value = localStorage.getItem("proxy-endpoint") || "/api/chat";
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

    try {
        const res = await fetch("http://localhost:11434/api/tags");
        if (res.ok) {
            const data = await res.json();
            const models = data.models || [];
            select.innerHTML = "";
            
            if (models.length === 0) {
                select.innerHTML = "<option value=''>未偵測到任何已下載的模型</option>";
                refBtn.disabled = false;
                return;
            }

            let defaultIdx = 0;
            models.forEach((m, idx) => {
                const opt = document.createElement("option");
                opt.value = m.name;
                opt.textContent = `${m.name} (${(m.size / (1024*1024*1024)).toFixed(1)}GB)`;
                if (m.name.toLowerCase().includes("gemma4")) defaultIdx = idx;
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
        }
    } catch (e) {
        select.innerHTML = "<option value=''>無法連線至本地 Ollama (11434)</option>";
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
    
    // 顯示 Bot 載入中
    const loadingMessageId = showLoadingMessage();

    try {
        const aiMode = localStorage.getItem("ai-mode") || "cloud";
        let responseText = "";

        if (aiMode === "local") {
            responseText = await callLocalOllama(text);
        } else {
            responseText = await callCloudAI(text);
        }

        // 移除載入中訊息並顯示回覆
        removeMessage(loadingMessageId);
        showBotMessage(responseText);

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
async function callLocalOllama(userPrompt) {
    const model = localStorage.getItem("local-model");
    if (!model) throw new Error("尚未選擇任何本地 Ollama 模型！");

    const systemPrompt = `你是一個專業的飲品訂單助手。請一律使用「繁體中文」回答。你擁有以下工具：
1. get_menu: 查詢目前菜單
2. place_drink_order: 進行點餐 (參數: name, drink_name, spec, topping)
3. list_recent_orders: 列出最近訂單
4. find_duplicate_orders_by_name: 查詢單人重複訂單 (參數: name)
5. search_all_duplicates: 全局搜尋所有重複
6. get_duplicate_statistics: 重複訂單統計

如果使用者想查詢菜單，請回答：「我幫你查詢了菜單，菜單如下...」並列出菜單。
請注意：這是一個極簡本地模型調用，若您的 Ollama 支援 tool call，我們將嘗試直接傳入 function。`;

    // 為 Ollama 構造 Tools Schema
    const tools = getBrowserToolSchemas();

    try {
        const res = await fetch("http://localhost:11434/v1/chat/completions", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                model: model,
                messages: [
                    { role: "system", content: systemPrompt },
                    { role: "user", content: userPrompt }
                ],
                tools: tools,
                temperature: 0.7
            })
        });

        if (!res.ok) throw new Error(`Ollama 回傳錯誤: ${res.statusText}`);
        const data = await res.json();
        const message = data.choices[0].message;

        // 處理本地 tool call
        if (message.tool_calls && message.tool_calls.length > 0) {
            return await executeBrowserToolCalls(message.tool_calls);
        }
        return message.content || "（本地模型未傳回文字）";
    } catch (e) {
        throw new Error(`無法連線至本地 Ollama，請確認服務已啟動。詳細錯誤: ${e.message}`);
    }
}

// B. 雲端 AI 呼叫 (三向金鑰路由 + Proxy)
async function callCloudAI(userPrompt) {
    const geminiKey = localStorage.getItem("key-gemini");
    const openaiKey = localStorage.getItem("key-openai");
    const anthropicKey = localStorage.getItem("key-anthropic");
    const proxyEndpoint = localStorage.getItem("proxy-endpoint") || "/api/chat";

    // 優先權 1: 瀏覽器本地直連 Gemini (免 CORS 限制)
    if (geminiKey) {
        return await callGeminiDirectly(userPrompt, geminiKey);
    }

    // 優先權 2: 瀏覽器本地直連 OpenAI (可能受限於 CORS)
    if (openaiKey) {
        return await callOpenAIDirectly(userPrompt, openaiKey);
    }

    // 優先權 3: 無金鑰，或者是 Anthropic 走中轉 Serverless Proxy
    return await callVercelProxy(userPrompt, proxyEndpoint, {
        geminiKey, openaiKey, anthropicKey
    });
}

// 直連 Gemini
async function callGeminiDirectly(prompt, apiKey) {
    const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${apiKey}`;
    const systemInstruction = "你是一個專業的飲品訂單助手。請一律使用「繁體中文」回答。你可以調用工具完成點餐、修改、刪除、查詢菜單或搜尋重複訂單。";
    
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

    const payload = {
        contents: [{ parts: [{ text: prompt }] }],
        systemInstruction: { parts: [{ text: systemInstruction }] },
        tools: [{ functionDeclarations: geminiTools }],
        generationConfig: { temperature: 0.7 }
    };

    const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });

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
async function callOpenAIDirectly(prompt, apiKey) {
    const url = "https://api.openai.com/v1/chat/completions";
    const tools = getBrowserToolSchemas();

    const res = await fetch(url, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${apiKey}`
        },
        body: JSON.stringify({
            model: "gpt-4o-mini",
            messages: [
                { role: "system", content: "你是一個專業的飲品訂單助手。請一律使用「繁體中文」回答。你可以執行點餐、修改、刪除、查詢菜單或搜尋重複訂單。" },
                { role: "user", content: prompt }
            ],
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
async function callVercelProxy(prompt, endpoint, localKeys) {
    try {
        const res = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                prompt: prompt,
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
    msg.innerHTML = `<div class="message-content">${escapeHTML(text)}</div>`;
    history.appendChild(msg);
    history.scrollTop = history.scrollHeight;
}

function showBotMessage(text) {
    const history = document.getElementById("chat-history");
    const msg = document.createElement("div");
    msg.className = "chat-message bot";
    // 支援換行符號
    const formatted = escapeHTML(text).replace(/\n/g, "<br>");
    msg.innerHTML = `<div class="message-content">${formatted}</div>`;
    history.appendChild(msg);
    history.scrollTop = history.scrollHeight;
}

function showLoadingMessage() {
    const id = `loading_${Date.now()}`;
    const history = document.getElementById("chat-history");
    const msg = document.createElement("div");
    msg.className = "chat-message bot";
    msg.id = id;
    msg.innerHTML = `<div class="message-content"><i class="fa-solid fa-circle-notch fa-spin"></i> AI 正在思考中...</div>`;
    history.appendChild(msg);
    history.scrollTop = history.scrollHeight;
    return id;
}

function removeMessage(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}
