/**
 * 旅伴 — 管理员用户管理
 */
var userState = { page: 1, pageSize: 20, search: '', filterRole: '' };

// ===== 初始化 =====
document.addEventListener('DOMContentLoaded', function () {
    var user = API.getUser();
    if (!user || user.role !== 'admin') { window.location.href = '/'; return; }
    document.getElementById('headerUser').textContent = user.nickname || user.username;

    // 搜索
    document.getElementById('searchInput').addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            userState.search = this.value.trim();
            userState.page = 1;
            loadUsers();
        }
    });
    document.getElementById('searchBtn').addEventListener('click', function () {
        userState.search = document.getElementById('searchInput').value.trim();
        userState.page = 1;
        loadUsers();
    });

    // 角色筛选
    document.getElementById('roleFilter').addEventListener('change', function () {
        userState.filterRole = this.value;
        userState.page = 1;
        loadUsers();
    });

    // 刷新
    document.getElementById('refreshBtn').addEventListener('click', function () {
        document.getElementById('searchInput').value = '';
        document.getElementById('roleFilter').value = '';
        userState = { page: 1, pageSize: 20, search: '', filterRole: '' };
        loadAll();
    });

    // 新增用户
    document.getElementById('addUserBtn').addEventListener('click', openUserModal);
    document.getElementById('saveUserBtn').addEventListener('click', createUser);

    // 退出
    document.getElementById('logoutBtn').addEventListener('click', function () {
        API.clearTokens();
        window.location.href = '/';
    });

    loadAll();
});

// ===== 加载全部数据 =====
async function loadAll() {
    try {
        await loadStats();
        await loadUsers();
    } catch (e) {
        Utils.showToast('加载失败: ' + e.message, 'error');
    }
}

// ===== 加载统计数据 =====
async function loadStats() {
    try {
        var stats = await API.get('/api/admin/users/stats');
        var cards = document.querySelectorAll('#statsRow .stat-card');
        cards[0].querySelector('.stat-value').textContent = stats.total_users;
        cards[1].querySelector('.stat-value').textContent = stats.today_new;
        cards[2].querySelector('.stat-value').textContent = stats.week_new;
        cards[3].querySelector('.stat-value').textContent = stats.month_new;
        cards[4].querySelector('.stat-value').textContent = stats.active_count;
        cards[5].querySelector('.stat-value').textContent = stats.admin_count;
    } catch (e) {
        console.error('加载统计数据失败:', e);
    }
}

// ===== 加载用户列表 =====
async function loadUsers() {
    var params = '?page=' + userState.page + '&page_size=' + userState.pageSize;
    if (userState.search) params += '&search=' + encodeURIComponent(userState.search);
    if (userState.filterRole) params += '&role=' + encodeURIComponent(userState.filterRole);

    try {
        var data = await API.get('/api/admin/users' + params);
        renderTable(data);
        renderPagination(data);
    } catch (e) {
        console.error('加载用户列表失败:', e);
        Utils.showToast('加载用户列表失败: ' + e.message, 'error');
    }
}

// ===== 渲染表格 =====
function renderTable(data) {
    var items = data.items || [];
    if (items.length === 0) {
        document.getElementById('tableBody').innerHTML =
            '<tr><td colspan="7" class="text-center text-muted">暂无用户数据</td></tr>';
        return;
    }

    var currentUserId = API.getUser() ? API.getUser().id : null;
    var html = '';
    items.forEach(function (u) {
        var roleBadge = u.role === 'admin'
            ? '<span class="badge badge-admin">管理员</span>'
            : '<span class="badge badge-user">普通用户</span>';
        var statusBadge = u.is_active
            ? '<span class="badge badge-active">正常</span>'
            : '<span class="badge badge-inactive">已禁用</span>';
        var regDate = u.created_at ? Utils.formatDate(u.created_at) : '-';

        // 操作按钮（不能操作自己）
        var isSelf = u.id === currentUserId;
        var actions = '';
        if (isSelf) {
            actions = '<span class="text-muted" style="font-size:12px;">当前用户</span>';
        } else {
            // 角色切换按钮
            if (u.role === 'admin') {
                actions += '<button class="btn-secondary btn-sm" onclick="changeRole(\'' + u.id + '\', \'user\')" title="降级为普通用户">降级</button> ';
            } else {
                actions += '<button class="btn-primary btn-sm" onclick="changeRole(\'' + u.id + '\', \'admin\')" title="提升为管理员">设为管理</button> ';
            }
            // 状态切换按钮
            if (u.is_active) {
                actions += '<button class="btn-danger btn-sm" onclick="toggleStatus(\'' + u.id + '\', false)" title="禁用此用户">禁用</button>';
            } else {
                actions += '<button class="btn-secondary btn-sm" onclick="toggleStatus(\'' + u.id + '\', true)" title="启用此用户">启用</button>';
            }
        }

        html += '<tr>' +
            '<td><strong>' + Utils.escapeHtml(u.username) + '</strong></td>' +
            '<td>' + Utils.escapeHtml(u.nickname || '-') + '</td>' +
            '<td>' + Utils.escapeHtml(u.email || '-') + '</td>' +
            '<td>' + roleBadge + '</td>' +
            '<td>' + statusBadge + '</td>' +
            '<td>' + regDate + '</td>' +
            '<td class="actions">' + actions + '</td>' +
            '</tr>';
    });
    document.getElementById('tableBody').innerHTML = html;
}

