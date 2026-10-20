/* Presentation-only forms. No registration, payment or refund is executed. */
(() => {
  document.querySelectorAll('form').forEach(form => {
    if (form.closest('[data-real-auth], [data-real-catalog], [data-real-commerce], [data-real-support]')) return;
    form.setAttribute('autocomplete', 'off');
    form.removeAttribute('action');
  });
})();
