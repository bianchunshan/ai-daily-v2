#!/usr/bin/env python3
"""
AI日报真实数据采集器。

每次运行会：
- 从配置中的 RSS 源抓取最近资讯
- 自动分类到 11 个板块
- 关联股票库和最新 Yahoo Finance 报价
- 生成新闻、行情和投资机会 JSON，供 GitHub Pages 前端直接读取
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
NEWS_DIR = ROOT / "data" / "news"
STOCK_DB_PATH = ROOT / "data" / "stocks" / "database.json"
STOCK_LATEST_PATH = ROOT / "data" / "stocks" / "latest.json"
OPPORTUNITIES_PATH = ROOT / "data" / "opportunities.json"

CN_TZ = timezone(timedelta(hours=8))


@dataclass
class Source:
    id: str
    name: str
    url: str
    credibility: int


class RealNewsScraper:
    def __init__(self) -> None:
        self.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        self.categories = self.config["categories"]
        self.sources = [Source(**src) for src in self.config["sources"]["rss"]]
        self.retention_hours = int(self.config.get("retention_hours", 72))
        self.per_category_limit = int(self.config.get("per_category_limit", 30))
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "AI-Daily/3.0 (+https://bianchunshan.github.io/ai-daily-v2/)"
        })
        NEWS_DIR.mkdir(parents=True, exist_ok=True)
        STOCK_LATEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.stocks = self.load_stocks()

    def load_stocks(self) -> list[dict[str, Any]]:
        data = json.loads(STOCK_DB_PATH.read_text(encoding="utf-8"))
        return data.get("stocks", [])

    def run(self) -> None:
        print("== AI日报每小时采集 ==")
        print("开始时间:", now_iso())
        all_items: list[dict[str, Any]] = []
        for source in self.sources:
            items = self.fetch_rss(source)
            print(f"{source.name}: {len(items)} 条")
            all_items.extend(items)
            time.sleep(0.4)

        merged = self.merge_related(all_items)
        recent = self.filter_recent(merged)
        enriched = [self.enrich_item(item) for item in recent]
        enriched.sort(key=lambda item: item["publish_time"], reverse=True)

        stock_quotes = self.fetch_stock_quotes(enriched)
        opportunities = self.build_opportunities(enriched, stock_quotes)
        self.save_news(enriched)
        self.save_stock_quotes(stock_quotes)
        self.save_opportunities(opportunities)
        self.save_daily_digest(enriched, opportunities)
        print(f"完成: 新闻 {len(enriched)} 条，机会 {len(opportunities)} 条，股票 {len(stock_quotes)} 只")

    def fetch_rss(self, source: Source) -> list[dict[str, Any]]:
        try:
            response = self.session.get(source.url, timeout=20)
            response.raise_for_status()
        except Exception as exc:
            print(f"  ! {source.name} 请求失败: {exc}")
            return []

        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as exc:
            print(f"  ! {source.name} RSS解析失败: {exc}")
            return []

        entries = root.findall(".//item")
        if not entries:
            entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")

        output = []
        for entry in entries[:40]:
            item = self.parse_entry(entry, source)
            if item and item["title"] and item["url"]:
                output.append(item)
        return output

    def parse_entry(self, entry: ET.Element, source: Source) -> dict[str, Any] | None:
        title = text_of(entry, "title")
        link = text_of(entry, "link")
        if not link:
            atom_link = entry.find("{http://www.w3.org/2005/Atom}link")
            link = atom_link.attrib.get("href", "") if atom_link is not None else ""
        summary = (
            text_of(entry, "description")
            or text_of(entry, "summary")
            or text_of(entry, "{http://www.w3.org/2005/Atom}summary")
            or text_of(entry, "content")
        )
        published_raw = (
            text_of(entry, "pubDate")
            or text_of(entry, "published")
            or text_of(entry, "updated")
            or text_of(entry, "{http://www.w3.org/2005/Atom}updated")
        )
        published = parse_time(published_raw)
        clean_title = clean_text(title, 180)
        clean_summary = clean_text(summary, 240)
        category = self.classify(clean_title, clean_summary)

        return {
            "id": stable_id(link or clean_title),
            "url": link,
            "title": clean_title,
            "summary": clean_summary or clean_title,
            "content": clean_summary or clean_title,
            "category": category,
            "tags": self.tags_for(clean_title, clean_summary, category),
            "publish_time": published,
            "sources": [{
                "name": source.name,
                "url": link,
                "verified": True,
                "verify_time": now_iso(),
                "credibility": source.credibility
            }],
            "stocks": [],
            "metrics": {
                "views": 0,
                "shares": 0,
                "saves": 0,
                "credibility_score": source.credibility,
                "opportunity_score": 0
            },
            "status": "published"
        }

    def classify(self, title: str, summary: str) -> str:
        text = f"{title} {summary}".lower()
        scores: dict[str, int] = {}
        for cat, meta in self.categories.items():
            score = sum(1 for kw in meta["keywords"] if kw.lower() in text)
            if score:
                scores[cat] = score
        if not scores:
            return "world"
        return max(scores, key=scores.get)

    def tags_for(self, title: str, summary: str, category: str) -> list[str]:
        text = f"{title} {summary}".lower()
        tags = []
        for kw in self.categories[category]["keywords"]:
            if kw.lower() in text and len(tags) < 4:
                tags.append(kw)
        return tags or [self.categories[category]["name"]]

    def merge_related(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        for item in items:
            match = next((old for old in merged if similarity_key(old["title"]) == similarity_key(item["title"])), None)
            if match:
                existing_urls = {src["url"] for src in match["sources"]}
                for src in item["sources"]:
                    if src["url"] not in existing_urls:
                        match["sources"].append(src)
                match["metrics"]["credibility_score"] = min(
                    99,
                    int(sum(src["credibility"] for src in match["sources"]) / len(match["sources"])) + 3 * (len(match["sources"]) - 1)
                )
            else:
                merged.append(item)
        return merged

    def filter_recent(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cutoff = datetime.now(CN_TZ) - timedelta(hours=self.retention_hours)
        return [item for item in items if parse_iso(item["publish_time"]) >= cutoff]

    def enrich_item(self, item: dict[str, Any]) -> dict[str, Any]:
        stocks = self.extract_stocks(item)
        item["stocks"] = stocks
        score = self.opportunity_score(item, stocks)
        item["metrics"]["opportunity_score"] = score
        return item

    def extract_stocks(self, item: dict[str, Any]) -> list[dict[str, Any]]:
        raw_text = f"{item['title']} {item.get('summary', '')}"
        text = raw_text.lower()
        found = []
        seen = set()
        for stock in self.stocks:
            explicit = stock_mentioned(raw_text, text, stock)
            if explicit:
                symbol = stock["symbol"]
                if symbol in seen:
                    continue
                seen.add(symbol)
                found.append({
                    "symbol": symbol,
                    "name": stock.get("name", symbol),
                    "exchange": stock.get("exchange", ""),
                    "impact": judge_impact(text),
                    "reason": "标题/摘要直接提及",
                    "confidence": "direct"
                })
            if len(found) >= 5:
                break
        if found:
            return found

        fallback_symbols = {
            "ai": ["NVDA", "MSFT"],
            "semiconductor": ["NVDA", "TSM"],
            "energy": ["TSLA", "BYD"],
            "consumer": ["AAPL", "QCOM"],
            "biotech": ["LLY", "NVO"],
            "quantum": ["IBM", "IONQ"]
        }.get(item["category"], [])
        stock_by_symbol = {stock["symbol"]: stock for stock in self.stocks}
        for symbol in fallback_symbols:
            stock = stock_by_symbol.get(symbol)
            if not stock:
                continue
            found.append({
                "symbol": symbol,
                "name": stock.get("name", symbol),
                "exchange": stock.get("exchange", ""),
                "impact": "neutral",
                "reason": f"板块弱关联：{self.categories[item['category']]['name']}",
                "confidence": "sector"
            })
        return found

    def opportunity_score(self, item: dict[str, Any], stocks: list[dict[str, Any]]) -> int:
        text = f"{item['title']} {item.get('summary', '')}".lower()
        catalyst_words = ["surge", "record", "breakthrough", "launch", "deal", "approval", "investment", "增长", "突破", "发布", "获批", "订单", "投资", "合作"]
        risk_words = ["probe", "ban", "delay", "lawsuit", "recall", "cut", "下跌", "调查", "禁令", "推迟", "召回", "裁员"]
        score = 35
        score += min(25, item["metrics"]["credibility_score"] - 70)
        direct_count = sum(1 for stock in stocks if stock.get("confidence") == "direct")
        score += min(20, direct_count * 8)
        if stocks and direct_count == 0:
            score -= 18
        score += min(15, sum(1 for word in catalyst_words if word in text) * 4)
        score -= min(18, sum(1 for word in risk_words if word in text) * 5)
        if len(item["sources"]) >= 2:
            score += 8
        return max(0, min(100, score))

    def fetch_stock_quotes(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        symbols = sorted({stock["symbol"] for item in items for stock in item.get("stocks", [])})
        quotes = {}
        for symbol in symbols[:60]:
            quote = self.fetch_yahoo_quote(symbol)
            if quote:
                quotes[symbol] = quote
            time.sleep(0.15)
        return quotes

    def fetch_yahoo_quote(self, symbol: str) -> dict[str, Any] | None:
        yahoo_symbol = symbol.replace(".SH", ".SS")
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(yahoo_symbol)}?range=5d&interval=1d"
        try:
            data = self.session.get(url, timeout=12).json()
            result = data["chart"]["result"][0]
            meta = result["meta"]
            price = meta.get("regularMarketPrice")
            previous = meta.get("chartPreviousClose") or meta.get("previousClose")
            if price is None:
                return None
            change = None if previous in (None, 0) else price - previous
            change_percent = None if change is None else change / previous * 100
            return {
                "symbol": symbol,
                "price": round(float(price), 2),
                "currency": meta.get("currency", "USD"),
                "change": None if change is None else round(float(change), 2),
                "change_percent": None if change_percent is None else round(float(change_percent), 2),
                "market_time": datetime.fromtimestamp(meta.get("regularMarketTime", time.time()), CN_TZ).isoformat(),
                "source": "Yahoo Finance"
            }
        except Exception:
            return None

    def build_opportunities(self, items: list[dict[str, Any]], quotes: dict[str, Any]) -> list[dict[str, Any]]:
        candidates = [
            item for item in items
            if item.get("stocks")
            and any(stock.get("confidence") == "direct" for stock in item.get("stocks", []))
            and item["metrics"].get("opportunity_score", 0) >= 50
        ]
        candidates.sort(key=lambda item: (item["metrics"]["opportunity_score"], item["publish_time"]), reverse=True)
        output = []
        for item in candidates[:20]:
            symbols = [stock["symbol"] for stock in item["stocks"]]
            output.append({
                "id": item["id"],
                "title": item["title"],
                "category": item["category"],
                "category_name": self.categories[item["category"]]["name"],
                "score": item["metrics"]["opportunity_score"],
                "publish_time": item["publish_time"],
                "stocks": item["stocks"],
                "quotes": {symbol: quotes[symbol] for symbol in symbols if symbol in quotes},
                "logic": build_logic(item),
                "risk": build_risk(item),
                "source_url": item["sources"][0]["url"]
            })
        return output

    def save_news(self, items: list[dict[str, Any]]) -> None:
        by_cat: dict[str, list[dict[str, Any]]] = {cat: [] for cat in self.categories}
        for item in items:
            by_cat.setdefault(item["category"], []).append(item)

        for cat, cat_items in by_cat.items():
            cat_items = cat_items[: self.per_category_limit]
            (NEWS_DIR / f"{cat}.json").write_text(json.dumps({
                "version": "3.0",
                "category": cat,
                "category_name": self.categories[cat]["name"],
                "total": len(cat_items),
                "updated": now_iso(),
                "news": cat_items
            }, ensure_ascii=False, indent=2), encoding="utf-8")

        all_limited = []
        for cat in self.categories:
            all_limited.extend(by_cat.get(cat, [])[: self.per_category_limit])
        all_limited.sort(key=lambda item: item["publish_time"], reverse=True)
        (NEWS_DIR / "all.json").write_text(json.dumps({
            "version": "3.0",
            "total": len(all_limited),
            "updated": now_iso(),
            "by_category": {cat: len(by_cat.get(cat, [])[: self.per_category_limit]) for cat in self.categories},
            "news": all_limited
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    def save_stock_quotes(self, quotes: dict[str, Any]) -> None:
        STOCK_LATEST_PATH.write_text(json.dumps({
            "version": "3.0",
            "updated": now_iso(),
            "source": "Yahoo Finance chart API",
            "quotes": quotes
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    def save_opportunities(self, opportunities: list[dict[str, Any]]) -> None:
        OPPORTUNITIES_PATH.write_text(json.dumps({
            "version": "3.0",
            "updated": now_iso(),
            "total": len(opportunities),
            "opportunities": opportunities,
            "disclaimer": "仅供信息整理和研究，不构成投资建议。"
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    def save_daily_digest(self, items: list[dict[str, Any]], opportunities: list[dict[str, Any]]) -> None:
        cutoff = datetime.now(CN_TZ) - timedelta(hours=24)
        recent = [item for item in items if parse_iso(item["publish_time"]) >= cutoff]
        (ROOT / "data" / "daily_digest.json").write_text(json.dumps({
            "date": datetime.now(CN_TZ).strftime("%Y-%m-%d"),
            "type": "daily_digest",
            "summary": {
                "total_new": len(recent),
                "breaking": sum(1 for item in recent if item["metrics"]["credibility_score"] >= 92),
                "opportunities": len(opportunities),
                "by_category": category_counts(recent)
            },
            "top_news": [{
                "id": item["id"],
                "title": item["title"],
                "category": item["category"],
                "credibility": item["metrics"]["credibility_score"],
                "opportunity_score": item["metrics"]["opportunity_score"],
                "stocks": [stock["symbol"] for stock in item.get("stocks", [])]
            } for item in sorted(recent, key=lambda x: x["metrics"]["opportunity_score"], reverse=True)[:8]],
            "generated_at": now_iso()
        }, ensure_ascii=False, indent=2), encoding="utf-8")


def clean_text(value: str, limit: int) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:limit].rstrip()


def text_of(entry: ET.Element, tag: str) -> str:
    node = entry.find(tag)
    if node is None and not tag.startswith("{"):
        node = entry.find(f"{{http://www.w3.org/2005/Atom}}{tag}")
    return "".join(node.itertext()) if node is not None else ""


def parse_time(value: str) -> str:
    if value:
        try:
            dt = parsedate_to_datetime(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(CN_TZ).isoformat()
        except Exception:
            pass
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.astimezone(CN_TZ).isoformat()
        except Exception:
            pass
    return now_iso()


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(CN_TZ)


def now_iso() -> str:
    return datetime.now(CN_TZ).isoformat()


def stable_id(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:14]


def similarity_key(title: str) -> str:
    words = re.findall(r"[a-zA-Z0-9\u4e00-\u9fff]+", title.lower())
    stop = {"the", "a", "an", "to", "of", "and", "in", "on", "for", "with", "is", "as"}
    words = [word for word in words if word not in stop]
    return " ".join(sorted(words[:12]))


def judge_impact(text: str) -> str:
    positive = ["rise", "gain", "surge", "record", "beat", "deal", "approval", "launch", "增长", "上涨", "突破", "获批", "订单", "合作"]
    negative = ["fall", "drop", "decline", "probe", "ban", "delay", "recall", "下跌", "调查", "禁令", "推迟", "召回", "亏损"]
    pos = sum(1 for word in positive if word in text)
    neg = sum(1 for word in negative if word in text)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def stock_mentioned(raw_text: str, lower_text: str, stock: dict[str, Any]) -> bool:
    symbol = stock.get("symbol", "")
    if symbol and re.search(rf"(?<![A-Z0-9.]){re.escape(symbol)}(?![A-Z0-9.])", raw_text):
        return True

    names = [stock.get("name", ""), stock.get("name_en", "")]
    aliases = {
        "GOOGL": ["Alphabet", "Google"],
        "META": ["Meta", "Facebook"],
        "MSFT": ["Microsoft"],
        "NVDA": ["Nvidia", "NVIDIA"],
        "TSM": ["TSMC", "Taiwan Semiconductor"],
        "TSLA": ["Tesla"],
        "AAPL": ["Apple"],
        "AMZN": ["Amazon", "AWS"],
        "AVGO": ["Broadcom"],
        "QCOM": ["Qualcomm"],
        "AMD": ["Advanced Micro Devices"],
        "INTC": ["Intel"],
        "ASML": ["ASML"],
        "BYD": ["BYD"],
        "LLY": ["Eli Lilly", "Lilly"],
        "NVO": ["Novo Nordisk"],
        "PFE": ["Pfizer"],
        "MRNA": ["Moderna"],
        "IBM": ["IBM"],
        "IONQ": ["IonQ"],
        "PLTR": ["Palantir"],
        "SNOW": ["Snowflake"],
        "CRM": ["Salesforce"],
        "ADBE": ["Adobe"],
        "NOW": ["ServiceNow"]
    }
    names.extend(aliases.get(symbol, []))
    for name in names:
        name = (name or "").strip()
        if not name:
            continue
        if has_cjk(name) and name in raw_text:
            return True
        if len(name) >= 4 and re.search(rf"(?<![A-Za-z0-9]){re.escape(name.lower())}(?![A-Za-z0-9])", lower_text):
            return True
    return False


def has_cjk(value: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", value))


def build_logic(item: dict[str, Any]) -> str:
    cat_name = item.get("category_name") or item["category"]
    stocks = "、".join(stock["symbol"] for stock in item.get("stocks", [])[:3])
    return f"{cat_name}板块出现新催化，相关标的 {stocks} 需要跟踪新闻后续和盘口反应。"


def build_risk(item: dict[str, Any]) -> str:
    impact = {stock["impact"] for stock in item.get("stocks", [])}
    if "negative" in impact:
        return "新闻含潜在负面因素，需关注业绩、监管和估值回撤风险。"
    return "仅代表资讯催化，不代表买卖建议；需结合估值、财报和市场风险。"


def category_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item["category"]] = counts.get(item["category"], 0) + 1
    return counts


if __name__ == "__main__":
    RealNewsScraper().run()
