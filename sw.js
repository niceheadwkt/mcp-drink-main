const CACHE_NAME = "drink-pwa-v2";
const ASSETS = [
  "./",
  "./index.html",
  "./style.css",
  "./app.js",
  "./manifest.json",
  "./logo.png"
];

// 安裝時快取靜態資源
self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS);
    }).then(() => self.skipWaiting())
  );
});

// 激活時清理舊快取
self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// 攔截請求 (Network-falling-back-to-cache + Cache Update)
self.addEventListener("fetch", (e) => {
  // 排除 Firebase 與本地 Ollama 的非 GET 請求
  if (e.request.method !== "GET" || 
      e.request.url.includes("firestore.googleapis.com") || 
      e.request.url.includes("11434") ||
      e.request.url.includes("generativelanguage.googleapis.com")) {
    return;
  }

  e.respondWith(
    fetch(e.request)
      .then((response) => {
        // 成功取得網路回應，更新快取
        if (response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(e.request, clone);
          });
        }
        return response;
      })
      .catch(() => {
        // 網路斷線，退回快取
        return caches.match(e.request);
      })
  );
});
