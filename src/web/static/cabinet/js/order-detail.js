(() => {
  document.querySelectorAll('[data-copy-target]').forEach(button => {
    button.addEventListener('click', async () => {
      const target = document.getElementById(button.dataset.copyTarget);
      const status = button.closest('details').querySelector('[data-copy-status]');
      if (!target || !status) return;
      try {
        await navigator.clipboard.writeText(target.textContent.trim());
        status.textContent = status.dataset.copied;
      } catch {
        status.textContent = status.dataset.copyFailed;
      }
    });
  });
})();
