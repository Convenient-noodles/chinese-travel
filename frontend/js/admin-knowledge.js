/**
 * 旅伴 — 知识库管理（简洁版）
 */
var state = { page: 1, pageSize: 20, search: '', filterType: '', editingId: null };
var API_PATH = '/api/admin/knowledge';

// ===== 初始化 =====
document.addEventListener('DOMContentLoaded', function () {
    var user = API.getUser();
    if (!user || user.role !== 'admin') { window.location.href = '/'; return; }
    document.getElementById('headerUser').textContent = user.nickname || user.username;

    // 类型 Tab
    document.querySelectorAll('.tab-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
            document.querySelectorAll('.tab-btn').forEach(function (b) { b.classList.remove('active'); });
            btn.classList.add('active');
            state.filterType = btn.dataset.type;
            state.page = 1;
            loadData();
        });
    });

    // 搜索
    document.getElementById('searchInput').addEventListener('keydown', function (e) {
        if (e.key === 'Enter') { state.search = this.value.trim(); state.page = 1; loadData(); }
    });
    document.getElementById('searchBtn').addEventListener('click', function () {
        state.search = document.getElementById('searchInput').value.trim();
        state.page = 1;
        loadData();
    });

    // 新增
    document.getElementById('addBtn').addEventListener('click', function () { openModal(); });
    // 保存
    document.getElementById('saveBtn').addEventListener('click', saveItem);
    // 退出
    document.getElementById('logoutBtn').addEventListener('click', function () { API.clearTokens(); window.location.href = '/'; });
    // 文件导入
    document.getElementById('fileInput').addEventListener('change', importFile);

    loadData();
});

// ===== 加载数据 =====
async function loadData() {
    var params = '?page=' + state.page + '&page_size=' + state.pageSize;
    if (state.search) params += '&search=' + encodeURIComponent(state.search);
    if (state.filterType) params += '&item_type=' + state.filterType;

    try {
        var data = await API.get(API_PATH + params);
        renderTable(data);
        renderPagination(data);
    } catch (e) {
        Utils.showToast('加载失败: ' + e.message, 'error');
    }
}

function renderTable(data) {
    var items = data.items || [];
    var types = { attraction: '🏔️ 景点', hotel: '🏨 住宿', food: '🍜 美食' };
    if (items.length === 0) {
        document.getElementById('tableBody').innerHTML = '<tr><td colspan="4" class="text-center text-muted">暂无数据</td></tr>';
        return;
    }
    var html = '';
    items.forEach(function (item) {
        html += '<tr>' +
            '<td>' + (types[item.item_type] || item.item_type) + '</td>' +
            '<td>' + Utils.escapeHtml(item.name) + '</td>' +
            '<td>' + Utils.escapeHtml(item.city || '') + '</td>' +
            '<td class="actions">' +
                '<button class="btn-secondary btn-sm" onclick="openModal(\'' + item.id + '\')">编辑</button> ' +
                '<button class="btn-danger btn-sm" onclick="deleteItem(\'' + item.id + '\')">删除</button>' +
            '</td></tr>';
    });
    document.getElementById('tableBody').innerHTML = html;
}

function renderPagination(data) {
    var p = document.getElementById('pagination');
    p.innerHTML =
        '<button ' + (state.page <= 1 ? 'disabled' : '') + ' onclick="goPage(' + (state.page - 1) + ')">上一页</button>' +
        '<span> ' + data.page + '/' + data.total_pages + ' 页 (' + data.total + '条)</span>' +
        '<button ' + (state.page >= data.total_pages ? 'disabled' : '') + ' onclick="goPage(' + (state.page + 1) + ')">下一页</button>';
}

function goPage(n) { state.page = n; loadData(); }

// ===== 新增/编辑弹窗 =====
function openModal(id) {
    state.editingId = id || null;
    document.getElementById('modalTitle').textContent = id ? '编辑' : '新增';
    document.getElementById('fType').value = 'attraction';
    document.getElementById('fName').value = '';
    document.getElementById('fCity').value = '';
    document.getElementById('fDesc').value = '';
    document.getElementById('fContent').value = '';
    document.getElementById('fLng').value = '';
    document.getElementById('fLat').value = '';
    document.getElementById('editModal').classList.remove('hidden');

    if (id) {
        API.get(API_PATH + '/' + id).then(function (item) {
            document.getElementById('fType').value = item.item_type || 'attraction';
            document.getElementById('fName').value = item.name || '';
            document.getElementById('fCity').value = item.city || '';
            document.getElementById('fDesc').value = item.description || '';
            document.getElementById('fContent').value = item.content || '';
            document.getElementById('fLng').value = item.longitude || '';
            document.getElementById('fLat').value = item.latitude || '';
        }).catch(function (e) {
            Utils.showToast('加载失败', 'error');
        });
    }
}

function closeModal() { document.getElementById('editModal').classList.add('hidden'); }

async function saveItem() {
    var payload = {
        item_type: document.getElementById('fType').value,
        name: document.getElementById('fName').value.trim(),
        city: document.getElementById('fCity').value.trim(),
        description: document.getElementById('fDesc').value.trim(),
        content: document.getElementById('fContent').value.trim(),
        longitude: parseFloat(document.getElementById('fLng').value) || null,
        latitude: parseFloat(document.getElementById('fLat').value) || null
    };
    if (!payload.name || !payload.city) { Utils.showToast('名称和城市为必填', 'error'); return; }
    if (!payload.content) { Utils.showToast('内容为必填', 'error'); return; }

    try {
        if (state.editingId) {
            await API.put(API_PATH + '/' + state.editingId, payload);
        } else {
            await API.post(API_PATH, payload);
        }
        Utils.showToast(state.editingId ? '已更新' : '已创建');
        closeModal();
        loadData();
    } catch (e) {
        Utils.showToast('保存失败: ' + e.message, 'error');
    }
}

async function deleteItem(id) {
    if (!confirm('确定删除？')) return;
    try { await API.delete(API_PATH + '/' + id); Utils.showToast('已删除'); loadData(); }
    catch (e) { Utils.showToast('删除失败: ' + e.message, 'error'); }
}

// ===== 文件导入（自动解析 === 类型：名称 === 结构化文本） =====
async function importFile(e) {
    var file = e.target.files[0];
    if (!file) return;
    var name = file.name.replace(/\.(txt|md)$/i, '');
    Utils.showToast('正在解析并导入: ' + name + '...');

    var reader = new FileReader();
    reader.onload = async function (ev) {
        try {
            var content = ev.target.result;
            var result = await API.post(API_PATH + '/batch-import', { content: content });
            Utils.showToast('导入成功！解析出 ' + result.success_count + ' 条记录');
            if (result.failed_count > 0) {
                Utils.showToast('有 ' + result.failed_count + ' 条导入失败', 'warn');
            }
            loadData();
        } catch (err) {
            // 如果 batch-import 解析失败（无有效格式），回退到整体导入
            if (err.status === 400 || err.message.indexOf('未找到') >= 0) {
                try {
                    await API.post(API_PATH, {
                        item_type: 'attraction',
                        name: name,
                        city: '文件导入',
                        description: name,
                        content: content
                    });
                    Utils.showToast('已整体导入: ' + name + '（未检测到结构化格式）');
                    loadData();
                } catch (err2) {
                    Utils.showToast('导入失败: ' + (err2.message || err2), 'error');
                }
                return;
            }
            Utils.showToast('导入失败: ' + (err.message || err), 'error');
        }
    };
    reader.readAsText(file, 'UTF-8');
    e.target.value = '';
}
