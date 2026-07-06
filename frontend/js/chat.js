/**
 * 聊天页面核心逻辑
 * 管理会话列表、SSE 流式问答、消息渲染、引用展示
 */

// ========== 全局状态 ==========
const ChatState = {
    currentUser: null,
    currentConversationId: null,
    conversations: [],
    isStreaming: false,
    mapLocations: [],  // 当前会话所有地图标记
    userLocation: null,  // { lat, lng, city }
};

// ========== 初始化 ==========

document.addEventListener('DOMContentLoaded', async () => {
    // 检查登录状态
    const user = API.getUser();
    if (!user) {
        window.location.href = '/';
        return;
    }
    ChatState.currentUser = user;
    document.getElementById('headerUsername').textContent = user.nickname || user.username;

    // 管理员显示管理入口
    if (user.role === 'admin') {
        document.getElementById('adminLink').classList.remove('hidden');
    }

    // 初始化
    loadConversations();
    setupEventListeners();
    setupInputAutoResize();
});

// ========== 事件绑定 ==========

function setupEventListeners() {
    // 发送按钮
    document.getElementById('sendBtn').addEventListener('click', sendMessage);
    // 回车发送
    document.getElementById('chatInput').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    // 新会话
    document.getElementById('newChatBtn').addEventListener('click', createNewConversation);
    // 退出
    document.getElementById('logoutBtn').addEventListener('click', logout);
    // 地图切换
    document.getElementById('toggleMapBtn').addEventListener('click', toggleMapPanel);
    // 字数统计
    document.getElementById('chatInput').addEventListener('input', updateCharCount);
}

function setupInputAutoResize() {
    const textarea = document.getElementById('chatInput');
    textarea.addEventListener('input', () => {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    });
}

function updateCharCount() {
    const len = document.getElementById('chatInput').value.length;
    document.getElementById('charCount').textContent = `${len}/2000`;
}

// ========== 会话管理 ==========

async function loadConversations() {
    try {
        const data = await API.get('/api/conversations');
        ChatState.conversations = data.items || [];
        renderConversationList();

        // 加载最后一个活跃会话
        if (ChatState.conversations.length > 0) {
            switchConversation(ChatState.conversations[0].id);
        }
    } catch (error) {
        console.error('加载会话列表失败:', error);
        document.getElementById('conversationList').innerHTML =
            '<div class="sidebar-loading">加载失败</div>';
    }
}

function renderConversationList() {
    const container = document.getElementById('conversationList');
    if (ChatState.conversations.length === 0) {
        container.innerHTML = '<div class="sidebar-loading">暂无对话记录<br>发送消息开始新会话</div>';
        return;
    }

    container.innerHTML = ChatState.conversations.map(conv => `
        <div class="conv-item ${conv.id === ChatState.currentConversationId ? 'active' : ''}"
             onclick="switchConversation('${conv.id}')">
            <span class="conv-item-icon">💬</span>
            <div class="conv-item-content">
                <div class="conv-item-title">${Utils.escapeHtml(conv.title)}</div>
                <div class="conv-item-time">${Utils.formatDate(conv.updated_at)}</div>
            </div>
            <span class="conv-item-delete" onclick="deleteConversation(event, '${conv.id}')" title="删除">🗑️</span>
        </div>
    `).join('');
}

async function createNewConversation() {
    if (ChatState.isStreaming) return;

    try {
        const data = await API.post('/api/conversations', {});
        ChatState.currentConversationId = data.id;
        document.getElementById('conversationTitle').textContent = data.title || '新的旅游咨询';
        document.getElementById('chatMessages').innerHTML = getWelcomeHTML();
        ChatState.mapLocations = [];
        MapView.clearMarkers();
        await loadConversations();
    } catch (error) {
        Utils.showToast('创建会话失败: ' + error.message, 'error');
    }
}

