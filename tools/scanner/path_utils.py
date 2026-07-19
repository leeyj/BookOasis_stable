# -*- coding: utf-8 -*-
import os


def canonical_path(path: str) -> str:
    """Return a stable scanner path key using normalized separators."""
    if path is None:
        return ''
    normalized = os.path.normpath(str(path).strip())
    normalized = normalized.replace('\\', '/')
    if len(normalized) > 1 and normalized.endswith('/'):
        normalized = normalized.rstrip('/')
    return normalized


def join_canonical(root: str, *parts: str) -> str:
    return canonical_path(os.path.join(root, *parts))
