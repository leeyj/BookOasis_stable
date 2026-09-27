# -*- coding: utf-8 -*-
"""
tts_engine.py - 듣기(TTS) 서버 미리 만들기용 음성 합성 엔진 (Supertonic 3, CPU onnxruntime)

브라우저 듣기 화면(static/js/tts/tts_player.js)과 같은 모델·같은 규칙으로 조각 하나를 합성해
AAC(.m4a)로 저장한다. 문장 나누기·한자 변환은 브라우저가 이미 끝낸 텍스트를 받으므로 여기서는 하지 않는다.

numpy/onnxruntime은 기능을 켠 서버에만 필요해서 지연 import한다 (없으면 availability()가 이유를 알려 준다).
"""
import hashlib
import os
import shutil
import subprocess
import threading

from services import tts_asset_service as assets

VOICES = ('F1', 'F2', 'F3', 'F4', 'F5', 'M1', 'M2', 'M3', 'M4', 'M5')
STEPS = (4, 8)
SPEEDS = (0.9, 1.05, 1.2, 1.4)
PAD_SEC = 0.25  # 브라우저와 같이 조각 끝에 붙이는 무음
AAC_BITRATE = '64k'


def _js_number(value):
    """JS의 `${number}`와 같은 표기 (1.0 → '1', 1.05 → '1.05'). 조각 키를 브라우저와 똑같이 만들기 위해."""
    number = float(value)
    return str(int(number)) if number.is_integer() else repr(number)


def piece_key(voice, steps, speed, text):
    """조각 음성 캐시 키. static/js/tts/tts_core.js의 pieceKey()와 같은 입력·같은 결과여야 한다."""
    raw = f'{assets.MODEL_REVISION}|{voice}|{int(steps)}|{_js_number(speed)}|{text}'
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def availability():
    """(사용 가능 여부, 이유). 관리자 화면에서 켤 때 보여 준다."""
    missing = []
    try:
        import numpy  # noqa: F401
    except ImportError:
        missing.append('numpy')
    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        missing.append('onnxruntime')
    if missing:
        return False, f"python package missing: {', '.join(missing)} (pip install {' '.join(missing)})"
    if not shutil.which('ffmpeg'):
        return False, 'ffmpeg not found'
    return True, ''


def is_near_silent(wav, sample_rate, pred_sec, min_ratio=0.15):
    """tts_core.js isNearSilent()와 같은 판정: 20ms 프레임 RMS 중 유성 구간이 예측 길이의 15% 미만이면 무음."""
    import numpy as np
    frame = int(sample_rate * 0.02)
    n = len(wav) // frame if frame > 0 else 0
    if not n or not pred_sec > 0:
        return False
    frames = np.asarray(wav[:n * frame], dtype=np.float64).reshape(n, frame)
    rms = np.sqrt((frames * frames).mean(axis=1))
    thr = max(0.01, 0.05 * float(rms.max()))
    voiced_sec = int((rms > thr).sum()) * 0.02
    return voiced_sec / pred_sec < min_ratio


class Engine:
    """모델 세션 4개 + 목소리 스타일 캐시. 한 번에 한 조각만 합성한다(작업 스레드 전용)."""

    def __init__(self, threads=2):
        import onnxruntime as ort
        from services import supertonic_helper as helper
        self._helper = helper
        for name in ('duration_predictor.onnx', 'text_encoder.onnx', 'vector_estimator.onnx', 'vocoder.onnx'):
            assets.ensure_model(name)
        for name in assets.ENGINE_CONFIG_FILES:
            assets.ensure_engine_file(f'onnx/{name}')
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = max(1, int(threads))
        opts.inter_op_num_threads = 1
        sessions = helper.load_onnx_all(assets.MODEL_DIR, opts, ['CPUExecutionProvider'])
        self.tts = helper.TextToSpeech(helper.load_cfgs(assets.MODEL_DIR), helper.load_text_processor(assets.MODEL_DIR), *sessions)
        self.sample_rate = self.tts.sample_rate
        self.threads = opts.intra_op_num_threads
        self._styles = {}

    def _style(self, voice):
        if voice not in self._styles:
            path = assets.ensure_engine_file(f'voice_styles/{voice}.json')
            self._styles[voice] = self._helper.load_voice_style([path])
        return self._styles[voice]

    def synthesize(self, text, voice, steps, speed):
        """float32 모노 파형(끝 무음 포함). 거의 무음이면 한 번 다시 만든다 (초기 노이즈가 랜덤이라 대부분 정상이 된다)."""
        import numpy as np
        style = self._style(voice)
        wav, duration = self.tts._infer([text], ['ko'], style, int(steps), float(speed))
        wav = wav[0]
        if is_near_silent(wav, self.sample_rate, float(duration[0])):
            wav, duration = self.tts._infer([text], ['ko'], style, int(steps), float(speed))
            wav = wav[0]
        pad = np.zeros(int(PAD_SEC * self.sample_rate), dtype=np.float32)
        return np.concatenate([wav.astype(np.float32), pad])


def encode_m4a(wav, sample_rate, out_path):
    """float32 파형을 AAC(.m4a)로 저장하고 파일 크기를 돌려준다. 임시 파일에 쓴 뒤 교체해서 반쯤 쓴 파일이 보이지 않는다."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    tmp = f'{out_path}.{os.getpid()}.{threading.get_ident()}.part.m4a'
    cmd = [
        'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
        '-f', 'f32le', '-ar', str(sample_rate), '-ac', '1', '-i', 'pipe:0',
        '-c:a', 'aac', '-b:a', AAC_BITRATE, '-movflags', '+faststart', tmp,
    ]
    try:
        proc = subprocess.run(cmd, input=wav.tobytes(), capture_output=True, timeout=120)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {proc.stderr.decode('utf-8', 'replace').strip()[:300]}")
        os.replace(tmp, out_path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return os.path.getsize(out_path)
