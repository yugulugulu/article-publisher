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
    """Generate article scores. Uses LLM when prompt_score is configured, otherwise deterministic."""

    def __init__(self, database: ArticleDatabase):
        self.database = database

    def score_article(self, article: dict) -> dict:
        """Score a single article. Tries LLM when prompt_score is configured."""
        llm_result = self._score_with_llm(article)
        if llm_result is not None:
            return llm_result
        return self._score_deterministic(article)

    def _score_with_llm(self, article: dict) -> dict | None:
        """Score using LLM with custom prompt_score rules. Returns None if not configured."""
        custom_prompt = (self.database.get_setting("prompt_score") or "").strip()
        if not custom_prompt:
            return None

        title = (article.get("title") or "").strip()
        content_length = self._content_length(article)
        source_key = article.get("source_key", "")
        article_id = article.get("article_id", "")

        # Build content preview (truncate to avoid token overflow)
        content_text = "\n".join(
            b.get("text", "").strip()
            for b in article.get("blocks", [])
            if b.get("type") != "img" and b.get("text")
        )
        if len(content_text) > 3000:
            content_text = content_text[:3000] + "...(内容过长已截断)"

        system_prompt = (
            f"{custom_prompt}\n\n"
            "【输出格式要求】\n"
            "你必须返回纯 JSON（不要包含 markdown 代码块标记），格式如下：\n"
            '{"score": <0-100的整数>, "reason": "<评分理由，包含加减分明细>", '
            '"tags": ["<标签1>", "<标签2>"], "article_category": "<ai/blockchain/mixed/other>", '
            '"keywords": ["<关键实体1>", "<关键实体2>"]}\n\n'
            "article_category 规则：根据标题和内容判断属于 ai / blockchain / mixed / other 哪一类。\n"
            "keywords 规则：从标题中提取 3-5 个最核心的关键实体或短语，用于文章去重。"
            "例如标题「贝莱德比特币现货ETF获SEC批准」应提取 [\"贝莱德\",\"比特币\",\"现货ETF\",\"SEC\",\"批准\"]。"
            "只提取有区分度的实体名称和关键动作，不要提取虚词或通用词。"
        )

        user_message = (
            f"文章标题：{title}\n"
            f"来源：{source_key}\n"
            f"正文长度：{content_length}字\n"
            f"正文内容：\n{content_text}"
        )

        import time as _time
        max_retries = 3
        retry_delays = [10, 20, 30]
        last_error = None

        for attempt in range(1 + max_retries):
            try:
                from services.llm_service import LLMService
                svc = LLMService(self.database)
                response = svc.chat("score", system_prompt, user_message,
                                    max_tokens=1024, temperature=0.1)
                if not response:
                    raise ValueError("LLM returned empty response")

                match = re.search(r'\{[\s\S]*\}', response)
                if not match:
                    raise ValueError("LLM response is not valid JSON")

                data = json.loads(match.group(0))
                score = int(data.get("score", 60))
                score = max(0, min(100, score))

                article_category = data.get("article_category", "") or self._detect_article_category(article)
                tags = data.get("tags", [])[:5]
                keywords = data.get("keywords", [])[:5]

                review_status, auto_publish_enabled = self.decide_review_status(source_key, score)

                log.info("[Scorer] LLM scoring success: aid=%s, score=%d", article_id, score)

                return {
                    "score": score,
                    "reason": data.get("reason", ""),
                    "tags": tags,
                    "keywords": keywords,
                    "review_status": review_status,
                    "auto_publish_enabled": auto_publish_enabled,
                    "raw_response": response,
                    "article_category": article_category,
                }
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    delay = retry_delays[attempt]
                    log.warning("[Scorer] LLM scoring attempt %d/%d failed for %s, retrying in %ds: %s",
                                attempt + 1, 1 + max_retries, article_id, delay, e)
                    _time.sleep(delay)

        # All retries exhausted — default 60, manual review
        log.warning("[Scorer] LLM scoring failed after %d attempts for %s: %s. Defaulting to 60.",
                    1 + max_retries, article_id, last_error)
        article_category = self._detect_article_category(article)
        keywords = self._extract_keywords(article)
        return {
            "score": 60,
            "reason": f"LLM 评分失败，默认 60 分待人工审核（错误：{last_error}）",
            "tags": [],
            "keywords": keywords,
            "review_status": "manual_review",
            "auto_publish_enabled": False,
            "raw_response": "",
            "article_category": article_category,
        }

    def _score_deterministic(self, article: dict) -> dict:
        """Deterministic keyword-based scoring (original logic)."""
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

        length_penalty = 0
        if content_length > 5000 or content_length < 200:
            length_penalty = LENGTH_PENALTY
            score -= length_penalty

        score = max(0, min(100, score))
        review_status, auto_publish_enabled = self.decide_review_status(article.get("source_key", ""), score)
        article_category = self._detect_article_category(article)

        tags = self._build_tags(matched_categories, article_category)
        reason = self._build_reason(score, matched_categories, length_penalty, content_length)
        keywords = self._extract_keywords(article, matched_categories)

        return {
            "score": score,
            "reason": reason,
            "tags": tags,
            "keywords": keywords,
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
    def _build_reason(score: int, matched_categories: list[tuple[int, int, list[str]]],
                      length_penalty: int = 0, content_length: int = 0) -> str:
        level = "爆文" if score >= EXPLOSIVE_THRESHOLD else "热文" if score >= HOT_THRESHOLD else "未达标"
        lines = [f"最终得分：{score}分", f"基础分：{BASE_SCORE}分"]

        # Addition items
        lines.append("加分项：")
        if matched_categories:
            for index, (category_no, points, matches) in enumerate(matched_categories, start=1):
                display = "、".join(matches)
                lines.append(f"{index}. 第{category_no}类 +{points}分：[{display}]")
        else:
            lines.append("1. 无匹配加分项")

        # Deduction items
        if length_penalty > 0:
            reason_text = "正文过长(>5000字)" if content_length > 5000 else "正文过短(<200字)"
            lines.append(f"扣分项：-{length_penalty}分（{reason_text}，共{content_length}字）")

        lines.append(f"等级：[{level}]")
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
    def _extract_keywords(
        article: dict,
        matched_categories: list[tuple[int, int, list[str]]] | None = None,
    ) -> list[str]:
        """Extract key entities from title for dedup (rule-based fallback)."""
        title = (article.get("title") or "").strip()
        if not title:
            return []

        keywords: list[str] = []
        seen: set[str] = set()

        # 1. Use matched scorer keywords (specific entities like 贝莱德, ETF, SEC etc.)
        if matched_categories:
            for _, _, matches in matched_categories:
                for m in matches:
                    if m.lower() not in seen:
                        keywords.append(m)
                        seen.add(m.lower())

        # 2. Extract English words and numbers
        for m in re.finditer(r'[a-zA-Z]{2,}|\d+(?:\.\d+)?', title):
            token = m.group(0)
            if token.lower() not in seen:
                keywords.append(token)
                seen.add(token.lower())

        # 3. Extract Chinese segments using scorer keyword lists as dictionary
        all_kw_lists = (CATEGORY_3_KEYWORDS, CATEGORY_4_KEYWORDS, CATEGORY_5_KEYWORDS,
                        CATEGORY_2_KEYWORDS, CATEGORY_1_KEYWORDS)
        for kw_list in all_kw_lists:
            for kw in kw_list:
                if kw in title and kw.lower() not in seen:
                    keywords.append(kw)
                    seen.add(kw.lower())

        # 4. Chinese bigrams (2-char sliding window) for remaining text
        chinese_chars = re.findall(r'[一-鿿]', title)
        for i in range(len(chinese_chars) - 1):
            bigram = chinese_chars[i] + chinese_chars[i + 1]
            if bigram not in seen and not all(c in '的了是在不有和人这我他她它们着过到说得就会被从让给用' for c in bigram):
                keywords.append(bigram)
                seen.add(bigram)

        return keywords[:8]

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
