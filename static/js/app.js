/* EmployeeManager — comportements communs */
(function () {
  'use strict';

  // Thème clair / sombre
  function applyTheme(theme) {
    document.documentElement.setAttribute('data-bs-theme', theme);
    try { localStorage.setItem('em-theme', theme); } catch (e) { /* stockage indisponible */ }
    document.querySelectorAll('[data-theme-icon]').forEach(function (icon) {
      icon.className = theme === 'dark' ? 'bi bi-sun' : 'bi bi-moon-stars';
    });
    document.dispatchEvent(new CustomEvent('em:theme', { detail: theme }));
  }
  document.addEventListener('click', function (event) {
    if (event.target.closest('[data-theme-toggle]')) {
      var current = document.documentElement.getAttribute('data-bs-theme');
      applyTheme(current === 'dark' ? 'light' : 'dark');
    }
  });
  applyTheme(document.documentElement.getAttribute('data-bs-theme') || 'light');

  // Barre latérale sur mobile
  document.addEventListener('click', function (event) {
    if (event.target.closest('[data-sidebar-toggle]')) {
      document.body.classList.toggle('sidebar-open');
    } else if (event.target.closest('[data-sidebar-close]')) {
      document.body.classList.remove('sidebar-open');
    }
  });

  // Confirmation avant les actions sensibles
  document.addEventListener('submit', function (event) {
    var form = event.target;
    var message = form.getAttribute('data-confirm');
    if (message && !window.confirm(message)) {
      event.preventDefault();
    }
  });

  // Filtres appliqués automatiquement
  document.querySelectorAll('[data-autosubmit]').forEach(function (element) {
    element.addEventListener('change', function () { element.form.submit(); });
  });

  // Info-bulles Bootstrap
  if (window.bootstrap) {
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
      new window.bootstrap.Tooltip(el);
    });
  }

  // Ouvre l'onglet indiqué dans l'URL (#documents, #contrats...)
  if (window.location.hash && window.bootstrap) {
    var trigger = document.querySelector('[data-bs-target="' + window.location.hash + '"]');
    if (trigger) { window.bootstrap.Tab.getOrCreateInstance(trigger).show(); }
  }
  document.querySelectorAll('[data-bs-toggle="tab"]').forEach(function (tab) {
    tab.addEventListener('shown.bs.tab', function () {
      history.replaceState(null, '', tab.getAttribute('data-bs-target'));
    });
  });

  // Horloge temps réel (pointage)
  var clocks = document.querySelectorAll('[data-clock]');
  if (clocks.length) {
    var tick = function () {
      var now = new Date();
      var text = now.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      clocks.forEach(function (c) { c.textContent = text; });
    };
    tick();
    setInterval(tick, 1000);
  }

  // Jeton CSRF pour les appels fetch
  window.emCsrfToken = function () {
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    if (match) { return decodeURIComponent(match[1]); }
    var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : '';
  };

  // Copie dans le presse-papiers
  document.addEventListener('click', function (event) {
    var button = event.target.closest('[data-copy]');
    if (!button) { return; }
    navigator.clipboard.writeText(button.getAttribute('data-copy')).then(function () {
      var original = button.innerHTML;
      button.innerHTML = '<i class="bi bi-check2"></i> Copié';
      setTimeout(function () { button.innerHTML = original; }, 1500);
    });
  });
})();
