/**
 * 前沿科技日报 - 核心应用逻辑
 * 架构师级优化：模块化、性能优化、缓存策略
 * @version 2.0
 */

// ==================== 配置常量 ====================
const CONFIG = {
    VERSION: '3.3.0',
    API_BASE: 'data/news',
    ITEMS_PER_PAGE: 10,
    CACHE_TTL: 5 * 60 * 1000, // 5分钟缓存
    DEBOUNCE_DELAY: 300,
    SCROLL_THRESHOLD: 200
};

function dataUrl(path) {
    if (window.location.protocol === 'file:') return path;
    const separator = path.includes('?') ? '&' : '?';
    return `${path}${separator}v=${CONFIG.VERSION}-${Date.now()}`;
}

// ==================== 状态管理 ====================
const State = {
    news: [],
    filtered: [],
    opportunities: [],
    stockQuotes: {},
    stockRefreshTimer: null,
    currentCategory: 'all',
    displayedCount: CONFIG.ITEMS_PER_PAGE,
    isLoading: false,
    cache: new Map(),
    categories: {
        'world': { name: '国际局势', icon: 'globe', color: 'blue' },
        'ai': { name: '人工智能', icon: 'brain', color: 'purple' },
        'semiconductor': { name: '半导体', icon: 'microchip', color: 'green' },
        'energy': { name: '新能源', icon: 'bolt', color: 'yellow' },
        'robotics': { name: '机器人', icon: 'robot', color: 'red' },
        'quantum': { name: '量子计算', icon: 'atom', color: 'cyan' },
        'biotech': { name: '创新药', icon: 'capsules', color: 'pink' },
        'bci': { name: '脑机接口', icon: 'head-side-virus', color: 'indigo' },
        'space': { name: '商业航天', icon: 'rocket', color: 'orange' },
        'gaming': { name: '游戏', icon: 'gamepad', color: 'teal' }
    }
};

function filterDefinitions() {
    return {
        all: { name: '全部资讯', icon: 'newspaper', color: 'primary', type: 'news' },
        opportunities: { name: '推荐机会', icon: 'chart-line', color: 'success', type: 'opportunities' },
        ...State.categories
    };
}

