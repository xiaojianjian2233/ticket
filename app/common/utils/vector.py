"""向量相似度（应用层余弦，替代 pgvector）。

候选量小（dedup top8 / hub top5 / 同产品线 FAQ），Python 计算足够。
embedding 以 jsonb(list[float]) 存库，取出后在此比对。
"""
from __future__ import annotations

import math
from typing import Optional


def cosine(a: Optional[list], b: Optional[list]) -> float:
    """余弦相似度 [-1,1]；空或维度不符返回 0。"""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def top_k(query: list, candidates: list[tuple], k: int) -> list[tuple]:
    """candidates: [(obj, embedding), ...] → 按余弦降序取前 k，返回 [(obj, score), ...]。"""
    scored = [(obj, cosine(query, emb)) for obj, emb in candidates]
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored[:k]