// ===== 渲染分页 =====
function renderPagination(data) {
    var p = document.getElementById('pagination');
    p.innerHTML =
        '<button ' + (userState.page <= 1 ? 'disabled' : '') +
        ' onclick="goPage(' + (userState.page - 1) + ')">上一页</button>' +
        '<span> ' + data.page + '/' + data.total_pages + ' 页 (共 ' + data.total + ' 名用户)</span>' +
        '<button ' + (userState.page >= data.total_pages ? 'disabled' : '') +
        ' onclick="goPage(' + (userState.page + 1) + ')">下一页</button>';
}

function goPage(n) {
    userState.page = n;
    loadUsers();
}

// ===== 新增用户弹窗 =====
function openUserModal() {
    document.getElementById('userModalTitle').textContent = '新增用户';
    document.getElementById('fUsername').value = '';
    document.getElementById('fPassword').value = '';
    document.getElementById('fNickname').value = '';
    document.getElementById('fEmail').value = '';
    document.getElementById('fRole').value = 'user';
    document.getElementById('userModal').classList.remove('hidden');
}

function closeUserModal() {
    document.getElementById('userModal').classList.add('hidden');
}

// ===== 创建用户 =====
async function createUser() {
    var username = document.getElementById('fUsername').value.trim();
    var password = document.getElementById('fPassword').value;
    var nickname = document.getElementById('fNickname').value.trim();
    var email = document.getElementById('fEmail').value.trim();
    var role = document.getElementById('fRole').value;

    if (!username || username.length < 2) {
        Utils.showToast('用户名至少2个字符', 'error');
        return;
    }
    if (!password || password.length < 6) {
        Utils.showToast('密码至少6位', 'error');
        return;
    }

    var btn = document.getElementById('saveUserBtn');
    btn.disabled = true;
    btn.textContent = '创建中...';

    try {
        await API.post('/api/admin/users', {
            username: username,
            password: password,
            nickname: nickname || undefined,
            email: email || undefined,
            role: role,
        });
        Utils.showToast('用户 "' + username + '" 创建成功', 'success');
        closeUserModal();
        loadAll();
    } catch (e) {
        Utils.showToast('创建失败: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '创建用户';
    }
}

// ===== 角色修改 =====
async function changeRole(userId, newRole) {
    var label = newRole === 'admin' ? '提升为管理员' : '降级为普通用户';
    if (!confirm('确定要' + label + '吗？')) return;

    try {
        await API.put('/api/admin/users/' + userId + '/role', { role: newRole });
        Utils.showToast('角色已更新', 'success');
        loadUsers();
    } catch (e) {
        Utils.showToast('操作失败: ' + e.message, 'error');
    }
}

// ===== 状态切换 =====
async function toggleStatus(userId, active) {
    var label = active ? '启用' : '禁用';
    if (!confirm('确定要' + label + '该用户吗？')) return;

    try {
        await API.put('/api/admin/users/' + userId + '/status', { is_active: active });
        Utils.showToast('用户状态已更新', 'success');
        loadUsers();
    } catch (e) {
        Utils.showToast('操作失败: ' + e.message, 'error');
    }
}