// ==================== 工具函数 ====================
const Utils = {
    /**
     * 防抖函数
     */
    debounce(fn, delay = CONFIG.DEBOUNCE_DELAY) {
        let timer = null;
        return function (...args) {
            if (timer) clearTimeout(timer);
            timer = setTimeout(() => fn.apply(this, args), delay);
        };
    },

    /**
     * 节流函数
     */
    throttle(fn, limit) {
        let inThrottle;
        return function (...args) {
            if (!inThrottle) {
                fn.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    },

    /**
     * 格式化时间
     */
    formatTime(timeStr) {
        const date = new Date(timeStr);
        const now = new Date();
        const diff = now - date;
        
        const minutes = Math.floor(diff / 60000);
        const hours = Math.floor(diff / 3600000);
        const days = Math.floor(diff / 86400000);
        
        if (minutes < 1) return '刚刚';
        if (minutes < 60) return `${minutes}分钟前`;
        if (hours < 24) return `${hours}小时前`;
        if (days < 7) return `${days}天前`;
        
        return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
    },

    /**
     * 生成唯一ID
     */
    generateId() {
        return Math.random().toString(36).substring(2, 15);
    },

    /**
     * 缓存管理
     */
    cache: {
        get(key) {
            const item = State.cache.get(key);
            if (!item) return null;
            if (Date.now() - item.timestamp > CONFIG.CACHE_TTL) {
                State.cache.delete(key);
                return null;
            }
            return item.data;
        },
        set(key, data) {
            State.cache.set(key, { data, timestamp: Date.now() });
        }
    }
};

// ==================== 数据服务 ====================
const DataService = {
    /**
     * 加载新闻数据
     */
    async loadNews() {
        // 检查缓存
        const cached = Utils.cache.get('news_data');
        if (cached) {
            console.log('✅ 从缓存加载数据');
            return cached;
        }

        try {
            const response = await fetch(dataUrl(`${CONFIG.API_BASE}/all.json`), { cache: 'no-store' });
            if (!response.ok) throw new Error('Failed to load');
            
            const data = await response.json();
            Utils.cache.set('news_data', data.news);
            
            return data.news;
        } catch (e) {
            console.error('❌ 加载数据失败:', e);
            // 尝试加载本地存储
            const local = localStorage.getItem('news_backup');
            if (local) return JSON.parse(local);
            return [];
        }
    },

    /**
     * 获取分类数据
     */
    async loadCategory(category) {
        const cacheKey = `cat_${category}`;
        const cached = Utils.cache.get(cacheKey);
        if (cached) return cached;

        try {
            const response = await fetch(dataUrl(`${CONFIG.API_BASE}/${category}.json`), { cache: 'no-store' });
            const data = await response.json();
            Utils.cache.set(cacheKey, data.news);
            return data.news;
        } catch (e) {
            console.error(`❌ 加载分类 ${category} 失败:`, e);
            return [];
        }
    },

    /**
     * 加载投资机会
     */
    async loadOpportunities() {
        const cached = Utils.cache.get('opportunities');
        if (cached) return cached;

        try {
            const response = await fetch(dataUrl('data/opportunities.json'), { cache: 'no-store' });
            if (!response.ok) throw new Error('Failed to load opportunities');
            const data = await response.json();
            const opportunities = data.opportunities || [];
            Utils.cache.set('opportunities', opportunities);
            return opportunities;
        } catch (e) {
            console.warn('机会池加载失败:', e);
            return [];
        }
    },

    /**
     * 加载最新股票行情
     */
    async loadStockQuotes(force = false) {
        const cached = Utils.cache.get('stock_quotes');
        if (cached && !force) return cached;

        try {
            const response = await fetch(dataUrl('data/stocks/latest.json'), { cache: 'no-store' });
            if (!response.ok) throw new Error('Failed to load stock quotes');
            const data = await response.json();
            const quotes = data.quotes || {};
            Utils.cache.set('stock_quotes', quotes);
            State.stockQuotes = quotes;
            return quotes;
        } catch (e) {
            console.warn('股票行情加载失败:', e);
            return {};
        }
    },

    /**
     * 备份数据到本地存储
     */
    backup(news) {
        try {
            localStorage.setItem('news_backup', JSON.stringify(news));
            localStorage.setItem('last_update', new Date().toISOString());
        } catch (e) {
            console.warn('本地存储失败:', e);
        }
    }
};

// ==================== UI渲染 ====================
const Renderer = {
    /**
     * 渲染分类网格
     */
    renderCategories() {
        const grid = document.getElementById('category-grid');
        const colors = {
            primary: 'from-primary/20 to-secondary/10 text-primary',
            success: 'from-success/20 to-emerald-600/10 text-success',
            blue: 'from-blue-500/20 to-blue-600/10 text-blue-400',
            purple: 'from-purple-500/20 to-purple-600/10 text-purple-400',
            green: 'from-green-500/20 to-green-600/10 text-green-400',
            yellow: 'from-yellow-500/20 to-yellow-600/10 text-yellow-400',
            red: 'from-red-500/20 to-red-600/10 text-red-400',
            cyan: 'from-cyan-500/20 to-cyan-600/10 text-cyan-400',
            pink: 'from-pink-500/20 to-pink-600/10 text-pink-400',
            orange: 'from-orange-500/20 to-orange-600/10 text-orange-400',
            amber: 'from-amber-500/20 to-amber-600/10 text-amber-400',
            indigo: 'from-indigo-500/20 to-indigo-600/10 text-indigo-400',
            teal: 'from-teal-500/20 to-teal-600/10 text-teal-400'
        };
        const filters = filterDefinitions();

        grid.innerHTML = Object.entries(filters).map(([key, cat]) => `
            <button onclick="App.filterCategory('${key}')" 
                    class="category-btn glass rounded-xl p-4 text-center transition border ${State.currentCategory === key ? 'border-primary bg-primary/10' : 'border-border'} hover:border-primary/50 group"
                    data-cat="${key}">
                <div class="w-10 h-10 mx-auto mb-2 rounded-lg bg-gradient-to-br ${colors[cat.color]} 
                            flex items-center justify-center group-hover:scale-110 transition">
                    <i class="fas fa-${cat.icon}"></i>
                </div>
                <p class="text-sm font-medium">${cat.name}</p>
                <p class="text-xs text-gray-500 mt-1">${Renderer.countForFilter(key)}条</p>
            </button>
        `).join('');
    },

    countForFilter(key) {
        if (key === 'all') return State.news.length;
        if (key === 'opportunities') return State.opportunities.length;
        return State.news.filter(item => item.category === key).length;
    },

    /**
     * 渲染新闻列表
     */
    renderNews(newsList) {
        const container = document.getElementById('news-container');
        
        if (!newsList || newsList.length === 0) {
            container.innerHTML = `
                <div class="text-center py-20 text-gray-400">
                    <i class="fas fa-inbox text-5xl mb-4 opacity-50"></i>
                    <p>暂无数据</p>
                </div>
            `;
            return;
        }

        // 使用文档片段提升性能
        const fragment = document.createDocumentFragment();
        
        newsList.forEach((news, index) => {
            const card = this.createNewsCard(news, index);
            fragment.appendChild(card);
        });

        container.innerHTML = '';
        container.appendChild(fragment);

        // 更新数量显示
        document.getElementById('news-count').textContent = `${newsList.length}条`;
    },

    renderOpportunityList(items) {
        const container = document.getElementById('news-container');
        const list = items || [];
        document.getElementById('news-count').textContent = `${list.length}条`;
        if (list.length === 0) {
            container.innerHTML = '<div class="text-center py-20 text-gray-400">暂无推荐机会</div>';
            return;
        }
        container.innerHTML = `<div class="grid md:grid-cols-2 xl:grid-cols-3 gap-4">${list.map(item => this.createOpportunityCard(item)).join('')}</div>`;
    },

    createOpportunityCard(item) {
        const cat = State.categories[item.category] || { name: item.category, color: 'gray' };
        const stocks = (item.stocks || []).slice(0, 4).map(stock => {
            const quote = State.stockQuotes?.[stock.symbol] || item.quotes?.[stock.symbol];
            const pct = quote?.change_percent;
            const pctText = typeof pct === 'number' ? `${pct > 0 ? '+' : ''}${pct}%` : '--';
            const pctClass = pct > 0 ? 'text-success' : pct < 0 ? 'text-danger' : 'text-gray-400';
            return `
                <button onclick="event.stopPropagation(); App.showStockDetail('${stock.symbol}')" class="stock-card inline-flex items-center gap-1 px-2 py-1 rounded text-xs">
                    <b class="font-mono">${stock.symbol}</b>
                    <span class="text-gray-300">${stock.name || ''}</span>
                    <span class="${pctClass}">${pctText}</span>
                </button>
            `;
        }).join('');

        return `
            <article onclick="App.showNewsDetail('${item.id}')" class="news-card p-5 border border-border cursor-pointer">
                <div class="flex items-center justify-between gap-3 mb-3">
                    <span class="px-2 py-1 bg-${cat.color}-500/20 text-${cat.color}-400 text-xs font-bold rounded">${cat.name}</span>
                    <span class="text-sm font-bold text-accent">机会分 ${item.score}</span>
                </div>
                <h3 class="font-semibold leading-snug mb-3 line-clamp-2 hover:text-primary transition">${item.title}</h3>
                <p class="text-sm text-gray-400 mb-3 line-clamp-2">${item.logic}</p>
                <div class="flex flex-wrap gap-2 mb-3">${stocks}</div>
                <div class="flex items-center justify-between text-xs text-gray-500">
                    <span>${Utils.formatTime(item.publish_time)}</span>
                    <a onclick="event.stopPropagation()" href="${item.source_url}" target="_blank" rel="noopener" class="text-primary hover:text-secondary">原文</a>
                </div>
                <p class="mt-3 text-xs text-warning/90">${item.risk}</p>
            </article>
        `;
    },

    /**
     * 创建新闻卡片
     */
    createNewsCard(news, index) {
        const div = document.createElement('div');
        div.className = 'news-card p-6 fade-in content-visibility-auto';
        div.style.animationDelay = `${index * 0.05}s`;
        
        const catInfo = State.categories[news.category] || { name: news.category, color: 'gray' };
        
        div.innerHTML = `
            <div class="flex items-start gap-4">
                <div class="flex-1 min-w-0">
                    <!-- 标签 -->
                    <div class="flex flex-wrap items-center gap-2 mb-3">
                        <span class="px-2 py-1 bg-${catInfo.color}-500/20 text-${catInfo.color}-400 text-xs font-bold rounded">
                            ${catInfo.name}
                        </span>
                        ${news.tags?.map(tag => `
                            <span class="px-2 py-1 bg-white/5 text-gray-400 text-xs rounded">${tag}</span>
                        `).join('') || ''}
                    </div>
                    
                    <!-- 标题 -->
                    <h3 class="text-lg font-semibold mb-2 hover:text-primary cursor-pointer transition line-clamp-2"
                        onclick="App.showNewsDetail('${news.id}')">
                        ${news.title}
                    </h3>
                    
                    <!-- 摘要 -->
                    <p class="text-gray-400 text-sm leading-relaxed mb-4 line-clamp-2">${news.summary}</p>
                    
                    <!-- 来源 -->
                    <div class="flex flex-wrap items-center gap-2 mb-4">
                        ${news.sources?.map(src => `
                            <a href="${src.url}" target="_blank" rel="noopener"
                               class="source-tag inline-flex items-center gap-1 px-2 py-1 rounded text-xs">
                                <i class="fas fa-check-circle"></i>
                                <span>${src.name}</span>
                                <span class="opacity-70">${src.credibility}%</span>
                            </a>
                        `).join('') || ''}
                        
                        <span class="ml-auto px-2 py-1 bg-accent/10 text-accent text-xs rounded">
                            可信度 ${news.metrics?.credibility_score || 90}%
                        </span>
                    </div>
                    
                    <!-- 股票 -->
                    ${news.stocks?.length ? `
                        <div class="flex flex-wrap items-center gap-2 mb-4">
                            ${news.stocks.map(stock => `
                                <button onclick="App.showStockDetail('${stock.symbol}')" 
                                        class="stock-card inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs">
                                    <span class="font-mono font-medium">${stock.symbol}</span>
                                    <span class="text-gray-400">${stock.name}</span>
                                    ${Renderer.renderQuoteBadge(stock.symbol)}
                                    <i class="fas fa-${stock.impact === 'positive' ? 'arrow-up text-success' : 
                                        stock.impact === 'negative' ? 'arrow-down text-danger' : 'minus text-gray-400'}"></i>
                                </button>
                            `).join('')}
                        </div>
                    ` : ''}
                    
                    <!-- 元信息 -->
                    <div class="flex items-center gap-4 text-sm text-gray-500">
                        <span><i class="far fa-clock mr-1"></i>${Utils.formatTime(news.publish_time)}</span>
                        <span><i class="far fa-eye mr-1"></i>${((news.metrics?.views || 0) / 1000).toFixed(1)}k</span>
                        <div class="ml-auto flex gap-3">
                            <button onclick="App.share('${news.id}')" class="hover:text-primary transition">
                                <i class="far fa-share-square"></i>
                            </button>
                            <button onclick="App.bookmark('${news.id}')" class="hover:text-primary transition">
                                <i class="far fa-bookmark"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        return div;
    },

    renderQuoteBadge(symbol) {
        const quote = State.stockQuotes?.[symbol];
        if (!quote || typeof quote.change_percent !== 'number') return '';
        const cls = quote.change_percent > 0 ? 'text-success' : quote.change_percent < 0 ? 'text-danger' : 'text-gray-400';
        const sign = quote.change_percent > 0 ? '+' : '';
        return `<span class="${cls}">${sign}${quote.change_percent}%</span>`;
    },

};

// ==================== 应用主逻辑 ====================
const App = {
    /**
     * 初始化应用
     */
    async init() {
        console.log(`前沿科技日报 v${CONFIG.VERSION} 启动中...`);
        
        // 更新日期
        this.updateDate();
        
        // 渲染分类
        Renderer.renderCategories();
        
        // 加载数据
        await this.loadData();
        
        // 绑定事件
        this.bindEvents();
        
        // 检查滚动
        this.initScrollHandler();
        
        console.log('✅ 应用初始化完成');
    },

    /**
     * 加载数据
     */
    async loadData() {
        State.isLoading = true;
        
        try {
            State.news = await DataService.loadNews();
            State.opportunities = await DataService.loadOpportunities();
            State.stockQuotes = await DataService.loadStockQuotes();
            State.filtered = [...State.news];
            
            // 备份到本地
            DataService.backup(State.news);
            
            // 渲染
            Renderer.renderCategories();
            Renderer.renderNews(State.filtered.slice(0, State.displayedCount));
            
            // 更新统计
            this.updateStats();
            this.handleRoute();
            
        } catch (e) {
            console.error('加载失败:', e);
        } finally {
            State.isLoading = false;
        }
    },

    /**
     * 筛选分类
     */
    filterCategory(category) {
        if (State.stockRefreshTimer) {
            clearInterval(State.stockRefreshTimer);
            State.stockRefreshTimer = null;
        }
        history.pushState('', document.title, window.location.pathname + window.location.search);
        document.getElementById('detail-view')?.classList.add('hidden');
        document.getElementById('list-view')?.classList.remove('hidden');
        State.currentCategory = category;
        State.displayedCount = CONFIG.ITEMS_PER_PAGE;
        
        // 更新导航样式
        document.querySelectorAll('.category-btn').forEach(btn => {
            const isActive = btn.dataset.cat === category;
            if (btn.classList.contains('category-btn')) {
                btn.classList.toggle('border-primary', isActive);
                btn.classList.toggle('bg-primary/10', isActive);
            }
        });
        
        // 筛选数据
        if (category === 'all') {
            State.filtered = [...State.news];
        } else if (category === 'opportunities') {
            State.filtered = [...State.opportunities];
        } else {
            State.filtered = State.news.filter(n => n.category === category);
        }
        
        // 更新标题
        const catName = filterDefinitions()[category]?.name || category;
        document.getElementById('section-title').textContent = catName;
        
        // 重新渲染
        if (category === 'opportunities') {
            Renderer.renderOpportunityList(State.filtered);
            document.getElementById('load-more-btn').style.display = 'none';
        } else {
            Renderer.renderNews(State.filtered.slice(0, State.displayedCount));
            document.getElementById('load-more-btn').style.display = State.displayedCount >= State.filtered.length ? 'none' : 'inline-flex';
        }
        
        // 滚动到顶部
        window.scrollTo({ top: 0, behavior: 'smooth' });
    },

    /**
     * 加载更多
     */
    loadMore() {
        if (State.isLoading || State.displayedCount >= State.filtered.length) return;
        
        State.displayedCount += CONFIG.ITEMS_PER_PAGE;
        if (State.currentCategory === 'opportunities') return;
        Renderer.renderNews(State.filtered.slice(0, State.displayedCount));
        
        // 更新按钮状态
        const btn = document.getElementById('load-more-btn');
        if (State.displayedCount >= State.filtered.length) {
            btn.style.display = 'none';
        }
    },

    /**
     * 搜索
     */
    searchNews: Utils.debounce((query) => {
        if (!query.trim()) {
            document.getElementById('search-results').innerHTML = '';
            return;
        }
        
        const results = State.news.filter(n => 
            n.title.toLowerCase().includes(query.toLowerCase()) ||
            n.summary?.toLowerCase().includes(query.toLowerCase()) ||
            n.stocks?.some(s => s.symbol.toLowerCase().includes(query.toLowerCase()))
        ).slice(0, 10);
        
        const container = document.getElementById('search-results');
        container.innerHTML = results.map(n => `
            <div class="p-3 hover:bg-white/5 rounded-lg cursor-pointer transition"
                 onclick="App.selectSearchResult('${n.id}')">
                <div class="text-sm font-medium line-clamp-1">${n.title}</div>
                <div class="text-xs text-gray-500 mt-1">${State.categories[n.category]?.name || n.category}</div>
            </div>
        `).join('') || '<p class="text-gray-500 text-center py-4">无搜索结果</p>';
    }),

    /**
     * 显示股票详情
     */
    async showStockDetail(symbol) {
        window.location.hash = `stock/${symbol}`;
        await this.renderStockDetail(symbol);
    },

    async renderStockDetail(symbol) {
        await DataService.loadStockQuotes(true);
        const quote = State.stockQuotes?.[symbol];
        const related = State.news.find(n => n.stocks?.some(s => s.symbol === symbol))?.stocks?.find(s => s.symbol === symbol);
        const name = related?.name || symbol;
        const price = typeof quote?.price === 'number' ? quote.price.toFixed(2) : '--';
        const changePercent = typeof quote?.change_percent === 'number' ? quote.change_percent : null;
        const isPositive = (changePercent || 0) >= 0;
        const changeText = changePercent === null ? '--' : `${isPositive ? '+' : ''}${changePercent}%`;
        const relatedCount = State.news.filter(n => n.stocks?.some(s => s.symbol === symbol)).length;
        const relatedNews = State.news.filter(n => n.stocks?.some(s => s.symbol === symbol)).slice(0, 8);
        const updated = quote?.market_time ? Utils.formatTime(quote.market_time) : '暂无';

        this.showDetailView();
        const content = document.getElementById('detail-content');
        content.innerHTML = `
            <div class="glass rounded-2xl p-6 md:p-8">
                <div class="flex items-start justify-between mb-6">
                    <div>
                        <div class="flex items-center gap-3 mb-2">
                            <span class="text-3xl font-bold font-mono">${symbol}</span>
                            <span class="text-xl text-gray-400">${name}</span>
                        </div>
                        <div class="flex items-center gap-4">
                            <span class="text-4xl font-bold">${quote?.currency || ''} ${price}</span>
                            <span class="${isPositive ? 'text-success' : 'text-danger'} text-lg font-medium">
                                <i class="fas fa-${isPositive ? 'arrow-up' : 'arrow-down'}"></i>
                                ${changeText}
                            </span>
                        </div>
                        <div class="text-xs text-gray-500 mt-2">行情来源：${quote?.source || '暂无行情'} · 行情时间：${updated}</div>
                    </div>
                    <button onclick="App.renderStockDetail('${symbol}')" class="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary/15 text-primary hover:bg-primary/25 transition">
                        <i class="fas fa-sync-alt"></i>
                        刷新行情
                    </button>
                </div>
                
                <div class="grid md:grid-cols-3 gap-4 mb-8">
                    <div class="glass rounded-xl p-4">
                        <div class="text-gray-400 text-sm mb-1">行情刷新</div>
                        <div class="text-xl font-bold">60秒</div>
                    </div>
                    <div class="glass rounded-xl p-4">
                        <div class="text-gray-400 text-sm mb-1">涨跌额</div>
                        <div class="text-xl font-bold">${typeof quote?.change === 'number' ? quote.change : '--'}</div>
                    </div>
                    <div class="glass rounded-xl p-4">
                        <div class="text-gray-400 text-sm mb-1">相关新闻</div>
                        <div class="text-xl font-bold text-primary">
                            ${relatedCount}
                        </div>
                    </div>
                </div>

                <div class="mb-8">
                    <h3 class="text-lg font-semibold mb-3">关联新闻</h3>
                    <div class="space-y-3">
                        ${relatedNews.map(news => `
                            <button onclick="App.showNewsDetail('${news.id}')" class="w-full text-left p-4 rounded-xl bg-white/5 hover:bg-white/10 transition">
                                <div class="text-sm text-gray-400 mb-1">${State.categories[news.category]?.name || news.category} · ${Utils.formatTime(news.publish_time)}</div>
                                <div class="font-medium">${news.title}</div>
                            </button>
                        `).join('') || '<div class="text-gray-500">暂无关联新闻</div>'}
                    </div>
                </div>
                
                <div class="flex gap-3">
                    <a href="https://finance.yahoo.com/quote/${symbol}" target="_blank" 
                       class="flex-1 bg-primary hover:bg-primary/80 text-center py-3 rounded-xl font-medium transition">
                        <i class="fas fa-chart-line mr-2"></i>查看行情
                    </a>
                </div>
            </div>
        `;

        if (State.stockRefreshTimer) clearInterval(State.stockRefreshTimer);
        State.stockRefreshTimer = setInterval(() => this.renderStockDetail(symbol), 60000);
    },

    /**
     * 绑定事件
     */
    bindEvents() {
        // 键盘快捷键
        document.addEventListener('keydown', (e) => {
            if (e.key === '/' && !e.ctrlKey && !e.metaKey) {
                e.preventDefault();
                this.toggleSearch();
            }
            if (e.key === 'Escape') {
                if (!document.getElementById('detail-view')?.classList.contains('hidden')) {
                    this.backToList();
                    return;
                }
                document.querySelectorAll('[id$="-modal"]').forEach(m => m.classList.add('hidden'));
            }
        });
        window.addEventListener('hashchange', () => this.handleRoute());
    },

    /**
     * 初始化滚动处理
     */
    initScrollHandler() {
        const handleScroll = Utils.throttle(() => {
            const scrollTop = window.pageYOffset;
            
            // 显示/隐藏回到顶部按钮
            const backToTop = document.getElementById('back-to-top');
            backToTop.style.opacity = scrollTop > 500 ? '1' : '0';
            backToTop.style.pointerEvents = scrollTop > 500 ? 'auto' : 'none';
            
            // 自动加载更多
            const scrollHeight = document.documentElement.scrollHeight;
            const clientHeight = document.documentElement.clientHeight;
            
            if (scrollTop + clientHeight >= scrollHeight - CONFIG.SCROLL_THRESHOLD) {
                this.loadMore();
            }
        }, 200);
        
        window.addEventListener('scroll', handleScroll);
    },

    /**
     * 更新日期
     */
    updateDate() {
        const now = new Date();
        const dateStr = now.toLocaleDateString('zh-CN', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            weekday: 'long'
        });
        document.getElementById('current-date').textContent = dateStr;
        
        // 更新最后更新时间
        const lastUpdate = localStorage.getItem('last_update');
        if (lastUpdate) {
            document.getElementById('last-update').textContent = 
                `上次更新: ${Utils.formatTime(lastUpdate)}`;
        }
    },

    /**
     * 更新统计
     */
    updateStats() {
        document.getElementById('stat-total').textContent = State.news.length.toLocaleString();
        document.getElementById('stat-opportunities').textContent = State.opportunities.length.toLocaleString();
        document.getElementById('stat-stocks').textContent = Object.keys(State.stockQuotes || {}).length.toLocaleString();
        
        // 计算24小时内新增
        const yesterday = new Date(Date.now() - 24 * 60 * 60 * 1000);
        const newCount = State.news.filter(n => new Date(n.publish_time) > yesterday).length;
        document.getElementById('stat-new').textContent = newCount;
    },

    // UI控制方法
    toggleSearch() {
        const modal = document.getElementById('search-modal');
        const isHidden = modal.classList.contains('hidden');
        modal.classList.toggle('hidden');
        if (isHidden) {
            document.getElementById('search-input')?.focus();
        }
    },

    closeModal(id) {
        document.getElementById(id)?.classList.add('hidden');
    },

    selectSearchResult(id) {
        this.toggleSearch();
        this.showNewsDetail(id);
    },

    showNewsDetail(id) {
        window.location.hash = `news/${id}`;
        this.renderNewsDetail(id);
    },

    renderNewsDetail(id) {
        if (State.stockRefreshTimer) {
            clearInterval(State.stockRefreshTimer);
            State.stockRefreshTimer = null;
        }
        const news = State.news.find(item => item.id === id);
        if (!news) return;
        const cat = State.categories[news.category] || { name: news.category, color: 'gray' };
        const opportunity = State.opportunities.find(item => item.id === id);
        const stocks = (news.stocks || []).map(stock => `
            <button onclick="App.showStockDetail('${stock.symbol}')" class="stock-card w-full md:w-auto inline-flex items-center justify-between gap-3 px-4 py-3 rounded-xl text-sm">
                <span><b class="font-mono">${stock.symbol}</b> <span class="text-gray-300">${stock.name}</span></span>
                ${Renderer.renderQuoteBadge(stock.symbol)}
            </button>
        `).join('');

        this.showDetailView();
        document.getElementById('detail-content').innerHTML = `
            <article class="glass rounded-2xl p-6 md:p-8">
                <div class="flex flex-wrap items-center gap-2 mb-4">
                    <span class="px-2 py-1 bg-${cat.color}-500/20 text-${cat.color}-400 text-xs font-bold rounded">${cat.name}</span>
                    ${(news.tags || []).map(tag => `<span class="px-2 py-1 bg-white/5 text-gray-400 text-xs rounded">${tag}</span>`).join('')}
                    ${opportunity ? `<span class="px-2 py-1 bg-accent/10 text-accent text-xs rounded">机会分 ${opportunity.score}</span>` : ''}
                </div>
                <h2 class="text-3xl font-bold leading-tight mb-4">${news.title}</h2>
                <div class="flex flex-wrap items-center gap-4 text-sm text-gray-500 mb-6">
                    <span><i class="far fa-clock mr-1"></i>${Utils.formatTime(news.publish_time)}</span>
                    <span>可信度 ${news.metrics?.credibility_score || 90}%</span>
                </div>
                <p class="text-lg text-gray-300 leading-relaxed mb-6">${news.summary}</p>
                ${opportunity ? `
                    <div class="rounded-xl border border-accent/30 bg-accent/10 p-5 mb-6">
                        <h3 class="font-semibold text-accent mb-2">推荐逻辑</h3>
                        <p class="text-sm text-gray-300 mb-2">${opportunity.logic}</p>
                        <p class="text-xs text-warning/90">${opportunity.risk}</p>
                    </div>
                ` : ''}
                <div class="mb-6">
                    <h3 class="text-lg font-semibold mb-3">关联股票</h3>
                    <div class="flex flex-wrap gap-3">${stocks || '<span class="text-gray-500">暂无关联股票</span>'}</div>
                </div>
                <div class="mb-6">
                    <h3 class="text-lg font-semibold mb-3">来源</h3>
                    <div class="flex flex-wrap gap-2">
                        ${(news.sources || []).map(src => `
                            <a href="${src.url}" target="_blank" rel="noopener" class="source-tag inline-flex items-center gap-2 px-3 py-2 rounded-lg text-sm">
                                <i class="fas fa-check-circle"></i>
                                ${src.name}
                                <span class="opacity-70">${src.credibility}%</span>
                            </a>
                        `).join('')}
                    </div>
                </div>
            </article>
        `;
    },

    showDetailView() {
        document.getElementById('list-view')?.classList.add('hidden');
        document.getElementById('detail-view')?.classList.remove('hidden');
        window.scrollTo({ top: 0, behavior: 'smooth' });
    },

    backToList() {
        if (State.stockRefreshTimer) {
            clearInterval(State.stockRefreshTimer);
            State.stockRefreshTimer = null;
        }
        history.pushState('', document.title, window.location.pathname + window.location.search);
        document.getElementById('detail-view')?.classList.add('hidden');
        document.getElementById('list-view')?.classList.remove('hidden');
    },

    handleRoute() {
        const hash = window.location.hash.replace(/^#\/?/, '');
        if (!hash) return;
        const [type, id] = hash.split('/');
        if (type === 'news' && id) this.renderNewsDetail(id);
        if (type === 'stock' && id) this.renderStockDetail(id);
    },

    share(id) {
        // TODO: 分享功能
        console.log('分享:', id);
    },

    bookmark(id) {
        // TODO: 收藏功能
        console.log('收藏:', id);
    },

    refreshNews() {
        const icon = document.getElementById('refresh-icon');
        icon?.classList.add('fa-spin');
        
        // 清除缓存
        State.cache.clear();
        
        this.loadData().then(() => {
            setTimeout(() => icon?.classList.remove('fa-spin'), 1000);
        });
    },

    scrollToTop() {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    },

    sortNews(sortBy) {
        const sorters = {
            newest: (a, b) => new Date(b.publish_time) - new Date(a.publish_time),
            hot: (a, b) => (b.metrics?.views || 0) - (a.metrics?.views || 0),
            credible: (a, b) => (b.metrics?.credibility_score || 0) - (a.metrics?.credibility_score || 0)
        };
        
        if (sorters[sortBy]) {
            State.filtered.sort(sorters[sortBy]);
            State.displayedCount = CONFIG.ITEMS_PER_PAGE;
            Renderer.renderNews(State.filtered.slice(0, State.displayedCount));
        }
    },

    toggleTheme() {
        document.documentElement.classList.toggle('dark');
        const isDark = document.documentElement.classList.contains('dark');
        const icon = document.getElementById('theme-icon');
        if (icon) {
            icon.className = isDark ? 'fas fa-sun text-yellow-400' : 'fas fa-moon text-gray-400';
        }
    }
};

// ==================== 启动应用 ====================
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => App.init());
} else {
    App.init();
}

// 暴露到全局
window.App = App;
window.Utils = Utils;
window.State = State;
window.filterCategory = (category) => App.filterCategory(category);
window.toggleSearch = () => App.toggleSearch();
window.searchNews = (query) => App.searchNews(query);
window.sortNews = (sortBy) => App.sortNews(sortBy);
window.refreshNews = () => App.refreshNews();
window.loadMore = () => App.loadMore();
window.toggleTheme = () => App.toggleTheme();
window.scrollToTop = () => App.scrollToTop();
