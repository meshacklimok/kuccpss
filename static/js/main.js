// KUCCPSS — Global JavaScript

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

function getCsrf() {
  var cookie = document.cookie.split(';').find(function (c) { return c.trim().startsWith('csrftoken='); });
  return cookie ? cookie.trim().split('=')[1] : '';
}
