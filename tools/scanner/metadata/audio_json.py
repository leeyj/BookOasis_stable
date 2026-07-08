# -*- coding: utf-8 -*-
import json
import os

TARGET_FILENAME = 'audio.json'


def _normalize_release_date(value):
    if not value:
        return ''
    text = str(value).strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
    return text


def _normalize_score(value):
    if value is None or value == '':
        return 0
    try:
        score = float(value)
        if score < 0:
            return 0
        return int(round(score))
    except Exception:
        return 0


def parse(target_path, files=None, is_remote=False):
    return parse_audio_json(target_path, files=files, is_remote=is_remote)


def parse_audio_json(folder_path, files=None, is_remote=False):
    json_path = os.path.join(folder_path, TARGET_FILENAME)
    meta = {
        'title': '',
        'author': '',
        'publisher': '',
        'summary': '',
        'release_date': '',
        'score': 0,
        'cover_image_url': '',
        'is_webtoon': False,
    }

    has_json = False
    if files is not None:
        has_json = any(f.lower() == TARGET_FILENAME for f in files)
    else:
        has_json = os.path.exists(json_path)

    if not has_json:
        return meta

    try:
        with open(json_path, 'r', encoding='utf-8', errors='ignore') as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return meta

        meta['title'] = (data.get('title') or '').strip()
        meta['author'] = (data.get('author') or '').strip()
        meta['publisher'] = (data.get('publisher') or '').strip()
        meta['summary'] = (data.get('desc') or '').strip()
        meta['release_date'] = _normalize_release_date(data.get('premiered'))
        meta['score'] = _normalize_score(data.get('ratings'))
        meta['cover_image_url'] = (data.get('poster') or '').strip()
    except Exception as e:
        print(f"[Scanner] audio.json parsing error ({folder_path}): {e}")

    return meta