async function switchConversation(convId) {
    if (convId === ChatState.currentConversationId) return;

    ChatState.currentConversationId = convId;
    document.getElementById('conversationTitle').textContent =
        ChatState.conversations.find(c => c.id === convId)?.title || '旅游咨询';
    document.getElementById('chatMessages').innerHTML = '<div class="sidebar-loading" style="margin:auto;">加载历史消息...</div>';

    try {
        const data = await API.get(`/api/conversations/${convId}`);
        renderMessages(data.messages || []);
        ChatState.mapLocations = [];
        MapView.clearMarkers();
        renderConversationList();
    } catch (error) {
        document.getElementById('chatMessages').innerHTML = getWelcomeHTML();
        Utils.showToast('加载历史消息失败', 'error');
    }
}

async function deleteConversation(event, convId) {
    event.stopPropagation();
    if (!confirm('确定要删除这个会话吗？')) return;

    try {
        await API.delete(`/api/conversations/${convId}`);
        if (ChatState.currentConversationId === convId) {
            ChatState.currentConversationId = null;
            document.getElementById('chatMessages').innerHTML = getWelcomeHTML();
            document.getElementById('conversationTitle').textContent = '旅游咨询';
        }
        await loadConversations();
        Utils.showToast('会话已删除');
    } catch (error) {
        Utils.showToast('删除失败: ' + error.message, 'error');
    }
}

// ========== 消息发送与接收 ==========

