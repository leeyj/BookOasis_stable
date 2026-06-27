# -*- coding: utf-8 -*-
import re

def natural_sort_key(text: str) -> list:
    """자연 정렬 키 생성 (1, 2, ..., 10, 11 순서 정렬 보장)"""
    if not text:
        return []
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', str(text))]
