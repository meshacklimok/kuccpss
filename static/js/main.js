// CareerNext — Global JavaScript

document.addEventListener('DOMContentLoaded', function () {

  // Auto-dismiss flash messages after 5s
  setTimeout(function () {
    document.querySelectorAll('.messages-container .alert').forEach(function (el) {
      var bsAlert = bootstrap.Alert.getOrCreateInstance(el);
      if (bsAlert) bsAlert.close();
    });
  }, 5000);

  // Highlight active nav link based on current path
  var path = window.location.pathname;
  document.querySelectorAll('.site-navbar .nav-link').forEach(function (link) {
    if (link.getAttribute('href') && path.startsWith(link.getAttribute('href')) && link.getAttribute('href') !== '/') {
      link.classList.add('active');
    }
  });

  // Highlight active mobile bottom nav link
  document.querySelectorAll('.mobile-bottom-nav a').forEach(function (link) {
    if (link.getAttribute('href') && path.startsWith(link.getAttribute('href')) && link.getAttribute('href') !== '/') {
      link.classList.add('active');
    }
  });

  // Course save/bookmark toggle (AJAX)
  document.querySelectorAll('[data-save-course]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var courseId = this.dataset.saveCourse;
      var icon = this.querySelector('i');
      fetch('/accounts/save-course/' + courseId + '/', {
        method: 'POST',
        headers: { 'X-CSRFToken': getCsrf(), 'X-Requested-With': 'XMLHttpRequest' }
      })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.saved) {
          icon.classList.replace('fa-regular', 'fa-solid');
          btn.title = 'Remove from saved';
        } else {
          icon.classList.replace('fa-solid', 'fa-regular');
          btn.title = 'Save course';
        }
      });
    });
  });

  // Career profile save toggle (AJAX)
  document.querySelectorAll('[data-save-career]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var profileId = this.dataset.saveCareer;
      var icon = this.querySelector('i');
      fetch('/accounts/save-career/' + profileId + '/', {
        method: 'POST',
        headers: { 'X-CSRFToken': getCsrf(), 'X-Requested-With': 'XMLHttpRequest' }
      })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.saved) {
          icon.classList.replace('fa-regular', 'fa-solid');
        } else {
          icon.classList.replace('fa-solid', 'fa-regular');
        }
      });
    });
  });

  // Initialize all Bootstrap tooltips
  document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
    new bootstrap.Tooltip(el);
  });

  // ── Scroll-reveal: only cards that start below the fold ──
  if ('IntersectionObserver' in window) {
    var revealObs = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          revealObs.unobserve(entry.target);
        }
      });
    }, { threshold: 0.08 });

    document.querySelectorAll('.card').forEach(function (card, i) {
      if (card.getBoundingClientRect().top > window.innerHeight) {
        card.classList.add('reveal');
        // stagger within groups of 4
        card.style.transitionDelay = (i % 4) * 70 + 'ms';
        revealObs.observe(card);
      }
    });
  }

  // ── Stat counter for [data-count] elements ──
  if ('IntersectionObserver' in window) {
    var countObs = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        var el = entry.target;
        var target = parseInt(el.dataset.count, 10);
        var duration = 1200;
        var start = performance.now();
        function tick(now) {
          var p = Math.min((now - start) / duration, 1);
          var eased = 1 - Math.pow(1 - p, 3);
          el.textContent = Math.round(eased * target).toLocaleString();
          if (p < 1) requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);
        countObs.unobserve(el);
      });
    }, { threshold: 0.5 });

    document.querySelectorAll('[data-count]').forEach(function (el) {
      countObs.observe(el);
    });
  }

});

