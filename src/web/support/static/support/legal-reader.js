/* Local reading utilities only; no storage, tracking or provider requests. */
(() => {
  'use strict';
  const reader = document.getElementById('legal-reader');
  if (!reader) return;
  document.getElementById('legal-print')?.addEventListener('click', () => window.print());
  const sections = [...reader.querySelectorAll('.legal-section')];
  const links = [...document.querySelectorAll('#tocNav .toc-link')];
  const bar = document.getElementById('readProgress');
  const update = () => {
    const rect = reader.getBoundingClientRect();
    const span = Math.max(1, rect.height - window.innerHeight + 160);
    if (bar) bar.style.width = `${Math.max(0, Math.min(100, (160 - rect.top) / span * 100))}%`;
    let active = sections[0];
    for (const section of sections) {
      if (section.getBoundingClientRect().top <= 200) active = section;
    }
    for (const link of links) {
      const selected = link.hash === `#${active?.id}`;
      link.classList.toggle('bg-surface', selected);
      link.classList.toggle('text-brand-deep', selected);
      link.classList.toggle('font-semibold', selected);
      link.classList.toggle('text-text-muted', !selected);
      if (selected) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    }
  };
  window.addEventListener('scroll', update, {passive: true});
  window.addEventListener('resize', update);
  update();
})();
