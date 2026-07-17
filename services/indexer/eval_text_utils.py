"""评估文本归一化与要点匹配（支持 must_include 的 | 分隔同义表述）。"""
import re
import unicodedata


def normalize_for_match(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.lower()
    # Markdown
    text = re.sub(r"\*+", "", text)
    text = re.sub(r"#+\s*", "", text)
    # LaTeX 定界符与常见命令
    text = re.sub(r"\\[\(\[\])]", "", text)
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    text = re.sub(r"\$+", "", text)
    text = re.sub(r"[{}]", "", text)
    # 下标/上标：a_n, a_{10} -> a10
    text = re.sub(r"([a-z])_\{?(\d+)\}?", r"\1\2", text)
    text = re.sub(r"([a-z])_\{?([a-z])\}?", r"\1\2", text)
    # 数学/标点变体
    text = text.replace("×", "*").replace("·", "*")
    text = text.replace("−", "-").replace("–", "-").replace("—", "-")
    text = text.replace("²", "2").replace("³", "3")
    text = re.sub(r"√\(?([^)]+)\)?", r"sqrt\1", text)
    # 路径与引用噪音（保留正文关键词）
    text = re.sub(r"d:/[^>\n]+>", "", text)
    text = re.sub(r"引用来源[:：]?", "", text)
    # 空白
    text = re.sub(r"\s+", "", text)
    return text


def point_matches(answer: str, point: str) -> bool:
    """单条 must/forbidden：支持用 | 分隔的任一同义表述命中即可。"""
    normalized = normalize_for_match(answer)
    if not normalized:
        return False
    for alt in point.split("|"):
        token = normalize_for_match(alt.strip())
        if token and token in normalized:
            return True
    return False


def point_coverage(answer: str, must_points: list[str]) -> float:
    if not must_points:
        return 1.0
    hit = sum(1 for p in must_points if point_matches(answer, p))
    return hit / len(must_points)


def forbidden_hit_rate(answer: str, forbidden_points: list[str]) -> float:
    if not forbidden_points:
        return 0.0
    hit = sum(1 for p in forbidden_points if point_matches(answer, p))
    return hit / len(forbidden_points)
