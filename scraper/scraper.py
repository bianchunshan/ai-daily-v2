#!/usr/bin/env python3
"""
AI日报数据采集引擎
支持RSS、API、网页三种数据源
自动分类、去重、双来源验证
"""

import json
import re
import hashlib
import time
import schedule
import requests
import feedparser
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse
from pathlib import Path

class NewsScraper:
    def __init__(self, config_path="config.json"):
        """初始化爬虫"""
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        self.output_dir = Path("../data/news")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        self.collected_news = []
        self.duplicate_hashes = set()
        
    def generate_id(self, title):
        """生成唯一ID"""
        return hashlib.md5(title.encode()).hexdigest()[:12]
    
    def generate_hash(self, text):
        """生成内容哈希用于去重"""
        # 提取关键词，忽略标点和大小写
        keywords = re.findall(r'\b\w+\b', text.lower())
        normalized = ' '.join(sorted(set(keywords)))
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def classify_category(self, title, summary):
        """自动分类"""
        text = f"{title} {summary}".lower()
        categories = self.config['categories']['keywords']
        
        scores = {}
        for cat, keywords in categories.items():
            score = sum(1 for kw in keywords if kw.lower() in text)
            if score > 0:
                scores[cat] = score
        
        if not scores:
            return 'market'
        
        return max(scores, key=scores.get)
    
    def extract_stocks(self, title, summary):
        """提取关联股票"""
        text = f"{title} {summary}"
        stock_mapping = self.config['stocks']['mapping']
        
        stocks = []
        seen = set()
        
        for company, symbols in stock_mapping.items():
            if company in text:
                for symbol in symbols:
                    if symbol not in seen:
                        seen.add(symbol)
                        # 判断影响（简单规则）
                        impact = self._judge_impact(text, company)
                        stocks.append({
                            "symbol": symbol,
                            "name": company,
                            "impact": impact,
                            "reason": f"新闻提及{company}"
                        })
        
        return stocks[:5]  # 最多5只股票
    
    def _judge_impact(self, text, company):
        """判断股票影响（利好/利空）"""
        positive = ['增长', '上涨', '突破', '创新', '领先', '强劲', '利好', '增长', 'rise', 'gain', 'surge', 'jump', 'breakthrough']
        negative = ['下跌', '下降', '亏损', '裁员', '监管', '调查', 'fall', 'drop', 'decline', 'crash', 'investigation']
        
        # 找到公司名称附近的关键词
        sentences = re.split(r'[。！？.!?]', text)
        for sent in sentences:
            if company in sent:
                pos_count = sum(1 for p in positive if p in sent)
                neg_count = sum(1 for n in negative if n in sent)
                
                if pos_count > neg_count:
                    return 'positive'
                elif neg_count > pos_count:
                    return 'negative'
        
        return 'neutral'
    
    def fetch_rss(self, source):
        """获取RSS源"""
        print(f"📡 获取RSS: {source['name']}")
        
        try:
            feed = feedparser.parse(source['url'])
            
            for entry in feed.entries[:20]:  # 只取前20条
                news = {
                    "id": self.generate_id(entry.get('title', '')),
                    "title": entry.get('title', ''),
                    "summary": entry.get('summary', entry.get('description', ''))[:300],
                    "category": source.get('category', 'market'),
                    "tags": [],
                    "publish_time": self._parse_time(entry.get('published', '')),
                    "sources": [{
                        "name": source['name'],
                        "url": entry.get('link', ''),
                        "verified": True,
                        "credibility": source.get('credibility', 80)
                    }],
                    "stocks": self.extract_stocks(entry.get('title', ''), entry.get('summary', '')),
                    "metrics": {
                        "views": 0,
                        "credibility_score": source.get('credibility', 80)
                    },
                    "status": "pending"
                }
                
                # 重新分类
                news['category'] = self.classify_category(news['title'], news['summary'])
                
                # 生成哈希去重
                content_hash = self.generate_hash(news['title'] + news['summary'])
                if content_hash not in self.duplicate_hashes:
                    self.duplicate_hashes.add(content_hash)
                    self.collected_news.append(news)
                    
            print(f"✅ {source['name']}: 获取 {len(feed.entries)} 条")
            
        except Exception as e:
            print(f"❌ {source['name']}: {e}")
    
    def _parse_time(self, time_str):
        """解析时间字符串"""
        formats = [
            '%a, %d %b %Y %H:%M:%S %z',
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%d %H:%M:%S',
            '%a, %d %b %Y %H:%M:%S GMT'
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(time_str, fmt)
                return dt.strftime('%Y-%m-%dT%H:%M:%S+08:00')
            except:
                continue
        
        # 默认返回当前时间
        return datetime.now().strftime('%Y-%m-%dT%H:%M:%S+08:00')
    
    def merge_duplicates(self):
        """合并重复新闻，添加多来源"""
        print("\n🔍 合并重复新闻...")
        
        merged = {}
        
        for news in self.collected_news:
            # 使用标题相似度去重
            key = self.generate_hash(news['title'])
            
            if key in merged:
                # 已存在，添加新来源
                existing = merged[key]
                new_source = news['sources'][0]
                
                # 检查是否已有相同来源
                if not any(s['name'] == new_source['name'] for s in existing['sources']):
                    existing['sources'].append(new_source)
                    # 更新可信度
                    existing['metrics']['credibility_score'] = min(99, 
                        existing['metrics']['credibility_score'] + 5)
            else:
                merged[key] = news
        
        self.collected_news = list(merged.values())
        print(f"✅ 合并后: {len(self.collected_news)} 条")
    
    def filter_validated(self):
        """筛选通过验证的新闻（至少2个来源）"""
        print("\n✅ 筛选验证新闻...")
        
        validated = []
        for news in self.collected_news:
            # 检查来源数量
            if len(news['sources']) >= self.config['validation']['min_sources']:
                # 检查可信度
                avg_cred = sum(s['credibility'] for s in news['sources']) / len(news['sources'])
                news['metrics']['credibility_score'] = int(avg_cred)
                
                if avg_cred >= self.config['validation']['min_credibility']:
                    news['status'] = 'published'
                    validated.append(news)
        
        self.collected_news = validated
        print(f"✅ 验证通过: {len(self.collected_news)} 条")
    
    def save_by_category(self):
        """按分类保存数据"""
        print("\n💾 保存数据...")
        
        # 按分类分组
        by_category = {}
        for news in self.collected_news:
            cat = news['category']
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(news)
        
        # 保存各分类文件
        for cat, news_list in by_category.items():
            file_path = self.output_dir / f"{cat}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "version": "2.0",
                    "category": cat,
                    "total": len(news_list),
                    "updated": datetime.now().isoformat(),
                    "news": news_list
                }, f, ensure_ascii=False, indent=2)
            print(f"  📄 {cat}.json: {len(news_list)} 条")
        
        # 保存汇总文件
        all_news = {
            "version": "2.0",
            "total": len(self.collected_news),
            "updated": datetime.now().isoformat(),
            "by_category": {k: len(v) for k, v in by_category.items()},
            "news": self.collected_news
        }
        
        with open(self.output_dir / "all.json", 'w', encoding='utf-8') as f:
            json.dump(all_news, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 总计保存: {len(self.collected_news)} 条新闻")
        for cat, count in all_news['by_category'].items():
            print(f"   {cat}: {count} 条")
    
    def run(self):
        """执行采集"""
        print("=" * 60)
        print("🚀 AI日报数据采集引擎 v2.0")
        print("=" * 60)
        print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # 1. 采集RSS源
        print("📡 阶段1: 采集RSS源")
        for source in self.config['sources']['rss']:
            self.fetch_rss(source)
            time.sleep(1)  # 礼貌延迟
        
        print(f"\n📊 RSS采集完成: {len(self.collected_news)} 条")
        
        # 2. 合并重复
        self.merge_duplicates()
        
        # 3. 验证筛选
        self.filter_validated()
        
        # 4. 保存数据
        self.save_by_category()
        
        print("\n" + "=" * 60)
        print(f"✅ 采集完成: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

def scheduled_job():
    """定时任务"""
    scraper = NewsScraper()
    scraper.run()

if __name__ == "__main__":
    # 立即执行一次
    scheduled_job()
    
    # 设置定时任务（每小时）
    # schedule.every().hour.do(scheduled_job)
    # while True:
    #     schedule.run_pending()
    #     time.sleep(60)