// ── Web Push Subscription ───────────────────────────────────────────────────
(function () {
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;
  if (Notification.permission === 'denied') return;

  var PUSH_ASKED = 'cn-push-asked';
  if (localStorage.getItem(PUSH_ASKED)) return;

  var vapidKey = (document.getElementById('vapid-public-key') || {}).content;
  if (!vapidKey) return;

  function urlB64ToUint8Array(base64String) {
    var padding = '='.repeat((4 - base64String.length % 4) % 4);
    var base64  = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    var raw     = atob(base64);
    var arr     = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
    return arr;
  }

  function doSubscribe() {
    navigator.serviceWorker.ready.then(function (reg) {
      return reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlB64ToUint8Array(vapidKey),
      });
    }).then(function (sub) {
      var json = sub.toJSON();
      return fetch('/accounts/push/subscribe/', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
        body:    JSON.stringify(json),
      });
    }).then(function () {
      localStorage.setItem(PUSH_ASKED, '1');
    }).catch(function () {
      localStorage.setItem(PUSH_ASKED, '1');
    });
  }

  // Ask after 12 seconds — after user has settled on the page
  setTimeout(function () {
    if (Notification.permission === 'granted') {
      doSubscribe();
      return;
    }
    Notification.requestPermission().then(function (p) {
      localStorage.setItem(PUSH_ASKED, '1');
      if (p === 'granted') doSubscribe();
    });
  }, 12000);
})();

// ── PWA Install Prompt ──────────────────────────────────────────────────────
(function () {
  var DISMISS_KEY   = 'cn-install-dismissed';
  var DISMISS_COUNT = 'cn-install-dismiss-count';

  // Already installed (running standalone) — do nothing
  if (window.matchMedia('(display-mode: standalone)').matches) return;
  if (window.navigator.standalone === true) return; // iOS standalone

  // Dismissed recently? 1st dismiss = 7 days, 2nd+ = 4 days
  var ts    = parseInt(localStorage.getItem(DISMISS_KEY) || '0', 10);
  var count = parseInt(localStorage.getItem(DISMISS_COUNT) || '0', 10);
  var wait  = count >= 1 ? 4 : 7;
  if (ts && Date.now() - ts < wait * 864e5) return;

  var banner       = document.getElementById('pwa-install-banner');
  var installBtn   = document.getElementById('pwa-install-btn');
  var dismissBtn   = document.getElementById('pwa-dismiss-btn');
  var iosModal     = document.getElementById('pwa-ios-modal');
  var iosClose     = document.getElementById('pwa-ios-close');
  var deferredEvt  = null;

  function dismiss() {
    var n = parseInt(localStorage.getItem(DISMISS_COUNT) || '0', 10);
    localStorage.setItem(DISMISS_COUNT, (n + 1).toString());
    localStorage.setItem(DISMISS_KEY, Date.now().toString());
    if (banner) banner.hidden = true;
    if (iosModal) iosModal.hidden = true;
  }

  // Android / Desktop Chrome — capture the event
  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault();
    deferredEvt = e;
    if (!banner) return;
    setTimeout(function () { banner.hidden = false; }, 4000);
  });

  if (installBtn) {
    installBtn.addEventListener('click', function () {
      if (!deferredEvt) return;
      deferredEvt.prompt();
      deferredEvt.userChoice.then(function (choice) {
        if (choice.outcome === 'accepted') dismiss();
        deferredEvt = null;
        if (banner) banner.hidden = true;
      });
    });
  }

  if (dismissBtn) dismissBtn.addEventListener('click', dismiss);

  // iOS Safari — no beforeinstallprompt, show manual modal instead
  var isIos = /iphone|ipad|ipod/i.test(navigator.userAgent);
  var isSafari = /^((?!chrome|android).)*safari/i.test(navigator.userAgent);
  if (isIos && isSafari && iosModal) {
    setTimeout(function () { iosModal.hidden = false; }, 5000);
    if (iosClose) iosClose.addEventListener('click', dismiss);
    iosModal.addEventListener('click', function (e) {
      if (e.target === iosModal) dismiss();
    });
  }

  // Hide banner once the app is installed
  window.addEventListener('appinstalled', function () { dismiss(); });
})();

function getCsrf() {
  var cookie = document.cookie.split(';').find(function (c) { return c.trim().startsWith('csrftoken='); });
  return cookie ? cookie.trim().split('=')[1] : '';
}
