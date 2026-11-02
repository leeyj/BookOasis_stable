const MAX_USERNAME_LENGTH = 128;
const MAX_PASSWORD_LENGTH = 256;

async function handleLogin(e) {
    e.preventDefault();
    const usernameInput = document.getElementById('username').value.trim();
    const passwordInput = document.getElementById('password').value;
    const rememberMeInput = document.getElementById('remember-me') ? document.getElementById('remember-me').checked : false;
    const errDiv = document.getElementById('login-error');
    const errText = document.getElementById('login-error-text');

    errDiv.style.display = 'none';

    if (usernameInput.length > MAX_USERNAME_LENGTH) {
        errText.innerText = i18n.t('login.username_max', { n: MAX_USERNAME_LENGTH });
        errDiv.style.display = 'flex';
        return;
    }
    if (passwordInput.length > MAX_PASSWORD_LENGTH) {
        errText.innerText = i18n.t('login.password_max', { n: MAX_PASSWORD_LENGTH });
        errDiv.style.display = 'flex';
        return;
    }

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
            errText.innerText = data.error || i18n.t('login.failed');
            errDiv.style.display = 'flex';
        }
    } catch (err) {
        errText.innerText = i18n.t('login.server_error');
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

    if (newPw.length > MAX_PASSWORD_LENGTH || confirmPw.length > MAX_PASSWORD_LENGTH) {
        errText.innerText = i18n.t('login.password_max', { n: MAX_PASSWORD_LENGTH });
        errDiv.style.display = 'flex';
        return;
    }

    if (newPw !== confirmPw) {
        errText.innerText = i18n.t('login.password_mismatch');
        errDiv.style.display = 'flex';
        return;
    }

    if (newPw.trim() === 'admin') {
        errText.innerText = i18n.t('login.password_same_as_default');
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
            errText.innerText = data.error || i18n.t('login.change_failed');
            errDiv.style.display = 'flex';
        }
    } catch (err) {
        errText.innerText = i18n.t('login.server_error');
        errDiv.style.display = 'flex';
        console.error(err);
    }
}
