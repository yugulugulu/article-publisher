# -*- coding: utf-8 -*-
"""Deterministic title scoring service for blockchain and AI articles."""

from __future__ import annotations

import json
import logging
import re
from typing import Iterable

from services.database import ArticleDatabase

log = logging.getLogger("pipeline")

BASE_SCORE = 60
LENGTH_PENALTY = 20
HOT_THRESHOLD = 75
EXPLOSIVE_THRESHOLD = 85

CATEGORY_1_KEYWORDS = (
    "爆发", "暴涨", "飙升", "大涨", "新高", "狂欢", "利好", "重磅", "超预期", "火爆",
    "疯涨", "起飞", "回暖", "强势", "突破", "疯抢", "引爆", "红利", "风口", "雄起",
    "稳了", "史诗级", "暴跌", "崩盘", "闪崩", "恐慌", "暴雷", "跑路", "血亏", "腰斩",
    "惊魂", "警报", "风险", "危机", "严查", "封杀", "禁令", "踩踏", "爆仓", "巨震",
    "黑天鹅", "悬崖", "失控", "造假", "诈骗", "对决", "互撕", "内讧", "夺权", "反水",
    "决裂", "围剿", "反击", "宣战", "炮轰", "打脸", "反转", "惊天", "罕见", "突发",
    "突袭", "震动", "炸锅", "刷屏", "热议", "质疑", "怒批", "警告", "禁止", "调查",
    "罚款", "下架", "杀", "打击", "制裁", "战争", "黑客", "盗币", "攻击", "操控",
    "割", "索赔", "怼", "怒", "离职", "做空", "避险", "加息", "降息", "加速", "重大", "爆",
)
CATEGORY_1_SPECIAL_TOKENS = ("？", "!", "！", "?", "万", "亿")

CATEGORY_2_KEYWORDS = (
    "突袭", "突发", "官宣", "落地", "获批", "通过", "逮捕", "重罚", "亮剑", "出手",
    "重拳", "斩首", "关停", "冻结", "抄底", "加仓", "扫货", "建仓", "增持", "入场",
    "布局", "砸盘", "出货", "套现", "撤离", "爆拉", "拉升", "洗盘", "逼空", "割韭菜",
    "吸筹", "上线", "主网", "公测", "升级", "分叉", "并购", "融资", "募资", "IPO",
    "备案", "起诉", "胜诉", "败诉", "和解", "结盟",
)

CATEGORY_3_KEYWORDS = (
    "贝莱德", "灰度", "microstrategy", "arkk", "币安", "okx", "coinbase", "ftx",
    "马斯克", "cz", "赵长鹏", "sbf", "v 神", "v神", "vitalik", "arthur hayes", "do kwon",
    "质押", "锁仓", "tvl", "巨鲸", "庄家", "合约", "杠杆", "挖矿", "减半", "jst",
    "黑客", "盗币", "漏洞", "后门", "sec", "监管", "牌照", "etf", "否决",
)

CATEGORY_4_KEYWORDS = (
    "openai", "gpt", "sora", "anthropic", "claude", "google", "gemini", "deepmind", "xai",
    "特斯拉", "微软", "英伟达", "nvidia", "amd", "百度", "字节", "阿里", "ai", "人工智能",
    "失控", "幻觉", "造假", "诈骗", "隐私泄露", "监控", "失业", "替代", "裁员", "垄断",
    "霸权", "算法歧视", "深度伪造",
)

CATEGORY_5_KEYWORDS = (
    "美联储", "缩表", "cpi", "非农", "通胀", "美元指数", "美债", "非农数据", "美股",
    "港股", "纳指", "标普", "道琼斯", "苹果", "谷歌", "金融危机", "流动性", "恐慌指数",
    "欧盟", "ai 法案", "审查", "反垄断", "地缘冲突", "制裁",
)

BLOCKCHAIN_KEYWORDS = {
    "btc", "bitcoin", "比特币", "eth", "ethereum", "以太坊", "加密货币", "crypto",
    "cryptocurrency", "defi", "dao", "nft", "web3", "区块链", "blockchain", "coin",
    "token", "代币", "挖矿", "mining", "交易所", "exchange", "binance", "okx",
    "coinbase", "solana", "polygon", "avalanche", "arb", "arbitrum", "op",
    "optimism", "base", "ftx", "algo",
}

AI_KEYWORDS = {
    "openai", "gpt", "sora", "anthropic", "claude", "chatgpt", "google", "gemini",
    "deepmind", "xai", "grok", "elon musk", "马斯克", "tesla", "微软", "英伟达",
    "nvidia", "amd", "百度", "字节", "字节跳动", "阿里", "阿里巴巴", "腾讯", "meta",
    "facebook", "amazon", "aws", "人工智能", "ai", "aigc", "大模型", "llm", "语言模型",
    "生成式ai", "generative ai", "机器学习", "深度学习", "神经网络", "transformer",
    "diffusion", "stable diffusion", "ai芯片", "ai算力", "ai模型", "智能助手", "聊天机器人",
    "文生图", "图生图", "ai绘画", "ai写作", "智谱", "月之暗面", "kimi", "零一万物",
    "01ai", "minimax", "百川", "科大讯飞", "出门问问",
}


