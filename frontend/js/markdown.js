/**
 * Markdown 渲染模块
 * 配置 marked.js 支持引用编号、地图卡片等自定义渲染
 */
(function () {
    if (typeof marked === 'undefined') {
        console.warn('marked.js 未加载，将使用纯文本渲染');
        return;
    }

    // 配置 marked
    marked.setOptions({
        breaks: true,        // 支持 GFM 换行
        gfm: true,           // GitHub Flavored Markdown
        headerIds: false,    // 不生成 header id
        mangle: false,       // 不混淆邮箱
    });

    // 自定义渲染器
    const renderer = new marked.Renderer();

    // 自定义链接：外部链接在新窗口打开
    renderer.link = function ({ href, title, text }) {
        const titleAttr = title ? ` title="${title}"` : '';
        return `<a href="${href}" target="_blank" rel="noopener noreferrer"${titleAttr}>${text}</a>`;
    };

    // 自定义引用块
    renderer.blockquote = function ({ text }) {
        return `<blockquote style="border-left:3px solid var(--color-primary);padding:8px 16px;margin:8px 0;background:var(--color-primary-light);border-radius:0 6px 6px 0;color:var(--color-text-secondary);">${text}</blockquote>`;
    };

    // 自定义表格
    renderer.table = function ({ header, rows }) {
        const headerHTML = header.map(cell => `<th style="padding:8px 12px;border:1px solid var(--color-border);background:var(--color-bg);text-align:left;">${cell}</th>`).join('');
        const bodyHTML = rows.map(row =>
            `<tr>${row.map(cell => `<td style="padding:8px 12px;border:1px solid var(--color-border);">${cell}</td>`).join('')}</tr>`
        ).join('');
        return `<table style="border-collapse:collapse;width:100%;margin:8px 0;font-size:13px;"><thead><tr>${headerHTML}</tr></thead><tbody>${bodyHTML}</tbody></table>`;
    };

    marked.use({ renderer });

    /**
     * 渲染 Markdown 文本为 HTML
     * 同时处理 [^N] 格式的引用标记转换为可点击元素
     */
    window.renderMarkdown = function (text) {
        if (!text) return '';

        // 预处理：将 [^N] 格式转换为可点击的引用标记
        // [^1] → <sup class="citation-ref" data-citation="1" onclick="scrollToCitation(1)">[1]</sup>
        let processed = text.replace(/\[\^(\d+)\]/g, (match, num) => {
            return `<sup class="citation-ref" data-citation="${num}" onclick="scrollToCitation(${num})" title="点击查看参考资料 ${num}">[${num}]</sup>`;
        });

        // 使用 marked 渲染
        try {
            let html = marked.parse(processed);
            // 后处理：为表格添加包装层以支持横向滚动
            html = html.replace(/<table>/g, '<div class="table-wrapper"><table>');
            html = html.replace(/<\/table>/g, '</table></div>');
            return html;
        } catch (e) {
            console.error('Markdown 渲染错误:', e);
            return processed.replace(/\n/g, '<br>');
        }
    };

    /**
     * 滚动到指定编号的引用卡片
     */
    window.scrollToCitation = function(num) {
        const ref = document.getElementById('citation-' + num);
        if (ref) {
            ref.scrollIntoView({ behavior: 'smooth', block: 'center' });
            ref.classList.add('citation-highlight');
            setTimeout(function() { ref.classList.remove('citation-highlight'); }, 2000);
        }
    };
})();
