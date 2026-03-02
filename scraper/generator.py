#!/usr/bin/env python3
"""
AI日报数据生成器
快速生成1100+条高质量模拟数据
用于演示和测试
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

class DataGenerator:
    def __init__(self):
        self.output_dir = Path("../data/news")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 11大板块
        self.categories = {
            "world": {
                "name": "国际局势",
                "keywords": ["美国", "中国", "欧盟", "中东", "俄罗斯", "日本", "贸易", "关税", "制裁", "外交"],
                "templates": [
                    "{country1}与{country2}就{topic}达成共识",
                    "{country1}宣布对{country2}实施{action}",
                    "{country1}与{country2}{topic}谈判取得进展",
                    "{organization}就{topic}发布最新声明",
                    "{country1}总统访问{country2}，签署{topic}协议"
                ]
            },
            "ai": {
                "name": "人工智能",
                "keywords": ["GPT", "大模型", "算力", "OpenAI", "Google", "微软", "Meta", "AI芯片", "自动驾驶", "生成式AI"],
                "templates": [
                    "{company}发布新一代{product}，性能提升{percent}%",
                    "{company}完成{amount}亿美元融资，估值达{valuation}亿美元",
                    "{company}与{company2}达成{topic}合作协议",
                    "{product}月活用户突破{number}亿，创行业新高",
                    "{company}开源{product}，推动{topic}发展"
                ]
            },
            "semiconductor": {
                "name": "半导体",
                "keywords": ["台积电", "英伟达", "Intel", "AMD", "ASML", "7nm", "5nm", "3nm", "EUV", "晶圆代工"],
                "templates": [
                    "{company}Q{quarter}营收{amount}亿美元，同比增长{percent}%",
                    "{company}宣布投资{amount}亿美元建设{location}新厂",
                    "{company}与{company2}签署{amount}亿美元{product}供应协议",
                    "{company}成功量产{process}制程芯片，领先竞争对手",
                    "{company}发布新一代{product}，能效提升{percent}%"
                ]
            },
            "energy": {
                "name": "新能源",
                "keywords": ["光伏", "储能", "锂电池", "电动车", "宁德时代", "比亚迪", "特斯拉", "风电", "氢能"],
                "templates": [
                    "{company}发布新一代{product}，续航提升{percent}%",
                    "{country}光伏装机量达{amount}GW，同比增长{percent}%",
                    "{company}与{company2}签署{amount}GWh{product}供应协议",
                    "{company}{product}产能突破{amount}GWh，全球领先",
                    "{company}投资{amount}亿元建设{location}{product}基地"
                ]
            },
            "robotics": {
                "name": "机器人",
                "keywords": ["人形机器人", "工业机器人", "Boston Dynamics", "特斯拉Optimus", "自动化", "智能制造"],
                "templates": [
                    "{company}发布{product}，可实现{capability}",
                    "{company}人形机器人{product}开始量产，售价{amount}万美元",
                    "{company}与{company2}合作开发{product}，应用于{field}",
                    "{company}机器人{product}获得{number}台订单",
                    "{company}投资{amount}亿美元建设{product}生产线"
                ]
            },
            "quantum": {
                "name": "量子计算",
                "keywords": ["量子比特", "量子霸权", "IBM", "Google", "本源量子", "量子通信", "量子加密"],
                "templates": [
                    "{company}成功研发{number}量子比特{product}",
                    "{company}量子计算机{product}算力突破{classical}倍",
                    "{company}与{company2}合作建设{location}量子计算中心",
                    "{company}发布量子操作系统{product}，开放下载",
                    "{company}量子计算云服务用户突破{number}万"
                ]
            },
            "biotech": {
                "name": "生物科技",
                "keywords": ["创新药", "基因治疗", "mRNA", "疫苗", "减肥药", "礼来", "诺和诺德", "癌症治疗"],
                "templates": [
                    "{company}新药{product}获批上市，治疗{condition}",
                    "{company}减肥药{product}III期临床成功，减重{percent}%",
                    "{company}与{company2}达成{amount}亿美元{product}合作",
                    "{company}基因治疗药物{product}获FDA批准",
                    "{company}投资{amount}亿美元建设{location}研发中心"
                ]
            },
            "space": {
                "name": "商业航天",
                "keywords": ["SpaceX", "星链", "火箭", "卫星", "火星", "NASA", "蓝色起源", "商业航天"],
                "templates": [
                    "{company}成功发射{product}，部署{number}颗卫星",
                    "{company}完成{product}第{number}次发射，成功率{percent}%",
                    "{company}与{company2}签署{amount}亿美元卫星发射合同",
                    "{company}火星探测器{product}成功着陆",
                    "{company}太空旅游票价降至{amount}万美元"
                ]
            },
            "fusion": {
                "name": "核聚变",
                "keywords": ["托卡马克", "激光聚变", "ITER", "人造太阳", "清洁能源", "等离子体"],
                "templates": [
                    "{company}核聚变装置{product}实现{duration}秒持续运行",
                    "{company}完成{amount}亿美元融资，推进{product}商业化",
                    "{company}与{company2}合作建设{location}核聚变电站",
                    "{country}核聚变实验装置{product}实现能量增益Q>1",
                    "{company}预计{year}年实现核聚变并网发电"
                ]
            },
            "consumer": {
                "name": "消费电子",
                "keywords": ["iPhone", "华为", "小米", "三星", "智能手机", "VR/AR", "可穿戴设备"],
                "templates": [
                    "{company}发布{product}，搭载{feature}",
                    "{company}{product}首销突破{amount}万台",
                    "{company}与{company2}达成{product}供应链合作",
                    "{company}折叠屏手机{product}出货量突破{amount}万台",
                    "{company}AR眼镜{product}开始量产，售价{amount}元"
                ]
            },
            "gaming": {
                "name": "游戏",
                "keywords": ["游戏", "腾讯", "网易", "米哈游", "Steam", "手游", "端游", "电竞", "元宇宙游戏", "AI游戏"],
                "templates": [
                    "{company}游戏{product}全球收入突破{amount}亿美元",
                    "{company}发布新游{product}，首周下载量达{number}万",
                    "{company}与{company2}达成{product}发行合作",
                    "{game}电竞赛事奖金池达{amount}万美元，创纪录",
                    "{company}投资{amount}亿美元建设{location}游戏工作室"
                ]
            }
        }
        
        # 来源配置
        self.sources = [
            {"name": "华尔街日报", "credibility": 95},
            {"name": "彭博社", "credibility": 96},
            {"name": "路透社", "credibility": 94},
            {"name": "金融时报", "credibility": 92},
            {"name": "CNBC", "credibility": 90},
            {"name": "新华网", "credibility": 97},
            {"name": "中国新闻网", "credibility": 88}
        ]
        
        # 股票配置
        self.stocks = {
            "NVDA": {"name": "英伟达", "categories": ["ai", "semiconductor"]},
            "AMD": {"name": "超威半导体", "categories": ["semiconductor"]},
            "INTC": {"name": "英特尔", "categories": ["semiconductor"]},
            "TSM": {"name": "台积电", "categories": ["semiconductor"]},
            "ASML": {"name": "阿斯麦", "categories": ["semiconductor"]},
            "AVGO": {"name": "博通", "categories": ["semiconductor"]},
            "QCOM": {"name": "高通", "categories": ["semiconductor", "consumer"]},
            "MSFT": {"name": "微软", "categories": ["ai", "gaming"]},
            "GOOGL": {"name": "谷歌", "categories": ["ai", "robotics"]},
            "AMZN": {"name": "亚马逊", "categories": ["ai", "gaming"]},
            "META": {"name": "Meta", "categories": ["ai", "consumer"]},
            "TSLA": {"name": "特斯拉", "categories": ["energy", "robotics", "consumer"]},
            "AAPL": {"name": "苹果", "categories": ["consumer", "ai"]},
            "BYD": {"name": "比亚迪", "categories": ["energy", "consumer"]},
            "PLTR": {"name": "Palantir", "categories": ["ai"]},
            "LLY": {"name": "礼来", "categories": ["biotech"]},
            "NVO": {"name": "诺和诺德", "categories": ["biotech"]},
            "JNJ": {"name": "强生", "categories": ["biotech"]},
            "PFE": {"name": "辉瑞", "categories": ["biotech"]},
            "MRNA": {"name": "Moderna", "categories": ["biotech"]},
            "IBM": {"name": "IBM", "categories": ["quantum", "ai"]},
            "IONQ": {"name": "IonQ", "categories": ["quantum"]}
        }
        
        self.companies = {
            "ai": ["OpenAI", "Google", "微软", "Meta", "Anthropic", "百度", "阿里巴巴", "字节跳动"],
            "semiconductor": ["英伟达", "台积电", "Intel", "AMD", "ASML", "三星", "高通", "博通"],
            "energy": ["特斯拉", "比亚迪", "宁德时代", "隆基绿能", "通威股份", "First Solar", "Enphase"],
            "biotech": ["礼来", "诺和诺德", "强生", "辉瑞", "Moderna", "基因泰克", "安进"],
            "space": ["SpaceX", "蓝色起源", "Rocket Lab", "星河动力", "星际荣耀", "长光卫星"],
            "gaming": ["腾讯", "网易", "米哈游", "Steam", "Epic Games", "动视暴雪", "EA", "任天堂"]
        }
    
    def random_date(self, days_back=30):
        """生成随机日期"""
        end = datetime.now()
        start = end - timedelta(days=days_back)
        random_date = start + timedelta(seconds=random.randint(0, int((end - start).total_seconds())))
        return random_date.strftime('%Y-%m-%dT%H:%M:%S+08:00')
    
    def generate_title(self, category):
        """生成标题"""
        cat_data = self.categories[category]
        template = random.choice(cat_data['templates'])
        
        # 替换变量
        variables = {
            "{company}": random.choice(self.companies.get(category, ["科技公司", "能源公司"])),
            "{company2}": random.choice(self.companies.get(category, ["合作伙伴"])),
            "{country}": random.choice(["中国", "美国", "欧盟", "日本", "韩国", "德国", "英国"]),
            "{country1}": random.choice(["中国", "美国", "欧盟"]),
            "{country2}": random.choice(["日本", "韩国", "英国", "法国", "印度"]),
            "{topic}": random.choice(cat_data['keywords']),
            "{product}": random.choice(["新产品", "新一代技术", "创新方案", "智能系统"]),
            "{amount}": str(random.choice([10, 50, 100, 500, 1000, 2000, 5000])),
            "{valuation}": str(random.choice([100, 500, 1000, 5000, 10000, 50000])),
            "{percent}": str(random.randint(10, 200)),
            "{number}": str(random.choice([1, 5, 10, 50, 100, 500])),
            "{quarter}": str(random.choice([1, 2, 3, 4])),
            "{process}": random.choice(["3nm", "5nm", "7nm", "2nm"]),
            "{location}": random.choice(["亚利桑那", "得克萨斯", "台湾", "上海", "北京", "新加坡"]),
            "{action}": random.choice(["制裁", "合作", "谈判", "投资", "加征关税"]),
            "{organization}": random.choice(["联合国", "WTO", "IMF", "世界银行", "G20"]),
            "{condition}": random.choice(["癌症", "糖尿病", "肥胖症", "罕见病"]),
            "{duration}": str(random.choice([100, 500, 1000, 3600])),
            "{classical}": str(random.choice([100, 1000, 10000, 100000])),
            "{year}": str(random.choice([2027, 2028, 2030])),
            "{market}": random.choice(["纳斯达克", "标普500", "上证指数", "恒生指数"]),
            "{scope}": random.choice(["全球", "亚太", "欧美", "新兴市场"]),
            "{field}": random.choice(["制造业", "物流", "医疗", "农业", "服务业"]),
            "{capability}": random.choice(["自主导航", "人机协作", "复杂环境作业", "精密操作"]),
            "{feature}": random.choice(["AI芯片", "卫星通信", "折叠屏", "超长续航"]),
            "{game}": random.choice(["王者荣耀", "原神", "英雄联盟", "魔兽世界", "塞尔达", "GTA", "使命召唤"])
        }
        
        title = template
        for key, value in variables.items():
            title = title.replace(key, value)
        
        return title
    
    def generate_summary(self, title, category):
        """生成摘要"""
        summaries = [
            f"据{random.choice(['官方', '知情人士', '分析师'])}透露，{title}，这将显著影响相关行业发展。",
            f"{title}。市场分析师认为此举将带来{random.randint(10, 50)}%的增长潜力。",
            f"最新数据显示，{title}。相关公司股价盘前{random.choice(['上涨', '下跌'])}约{random.randint(1, 10)}%。",
            f"{title}。业内人士预计该趋势将在未来{random.randint(1, 5)}年内持续。",
            f"据报道，{title}。这一进展标志着行业进入新的发展阶段。"
        ]
        return random.choice(summaries)
    
    def generate_sources(self):
        """生成双来源"""
        num_sources = random.randint(2, 3)
        selected = random.sample(self.sources, num_sources)
        
        return [{
            "name": s["name"],
            "url": f"https://example.com/news/{random.randint(10000, 99999)}",
            "verified": True,
            "verify_time": self.random_date(1),
            "credibility": s["credibility"]
        } for s in selected]
    
    def generate_stocks(self, category):
        """生成关联股票"""
        # 根据分类选择相关股票
        related = [sym for sym, data in self.stocks.items() if category in data['categories']]
        
        if not related:
            related = list(self.stocks.keys())
        
        num_stocks = random.randint(1, min(4, len(related)))
        selected = random.sample(related, num_stocks)
        
        return [{
            "symbol": sym,
            "name": self.stocks[sym]["name"],
            "impact": random.choice(["positive", "positive", "positive", "negative", "neutral"]),
            "reason": f"新闻提及{self.stocks[sym]['name']}"
        } for sym in selected]
    
    def generate_news_item(self, category, index):
        """生成单条新闻"""
        title = self.generate_title(category)
        
        sources = self.generate_sources()
        avg_cred = sum(s["credibility"] for s in sources) / len(sources)
        
        return {
            "id": f"{category}-{index:04d}",
            "title": title,
            "summary": self.generate_summary(title, category),
            "content": self.generate_summary(title, category) + "详细内容待补充...",
            "category": category,
            "tags": random.sample(self.categories[category]["keywords"], min(3, len(self.categories[category]["keywords"]))),
            "publish_time": self.random_date(7),
            "sources": sources,
            "stocks": self.generate_stocks(category),
            "metrics": {
                "views": random.randint(5000, 100000),
                "shares": random.randint(100, 5000),
                "saves": random.randint(50, 2000),
                "credibility_score": int(avg_cred)
            },
            "status": "published"
        }
    
    def generate_all(self):
        """生成所有数据"""
        print("🚀 AI日报数据生成器 v2.0")
        print("=" * 60)
        
        all_news = []
        by_category = {}
        
        # 为每个分类生成100条
        for cat, data in self.categories.items():
            print(f"\n📂 生成分类: {data['name']} ({cat})")
            
            cat_news = []
            for i in range(100):
                news = self.generate_news_item(cat, i + 1)
                cat_news.append(news)
                all_news.append(news)
            
            by_category[cat] = cat_news
            
            # 保存分类文件
            file_path = self.output_dir / f"{cat}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "version": "2.0",
                    "category": cat,
                    "name": data["name"],
                    "total": len(cat_news),
                    "updated": datetime.now().isoformat(),
                    "news": cat_news
                }, f, ensure_ascii=False, indent=2)
            
            print(f"   ✅ {cat}.json: {len(cat_news)} 条")
        
        # 保存汇总文件
        summary = {
            "version": "2.0",
            "total": len(all_news),
            "updated": datetime.now().isoformat(),
            "by_category": {cat: len(news_list) for cat, news_list in by_category.items()},
            "news": all_news
        }
        
        with open(self.output_dir / "all.json", 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        print("\n" + "=" * 60)
        print(f"✅ 数据生成完成!")
        print(f"📊 总计: {len(all_news)} 条新闻")
        print(f"📁 文件数: {len(by_category) + 1} 个")
        for cat, count in summary['by_category'].items():
            print(f"   {self.categories[cat]['name']}: {count} 条")
        print("=" * 60)

if __name__ == "__main__":
    generator = DataGenerator()
    generator.generate_all()