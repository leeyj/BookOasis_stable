// cover_storage_settings.js - 커버 이미지 저장 경로 설정 및 기존 커버 파일 이관(마이그레이션)
import * as api from '../api.js';

let coverMigratePolling = false;

export async function startCoverStorageMigration() {
  const resultEl = document.getElementById('cover-storage-migrate-result');
  try {
    const data = await api.migrateCoverStorage();
    if (!data || !data.success) throw new Error((data && data.error) || '알 수 없는 오류');
    if (resultEl) {
      resultEl.textContent = '이관 시작됨...';
      resultEl.style.color = 'var(--app-text-muted)';
    }
    if (!coverMigratePolling) {
      coverMigratePolling = true;
      pollCoverStorageMigrateStatus();
    }
  } catch (e) {
    console.error('[Settings] 커버 이관 시작 실패:', e);
    if (resultEl) {
      resultEl.textContent = `이관 시작 실패: ${e.message || e}`;
      resultEl.style.color = '#f87171';
    }
  }
}

async function pollCoverStorageMigrateStatus() {
  const resultEl = document.getElementById('cover-storage-migrate-result');
  try {
    const data = await api.fetchCoverStorageMigrateStatus();
    const status = data && data.status;
    if (!status) return;
    if (resultEl) {
      if (status.status === 'running') {
        resultEl.textContent = `이관 중... (${status.moved}/${status.total})`;
        resultEl.style.color = 'var(--app-text-muted)';
      } else if (status.status === 'done') {
        resultEl.textContent = `이관 완료: ${status.moved}개 파일 이동됨`;
        resultEl.style.color = 'var(--app-text-muted)';
      } else if (status.status === 'error') {
        resultEl.textContent = `이관 실패: ${status.error}`;
        resultEl.style.color = '#f87171';
      }
    }
    if (status.status === 'running') {
      setTimeout(() => { pollCoverStorageMigrateStatus(); }, 1500);
    } else {
      coverMigratePolling = false;
    }
  } catch (e) {
    console.error('[Settings] 커버 이관 상태 조회 실패:', e);
    coverMigratePolling = false;
  }
}