async function sendMessage() {
    if (ChatState.isStreaming) return;

    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    if (!message) return;

    // 隐藏欢迎消息
    const welcomeEl = document.querySelector('.welcome-message');
    if (welcomeEl) welcomeEl.remove();

    // 添加用户消息
    addMessage('user', message);
    input.value = '';
    input.style.height = 'auto';
    updateCharCount();

    // 添加 AI 消息气泡（流式填充）
    const assistantMsgEl = addMessage('assistant', '', true);
    ChatState.isStreaming = true;
    document.getElementById('sendBtn').disabled = true;
    ChatState.mapLocations = [];

    try {
        const token = API.getToken();
        const response = await fetch(`${CONFIG.API_BASE}/api/chat/stream`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`,
            },
            body: JSON.stringify({
                conversation_id: ChatState.currentConversationId || null,
                message: message,
                options: {
                    location: ChatState.userLocation,
                },
            }),
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || '请求失败');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let fullContent = '';
        let currentEvent = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (line.startsWith('event: ')) {
                    currentEvent = line.slice(7).trim();
                    continue;
                }
                if (line.startsWith('data: ')) {
                    const data = JSON.parse(line.slice(6));
                    handleSSEEvent(currentEvent, data, assistantMsgEl);
                    if (currentEvent === 'token') {
                        fullContent += data.text || '';
                    }
                    currentEvent = '';
                }
            }
        }

        // 更新消息内容 — 渲染 Markdown
        const contentEl = assistantMsgEl.querySelector('.message-content');
        contentEl.innerHTML = renderMarkdown(fullContent);
        // 移除流式光标
        assistantMsgEl.querySelector('.message-bubble').classList.remove('streaming-cursor');

        // 刷新会话列表
        await loadConversations();

        // 更新会话标题（首条消息后自动生成）
        if (ChatState.conversations.find(c => c.id === ChatState.currentConversationId)?.message_count <= 2) {
            document.getElementById('conversationTitle').textContent =
                Utils.truncate(message, 30);
        }
    } catch (error) {
        assistantMsgEl.querySelector('.message-content').innerHTML =
            `<span style="color:var(--color-error)">⚠️ 抱歉，请求失败: ${Utils.escapeHtml(error.message)}</span>`;
        assistantMsgEl.querySelector('.message-bubble').classList.remove('streaming-cursor');
    } finally {
        ChatState.isStreaming = false;
        document.getElementById('sendBtn').disabled = false;
        Utils.scrollToBottom(document.getElementById('chatMessages'));
    }
}

function handleSSEEvent(event, data, msgEl) {
    const contentEl = msgEl.querySelector('.message-content');

    switch (event) {
        case 'token':
            contentEl.textContent += data.text || '';
            Utils.scrollToBottom(document.getElementById('chatMessages'));
            break;

        case 'citation':
            if (data.kb_items && data.kb_items.length > 0) {
                addCitations(msgEl, data.kb_items);
            }
            break;

        case 'map':
            if (data.pois && data.pois.length > 0) {
                ChatState.mapLocations = data.pois;
                // 如果还没定位，自动获取当前位置
                if (!ChatState.userLocation && navigator.geolocation) {
                    navigator.geolocation.getCurrentPosition(function(pos) {
                        ChatState.userLocation = {
                            lat: pos.coords.latitude,
                            lng: pos.coords.longitude,
                            city: '当前位置'
                        };
                        document.getElementById('userLocation').textContent = '📍 已自动定位';
                        showMapWithRoute(data.pois);
                    }, function() {
                        // 定位失败也照常显示地图（无用户位置）
                        showMapWithRoute(data.pois);
                    }, { timeout: 5000, enableHighAccuracy: false });
                } else {
                    showMapWithRoute(data.pois);
                }
            }
            break;

        function showMapWithRoute(pois) {
            try {
                if (ChatState.userLocation) {
                    MapView.setUserLocation(ChatState.userLocation.lng, ChatState.userLocation.lat);
                }
                MapView.showLocations(pois);
                addMapCard(msgEl, pois);
            } catch (e) {
                console.warn('Map显示失败:', e);
            }
        }

        case 'done':
            if (data.message_id) {
                msgEl.dataset.messageId = data.message_id;
            }
            if (data.conversation_id && !ChatState.currentConversationId) {
                ChatState.currentConversationId = data.conversation_id;
                document.getElementById('conversationTitle').textContent =
                    Utils.truncate(document.getElementById('chatInput').value || '旅游咨询', 30);
            }
            break;

        case 'error':
            contentEl.textContent += `\n\n⚠️ ${data.message}`;
            break;
    }
}

function sendQuickQuestion(question) {
    document.getElementById('chatInput').value = question;
    sendMessage();
}

// ========== 消息渲染 ==========

function addMessage(role, content, isStreaming = false) {
    const container = document.getElementById('chatMessages');
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;

    const avatar = role === 'user' ? '👤' : '🤖';
    const bubbleClass = isStreaming ? 'message-bubble streaming-cursor' : 'message-bubble';

    // AI 回复渲染 Markdown，用户消息和流式消息保持纯文本
    let displayContent;
    if (isStreaming) {
        displayContent = '';
    } else if (role === 'assistant') {
        displayContent = renderMarkdown(content);
    } else {
        displayContent = Utils.escapeHtml(content);
    }

    msgDiv.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div>
            <div class="${bubbleClass}">
                <div class="message-content">${displayContent}</div>
            </div>
            <div class="message-time">${Utils.formatDate(new Date().toISOString())}</div>
        </div>
    `;

    container.appendChild(msgDiv);
    Utils.scrollToBottom(container);
    return msgDiv;
}

function renderMessages(messages) {
    const container = document.getElementById('chatMessages');
    container.innerHTML = '';

    if (messages.length === 0) {
        container.innerHTML = getWelcomeHTML();
        return;
    }

    messages.forEach(msg => {
        addMessage(msg.role, msg.content);

        // 渲染引用
        if (msg.citations) {
            try {
                const citations = typeof msg.citations === 'string'
                    ? JSON.parse(msg.citations) : msg.citations;
                if (citations.length > 0) {
                    const lastMsg = container.lastElementChild;
                    addCitations(lastMsg, citations);
                }
            } catch { /* ignore */ }
        }

        // 渲染地图
        if (msg.map_data) {
            try {
                const mapData = typeof msg.map_data === 'string'
                    ? JSON.parse(msg.map_data) : msg.map_data;
                if (mapData.pois && mapData.pois.length > 0) {
                    ChatState.mapLocations = mapData.pois;
                    MapView.showLocations(mapData.pois);
                }
            } catch { /* ignore */ }
        }
    });

    Utils.scrollToBottom(container);
}

function addCitations(msgEl, kbItems) {
    const bubble = msgEl.querySelector('.message-bubble')?.parentElement;
    if (!bubble) return;

    let citationsHTML = '<div class="citations-section" style="margin-top:12px;">';
    citationsHTML += '<div style="font-size:12px;color:var(--color-text-muted);margin-bottom:6px;">📖 参考资料：</div>';

    kbItems.forEach((item, i) => {
        const refNum = i + 1;
        citationsHTML += `
            <div id="citation-${refNum}" class="citation-card" style="margin-bottom:6px;cursor:pointer;" onclick="showCitationDetail('${item.id}', '${Utils.escapeHtml(item.title || '')}', '${Utils.escapeHtml(item.snippet || '')}')">
                <strong>[${refNum}] ${Utils.escapeHtml(item.title || '未知来源')}</strong>
                <span style="font-size:11px;color:var(--color-text-muted)">(${Utils.escapeHtml(item.type || '未知类型')} · 相似度: ${(item.score || 0).toFixed(2)})</span>
                <br><span style="font-size:12px;">${Utils.escapeHtml(Utils.truncate(item.snippet || '', 100))}</span>
            </div>
        `;
    });

    citationsHTML += '</div>';
    bubble.innerHTML += citationsHTML;
}

function addMapCard(msgEl, pois) {
    const bubble = msgEl.querySelector('.message-bubble')?.parentElement;
    if (!bubble) return;

    let html = '<div class="map-card"><div class="map-card-header">📍 相关地点</div>';
    html += '<div style="padding:8px 12px;font-size:13px;">';
    pois.forEach(poi => {
        html += `<div style="margin-bottom:4px;">· <strong>${Utils.escapeHtml(poi.name)}</strong>`;
        if (poi.description) html += ` - ${Utils.escapeHtml(poi.description)}`;
        html += '</div>';
    });
    html += '</div></div>';
    bubble.innerHTML += html;
}

function getWelcomeHTML() {
    return `
        <div class="welcome-message">
            <div class="welcome-icon">🏔️</div>
            <h2>欢迎使用旅伴</h2>
            <p>我是您的中国旅游推荐助手，可以为您：</p>
            <div class="welcome-features">
                <div class="welcome-card" onclick="sendQuickQuestion('推荐北京的热门景点')">
                    <span>🗺️</span><strong>景点推荐</strong><small>发现国内最美目的地</small>
                </div>
                <div class="welcome-card" onclick="sendQuickQuestion('杭州西湖附近有什么好的酒店推荐？')">
                    <span>🏨</span><strong>住宿推荐</strong><small>找到舒适的落脚之处</small>
                </div>
                <div class="welcome-card" onclick="sendQuickQuestion('成都必吃的特色美食有哪些？')">
                    <span>🍜</span><strong>美食推荐</strong><small>品尝地道中国味道</small>
                </div>
                <div class="welcome-card" onclick="sendQuickQuestion('帮我规划一个3天的西安旅游行程')">
                    <span>📋</span><strong>行程规划</strong><small>一键生成旅行计划</small>
                </div>
            </div>
        </div>
    `;
}

// ========== 引用弹窗 ==========

function showCitationDetail(id, title, snippet) {
    document.getElementById('citationContent').innerHTML = `
        <h4>📖 ${Utils.escapeHtml(title)}</h4>
        <p style="margin-top:12px;line-height:1.8;color:var(--color-text-secondary);">${Utils.escapeHtml(snippet)}</p>
    `;
    document.getElementById('citationModal').classList.remove('hidden');
}

function closeCitationModal() {
    document.getElementById('citationModal').classList.add('hidden');
}

// ========== 地图面板 ==========

function toggleMapPanel() {
    const panel = document.getElementById('mapPanel');
    const btn = document.getElementById('toggleMapBtn');
    panel.classList.toggle('collapsed');
    btn.textContent = panel.classList.contains('collapsed') ? '▲' : '▼';
}

// ========== 定位功能已移至 chat.html 内嵌脚本 ==========

function logout() {
    API.clearTokens();
    window.location.href = '/';
}
