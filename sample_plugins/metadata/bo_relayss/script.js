(function () {
    console.log("[bo.relaySS Category View] Script loaded");

    const btnRefresh = document.getElementById("btnRelayRefresh");
    const btnRegister = document.getElementById("btnRegisterLink");
    const inputTitle = document.getElementById("inputLinkTitle");
    const inputUrl = document.getElementById("inputGoogleUrl");
    const myLinksContainer = document.getElementById("myLinksContainer");
    const allLinksContainer = document.getElementById("allLinksContainer");
    const myLinksCount = document.getElementById("myLinksCount");
    const allLinksCount = document.getElementById("allLinksCount");

    function getConfig() {
        const raw = localStorage.getItem("bo_relayss_config");
        if (!raw) return null;
        try {
            return JSON.parse(raw);
        } catch (e) {
            return null;
        }
    }

    function checkConfigValid(config) {
        if (!config || !config.user_id || !config.domain_url || !config.secret_token) {
            return false;
        }
        return true;
    }

    function renderConfigAlert() {
        const html = `
            <div class="bo-alert">
                <i class="bi bi-exclamation-triangle-fill me-2"></i>
                <strong>플러그인 설정이 필요합니다</strong><br>
                [설정] ⚙️ -> [플러그인] -> <strong>bo.relaySS</strong>에서 사용자 식별코드, 도메인 주소 및 32자리 인증 토큰을 생성하십시오.
            </div>
        `;
        myLinksContainer.innerHTML = html;
        allLinksContainer.innerHTML = html;
    }

    async function loadRelayData() {
        const config = getConfig();
        if (!checkConfigValid(config)) {
            renderConfigAlert();
            return;
        }

        try {
            const url = `${config.domain_url}/api/links?user_id=${encodeURIComponent(config.user_id)}&secret_token=${encodeURIComponent(config.secret_token)}`;
            const res = await fetch(url);
            const data = await res.json();

            if (res.ok && data.success) {
                renderMyLinks(data.my_links || []);
                renderAllLinks(data.all_links || []);
            } else {
                alert(`데이터 조회 실패: ${data.message || '오류 발생'}`);
            }
        } catch (err) {
            console.error("[bo.relaySS] Data load error:", err);
            myLinksContainer.innerHTML = `<div class="bo-alert">bo.relaySS 서버 연결 오류: ${err.message}</div>`;
            allLinksContainer.innerHTML = `<div class="bo-alert">bo.relaySS 서버 연결 오류: ${err.message}</div>`;
        }
    }

    function renderMyLinks(links) {
        myLinksCount.textContent = `${links.length}개`;
        if (links.length === 0) {
            myLinksContainer.innerHTML = `<div class="bo-empty-state"><i class="bi bi-inbox"></i><p>등록한 구글 링크가 없습니다.</p></div>`;
            return;
        }

        let html = `<ul class="bo-list">`;
        links.forEach(link => {
            html += `
                <li class="bo-list-item">
                    <div class="bo-item-content">
                        <span class="bo-item-title">${escapeHtml(link.title)}</span>
                        <span style="color: #64748b;">:</span>
                        <a href="${escapeHtml(link.google_url)}" target="_blank" class="bo-item-link">
                            ${escapeHtml(link.google_url)} <i class="bi bi-box-arrow-up-right small"></i>
                        </a>
                    </div>
                    <button type="button" class="bo-btn-delete btn-delete-link" data-id="${link.id}" title="삭제">
                        <i class="bi bi-trash-fill"></i> 삭제
                    </button>
                </li>
            `;
        });
        html += `</ul>`;
        myLinksContainer.innerHTML = html;

        // 삭제 이벤트 연결
        myLinksContainer.querySelectorAll(".btn-delete-link").forEach(btn => {
            btn.addEventListener("click", function () {
                const id = this.getAttribute("data-id");
                if (confirm("이 구글 링크를 삭제하시겠습니까?")) {
                    deleteLink(id);
                }
            });
        });
    }

    function renderAllLinks(links) {
        allLinksCount.textContent = `${links.length}개`;
        if (links.length === 0) {
            allLinksContainer.innerHTML = `<div class="bo-empty-state"><i class="bi bi-inbox"></i><p>bo.relaySS에 등록된 링크가 없습니다.</p></div>`;
            return;
        }

        let html = `<ul class="bo-list">`;
        links.forEach(link => {
            html += `
                <li class="bo-list-item">
                    <div class="bo-item-content">
                        <span class="bo-badge bo-badge-info" style="margin-right: 4px;">${escapeHtml(link.user_id)}</span>
                        <span class="bo-item-title" style="color: #fbbf24;">${escapeHtml(link.title)}</span>
                        <span style="color: #64748b;">:</span>
                        <a href="${escapeHtml(link.google_url)}" target="_blank" class="bo-item-link">
                            ${escapeHtml(link.google_url)} <i class="bi bi-box-arrow-up-right small"></i>
                        </a>
                    </div>
                    <span style="color: #64748b; font-size: 12px;">${link.created_at || ''}</span>
                </li>
            `;
        });
        html += `</ul>`;
        allLinksContainer.innerHTML = html;
    }

    async function registerLink() {
        const config = getConfig();
        if (!checkConfigValid(config)) {
            alert("먼저 플러그인 환경설정을 완료해주세요.");
            return;
        }

        const title = inputTitle.value.trim();
        const googleUrl = inputUrl.value.trim();

        if (!title) {
            alert("명칭을 입력하세요.");
            inputTitle.focus();
            return;
        }
        if (!googleUrl) {
            alert("구글 링크를 입력하세요.");
            inputUrl.focus();
            return;
        }

        try {
            const res = await fetch(`${config.domain_url}/api/links`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: config.user_id,
                    secret_token: config.secret_token,
                    title: title,
                    google_url: googleUrl
                })
            });

            const data = await res.json();
            if (res.ok && data.success) {
                inputTitle.value = "";
                inputUrl.value = "";
                loadRelayData();
            } else {
                alert(`등록 실패: ${data.message || '서버 오류'}`);
            }
        } catch (err) {
            console.error("[bo.relaySS] Register link error:", err);
            alert(`등록 오류: ${err.message}`);
        }
    }

    async function deleteLink(linkId) {
        const config = getConfig();
        if (!checkConfigValid(config)) return;

        try {
            const res = await fetch(`${config.domain_url}/api/links/${linkId}`, {
                method: "DELETE",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: config.user_id,
                    secret_token: config.secret_token
                })
            });

            const data = await res.json();
            if (res.ok && data.success) {
                loadRelayData();
            } else {
                alert(`삭제 실패: ${data.message || '서버 오류'}`);
            }
        } catch (err) {
            console.error("[bo.relaySS] Delete link error:", err);
            alert(`삭제 오류: ${err.message}`);
        }
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    if (btnRefresh) btnRefresh.addEventListener("click", loadRelayData);
    if (btnRegister) btnRegister.addEventListener("click", registerLink);

    if (inputUrl) {
        inputUrl.addEventListener("keyup", function (e) {
            if (e.key === "Enter") registerLink();
        });
    }

    loadRelayData();
})();
