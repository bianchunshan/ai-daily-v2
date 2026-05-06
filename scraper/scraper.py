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
TRANSLATION_CACHE_PATH = ROOT / "scraper" / "translation_cache.json"

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
        self.translation_cache = self.load_translation_cache()

    def load_stocks(self) -> list[dict[str, Any]]:
        data = json.loads(STOCK_DB_PATH.read_text(encoding="utf-8"))
        return data.get("stocks", [])

    def load_translation_cache(self) -> dict[str, str]:
        if not TRANSLATION_CACHE_PATH.exists():
            return {}
        try:
            return json.loads(TRANSLATION_CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save_translation_cache(self) -> None:
        TRANSLATION_CACHE_PATH.write_text(
            json.dumps(self.translation_cache, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8"
        )

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
        enriched = self.limit_by_category(enriched)
        self.localize_items(enriched)
        for item in enriched:
            normalize_visible_fields(item)
        enriched = [item for item in enriched if publishable_chinese_item(item)]

        stock_quotes = self.fetch_stock_quotes(enriched)
        opportunities = self.build_opportunities(enriched, stock_quotes)
        self.save_news(enriched)
        self.save_stock_quotes(stock_quotes)
        self.save_opportunities(opportunities)
        self.save_daily_digest(enriched, opportunities)
        self.save_translation_cache()
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
        if category == "world":
            category = source_hint_category(source.name) or category

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
                "name": source_display_name(source.name),
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
            score = sum(1 for kw in meta["keywords"] if keyword_matches(kw, text))
            if score:
                scores[cat] = score
        if not scores:
            return "world"
        return max(scores, key=scores.get)

    def tags_for(self, title: str, summary: str, category: str) -> list[str]:
        text = f"{title} {summary}".lower()
        tags = []
        for kw in self.categories[category]["keywords"]:
            if keyword_matches(kw, text) and len(tags) < 4:
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

    def limit_by_category(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        counts = {cat: 0 for cat in self.categories}
        limited = []
        for item in items:
            cat = item["category"]
            if counts.get(cat, 0) >= self.per_category_limit:
                continue
            counts[cat] = counts.get(cat, 0) + 1
            limited.append(item)
        return limited

    def enrich_item(self, item: dict[str, Any]) -> dict[str, Any]:
        stocks = self.extract_stocks(item)
        item["stocks"] = stocks
        score = self.opportunity_score(item, stocks)
        item["metrics"]["opportunity_score"] = score
        return item

    def localize_items(self, items: list[dict[str, Any]]) -> None:
        for index, item in enumerate(items, 1):
            original_title = item["title"]
            original_summary = item.get("summary", "")
            item["original_title"] = original_title
            item["original_summary"] = original_summary
            item["language"] = "zh-CN"
            item["title"], item["summary"] = self.translate_pair(original_title, original_summary)
            item["content"] = item["summary"] or item["title"]
            item["tags"] = unique_values(translate_tag(tag) for tag in item.get("tags", []))
            if index % 30 == 0:
                print(f"  翻译进度: {index}/{len(items)}")

    def translate_pair(self, title: str, summary: str) -> tuple[str, str]:
        if mostly_chinese(title) and mostly_chinese(summary):
            return cleanup_translation(title, 180), cleanup_translation(summary, 280)
        joined = f"{title}\n|||AI_DAILY_SUMMARY|||\n{summary}"
        translated = self.translate_to_chinese(joined)
        translated = translated.replace("AI_DAILY_SUMMARY--", "|||AI_DAILY_SUMMARY|||")
        translated = translated.replace("AI_DAILY_SUMMARY", "|||AI_DAILY_SUMMARY|||")
        if "|||AI_DAILY_SUMMARY|||" in translated:
            zh_title, zh_summary = translated.split("|||AI_DAILY_SUMMARY|||", 1)
        elif "|||" in translated:
            parts = [part for part in translated.split("|||") if part.strip()]
            zh_title = parts[0] if parts else translated
            zh_summary = parts[1] if len(parts) > 1 else self.translate_to_chinese(summary)
        elif "---" in translated:
            zh_title, zh_summary = translated.split("---", 1)
        else:
            zh_title, zh_summary = translated, self.translate_to_chinese(summary)
        return cleanup_translation(zh_title, 180), cleanup_translation(zh_summary, 280)

    def translate_to_chinese(self, text: str) -> str:
        text = clean_text(text, 900)
        if not text or mostly_chinese(text):
            return text
        cache_key = hashlib.sha1(text.encode("utf-8")).hexdigest()
        if cache_key in self.translation_cache:
            return self.translation_cache[cache_key]

        params = urllib.parse.urlencode({
            "client": "gtx",
            "sl": "auto",
            "tl": "zh-CN",
            "dt": "t",
            "q": text
        })
        url = f"https://translate.googleapis.com/translate_a/single?{params}"
        for attempt in range(3):
            try:
                response = self.session.get(url, timeout=10)
                if response.status_code != 200:
                    raise ValueError(f"HTTP {response.status_code}")
                data = response.json()
                translated = "".join(part[0] for part in data[0] if part and part[0])
                translated = clean_text(translated, 900)
                if translated and translated != text:
                    self.translation_cache[cache_key] = translated
                    return translated
            except Exception as exc:
                if attempt == 2:
                    print(f"  ! 翻译失败，保留原文: {text[:42]} ({exc})")
                time.sleep(0.8 * (attempt + 1))
        return text

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
            "biotech": ["LLY", "NVO"],
            "bci": ["TSLA", "ABT"],
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
        stock_by_symbol = {stock["symbol"]: stock for stock in self.stocks}
        quotes = {}
        for symbol in symbols[:60]:
            quote = self.fetch_yahoo_quote(symbol, stock_by_symbol.get(symbol, {}))
            if quote:
                quotes[symbol] = quote
            time.sleep(0.15)
        return quotes

    def fetch_yahoo_quote(self, symbol: str, stock: dict[str, Any] | None = None) -> dict[str, Any] | None:
        yahoo_symbol = (stock or {}).get("quote_symbol") or symbol.replace(".SH", ".SS")
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
                "quote_symbol": yahoo_symbol,
                "price": round(float(price), 2),
                "currency": meta.get("currency", "USD"),
                "change": None if change is None else round(float(change), 2),
                "change_percent": None if change_percent is None else round(float(change_percent), 2),
                "market_time": datetime.fromtimestamp(meta.get("regularMarketTime", time.time()), CN_TZ).isoformat(),
                "source": "雅虎财经"
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
            "source": "雅虎财经行情接口",
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


def cleanup_translation(value: str, limit: int) -> str:
    value = clean_text(value, limit)
    value = value.replace("| | |", "").replace("|||", "")
    value = value.replace("AI_DAILY_SUMMARY", "")
    value = value.strip(" -—|")
    value = localize_known_names(value)
    value = value.replace("美国航天局 的", "美国航天局的")
    value = re.sub(r"(美国\s*)+FDA", "美国 FDA", value)
    value = re.sub(r"(美国\s*)+航天局", "美国航天局", value)
    value = value.replace("谷歌 正在", "谷歌正在")
    value = value.replace("超威半导体 的", "超威半导体的")
    value = value.replace("强生 的", "强生的")
    value = re.sub(r"([\u4e00-\u9fff])\s+([\u4e00-\u9fff])", r"\1\2", value)
    value = re.sub(r"([\u4e00-\u9fff]{2,})\s*\(\1\)", r"\1", value)
    return clean_text(value, limit)


def normalize_visible_fields(item: dict[str, Any]) -> None:
    item["title"] = cleanup_translation(item.get("title", ""), 180)
    item["summary"] = cleanup_translation(item.get("summary", ""), 280)
    item["content"] = cleanup_translation(item.get("content", item.get("summary", "")), 280)
    item["tags"] = unique_values(translate_tag(tag) for tag in item.get("tags", []))


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


def keyword_matches(keyword: str, text: str) -> bool:
    keyword_lower = keyword.lower()
    if has_cjk(keyword_lower):
        return keyword_lower in text
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(keyword_lower)}(?![a-z0-9])", text))


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


def mostly_chinese(value: str) -> bool:
    letters = re.findall(r"[A-Za-z\u4e00-\u9fff]", value)
    if not letters:
        return True
    cjk = re.findall(r"[\u4e00-\u9fff]", value)
    return len(cjk) / len(letters) >= 0.45


def publishable_chinese_item(item: dict[str, Any]) -> bool:
    visible = " ".join([
        item.get("title", ""),
        item.get("summary", ""),
        " ".join(item.get("tags", []))
    ])
    return len(untranslated_terms(visible)) <= 3


def untranslated_terms(value: str) -> list[str]:
    allowed = {
        "FDA", "AI", "IND", "TSLP", "PI3K", "mTOR", "PK", "PID", "ABIA", "LLM",
        "GPU", "CPU", "CPO", "TSMC", "OpenAI", "ChatGPT", "Claude", "Gemini",
        "SpaceX", "NASA", "USD", "IPO", "CEO", "R2X", "V6", "Wi-Fi", "GLP-1",
        "CAR-T", "J&J", "iOS", "AR", "VR", "EV", "HBM", "ITER",
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "INTC", "TSM", "MRNA", "VRTX",
        "NVO", "LLY", "JNJ", "AMD", "ASML", "BYD", "QCOM", "IBM", "IONQ",
        "PFE", "TSLA", "CRM", "META", "AVGO", "MU", "AMAT", "LRCX"
    }
    words = re.findall(r"\b[A-Za-z][A-Za-z0-9&+.-]{2,}\b", value)
    return [word for word in words if word not in allowed]


def translate_tag(tag: str) -> str:
    mapping = {
        "geopolitics": "地缘政治",
        "military": "军事",
        "conflict": "冲突",
        "war": "战争",
        "tariff": "关税",
        "sanction": "制裁",
        "trade": "贸易",
        "election": "选举",
        "artificial intelligence": "人工智能",
        "AI": "人工智能",
        "OpenAI": "OpenAI",
        "ChatGPT": "ChatGPT",
        "Claude": "Claude",
        "Gemini": "Gemini",
        "LLM": "大语言模型",
        "machine learning": "机器学习",
        "semiconductor": "半导体",
        "chip": "芯片",
        "TSMC": "台积电",
        "Intel": "英特尔",
        "AMD": "超威半导体",
        "ASML": "阿斯麦",
        "memory": "存储芯片",
        "HBM": "高带宽内存",
        "renewable": "可再生能源",
        "solar": "太阳能",
        "battery": "电池",
        "EV": "电动车",
        "electric vehicle": "电动车",
        "BYD": "比亚迪",
        "CATL": "宁德时代",
        "storage": "储能",
        "robot": "机器人",
        "robotics": "机器人",
        "humanoid": "人形机器人",
        "automation": "自动化",
        "drone": "无人机",
        "Optimus": "特斯拉机器人",
        "quantum": "量子",
        "qubit": "量子比特",
        "biotech": "创新药",
        "pharma": "制药",
        "drug": "药物",
        "clinical": "临床试验",
        "gene therapy": "基因治疗",
        "CRISPR": "基因编辑",
        "vaccine": "疫苗",
        "space": "航天",
        "SpaceX": "SpaceX",
        "rocket": "火箭",
        "satellite": "卫星",
        "launch": "发射",
        "brain-computer interface": "脑机接口",
        "BCI": "脑机接口",
        "brain implant": "脑植入",
        "neural interface": "神经接口",
        "neurotechnology": "神经科技",
        "Neuralink": "Neuralink",
        "Synchron": "Synchron",
        "tokamak": "托卡马克",
        "ITER": "国际热核聚变实验堆",
        "plasma": "等离子体",
        "gaming": "游戏",
        "game": "游戏",
        "Nintendo": "任天堂",
        "Sony": "索尼",
        "Tencent": "腾讯",
        "NetEase": "网易",
        "Steam": "Steam",
        "esports": "电竞",
        "Apple": "苹果",
        "Microsoft": "微软",
        "Google": "谷歌",
        "NVIDIA": "英伟达",
        "Tesla": "特斯拉",
        "FDA": "美国 FDA",
        "NASA": "美国航天局",
        "CEO": "首席执行官",
        "EV": "电动车"
    }
    return mapping.get(tag, tag)


def unique_values(values) -> list[str]:
    seen = set()
    output = []
    for value in values:
        value = (value or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def source_display_name(name: str) -> str:
    mapping = {
        "CNBC Technology": "美国财经媒体·科技",
        "CNBC Markets": "美国财经媒体·市场",
        "TechCrunch": "美国创业科技媒体",
        "The Verge": "美国科技媒体",
        "Ars Technica": "美国技术媒体",
        "MIT Technology Review": "麻省理工科技评论",
        "Nature": "自然杂志",
        "ScienceDaily": "科学日报",
        "Fierce Biotech": "美国创新药媒体",
        "BioPharma Dive": "美国生物医药媒体",
        "GEN": "基因工程新闻",
        "The Quantum Insider": "量子科技资讯",
        "Quantum Computing Report": "量子计算报告",
        "NASA": "美国国家航空航天局",
        "SpaceNews": "航天新闻",
        "Electrek": "新能源交通媒体",
        "pv magazine": "光伏杂志",
        "VentureBeat": "美国科技商业媒体",
        "Google AI Blog": "谷歌 AI 博客",
        "OpenAI News": "OpenAI 官方新闻",
        "Google News BCI": "脑机接口聚合新闻",
        "GamesIndustry.biz": "游戏产业媒体",
        "IT之家": "IT之家",
        "机器之心": "机器之心",
        "财联社": "财联社"
    }
    return mapping.get(name, name)


def category_display_name(category: str) -> str:
    mapping = {
        "world": "国际局势",
        "ai": "人工智能",
        "semiconductor": "半导体",
        "energy": "新能源",
        "robotics": "机器人",
        "quantum": "量子计算",
        "biotech": "创新药",
        "bci": "脑机接口",
        "space": "商业航天",
        "gaming": "游戏"
    }
    return mapping.get(category, category)


def source_hint_category(source_name: str) -> str | None:
    name = source_name.lower()
    if any(token in name for token in ["biotech", "biopharma", "gen"]):
        return "biotech"
    if any(token in name for token in ["quantum"]):
        return "quantum"
    if any(token in name for token in ["neuralink", "neuro", "brain", "bci"]):
        return "bci"
    if any(token in name for token in ["gamesindustry", "gaming", "game"]):
        return "gaming"
    if any(token in name for token in ["nasa", "spacenews"]):
        return "space"
    if any(token in name for token in ["electrek", "pv magazine"]):
        return "energy"
    if any(token in name for token in ["technology", "techcrunch", "verge", "ars technica", "venturebeat", "google ai", "openai"]):
        return "ai"
    return None


def localize_known_names(value: str) -> str:
    replacements = {
        "Vertex Pharmaceuticals": "福泰制药",
        "Vertex": "福泰制药",
        "Moderna": "莫德纳",
        "Novo Nordisk": "诺和诺德",
        "Novo": "诺和诺德",
        "Johnson & Johnson": "强生",
        "J&J": "强生",
        "Pfizer": "辉瑞",
        "Amgen": "安进",
        "AbbVie": "艾伯维",
        "BioNTech": "BioNTech",
        "Rivian": "Rivian 电动车",
        "Restaurant Brands International": "餐饮品牌国际",
        "TechCrunch Disrupt": "TechCrunch 创业大会",
        "Apple": "苹果",
        "Nvidia": "英伟达",
        "NVIDIA": "英伟达",
        "Intel": "英特尔",
        "Google": "谷歌",
        "Microsoft": "微软",
        "Amazon": "亚马逊",
        "Tesla": "特斯拉",
        "Meta": "Meta 平台",
        "Samsung": "三星",
        "Qualcomm": "高通",
        "Broadcom": "博通",
        "AMD": "超威半导体",
        "TSMC": "台积电",
        "IBM": "IBM",
        "NASA": "美国航天局",
        "CEO": "首席执行官",
        "FDA": "美国 FDA"
    }
    for old, new in replacements.items():
        value = re.sub(rf"(?<![A-Za-z]){re.escape(old)}(?![A-Za-z])", new, value)
    return value


def build_logic(item: dict[str, Any]) -> str:
    cat_name = item.get("category_name") or category_display_name(item["category"])
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
