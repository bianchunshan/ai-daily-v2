/**
 * AI日报 - 核心应用逻辑
 * 架构师级优化：模块化、性能优化、缓存策略
 * @version 2.0
 */

// ==================== 配置常量 ====================
const CONFIG = {
    VERSION: '2.0.0',
    API_BASE: 'data/news',
    ITEMS_PER_PAGE: 10,
    CACHE_TTL: 5 * 60 * 1000, // 5分钟缓存
    DEBOUNCE_DELAY: 300,
    SCROLL_THRESHOLD: 200
};

// ==================== 状态管理 ====================
const State = {
    news: [],
    filtered: [],
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
        'biotech': { name: '生物科技', icon: 'dna', color: 'pink' },
        'space': { name: '商业航天', icon: 'rocket', color: 'orange' },
        'fusion': { name: '核聚变', icon: 'fire', color: 'amber' },
        'consumer': { name: '消费电子', icon: 'mobile-alt', color: 'indigo' },
        'gaming': { name: '游戏', icon: 'gamepad', color: 'teal' }
    }
};

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
            const response = await fetch(`${CONFIG.API_BASE}/all.json`);
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
            const response = await fetch(`${CONFIG.API_BASE}/${category}.json`);
            const data = await response.json();
            Utils.cache.set(cacheKey, data.news);
            return data.news;
        } catch (e) {
            console.error(`❌ 加载分类 ${category} 失败:`, e);
            return [];
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

        grid.innerHTML = Object.entries(State.categories).map(([key, cat]) => `
            <button onclick="App.filterCategory('${key}')" 
                    class="category-btn glass rounded-xl p-4 text-center transition border border-border hover:border-primary/50 group"
                    data-cat="${key}">
                <div class="w-10 h-10 mx-auto mb-2 rounded-lg bg-gradient-to-br ${colors[cat.color]} 
                            flex items-center justify-center group-hover:scale-110 transition">
                    <i class="fas fa-${cat.icon}"></i>
                </div>
                <p class="text-sm font-medium">${cat.name}</p>
                <p class="text-xs text-gray-500 mt-1">100+条</p>
            </button>
        `).join('');
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

    /**
     * 渲染突发新闻
     */
    renderBreakingNews() {
        const breaking = State.news.filter(n => n.metrics?.credibility_score >= 95).slice(0, 5);
        const container = document.getElementById('breaking-news');
        
        if (!container || breaking.length === 0) return;
        
        const items = [...breaking, ...breaking]; // 复制一份用于无缝滚动
        container.innerHTML = items.map(news => `
            <span class="text-gray-300 whitespace-nowrap flex items-center gap-2">
                ${news.metrics?.credibility_score >= 97 ? 
                    '<i class="fas fa-bolt text-red-400"></i>' : ''}
                ${news.title.substring(0, 40)}${news.title.length > 40 ? '...' : ''}
            </span>
            <span class="text-gray-600">|</span>
        `).join('');
    }
};

