/* LAN browser presentation only. Keep upstream navigation and playback handlers. */
(function () {
  'use strict';
  var root = document.documentElement;
  var shell = document.querySelector('.app-shell');
  var sidebar = document.querySelector('.sidebar');
  var surface = document.getElementById('main-surface');
  if (!shell || !sidebar || !surface || document.getElementById('ow-mobile-header')) return;
  var media = window.matchMedia('(max-width: 900px)');
  var header = document.createElement('header');
  header.id = 'ow-mobile-header';
  header.className = 'ow-mobile-header';
  var toggle = document.createElement('button');
  toggle.type = 'button'; toggle.className = 'ow-mobile-menu';
  toggle.textContent = '☰'; toggle.setAttribute('aria-label', '打开导航');
  toggle.setAttribute('aria-expanded', 'false');
  sidebar.id = sidebar.id || 'ow-mobile-sidebar';
  toggle.setAttribute('aria-controls', sidebar.id);
  var title = document.createElement('strong'); title.className = 'ow-mobile-title';
  title.textContent = '红果短剧';
  var search = document.createElement('button');
  search.type = 'button'; search.className = 'ow-mobile-search'; search.textContent = '找剧';
  search.setAttribute('aria-label', '搜索短剧');
  header.appendChild(toggle); header.appendChild(title); header.appendChild(search);
  var shade = document.createElement('button');
  shade.type = 'button'; shade.className = 'ow-mobile-shade';
  shade.setAttribute('aria-label', '关闭导航'); shade.tabIndex = -1; shade.hidden = true;
  document.body.insertBefore(header, document.body.firstChild);
  document.body.appendChild(shade);
  var opened = false;
  function menu(value, restoreFocus) {
    opened = !!value && media.matches;
    root.classList.toggle('ow-menu-open', opened);
    toggle.setAttribute('aria-expanded', String(opened));
    toggle.setAttribute('aria-label', opened ? '关闭导航' : '打开导航');
    shade.hidden = !opened;
    sidebar.inert = media.matches && !opened;
    if (media.matches && !opened) sidebar.setAttribute('aria-hidden', 'true');
    else sidebar.removeAttribute('aria-hidden');
    surface.inert = opened;
    if (opened) {
      var first = sidebar.querySelector('.side-item.is-active') || sidebar.querySelector('.side-item');
      if (first) first.focus();
    } else if (restoreFocus && media.matches) toggle.focus();
  }
  function sync() {
    var active = sidebar.querySelector('.side-item.is-active');
    title.textContent = active ? (active.getAttribute('aria-label') || active.textContent.trim()) : '红果短剧';
    root.classList.toggle('ow-cinema', shell.classList.contains('is-cinema'));
  }
  function viewport() {
    var visual = window.visualViewport;
    if (!visual || visual.scale === 1) root.style.setProperty('--ow-viewport', (visual ? visual.height : window.innerHeight) + 'px');
  }
  toggle.addEventListener('click', function () { menu(!opened); });
  shade.addEventListener('click', function () { menu(false, true); });
  sidebar.addEventListener('click', function (event) {
    if (event.target.closest('.side-item[data-page]')) { menu(false); sync(); }
  });
  search.addEventListener('click', function () {
    menu(false);
    var button = sidebar.querySelector('[data-page="search"]');
    if (button) button.click();
    var input = document.getElementById('search-input');
    if (input) input.focus();
  });
  document.addEventListener('keydown', function (event) {
    if (!opened) return;
    if (event.key === 'Escape') {
      event.preventDefault(); event.stopImmediatePropagation(); menu(false, true);
    } else if (event.key === 'Tab') {
      var items = [toggle].concat(Array.prototype.filter.call(sidebar.querySelectorAll('button, a, input, [tabindex]'), function (item) {
        return !item.disabled && item.tabIndex >= 0 && item.getClientRects().length > 0;
      }));
      var index = items.indexOf(document.activeElement);
      if (event.shiftKey && index <= 0 || !event.shiftKey && index === items.length - 1) {
        event.preventDefault(); items[event.shiftKey ? items.length - 1 : 0].focus();
      }
    }
  }, true);
  function resized() { menu(false); viewport(); sync(); }
  if (media.addEventListener) media.addEventListener('change', resized);
  else media.addListener(resized);
  window.addEventListener('resize', viewport);
  if (window.visualViewport) window.visualViewport.addEventListener('resize', viewport);
  document.querySelectorAll('video').forEach(function (video) {
    video.setAttribute('playsinline', ''); video.setAttribute('webkit-playsinline', '');
  });
  if (window.MutationObserver) {
    new MutationObserver(sync).observe(sidebar, { subtree: true, attributes: true, attributeFilter: ['class'] });
    new MutationObserver(sync).observe(shell, { attributes: true, attributeFilter: ['class'] });
  }
  root.classList.add('openwrt-web');
  resized();
}());
