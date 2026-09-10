// detail/script.js - detail_view 계약 참조 구현. pluginId/container/context는
// static/js/detail/index.js의 openBookDetail()이 new Function('pluginId','container','context', ...)로
// 실행한다 (자세한 계약은 docs/guide_plugins.md "도서 상세 페이지 본문 전체 대체" 참고).
function renderDetailViewDemo(pluginId, container, context) {
    var meta = context.meta || {};
    var books = context.books || [];

    function escapeHtml(str) {
        return String(str == null ? '' : str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    var coverEl = container.querySelector('.dvd-cover');
    if (coverEl) {
        coverEl.src = meta.cover_image ? ('/covers/' + meta.cover_image) : '';
        coverEl.alt = meta.series_name || '';
    }

    // 배너 전용 이미지가 스캔돼 있으면 그걸 쓰고, 없으면 표지를 배경으로 재사용해
    // (크롭이 다소 어색하더라도) 완전히 빈 히어로 영역이 되는 것보다는 낫게 처리한다.
    var bannerEl = container.querySelector('.dvd-banner-img');
    if (bannerEl) {
        var bannerSrc = meta.banner_image || meta.cover_image;
        bannerEl.src = bannerSrc ? ('/covers/' + bannerSrc) : '';
        bannerEl.alt = '';
    }

    var titleEl = container.querySelector('.dvd-title');
    if (titleEl) titleEl.textContent = meta.series_alias || meta.series_name || '';

    var authorEl = container.querySelector('.dvd-author');
    if (authorEl) authorEl.textContent = meta.author && meta.author !== '-' ? ('저자: ' + meta.author) : '';

    var metaLineEl = container.querySelector('.dvd-meta-line');
    if (metaLineEl) {
        var parts = [];
        if (meta.publisher && meta.publisher !== '-') parts.push(meta.publisher);
        if (meta.genre) parts.push(meta.genre);
        parts.push(books.length + '권');
        metaLineEl.textContent = parts.join(' · ');
    }

    var summaryEl = container.querySelector('.dvd-summary');
    if (summaryEl) summaryEl.textContent = meta.summary || '';

    var rowEl = container.querySelector('.dvd-volumes-row');
    if (rowEl) {
        rowEl.innerHTML = books.map(function (book) {
            var cover = book.cover_image ? ('/covers/' + book.cover_image) : '';
            return '<div class="dvd-volume-card" data-book-id="' + book.id + '">' +
                '<img src="' + escapeHtml(cover) + '" alt="" loading="lazy">' +
                '<span>' + escapeHtml(book.title) + '</span>' +
                '</div>';
        }).join('');

        rowEl.querySelectorAll('.dvd-volume-card').forEach(function (card) {
            card.addEventListener('click', function () {
                var bookId = parseInt(card.dataset.bookId, 10);
                var book = books.filter(function (b) { return b.id === bookId; })[0];
                if (book && typeof window.openReader === 'function') {
                    window.openReader(book.id, book.file_format, book.title, book.pages_read, book.total_pages);
                }
            });
        });
    }
}

renderDetailViewDemo(pluginId, container, context);
