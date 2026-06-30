# -*- coding: utf-8 -*-
import os
import json
from flask import request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
I18N_DIR = os.path.join(BASE_DIR, 'static', 'i18n')

_translations = {}
_loaded = False

def _load_translations():
    global _translations, _loaded
    if _loaded:
        return
    for lang in ['ko', 'en']:
        file_path = os.path.join(I18N_DIR, f"{lang}.json")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                _translations[lang] = json.load(f)
        except Exception as e:
            print(f"[i18n] Error loading translation file {lang}.json: {e}")
            _translations[lang] = {}
    _loaded = True

def get_text(key, lang=None, **kwargs):
    """
    Retrieve translation string.
    If lang is not provided, defaults to request cookie 'bookoasis_lang'.
    Falls back to 'ko' if not found.
    """
    if not _loaded:
        _load_translations()
        
    if not lang:
        try:
            lang = request.cookies.get('bookoasis_lang', 'ko')
        except Exception:
            lang = 'ko'

    # Fallback to Korean if lang file is missing
    lang_dict = _translations.get(lang, _translations.get('ko', {}))
    
    # key structure: "category.key"
    keys = key.split('.')
    val = lang_dict
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
        else:
            val = None
            break
            
    if val is None:
        return key

    if kwargs:
        try:
            return str(val).format(**kwargs)
        except Exception:
            return str(val)
            
    return str(val)

# alias
_t = get_text
