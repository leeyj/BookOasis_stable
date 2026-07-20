# -*- coding: utf-8 -*-
import os
import redis
import logging
import time
import uuid

logger = logging.getLogger("bookoasis")

REDIS_URL = os.getenv("REDIS_URL")
_client = None

# 키 접두사 (Key Prefix) 네임스페이스 격리
KEY_PREFIX = "bookoasis:"

def get_redis_client():
    """
    Redis 클라이언트를 안전하게 초기화 및 반환합니다.
    REDIS_URL이 설정되어 있지 않거나 연결 실패 시 None을 반환하여
    기존 SQLite 직접 쓰기 모드로 Fallback 처리할 수 있게 지원합니다.
    """
    global _client
    if _client is not None:
        return _client

    if not REDIS_URL:
        logger.info("[Redis] REDIS_URL is not set. Running in SQLite-direct mode.")
        return None

    try:
        # 단일 레디스 클라이언트 생성 (socket_timeout 및 connection_pool 튜닝)
        pool = redis.ConnectionPool.from_url(
            REDIS_URL, 
            socket_timeout=15.0, 
            socket_connect_timeout=2.0,
            max_connections=20,
            decode_responses=True  # 문자열 자동 디코딩
        )
        client = redis.Redis(connection_pool=pool)
        
        # 실제 연결 테스트 (ping)
        if client.ping():
            logger.info(f"[Redis] Successfully connected to Redis ({REDIS_URL})")
            _client = client
            return _client
    except Exception as e:
        logger.warning(f"[Redis] Connection to {REDIS_URL} failed: {e}. Falling back to SQLite-direct.")
        _client = None

    return _client

def make_key(key: str) -> str:
    """모든 Redis 키에 bookoasis: 접두사를 강제 부착하여 다른 시스템과의 충돌을 원천 차단합니다."""
    return f"{KEY_PREFIX}{key}"

def redis_get(key: str) -> str:
    """Redis에서 안전하게 키 값을 읽어옵니다. 실패 시 None을 반환합니다."""
    client = get_redis_client()
    if not client:
        return None
    try:
        return client.get(make_key(key))
    except Exception as e:
        logger.warning(f"[Redis] redis_get failed for key '{key}': {e}")
        return None

def redis_set(key: str, value: str, ex: int = None) -> bool:
    """Redis에 안전하게 키 값을 저장합니다. 실패 시 False를 반환합니다."""
    client = get_redis_client()
    if not client:
        return False
    try:
        return bool(client.set(make_key(key), value, ex=ex))
    except Exception as e:
        logger.warning(f"[Redis] redis_set failed for key '{key}': {e}")
        return False

def redis_del(key: str) -> bool:
    """Redis에서 안전하게 키를 삭제합니다. 실패 시 False를 반환합니다."""
    client = get_redis_client()
    if not client:
        return False
    try:
        return bool(client.delete(make_key(key)))
    except Exception as e:
        logger.warning(f"[Redis] redis_del failed for key '{key}': {e}")
        return False

def redis_delete_pattern(pattern: str) -> int:
    """패턴에 매칭되는 모든 키를 삭제합니다. 실패 시 0을 반환합니다."""
    client = get_redis_client()
    if not client:
        return 0
    try:
        full_pattern = make_key(pattern)
        keys = client.keys(full_pattern)
        if keys:
            # client.delete는 리스트 형태로 받으면 한 번에 지워줍니다.
            return client.delete(*keys)
        return 0
    except Exception as e:
        logger.warning(f"[Redis] redis_delete_pattern failed for pattern '{pattern}': {e}")
        return 0

def redis_lpush(key: str, value: str) -> bool:
    """Redis List의 왼쪽에 값을 안전하게 추가합니다."""
    client = get_redis_client()
    if not client:
        return False
    try:
        return bool(client.lpush(make_key(key), value))
    except Exception as e:
        logger.warning(f"[Redis] redis_lpush failed for key '{key}': {e}")
        return False

def redis_brpop(key: str, timeout: int = 5) -> str:
    """Redis List의 오른쪽에서 값을 블로킹으로 꺼내옵니다. (Timeout 단위: 초)"""
    client = get_redis_client()
    if not client:
        return None
    try:
        res = client.brpop(make_key(key), timeout=timeout)
        if res:
            # brpop은 (key, value) 튜플을 반환하므로 값만 꺼냅니다.
            return res[1]
        return None
    except Exception as e:
        logger.warning(f"[Redis] redis_brpop failed for key '{key}': {e}")
        return None

def redis_acquire_lock(key: str, ttl: int = 60, wait_timeout: float = 0.0, sleep_interval: float = 0.1):
    """Redis 기반 분산 락을 획득합니다. 성공 시 token, 실패 시 None을 반환합니다."""
    client = get_redis_client()
    if not client:
        # Redis가 설정되어 있지 않거나 연결할 수 없는 경우,
        # SQLite 직접 쓰기 모드로 진행할 수 있도록 가상의 토큰을 반환합니다.
        return "mock_sqlite_direct_token"

    lock_key = make_key(key)
    token = uuid.uuid4().hex
    ttl = max(1, int(ttl))
    deadline = time.monotonic() + max(0.0, float(wait_timeout))

    while True:
        try:
            if client.set(lock_key, token, nx=True, ex=ttl):
                return token
        except Exception as e:
            logger.warning(f"[Redis] redis_acquire_lock failed for key '{key}': {e}")
            return None

        if wait_timeout <= 0.0 or time.monotonic() >= deadline:
            return None

        time.sleep(max(0.01, float(sleep_interval)))

def redis_release_lock(key: str, token: str) -> bool:
    """Redis 기반 분산 락을 안전하게 해제합니다."""
    client = get_redis_client()
    if not client or not token:
        return False

    lock_key = make_key(key)
    release_script = (
        "if redis.call('get', KEYS[1]) == ARGV[1] then "
        "return redis.call('del', KEYS[1]) "
        "else return 0 end"
    )
    try:
        return bool(client.eval(release_script, 1, lock_key, token))
    except Exception as e:
        logger.warning(f"[Redis] redis_release_lock failed for key '{key}': {e}")
        return False

