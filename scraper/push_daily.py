#!/usr/bin/env python3
"""
AI日报 - 定时推送服务
每天早上9点生成并推送新资讯摘要
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

def generate_daily_digest():
    """生成每日资讯摘要"""
    
    # 加载数据
    data_path = Path(__file__).parent / '..' / 'data' / 'news' / 'all.json'
    
    try:
        with open(data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ 加载数据失败: {e}")
        return None
    
    news_list = data.get('news', [])
    
    # 筛选24小时内的新闻
    yesterday = datetime.now() - timedelta(hours=24)
    recent_news = [
        n for n in news_list 
        if datetime.fromisoformat(n['publish_time'].replace('+08:00', '')) > yesterday
    ]
    
    # 筛选高可信度新闻（突发）
    breaking_news = [n for n in recent_news if n['metrics']['credibility_score'] >= 95]
    
    # 按分类统计
    by_category = {}
    for news in recent_news:
        cat = news['category']
        by_category[cat] = by_category.get(cat, 0) + 1
    
    # 选取Top 5重要新闻
    top_news = sorted(
        recent_news, 
        key=lambda x: (x['metrics']['credibility_score'], x['metrics']['views']), 
        reverse=True
    )[:5]
    
    digest = {
        "date": datetime.now().strftime('%Y-%m-%d'),
        "type": "daily_digest",
        "summary": {
            "total_new": len(recent_news),
            "breaking": len(breaking_news),
            "by_category": by_category
        },
        "top_news": [
            {
                "id": n['id'],
                "title": n['title'],
                "category": n['category'],
                "credibility": n['metrics']['credibility_score'],
                "stocks": [s['symbol'] for s in n.get('stocks', [])]
            }
            for n in top_news
        ],
        "generated_at": datetime.now().isoformat()
    }
    
    return digest

def send_notification(digest):
    """发送推送通知（多种方式）"""
    
    if not digest:
        print("❌ 没有数据可推送")
        return
    
    # 1. 保存到文件
    output_path = Path(__file__).parent / '..' / 'data' / 'daily_digest.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(digest, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 日报已保存: {output_path}")
    
    # 2. 生成推送消息文本
    msg_lines = [
        f"📰 AI日报 - {digest['date']}",
        "",
        f"📊 24小时新增: {digest['summary']['total_new']} 条",
        f"🔥 突发新闻: {digest['summary']['breaking']} 条",
        "",
        "📌 重要资讯:"
    ]
    
    for i, news in enumerate(digest['top_news'][:3], 1):
        msg_lines.append(f"{i}. {news['title'][:50]}...")
        if news['stocks']:
            msg_lines.append(f"   📈 相关: {', '.join(news['stocks'])}")
    
    msg_lines.append("")
    msg_lines.append("🔗 查看详情: https://bianchunshan.github.io/ai-daily-v2/")
    
    message = '\n'.join(msg_lines)
    
    # 保存消息文本
    msg_path = Path(__file__).parent / '..' / 'data' / 'push_message.txt'
    with open(msg_path, 'w', encoding='utf-8') as f:
        f.write(message)
    
    print(f"✅ 推送消息已生成: {msg_path}")
    print("\n" + "="*60)
    print(message)
    print("="*60)
    
    # TODO: 接入实际推送服务
    # - 飞书机器人
    # - 邮件推送
    # - Telegram Bot
    # - 短信通知

def main():
    """主函数"""
    print("🚀 AI日报推送服务")
    print(f"⏰ 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    digest = generate_daily_digest()
    
    if digest:
        send_notification(digest)
        print("\n✅ 推送完成!")
    else:
        print("\n❌ 推送失败")
        sys.exit(1)

if __name__ == "__main__":
    main()