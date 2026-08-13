// 보스키(Boss Key) 이스터에그: Alt+Q 또는 qq(빠르게 두 번) 입력 시 위장 화면 표시
(function () {
    var IMAGE_URL = '/static/images/fake_screen.png';
    var DOUBLE_Q_WINDOW_MS = 400;

    var overlay = null;
    var lastQTime = 0;

    function isTypingTarget(target) {
        if (!target) return false;
        var tag = target.tagName;
        return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target.isContentEditable;
    }

    function showOverlay() {
        if (overlay) return;

        overlay = document.createElement('div');
        overlay.id = 'boss-key-overlay';
        overlay.style.cssText = [
            'position: fixed', 'inset: 0', 'z-index: 2147483647',
            'background: #202124 center / cover no-repeat',
            'background-image: url(' + IMAGE_URL + ')',
            'cursor: pointer'
        ].join(';');

        var closeOverlay = function () {
            if (!overlay) return;
            overlay.remove();
            overlay = null;
            document.removeEventListener('keydown', onOverlayKeydown, true);
        };

        function onOverlayKeydown() {
            closeOverlay();
        }

        overlay.addEventListener('click', closeOverlay);
        document.addEventListener('keydown', onOverlayKeydown, true);

        document.body.appendChild(overlay);
    }

    document.addEventListener('keydown', function (e) {
        if (overlay) return;

        if (e.altKey && (e.key === 'q' || e.key === 'Q')) {
            e.preventDefault();
            showOverlay();
            return;
        }

        if (isTypingTarget(e.target)) return;

        if (e.key === 'q' || e.key === 'Q') {
            var now = Date.now();
            if (now - lastQTime <= DOUBLE_Q_WINDOW_MS) {
                lastQTime = 0;
                showOverlay();
            } else {
                lastQTime = now;
            }
        }
    }, true);
})();
