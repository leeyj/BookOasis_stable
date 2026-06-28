// app.js – BookOasis 랜딩 웹사이트 인터랙션 스크립트 (Vanilla JS)

document.addEventListener('DOMContentLoaded', () => {
  // ── 미니 만화 뷰어 데모 동작 ──
  const pages = document.querySelectorAll('#comic-pages .comic-page');
  const btnPrev = document.getElementById('btn-prev-page');
  const btnNext = document.getElementById('btn-next-page');
  const pageIndicator = document.getElementById('hud-page-indicator');

  if (pages.length > 0 && btnPrev && btnNext && pageIndicator) {
    let currentPageIndex = 0;
    const totalPages = pages.length;

    const updateDemoViewer = () => {
      pages.forEach((page, idx) => {
        if (idx === currentPageIndex) {
          page.classList.add('active');
        } else {
          page.classList.remove('active');
        }
      });
      pageIndicator.innerText = `${currentPageIndex + 1} / ${totalPages}`;
      
      // 첫 페이지 또는 마지막 페이지에서의 버튼 활성화 상태 제어
      btnPrev.disabled = (currentPageIndex === 0);
      btnPrev.style.opacity = (currentPageIndex === 0) ? '0.4' : '1';
      btnPrev.style.cursor = (currentPageIndex === 0) ? 'not-allowed' : 'pointer';

      btnNext.disabled = (currentPageIndex === totalPages - 1);
      btnNext.style.opacity = (currentPageIndex === totalPages - 1) ? '0.4' : '1';
      btnNext.style.cursor = (currentPageIndex === totalPages - 1) ? 'not-allowed' : 'pointer';
    };

    btnPrev.addEventListener('click', () => {
      if (currentPageIndex > 0) {
        currentPageIndex--;
        updateDemoViewer();
      }
    });

    btnNext.addEventListener('click', () => {
      if (currentPageIndex < totalPages - 1) {
        currentPageIndex++;
        updateDemoViewer();
      }
    });

    // 초기 상태 반영
    updateDemoViewer();
  }

  // ── 스크롤에 따른 헤더 내비게이션 바 블러 효과 제어 ──
  const navBar = document.querySelector('.nav-bar');
  if (navBar) {
    window.addEventListener('scroll', () => {
      if (window.scrollY > 20) {
        navBar.style.boxShadow = '0 10px 30px rgba(0, 0, 0, 0.3)';
        navBar.style.background = 'rgba(11, 15, 25, 0.85)';
      } else {
        navBar.style.boxShadow = 'none';
        navBar.style.background = 'rgba(17, 24, 39, 0.7)';
      }
    });
  }
});