class ScorerService:
    """Generate deterministic article scores and publishing lanes."""

    def __init__(self, database: ArticleDatabase):
        self.database = database

    def score_article(self, article: dict) -> dict:
        """Score a single article and compute the downstream decision."""
        title = (article.get("title") or "").strip()
        title_lower = title.lower()
        content_length = self._content_length(article)

        score = BASE_SCORE
        matched_categories: list[tuple[int, int, list[str]]] = []

        category_1_matches = self._unique_matches(title, title_lower, CATEGORY_1_KEYWORDS, CATEGORY_1_SPECIAL_TOKENS)
        if category_1_matches:
            score += 15
            matched_categories.append((1, 15, category_1_matches))

        category_2_matches = self._unique_matches(title, title_lower, CATEGORY_2_KEYWORDS)
        if category_2_matches:
            score += 10
            matched_categories.append((2, 10, category_2_matches))

        category_3_matches = self._unique_matches(title, title_lower, CATEGORY_3_KEYWORDS)
        if category_3_matches:
            score += 10
            matched_categories.append((3, 10, category_3_matches))

        category_4_matches = self._unique_matches(title, title_lower, CATEGORY_4_KEYWORDS)
        if category_4_matches:
            score += 10
            matched_categories.append((4, 10, category_4_matches))

        category_5_matches = self._unique_matches(title, title_lower, CATEGORY_5_KEYWORDS)
        if category_5_matches:
            score += 10
            matched_categories.append((5, 10, category_5_matches))

        if content_length > 5000 or content_length < 200:
            score -= LENGTH_PENALTY

        score = max(0, min(100, score))
        review_status, auto_publish_enabled = self.decide_review_status(article.get("source_key", ""), score)
        article_category = self._detect_article_category(article)

        tags = self._build_tags(matched_categories, article_category)
        reason = self._build_reason(score, matched_categories)

        return {
            "score": score,
            "reason": reason,
            "tags": tags,
            "review_status": review_status,
            "auto_publish_enabled": auto_publish_enabled,
            "raw_response": "",
            "article_category": article_category,
        }

    def decide_review_status(self, source_key: str, score: int) -> tuple[str, bool]:
        """Map score to the publishing lane."""
        auto_sources = self._get_auto_sources()
        is_auto_source = source_key in auto_sources

        if score < 60:
            return "low_priority", False
        if score <= 70:
            return "manual_review", False
        if score < 75:
            return "auto_candidate", False
        if not is_auto_source:
            return "auto_candidate", False
        return "auto_candidate", True

    def _get_auto_sources(self) -> set[str]:
        raw = (self.database.get_setting("push_auto_sources") or "techflow,blockbeats").strip()
        if raw.startswith("["):
            try:
                return {str(item).strip() for item in json.loads(raw) if str(item).strip()}
            except json.JSONDecodeError:
                pass
        return {item.strip() for item in raw.split(",") if item.strip()}

    @staticmethod
    def _content_length(article: dict) -> int:
        return sum(len((block.get("text") or "").strip()) for block in article.get("blocks", []) if block.get("type") != "img")

    @staticmethod
    def _build_reason(score: int, matched_categories: list[tuple[int, int, list[str]]]) -> str:
        level = "爆文" if score >= EXPLOSIVE_THRESHOLD else "热文" if score >= HOT_THRESHOLD else "未达标"
        lines = [f"最终得分：{score}分", "加分项明细："]
        if matched_categories:
            for index, (category_no, _, matches) in enumerate(matched_categories, start=1):
                display = "、".join(matches)
                lines.append(f"{index}. 第{category_no}类加分项：[{display}]")
        else:
            lines.append("1. 第0类加分项：[无]")
        lines.append(f"等级判定：[{level}]")
        return "\n".join(lines)

    @staticmethod
    def _build_tags(matched_categories: list[tuple[int, int, list[str]]], article_category: str) -> list[str]:
        tags: list[str] = []
        for _, _, matches in matched_categories:
            for match in matches:
                if match not in tags:
                    tags.append(match)
                if len(tags) >= 5:
                    break
            if len(tags) >= 5:
                break
        if article_category and article_category not in {"other", ""}:
            tags.append(article_category)
        return tags[:5]

    @staticmethod
    def _unique_matches(
        title: str,
        title_lower: str,
        keywords: Iterable[str],
        extra_tokens: Iterable[str] | None = None,
    ) -> list[str]:
        matches: list[str] = []
        seen: set[str] = set()

        for keyword in keywords:
            if ScorerService._contains_keyword(title, title_lower, keyword):
                key = keyword.lower()
                if key not in seen:
                    matches.append(keyword)
                    seen.add(key)

        for token in extra_tokens or ():
            if token in title and token not in seen:
                matches.append(token)
                seen.add(token)

        return matches

    @staticmethod
    def _contains_keyword(title: str, title_lower: str, keyword: str) -> bool:
        token = (keyword or "").strip()
        if not token:
            return False

        lowered = token.lower()
        if re.fullmatch(r"[a-z0-9][a-z0-9\s\.\-]*", lowered):
            escaped = re.escape(lowered)
            pattern = rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
            return re.search(pattern, title_lower) is not None
        return lowered in title_lower

    @staticmethod
    def _detect_article_category(article: dict) -> str:
        """Detect article category: ai / blockchain / mixed / other."""
        title = (article.get("title") or "").lower()
        source_key = article.get("source_key", "")

        has_ai_keyword = any(ScorerService._contains_keyword(title, title, keyword) for keyword in AI_KEYWORDS)
        has_blockchain_keyword = any(ScorerService._contains_keyword(title, title, keyword) for keyword in BLOCKCHAIN_KEYWORDS)

        ai_sources = {"kr36", "baoyu", "claude", "qbitai", "aiera", "aibase"}
        if source_key in ai_sources:
            return "ai"
        if has_ai_keyword and has_blockchain_keyword:
            return "mixed"
        if has_ai_keyword:
            return "ai"
        if has_blockchain_keyword:
            return "blockchain"
        return "other"
