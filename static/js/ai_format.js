/* CareerNext AI — render the assistant's light Markdown as safe HTML.
 * Supports: ### headings, **bold**, "- " / "• " bullets, "1. " lists and
 * [label](url) links. Links are allowed only to site paths ("/...") and a few
 * official HTTPS domains; everything else is shown as plain text.
 * The model ends replies with "<<FOLLOWUPS: a | b | c>>"; cnAiFormat hides it
 * (including a half-streamed one) and cnAiFollowups(text) returns the list.
 * Usage: el.innerHTML = cnAiFormat(text)
 */
(function () {
  'use strict';

  var SAFE_HOSTS = [
    'careernext.co.ke', 'kuccps.net', 'kuccps.ac.ke', 'hef.co.ke',
    'helb.co.ke', 'knec.ac.ke', 'kmtc.ac.ke', 'education.go.ke',
  ];
  var LINK_STYLE = 'color:#4f46e5;font-weight:600;text-decoration:underline;';

  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function safeHref(url) {
    if (/^\/(?!\/)[^\s]*$/.test(url)) return url;            // same-site path
    try {
      var u = new URL(url);
      if (u.protocol !== 'https:') return null;
      var host = u.hostname.toLowerCase();
      for (var i = 0; i < SAFE_HOSTS.length; i++) {
        var h = SAFE_HOSTS[i];
        if (host === h || host.slice(-(h.length + 1)) === '.' + h) return u.href;
      }
    } catch (e) { /* not a URL */ }
    return null;
  }

  // `s` is already HTML-escaped.
  function inline(s) {
    s = s.replace(/\[([^\]\n]+)\]\(([^)\s]+)\)/g, function (m, label, url) {
      var raw = url.replace(/&amp;/g, '&').replace(/&quot;/g, '"');
      var href = safeHref(raw);
      if (!href) return label;
      return '<a href="' + esc(href) + '" target="_blank" rel="noopener" style="' +
             LINK_STYLE + '">' + label + '</a>';
    });
    return s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  }

  var FOLLOWUPS_RE = /<<\s*FOLLOWUPS\s*:([\s\S]*?)>>/gi;

  // Remove complete follow-up markers and any partial one still streaming in.
  function stripFollowups(text) {
    return String(text || '').replace(FOLLOWUPS_RE, '')
      .replace(/<(<(\s*F[A-Z]*(\s*:[^>]*)?)?)?$/i, '')
      .replace(/<<\s*FOLLOWUPS[\s\S]*$/i, '')
      .trim();
  }
  window.cnAiStrip = stripFollowups;

  window.cnAiFollowups = function (text) {
    var out = [], m;
    FOLLOWUPS_RE.lastIndex = 0;
    while ((m = FOLLOWUPS_RE.exec(String(text || ''))) !== null) {
      m[1].split('|').forEach(function (q) { q = q.trim(); if (q) out.push(q.slice(0, 80)); });
    }
    return out.slice(0, 3);
  };

  window.cnAiFormat = function (text, opts) {
    opts = opts || {};
    text = stripFollowups(text);
    var listStyle = opts.listStyle ? ' style="' + opts.listStyle + '"' : '';
    var out = '', list = null;
    function closeList() { if (list) { out += '</' + list + '>'; list = null; } }

    var lines = esc(text).split('\n');
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      var head   = line.match(/^#{1,4}\s+(.*)/);
      var bullet = line.match(/^\s*[•\-\*]\s+(.*)/);
      var number = line.match(/^\s*\d+[.)]\s+(.*)/);
      if (head) {
        closeList();
        out += '<strong style="display:block;margin:8px 0 3px">' + inline(head[1]) + '</strong>';
      } else if (bullet) {
        if (list !== 'ul') { closeList(); out += '<ul' + listStyle + '>'; list = 'ul'; }
        out += '<li>' + inline(bullet[1]) + '</li>';
      } else if (number) {
        if (list !== 'ol') { closeList(); out += '<ol' + listStyle + '>'; list = 'ol'; }
        out += '<li>' + inline(number[1]) + '</li>';
      } else {
        closeList();
        out += line.trim() ? '<p style="margin:0 0 4px">' + inline(line) + '</p>' : '<br>';
      }
    }
    closeList();
    return out;
  };
})();
