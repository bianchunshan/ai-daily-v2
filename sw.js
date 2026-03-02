/**
 * Service Worker - 离线缓存与性能优化
 * @version 2.0
 */

const CACHE_NAME = 'ai-daily-v2-cache-v1';
const STATIC_ASSETS = [
    '/',
    '/index.html',
    '/assets/js/app.js',
    'https://cdn.tailwindcss.com',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
    'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+SC:wght@400;500;700&display=swap'
];

// 安装 - 缓存静态资源
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(STATIC_ASSETS))
            .then(() => self.skipWaiting())
    );
});

// 激活 - 清理旧缓存
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys()
            .then(cacheNames => {
                return Promise.all(
                    cacheNames
                        .filter(name => name !== CACHE_NAME)
                        .map(name => caches.delete(name))
                );
            })
            .then(() => self.clients.claim())
    );
});

// 拦截请求
self.addEventListener('fetch', (event) => {
    const { request } = event;
    
    // 数据API请求 - 网络优先
    if (request.url.includes('/data/news/')) {
        event.respondWith(networkFirst(request));
        return;
    }
    
    // 静态资源 - 缓存优先
    event.respondWith(cacheFirst(request));
});

// 缓存优先策略
async function cacheFirst(request) {
    const cached = await caches.match(request);
    if (cached) return cached;
    
    try {
        const response = await fetch(request);
        const cache = await caches.open(CACHE_NAME);
        cache.put(request, response.clone());
        return response;
    } catch (e) {
        // 离线时返回缓存或错误页
        return cached || new Response('Offline', { status: 503 });
    }
}

// 网络优先策略
async function networkFirst(request) {
    try {
        const networkResponse = await fetch(request);
        const cache = await caches.open(CACHE_NAME);
        cache.put(request, networkResponse.clone());
        return networkResponse;
    } catch (e) {
        const cached = await caches.match(request);
        if (cached) return cached;
        throw e;
    }
}