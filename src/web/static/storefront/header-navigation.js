/* Native details is the no-JavaScript fallback; enhancement adds Escape/outside close. */
(() => {
  'use strict';
  document.querySelectorAll('[data-header-menu]').forEach(menu => {
    const toggle = menu.querySelector('summary');
    if (!toggle) return;
    const sync = () => toggle.setAttribute('aria-expanded', String(menu.open));
    const close = returnFocus => {
      if (!menu.open) return;
      menu.open = false; sync();
      if (returnFocus) toggle.focus();
    };
    menu.addEventListener('toggle', sync);
    menu.addEventListener('keydown', event => {
      if (event.key === 'Escape' && menu.open) {
        event.preventDefault(); event.stopPropagation(); close(true);
      }
    });
    menu.addEventListener('click', event => {
      if (event.target.closest('a[href]')) close(false);
    });
    document.addEventListener('pointerdown', event => {
      if (!menu.contains(event.target)) close(false);
    });
    document.addEventListener('focusin', event => {
      if (menu.open && !menu.contains(event.target)) close(false);
    });
    sync();
  });
})();