// ==================== 应用主逻辑 ====================
const App = {
    /**
     * 初始化应用
     */
    async init() {
        console.log('🚀 AI日报 v2.0 启动中...');
        
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
            State.filtered = [...State.news];
            
            // 备份到本地
            DataService.backup(State.news);
            
            // 渲染
            Renderer.renderNews(State.filtered.slice(0, State.displayedCount));
            Renderer.renderBreakingNews();
            
            // 更新统计
            this.updateStats();
            
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
        State.currentCategory = category;
        State.displayedCount = CONFIG.ITEMS_PER_PAGE;
        
        // 更新导航样式
        document.querySelectorAll('.nav-btn, .category-btn').forEach(btn => {
            const isActive = btn.dataset.cat === category;
            if (btn.classList.contains('nav-btn')) {
                btn.className = isActive ? 
                    'nav-btn px-4 py-2 rounded-lg text-sm font-medium text-primary bg-primary/10 transition' :
                    'nav-btn px-4 py-2 rounded-lg text-sm font-medium text-gray-400 hover:text-white hover:bg-white/5 transition';
            }
        });
        
        // 筛选数据
        if (category === 'all') {
            State.filtered = [...State.news];
        } else {
            State.filtered = State.news.filter(n => n.category === category);
        }
        
        // 更新标题
        const catName = category === 'all' ? '全部资讯' : State.categories[category]?.name || category;
        document.getElementById('section-title').textContent = catName;
        
        // 重新渲染
        Renderer.renderNews(State.filtered.slice(0, State.displayedCount));
        
        // 滚动到顶部
        window.scrollTo({ top: 0, behavior: 'smooth' });
    },

    /**
     * 加载更多
     */
    loadMore() {
        if (State.isLoading || State.displayedCount >= State.filtered.length) return;
        
        State.displayedCount += CONFIG.ITEMS_PER_PAGE;
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
    showStockDetail(symbol) {
        // 模拟股票数据
        const stockData = {
            'NVDA': { name: '英伟达', price: 875.50, change: -5.5, marketCap: '2.15T', pe: 52 },
            'AMD': { name: '超威半导体', price: 102.30, change: -3.2, marketCap: '165B', pe: 38 },
            'TSM': { name: '台积电', price: 142.80, change: -2.8, marketCap: '740B', pe: 22 },
            'MSFT': { name: '微软', price: 412.20, change: 1.2, marketCap: '3.06T', pe: 32 },
            'TSLA': { name: '特斯拉', price: 248.50, change: -1.5, marketCap: '795B', pe: 68 },
            'AAPL': { name: '苹果', price: 235.20, change: 0.5, marketCap: '3.58T', pe: 30 },
            'AMZN': { name: '亚马逊', price: 198.50, change: 0.8, marketCap: '2.07T', pe: 58 },
            'META': { name: 'Meta', price: 625.30, change: 2.1, marketCap: '1.59T', pe: 24 }
        };
        
        const stock = stockData[symbol] || { name: symbol, price: 0, change: 0, marketCap: 'N/A', pe: 'N/A' };
        const isPositive = stock.change >= 0;
        
        const content = document.getElementById('stock-detail-content');
        content.innerHTML = `
            <div class="p-6">
                <div class="flex items-start justify-between mb-6">
                    <div>
                        <div class="flex items-center gap-3 mb-2">
                            <span class="text-3xl font-bold font-mono">${symbol}</span>
                            <span class="text-xl text-gray-400">${stock.name}</span>
                        </div>
                        <div class="flex items-center gap-4">
                            <span class="text-4xl font-bold">$${stock.price.toFixed(2)}</span>
                            <span class="${isPositive ? 'text-success' : 'text-danger'} text-lg font-medium">
                                <i class="fas fa-${isPositive ? 'arrow-up' : 'arrow-down'}"></i>
                                ${Math.abs(stock.change)}%
                            </span>
                        </div>
                    </div>
                    <button onclick="App.closeModal('stock-modal')" class="w-10 h-10 flex items-center justify-center rounded-lg hover:bg-white/10 transition">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                
                <div class="grid grid-cols-3 gap-4 mb-6">
                    <div class="glass rounded-xl p-4">
                        <div class="text-gray-400 text-sm mb-1">市值</div>
                        <div class="text-xl font-bold">${stock.marketCap}</div>
                    </div>
                    <div class="glass rounded-xl p-4">
                        <div class="text-gray-400 text-sm mb-1">市盈率</div>
                        <div class="text-xl font-bold">${stock.pe}</div>
                    </div>
                    <div class="glass rounded-xl p-4">
                        <div class="text-gray-400 text-sm mb-1">相关新闻</div>
                        <div class="text-xl font-bold text-primary">
                            ${State.news.filter(n => n.stocks?.some(s => s.symbol === symbol)).length}
                        </div>
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
        
        document.getElementById('stock-modal').classList.remove('hidden');
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
                document.querySelectorAll('[id$="-modal"]').forEach(m => m.classList.add('hidden'));
            }
        });
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
        const news = State.news.find(n => n.id === id);
        if (news) {
            this.filterCategory(news.category);
        }
    },

    showNewsDetail(id) {
        // TODO: 显示新闻详情弹窗
        console.log('查看新闻:', id);
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