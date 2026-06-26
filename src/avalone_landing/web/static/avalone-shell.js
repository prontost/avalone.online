/* Avalone shared shell JS */

(function() {
  'use strict';

  const $ = (id) => document.getElementById(id);

  // Theme
  function initTheme() {
    const saved = localStorage.getItem('avalone_theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const isDark = saved ? saved === 'dark' : prefersDark;
    document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
  }

  window.toggleTheme = function() {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('avalone_theme', next);
  };

  // App switcher
  function initAppSwitcher() {
    const switcher = document.querySelector('.avalone-app-switcher');
    if (!switcher) return;
    const btn = switcher.querySelector('.avalone-app-switcher__btn');
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      switcher.classList.toggle('open');
    });
    document.addEventListener('click', () => switcher.classList.remove('open'));
  }

  // Profile menu
  function initProfileMenu() {
    const profile = document.querySelector('.avalone-profile');
    if (!profile) return;
    const avatar = profile.querySelector('.avalone-profile__avatar');
    const menu = profile.querySelector('.avalone-profile__menu');
    if (!menu || !avatar) return;
    avatar.addEventListener('click', (e) => {
      e.stopPropagation();
      const isOpen = menu.classList.toggle('open');
      avatar.setAttribute('aria-expanded', String(isOpen));
    });
    document.addEventListener('click', () => {
      menu.classList.remove('open');
      avatar.setAttribute('aria-expanded', 'false');
    });
  }

  // Notifications
  async function updateNotificationCount() {
    const badge = document.querySelector('.avalone-notifications__count');
    if (!badge) return;
    try {
      const res = await fetch('/api/notifications/unread-count', { credentials: 'same-origin' });
      if (!res.ok) return;
      const data = await res.json();
      const count = data.count || 0;
      badge.textContent = count > 99 ? '99+' : String(count);
      badge.style.display = count ? 'inline-flex' : 'none';
    } catch (e) {
      // silently fail
    }
  }

  window.openNotifications = function() {
    const panel = document.querySelector('.avalone-notifications__panel');
    if (panel) panel.classList.toggle('open');
  };

  // Language
  window.setLang = function(lang) {
    localStorage.setItem('avalone_lang', lang);
    document.documentElement.lang = lang === 'auto' ? 'ru' : lang;
    if (window.applyLang) window.applyLang(lang);
  };

  // Search
  window.openGlobalSearch = function() {
    const panel = document.querySelector('.avalone-search__panel');
    if (panel) panel.classList.add('open');
    const input = document.querySelector('.avalone-search__panel input');
    if (input) input.focus();
  };

  function init() {
    initTheme();
    initAppSwitcher();
    initProfileMenu();
    updateNotificationCount();
    setInterval(updateNotificationCount, 60000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
