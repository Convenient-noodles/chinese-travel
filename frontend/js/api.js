/**
 * API 请求封装（统一 Token 管理、错误处理）
 */
const API = {
    /**
     * 获取存储的 Token
     */
    getToken() {
        return localStorage.getItem(CONFIG.TOKEN_KEY);
    },

    getRefreshToken() {
        return localStorage.getItem(CONFIG.REFRESH_TOKEN_KEY);
    },

    setTokens(accessToken, refreshToken) {
        localStorage.setItem(CONFIG.TOKEN_KEY, accessToken);
        localStorage.setItem(CONFIG.REFRESH_TOKEN_KEY, refreshToken);
    },

    clearTokens() {
        localStorage.removeItem(CONFIG.TOKEN_KEY);
        localStorage.removeItem(CONFIG.REFRESH_TOKEN_KEY);
        localStorage.removeItem(CONFIG.USER_KEY);
    },

    saveUser(user) {
        localStorage.setItem(CONFIG.USER_KEY, JSON.stringify(user));
    },

    getUser() {
        const data = localStorage.getItem(CONFIG.USER_KEY);
        return data ? JSON.parse(data) : null;
    },

    /**
     * 统一请求方法
     */
    async request(method, path, body = null, options = {}) {
        const url = `${CONFIG.API_BASE}${path}`;
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers,
        };

        const token = this.getToken();
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const config = { method, headers };

        if (body && method !== 'GET') {
            config.body = JSON.stringify(body);
        }

        try {
            const response = await fetch(url, config);

            // Token 过期：尝试刷新
            if (response.status === 401 && token) {
                const refreshed = await this.tryRefreshToken();
                if (refreshed) {
                    headers['Authorization'] = `Bearer ${this.getToken()}`;
                    config.headers = headers;
                    const retryResponse = await fetch(url, config);
                    return await this.handleResponse(retryResponse);
                }
            }

            return await this.handleResponse(response);
        } catch (error) {
            if (error.name === 'TypeError' && error.message.includes('fetch')) {
                throw new Error('网络连接失败，请检查网络');
            }
            throw error;
        }
    },

    /**
     * 处理响应
     */
    async handleResponse(response) {
        const data = await response.json();

        if (!response.ok) {
            const message = data.detail || data.error?.message || '请求失败';
            throw new Error(message);
        }

        return data;
    },

    /**
     * 尝试刷新 Token
     */
    async tryRefreshToken() {
        const refreshToken = this.getRefreshToken();
        if (!refreshToken) {
            this.clearTokens();
            return false;
        }

        try {
            const response = await fetch(`${CONFIG.API_BASE}/api/auth/refresh`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh_token: refreshToken }),
            });

            if (response.ok) {
                const data = await response.json();
                this.setTokens(data.access_token, data.refresh_token);
                return true;
            }
        } catch {
            // 刷新失败
        }

        this.clearTokens();
        return false;
    },

    // ========== 便捷方法 ==========

    get(path, options) { return this.request('GET', path, null, options); },
    post(path, body, options) { return this.request('POST', path, body, options); },
    put(path, body, options) { return this.request('PUT', path, body, options); },
    delete(path, options) { return this.request('DELETE', path, null, options); },

    // ========== 认证 API ==========

    auth: {
        register(data) { return API.post('/api/auth/register', data); },
        login(data) { return API.post('/api/auth/login', data); },
        logout() { return API.post('/api/auth/logout'); },
        me() { return API.get('/api/auth/me'); },
        changePassword(data) { return API.put('/api/auth/password', data); },
    },
};
