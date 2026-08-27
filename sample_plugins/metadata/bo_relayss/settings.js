(function () {
    console.log("[bo.relaySS] Initializing settings JS...");

    const userIdInput = document.getElementById("relayssUserId");
    const domainInput = document.getElementById("relayssDomainUrl");
    const tokenInput = document.getElementById("relayssSecretToken");
    const btnGenerate = document.getElementById("btnGenerateToken");
    const btnTest = document.getElementById("btnTestConnection");
    const statusBadge = document.getElementById("connectionStatusBadge");

    // 32자리 랜덤 알파뉴메릭 코드 생성 함수
    function generate32RandomCode() {
        const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
        let result = "";
        const cryptoObj = window.crypto || window.msCrypto;
        if (cryptoObj && cryptoObj.getRandomValues) {
            const values = new Uint8Array(32);
            cryptoObj.getRandomValues(values);
            for (let i = 0; i < 32; i++) {
                result += chars[values[i] % chars.length];
            }
        } else {
            for (let i = 0; i < 32; i++) {
                result += chars.charAt(Math.floor(Math.random() * chars.length));
            }
        }
        return result;
    }

    // 설정값 불러오기 (로컬 스토리지 또는 설정 API)
    function loadSavedSettings() {
        const savedConfig = localStorage.getItem("bo_relayss_config");
        if (savedConfig) {
            try {
                const config = JSON.parse(savedConfig);
                if (config.user_id) userIdInput.value = config.user_id;
                if (config.domain_url) domainInput.value = config.domain_url;
                if (config.secret_token) tokenInput.value = config.secret_token;
            } catch (e) {
                console.error("[bo.relaySS] Error loading settings:", e);
            }
        }
    }

    function saveSettings() {
        const config = {
            user_id: userIdInput.value.trim(),
            domain_url: domainInput.value.trim().replace(/\/+$/, ""),
            secret_token: tokenInput.value.trim()
        };
        localStorage.setItem("bo_relayss_config", JSON.stringify(config));
        return config;
    }

    // "생성" 버튼 누르면 32자리 코드 생성 및 설정 저장
    if (btnGenerate) {
        btnGenerate.addEventListener("click", function () {
            const userId = userIdInput.value.trim();
            const domainUrl = domainInput.value.trim();

            if (!userId) {
                alert("사용자 식별코드(아이디)를 먼저 입력해주세요.");
                userIdInput.focus();
                return;
            }
            if (!domainUrl) {
                alert("bo.relaySS 도메인 주소를 먼저 입력해주세요.");
                domainInput.focus();
                return;
            }

            const token = generate32RandomCode();
            tokenInput.value = token;
            saveSettings();
            alert("32자리 인증 토큰이 성공적으로 생성되었습니다.");
        });
    }

    // "bo.relaySS 접속" 버튼 눌러서 성공/실패 확인
    if (btnTest) {
        btnTest.addEventListener("click", async function () {
            const config = saveSettings();
            if (!config.user_id || !config.domain_url || !config.secret_token) {
                alert("식별코드, 도메인주소, 32자리 인증 토큰을 모두 생성 및 입력해주세요.");
                return;
            }

            statusBadge.className = "bo-status-badge status-loading";
            statusBadge.innerHTML = '<i class="bi bi-hourglass-split"></i> 접속 확인 중...';

            try {
                const response = await fetch(`${config.domain_url}/api/verify`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        user_id: config.user_id,
                        secret_token: config.secret_token
                    })
                });

                const data = await response.json();
                if (response.ok && data.success) {
                    statusBadge.className = "bo-status-badge status-success";
                    statusBadge.innerHTML = '<i class="bi bi-check-circle-fill"></i> 접속 성공';
                    alert(`[접속 성공] ${data.message}`);
                } else {
                    statusBadge.className = "bo-status-badge status-error";
                    statusBadge.innerHTML = '<i class="bi bi-x-circle-fill"></i> 접속 실패';
                    alert(`[접속 실패] ${data.message || '서버 응답 오류'}`);
                }
            } catch (err) {
                console.error("[bo.relaySS] Connection test error:", err);
                statusBadge.className = "bo-status-badge status-error";
                statusBadge.innerHTML = '<i class="bi bi-exclamation-triangle-fill"></i> 연결 오류';
                alert(`[접속 오류] bo.relaySS 서버에 연결할 수 없습니다.\n도메인 주소를 확인하세요: ${err.message}`);
            }
        });
    }

    // 초기화 시 기존 저장 설정 로드
    loadSavedSettings();
})();
