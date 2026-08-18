// USB 디버깅이 안 되는 모바일 환경에서 콘솔 로그를 서버 로그 파일로 대신 전송하기 위한 헬퍼.
export function remoteLog(tag, data) {
  try {
    const message = typeof data === 'string' ? data : JSON.stringify(data);
    // 객체 그대로 찍으면 콘솔에서 접혀 나와 캡처가 번거로우니, 펼쳐볼 필요 없이
    // 한 줄 문자열로도 같이 남긴다.
    console.log(`[remoteLog:${tag}] ${message}`);
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
