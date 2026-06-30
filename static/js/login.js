async function handleLogin(e) {
    e.preventDefault();
    const usernameInput = document.getElementById('username').value.trim();
    const passwordInput = document.getElementById('password').value;
    const rememberMeInput = document.getElementById('remember-me') ? document.getElementById('remember-me').checked : false;
    const errDiv = document.getElementById('login-error');
    const errText = document.getElementById('login-error-text');

    errDiv.style.display = 'none';

    try {
        const res = await fetch('/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                username: usernameInput, 
                password: passwordInput,
                remember_me: rememberMeInput
            })
        });
        const data = await res.json();

        if (data.success) {
            if (data.is_default_password === 1) {
                const loginCard = document.getElementById('login-card');
                const changeCard = document.getElementById('change-card');

                loginCard.style.opacity = '0';
                setTimeout(() => {
                    loginCard.style.display = 'none';
                    changeCard.style.display = 'block';
                    changeCard.style.opacity = '0';
                    setTimeout(() => {
                        changeCard.style.opacity = '1';
                    }, 50);
                }, 300);
            } else {
                window.location.href = '/';
            }
        } else {
            errText.innerText = data.error || '로그인 실패';
            errDiv.style.display = 'flex';
        }
    } catch (err) {
        errText.innerText = '서버 연결 오류가 발생했습니다.';
        errDiv.style.display = 'flex';
        console.error(err);
    }
}

async function handleChangePassword(e) {
    e.preventDefault();
    const newPw = document.getElementById('new-password').value;
    const confirmPw = document.getElementById('confirm-password').value;
    const errDiv = document.getElementById('change-error');
    const errText = document.getElementById('change-error-text');

    errDiv.style.display = 'none';

    if (newPw !== confirmPw) {
        errText.innerText = '비밀번호가 일치하지 않습니다.';
        errDiv.style.display = 'flex';
        return;
    }

    if (newPw.trim() === 'admin') {
        errText.innerText = '새 비밀번호는 초기 비밀번호(admin)와 다르게 입력해 주세요.';
        errDiv.style.display = 'flex';
        return;
    }

    try {
        const res = await fetch('/change-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ new_password: newPw })
        });
        const data = await res.json();

        if (data.success) {
            window.location.href = '/';
        } else {
            errText.innerText = data.error || '비밀번호 변경 실패';
            errDiv.style.display = 'flex';
        }
    } catch (err) {
        errText.innerText = '서버 연결 오류가 발생했습니다.';
        errDiv.style.display = 'flex';
        console.error(err);
    }
}
