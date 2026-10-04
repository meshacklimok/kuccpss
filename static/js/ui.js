/* ============================================================
   CareerNext UI helpers — in-app toast and confirm dialog.
   Replace native alert()/confirm() so prompts match the site
   (and its One UI-style dark mode) instead of browser chrome.

   cnToast(message, type?)        type: info | success | warning | error
   cnConfirm(message, opts?)      → Promise<boolean>
                                  opts: { title, okText, cancelText, danger }

   Declarative confirm: put data-confirm="Question?" on a <form> or
   on its submit button. Optional data-confirm-ok="Remove" sets the
   confirm button label; data-confirm-safe marks a non-destructive action.
   ============================================================ */
(function () {
  'use strict';

  /* ── Toast ─────────────────────────────────────────────── */
  var ICONS = {
    info: 'fa-circle-info', success: 'fa-circle-check',
    warning: 'fa-triangle-exclamation', error: 'fa-circle-exclamation'
  };

  function toastStack() {
    var el = document.getElementById('cn-toast-stack');
    if (!el) {
      el = document.createElement('div');
      el.id = 'cn-toast-stack';
      el.className = 'cn-toast-stack';
      el.setAttribute('aria-live', 'polite');
      document.body.appendChild(el);
    }
    return el;
  }

  window.cnToast = function (message, type) {
    type = ICONS[type] ? type : 'info';
    var t = document.createElement('div');
    t.className = 'cn-toast cn-toast--' + type;
    t.setAttribute('role', type === 'error' ? 'alert' : 'status');

    var icon = document.createElement('i');
    icon.className = 'fas ' + ICONS[type] + ' cn-toast-icon';
    icon.setAttribute('aria-hidden', 'true');
    var msg = document.createElement('div');
    msg.className = 'cn-toast-msg';
    msg.textContent = message;
    var close = document.createElement('button');
    close.type = 'button';
    close.className = 'cn-toast-close';
    close.setAttribute('aria-label', 'Dismiss');
    close.innerHTML = '&times;';

    t.appendChild(icon); t.appendChild(msg); t.appendChild(close);
    toastStack().appendChild(t);
    requestAnimationFrame(function () { t.classList.add('show'); });

    function dismiss() {
      t.classList.remove('show');
      setTimeout(function () { t.remove(); }, 250);
    }
    close.addEventListener('click', dismiss);
    // Errors stay longer; everything is still dismissible by hand.
    setTimeout(dismiss, type === 'error' || type === 'warning' ? 8000 : 4500);
    return t;
  };

  /* ── Confirm dialog ────────────────────────────────────── */
  window.cnConfirm = function (message, opts) {
    opts = opts || {};
    return new Promise(function (resolve) {
      var lastFocus = document.activeElement;
      var backdrop = document.createElement('div');
      backdrop.className = 'cn-dialog-backdrop';

      var dlg = document.createElement('div');
      dlg.className = 'cn-dialog';
      dlg.setAttribute('role', 'alertdialog');
      dlg.setAttribute('aria-modal', 'true');
      dlg.setAttribute('aria-labelledby', 'cn-dialog-title');
      dlg.setAttribute('aria-describedby', 'cn-dialog-msg');

      var title = document.createElement('h2');
      title.id = 'cn-dialog-title';
      title.className = 'cn-dialog-title';
      title.textContent = opts.title || (opts.danger ? 'Are you sure?' : 'Please confirm');
      var body = document.createElement('p');
      body.id = 'cn-dialog-msg';
      body.className = 'cn-dialog-msg';
      body.textContent = message;

      var actions = document.createElement('div');
      actions.className = 'cn-dialog-actions';
      var cancel = document.createElement('button');
      cancel.type = 'button';
      cancel.className = 'cn-dialog-btn';
      cancel.textContent = opts.cancelText || 'Cancel';
      var ok = document.createElement('button');
      ok.type = 'button';
      ok.className = 'cn-dialog-btn cn-dialog-btn--primary' + (opts.danger ? ' cn-dialog-btn--danger' : '');
      ok.textContent = opts.okText || 'OK';
      actions.appendChild(cancel); actions.appendChild(ok);

      dlg.appendChild(title); dlg.appendChild(body); dlg.appendChild(actions);
      backdrop.appendChild(dlg);
      document.body.appendChild(backdrop);
      document.body.classList.add('cn-dialog-open');
      requestAnimationFrame(function () { backdrop.classList.add('show'); });
      ok.focus();

      function finish(result) {
        document.removeEventListener('keydown', onKey, true);
        backdrop.classList.remove('show');
        document.body.classList.remove('cn-dialog-open');
        setTimeout(function () { backdrop.remove(); }, 200);
        if (lastFocus && lastFocus.focus) lastFocus.focus();
        resolve(result);
      }
      function onKey(e) {
        if (e.key === 'Escape') { e.preventDefault(); finish(false); }
        else if (e.key === 'Tab') {            // keep focus inside the dialog
          e.preventDefault();
          (document.activeElement === ok ? cancel : ok).focus();
        }
      }
      document.addEventListener('keydown', onKey, true);
      cancel.addEventListener('click', function () { finish(false); });
      ok.addEventListener('click', function () { finish(true); });
      backdrop.addEventListener('click', function (e) { if (e.target === backdrop) finish(false); });
    });
  };

  /* ── Chart.js dark theme ───────────────────────────────── */
  // Charts hard-code light-mode greys for axis text and grid lines. In dark
  // mode swap those for One UI neutrals; the originals are remembered so
  // switching back to light restores each chart exactly.
  var DARK_TEXT = '#a3a3a3', DARK_LINE = 'rgba(255,255,255,0.08)', DARK_SURFACE = '#171717';

  function swap(obj, key, darkVal, dark) {
    if (!obj) return;
    var store = '_cn_' + key;
    if (dark) {
      if (!(store in obj)) obj[store] = obj[key];
      obj[key] = darkVal;
    } else if (store in obj) {
      obj[key] = obj[store];
      delete obj[store];
    }
  }

  function themeChart(chart, dark, skipUpdate) {
    var o = chart.config.options || {};
    var scales = o.scales || {};
    Object.keys(scales).forEach(function (id) {
      var s = scales[id];
      swap(s.ticks, 'color', DARK_TEXT, dark);
      swap(s.title, 'color', DARK_TEXT, dark);
      swap(s.grid, 'color', DARK_LINE, dark);
      swap(s.grid, 'borderColor', DARK_LINE, dark);
      swap(s.border, 'color', DARK_LINE, dark);
      swap(s.angleLines, 'color', DARK_LINE, dark);
      swap(s.pointLabels, 'color', DARK_TEXT, dark);
      if (s.ticks) swap(s.ticks, 'backdropColor', 'transparent', dark);  // radial tick labels
    });
    var p = o.plugins || {};
    if (p.legend) swap(p.legend.labels, 'color', DARK_TEXT, dark);
    swap(p.title, 'color', DARK_TEXT, dark);
    // Doughnut/pie segment separators default to white
    (chart.data.datasets || []).forEach(function (ds) {
      if (chart.config.type === 'doughnut' || chart.config.type === 'pie' || chart.config.type === 'polarArea') {
        swap(ds, 'borderColor', DARK_SURFACE, dark);
      }
    });
    if (!skipUpdate) chart.update('none');
  }

  function applyChartTheme() {
    if (typeof window.Chart === 'undefined' || !Chart.instances) return;
    var dark = document.body.classList.contains('dark');
    var d = Chart.defaults;
    if (!d._cnLight) d._cnLight = { color: d.color, borderColor: d.borderColor };
    d.color = dark ? DARK_TEXT : d._cnLight.color;
    d.borderColor = dark ? DARK_LINE : d._cnLight.borderColor;
    Object.keys(Chart.instances).forEach(function (k) { themeChart(Chart.instances[k], dark); });
  }
  window.cnApplyChartTheme = applyChartTheme;

  document.addEventListener('cn:themechange', applyChartTheme);
  // Charts that already exist at load are themed directly; the plugin
  // themes any chart created afterwards before its first draw.
  window.addEventListener('load', function () {
    if (typeof window.Chart === 'undefined') return;
    Chart.register({
      id: 'cnTheme',
      beforeInit: function (chart) {
        if (document.body.classList.contains('dark')) themeChart(chart, true, true);
      }
    });
    applyChartTheme();
  });

  /* ── Declarative data-confirm on forms / submit buttons ── */
  // Capture phase: runs before HTMX or inline handlers see the submit.
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (form.dataset.cnConfirmed === '1') { delete form.dataset.cnConfirmed; return; }
    var btn = e.submitter;
    var src = (btn && btn.hasAttribute('data-confirm')) ? btn
            : (form.hasAttribute('data-confirm') ? form : null);
    if (!src) return;

    e.preventDefault();
    e.stopImmediatePropagation();
    window.cnConfirm(src.getAttribute('data-confirm'), {
      okText: src.getAttribute('data-confirm-ok') || 'Confirm',
      danger: !src.hasAttribute('data-confirm-safe')
    }).then(function (yes) {
      if (!yes) return;
      form.dataset.cnConfirmed = '1';
      if (form.requestSubmit) form.requestSubmit(btn && btn.form === form ? btn : undefined);
      else form.submit();
    });
  }, true);
}());
