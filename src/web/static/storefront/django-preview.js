/* Presentation-only forms. No registration, payment or refund is executed. */
(() => {
  document.querySelectorAll('form').forEach(form => {
    if (form.closest('[data-real-auth]')) return;
    form.setAttribute('autocomplete', 'off');
    form.removeAttribute('action');
  });
})();
