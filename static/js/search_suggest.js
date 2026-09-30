/*
 * In-page search suggestions.
 *
 *   <input name="q" data-suggest="courses" data-suggest-params="type=degree">
 *       → fetches /api/search/terms/?scope=courses&type=degree&q=…
 *   <input name="course" data-suggest-local="someJsonScriptId">
 *       → filters a list rendered with Django's |json_script
 *
 * Picking a suggestion fills the input and runs the page's own search:
 * htmx inputs get a "search" event, plain inputs submit their form.
 */
(function () {
    'use strict';

    var STYLE = '' +
        '.ssg-drop{position:absolute;z-index:1080;background:#fff;border:1px solid #e2e8f0;border-radius:10px;' +
        'box-shadow:0 10px 30px rgba(15,23,42,.14);max-height:320px;overflow-y:auto;display:none;padding:4px 0;text-align:left;}' +
        '.ssg-drop.open{display:block;}' +
        '.ssg-item{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:8px 12px;cursor:pointer;' +
        'font-size:.86rem;color:#1e293b;line-height:1.3;}' +
        '.ssg-item:hover,.ssg-item.active{background:#eef2ff;}' +
        '.ssg-item mark{background:none;color:#4f46e5;font-weight:700;padding:0;}' +
        '.ssg-sub{font-size:.7rem;color:#64748b;white-space:nowrap;flex-shrink:0;}' +
        '.ssg-empty{padding:8px 12px;font-size:.8rem;color:#94a3b8;}';

    function injectStyle() {
        if (document.getElementById('ssg-style')) return;
        var el = document.createElement('style');
        el.id = 'ssg-style';
        el.textContent = STYLE;
        document.head.appendChild(el);
    }

    function esc(s) {
        return String(s).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }

    function highlight(text, q) {
        var i = text.toLowerCase().indexOf(q.toLowerCase());
        if (i < 0) return esc(text);
        return esc(text.slice(0, i)) + '<mark>' + esc(text.slice(i, i + q.length)) + '</mark>' + esc(text.slice(i + q.length));
    }

    function debounce(fn, ms) {
        var t;
        return function () { clearTimeout(t); t = setTimeout(fn, ms); };
    }

    // Local list ranking: prefix > word prefix > substring > all words present
    function rankLocal(list, q) {
        var ql = q.toLowerCase(), toks = ql.split(/\s+/).filter(Boolean), out = [];
        list.forEach(function (label) {
            var l = String(label).toLowerCase(), s = 0;
            if (l.indexOf(ql) === 0) s = 4;
            else if ((' ' + l).indexOf(' ' + ql) >= 0 || l.indexOf('(' + ql) >= 0) s = 3;
            else if (l.indexOf(ql) >= 0) s = 2;
            else if (toks.length > 1 && toks.every(function (t) { return l.indexOf(t) >= 0; })) s = 1;
            if (s) out.push({ s: s, label: label });
        });
        out.sort(function (a, b) { return b.s - a.s || a.label.length - b.label.length; });
        return out.slice(0, 8).map(function (o) { return { label: o.label, sub: '' }; });
    }

    function attach(input) {
        if (input.dataset.ssgReady) return;
        input.dataset.ssgReady = '1';
        input.setAttribute('autocomplete', 'off');

        var scope = input.dataset.suggest || '';
        var localList = null;
        if (input.dataset.suggestLocal) {
            var src = document.getElementById(input.dataset.suggestLocal);
            try { localList = src ? JSON.parse(src.textContent) : []; } catch (e) { localList = []; }
        }

        var drop = document.createElement('div');
        drop.className = 'ssg-drop';
        drop.setAttribute('role', 'listbox');
        document.body.appendChild(drop);

        var items = [], active = -1, lastQ = null, picking = false;

        function position() {
            var r = input.getBoundingClientRect();
            drop.style.left = (r.left + window.scrollX) + 'px';
            drop.style.top = (r.bottom + window.scrollY + 4) + 'px';
            drop.style.width = Math.max(r.width, 260) + 'px';
        }

        function close() { drop.classList.remove('open'); active = -1; }

        function render(list, q) {
            items = list;
            active = -1;
            if (!list.length) {
                drop.innerHTML = '<div class="ssg-empty">No suggestions, press Enter to search anyway</div>';
            } else {
                drop.innerHTML = list.map(function (it, i) {
                    return '<div class="ssg-item" role="option" data-i="' + i + '"><span>' + highlight(it.label, q) + '</span>' +
                        (it.sub ? '<span class="ssg-sub">' + esc(it.sub) + '</span>' : '') + '</div>';
                }).join('');
            }
            position();
            drop.classList.add('open');
        }

        function run() {
            var q = input.value.trim();
            if (q.length < 2) { close(); lastQ = null; return; }
            if (q === lastQ && drop.classList.contains('open')) return;
            lastQ = q;
            if (localList) { render(rankLocal(localList, q), q); return; }
            var url = '/api/search/terms/?scope=' + encodeURIComponent(scope) + '&q=' + encodeURIComponent(q);
            if (input.dataset.suggestParams) url += '&' + input.dataset.suggestParams;
            fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
                .then(function (r) { return r.ok ? r.json() : Promise.reject(); })
                .then(function (d) { if (input.value.trim() === q) render(d.suggestions || [], q); })
                .catch(close);
        }

        function pick(i) {
            var it = items[i];
            if (!it) return;
            picking = true;
            input.value = it.label;
            lastQ = it.label;
            close();
            if (input.hasAttribute('hx-get') || input.hasAttribute('hx-post')) {
                input.dispatchEvent(new Event('search', { bubbles: true }));
            } else if (input.form) {
                if (input.form.requestSubmit) input.form.requestSubmit(); else input.form.submit();
            }
            setTimeout(function () { picking = false; }, 400);
        }

        var debounced = debounce(run, localList ? 60 : 200);
        input.addEventListener('input', function () { if (!picking) debounced(); });
        input.addEventListener('focus', function () { if (input.value.trim().length >= 2) { lastQ = null; run(); } });

        input.addEventListener('keydown', function (e) {
            if (!drop.classList.contains('open')) return;
            var els = drop.querySelectorAll('.ssg-item');
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                active = Math.min(active + 1, els.length - 1);
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                active = Math.max(active - 1, -1);
            } else if (e.key === 'Enter') {
                if (active >= 0) { e.preventDefault(); pick(active); } else { close(); }
                return;
            } else if (e.key === 'Escape') {
                close(); return;
            } else { return; }
            els.forEach(function (el, i) { el.classList.toggle('active', i === active); });
            if (els[active]) els[active].scrollIntoView({ block: 'nearest' });
        });

        // mousedown (not click) so it fires before the input loses focus
        drop.addEventListener('mousedown', function (e) {
            var el = e.target.closest('.ssg-item');
            if (!el) return;
            e.preventDefault();
            pick(+el.dataset.i);
        });

        input.addEventListener('blur', function () { setTimeout(close, 150); });
        window.addEventListener('resize', function () { if (drop.classList.contains('open')) position(); });
        window.addEventListener('scroll', function () { if (drop.classList.contains('open')) position(); }, { passive: true });
    }

    function init(root) {
        injectStyle();
        (root || document).querySelectorAll('input[data-suggest], input[data-suggest-local]').forEach(attach);
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { init(); });
    else init();
    // Re-scan after htmx swaps in new content
    document.addEventListener('htmx:afterSwap', function (e) { init(e.target); });
    window.initSearchSuggest = init;
}());
