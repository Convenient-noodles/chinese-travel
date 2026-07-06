/**
 * 认证页面逻辑：登录、注册、表单切换
 */

// ========== 表单切换 ==========

function switchForm(type) {
    document.getElementById('loginForm').classList.toggle('active', type === 'login');
    document.getElementById('registerForm').classList.toggle('active', type === 'register');
    // 清空错误信息
    document.getElementById('loginError').textContent = '';
    document.getElementById('regError').textContent = '';
}

// ========== 登录 ==========

document.getElementById('loginBtn').addEventListener('click', async () => {
    const username = document.getElementById('loginUsername').value.trim();
    const password = document.getElementById('loginPassword').value;
    const errorEl = document.getElementById('loginError');
    const btn = document.getElementById('loginBtn');

    errorEl.textContent = '';

    if (!username || !password) {
        errorEl.textContent = '请输入用户名和密码';
        return;
    }

    btn.disabled = true;
    btn.textContent = '登录中...';

    try {
        const data = await API.auth.login({ username, password });

        // 保存 Token 和用户信息
        API.setTokens(data.access_token, data.refresh_token);
        API.saveUser(data.user);

        // 根据角色跳转
        if (data.user.role === 'admin') {
            window.location.href = '/pages/admin-knowledge.html';
        } else {
            window.location.href = '/pages/chat.html';
        }
    } catch (error) {
        errorEl.textContent = error.message || '登录失败';
    } finally {
        btn.disabled = false;
        btn.textContent = '登 录';
    }
});

// 回车键登录
document.getElementById('loginPassword').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') document.getElementById('loginBtn').click();
});

// ========== 注册 ==========

document.getElementById('regBtn').addEventListener('click', async () => {
    const username = document.getElementById('regUsername').value.trim();
    const password = document.getElementById('regPassword').value;
    const nickname = document.getElementById('regNickname').value.trim();
    const errorEl = document.getElementById('regError');
    const btn = document.getElementById('regBtn');

    errorEl.textContent = '';

    if (!username || !password) {
        errorEl.textContent = '用户名和密码为必填项';
        return;
    }

    if (username.length < 2) {
        errorEl.textContent = '用户名至少2个字符';
        return;
    }

    if (password.length < 6) {
        errorEl.textContent = '密码至少6位';
        return;
    }

    btn.disabled = true;
    btn.textContent = '注册中...';

    try {
        await API.auth.register({
            username,
            password,
            nickname: nickname || undefined,
        });

        Utils.showToast('注册成功！请登录', 'success');
        switchForm('login');
        document.getElementById('loginUsername').value = username;
    } catch (error) {
        errorEl.textContent = error.message || '注册失败';
    } finally {
        btn.disabled = false;
        btn.textContent = '注 册';
    }
});

// ========== 初始状态：检查是否已登录 ==========

(async function checkLoginStatus() {
    const token = API.getToken();
    if (!token) return;

    try {
        const data = await API.auth.me();
        API.saveUser(data);
        // 已登录，直接跳转
        if (data.role === 'admin') {
            window.location.href = '/pages/admin-knowledge.html';
        } else {
            window.location.href = '/pages/chat.html';
        }
    } catch {
        // Token 过期，清除
        API.clearTokens();
    }
})();
