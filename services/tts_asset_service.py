# -*- coding: utf-8 -*-
"""
tts_asset_service.py - 브라우저 TTS(Supertonic 3, onnxruntime-web)가 쓰는 정적 자산 서빙 도우미.

합성은 전부 클라이언트(WebGPU/WASM)에서 한다. 서버는
  - ORT 런타임 파일(static/lib/onnxruntime-web)을 교차 출처 격리 헤더와 함께 내주고,
  - HF 직접 다운로드가 막힌 브라우저를 위해 모델 가중치를 한 번 받아 캐시해 둔다.
"""
import hashlib
import os
import threading

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 멀티스레드 WASM(SharedArrayBuffer)에 COOP/COEP가 필요한데, 다른 화면에 영향을 주지 않도록
# TTS 페이지와 ORT 런타임 파일 응답에만 붙인다.
ORT_DIR = os.path.join(_ROOT, 'static', 'lib', 'onnxruntime-web')
ORT_FILES = {
    'ort.all.min.mjs',
    'ort-wasm-simd-threaded.jsep.mjs',
    'ort-wasm-simd-threaded.jsep.wasm',
}

# 모델 가중치 대체 경로. 기본은 브라우저가 HF에서 직접 받지만, HF가 가중치를 다른 도메인의
# CDN(us.aws.cdn.hf.co 등)으로 리다이렉트하면서 CDN 엣지가 Origin을 그대로 되돌려 주는 경우
# 브라우저가 리다이렉트 뒤 Origin을 null로 바꾸는 규칙과 어긋나 CORS로 막힌다. 그때만
# tts_core.js의 resumableFetch가 이 경로로 넘어온다. 서버는 파일마다 한 번만 받아 캐시한다.
# 리비전은 static/js/tts/tts_core.js의 MODEL_REVISION과 같아야 한다.
MODEL_REPO = 'Supertone/supertonic-3'
MODEL_REVISION = '724fb5abbf5502583fb520898d45929e62f02c0b'
MODEL_FILES = {
    'duration_predictor.onnx',
    'text_encoder.onnx',
    'vector_estimator.onnx',
    'vocoder.onnx',
}
MODEL_DIR = os.path.join(_ROOT, 'cache', 'tts_models', MODEL_REVISION)

_locks = {}
_locks_guard = threading.Lock()


def cross_origin_isolate(response):
    response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
    response.headers['Cross-Origin-Embedder-Policy'] = 'require-corp'
    return response


def ensure_model(name):
    """name(onnx 가중치) 파일이 캐시에 없으면 HF에서 받아 저장하고 경로를 돌려준다."""
    return _ensure(f'onnx/{name}', os.path.join(MODEL_DIR, name))


# 서버 미리 만들기(services/tts_engine.py)가 추가로 쓰는 파일. 브라우저는 HF에서 직접 받는다.
ENGINE_CONFIG_FILES = ('tts.json', 'unicode_indexer.json')


def ensure_engine_file(rel_path):
    """onnx/tts.json, onnx/unicode_indexer.json, voice_styles/F1.json 같은 엔진 보조 파일.
    onnx/ 아래 파일은 가중치와 같은 자리(MODEL_DIR)에, voice_styles/는 하위 폴더에 둔다."""
    if rel_path.startswith('onnx/'):
        local = os.path.join(MODEL_DIR, rel_path[len('onnx/'):])
    else:
        local = os.path.join(MODEL_DIR, *rel_path.split('/'))
    return _ensure(rel_path, local)


def _ensure(rel_path, path):
    """rel_path 파일이 캐시에 없으면 HF에서 받아 sha256(X-Linked-ETag, LFS 파일만 있음)을 확인한 뒤 저장한다.
    같은 파일을 동시에 요청하면 한 스레드만 받고 나머지는 기다린다. 워커가 여럿이어도 임시 파일명이
    달라서 섞이지 않고, os.replace가 원자적이라 반쯤 받은 파일이 노출되지 않는다."""
    if os.path.isfile(path):
        return path
    with _locks_guard:
        lock = _locks.setdefault(rel_path, threading.Lock())
    with lock:
        if os.path.isfile(path):
            return path
        import requests
        os.makedirs(os.path.dirname(path), exist_ok=True)
        url = f'https://huggingface.co/{MODEL_REPO}/resolve/{MODEL_REVISION}/{rel_path}'
        tmp = f'{path}.{os.getpid()}.{threading.get_ident()}.part'
        try:
            with requests.get(url, stream=True, timeout=(10, 60)) as r:
                r.raise_for_status()
                first = r.history[0] if r.history else r
                expected = (first.headers.get('X-Linked-ETag') or '').strip('"').lower()
                digest = hashlib.sha256()
                with open(tmp, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        f.write(chunk)
                        digest.update(chunk)
            # X-Linked-ETag는 LFS 파일에만 있는 sha256(64자리)이다. 작은 json 파일은 git 해시라 비교하지 않는다
            if len(expected) == 64 and digest.hexdigest() != expected:
                raise ValueError(f'{rel_path}: sha256 mismatch')
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
    return path
