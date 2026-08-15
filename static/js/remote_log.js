// USB 디버깅이 안 되는 모바일 환경에서 콘솔 로그를 서버 로그 파일로 대신 전송하기 위한 헬퍼.
export function remoteLog(tag, data) {
  try {
    const message = typeof data === 'string' ? data : JSON.stringify(data);
    console.log(`[remoteLog:${tag}]`, data);
    const body = JSON.stringify({ tag, message });
    if (navigator.sendBeacon) {
      const blob = new Blob([body], { type: 'application/json' });
      navigator.sendBeacon('/api/client-log', blob);
    } else {
      fetch('/api/client-log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
        keepalive: true
      }).catch(() => {});
    }
  } catch (e) {
    // 로깅 실패는 뷰어 동작에 영향을 주지 않아야 한다.
  }
}
