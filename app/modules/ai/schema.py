"""Skill 信封：统一 {status, fields, evidence, model_used}。"""
from __future__ import annotations

from typing import Any


def ok(fields: dict[str, Any], *, evidence: str = "", model_used: str = "") -> dict:
    return {"status": "ok", "fields": fields, "evidence": evidence, "model_used": model_used}


def failed(error: str, *, model_used: str = "") -> dict:
    return {"status": "failed", "fields": {}, "evidence": error, "model_used": model_used, "error": error}
