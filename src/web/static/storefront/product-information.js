/* PDP tabs and brand size guide, with native modal keyboard/focus handling. */
(() => {
  'use strict';
  class ProductInformation {
    constructor(root) {
      this.root = root;
      this.tabsRoot = root.querySelector('[data-product-tabs]');
      this.tabs = Array.from(root.querySelectorAll('[data-information-tab]'));
      this.panels = Array.from(root.querySelectorAll('[data-information-panel]'));
      this.dialog = document.getElementById('sizeGuideModal');
      this.openButton = document.getElementById('openSizeGuideBtn');
      this.tabsRoot.querySelector('[data-information-tablist]').setAttribute('role', 'tablist');
      this.tabs.forEach(button => {
        button.setAttribute('role', 'tab');
        button.setAttribute('aria-controls', `product-${button.dataset.informationTab}`);
        button.addEventListener('click', () => this.activate(button.dataset.informationTab));
        button.addEventListener('keydown', event => {
          if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
          const index = this.tabs.indexOf(button);
          const next = event.key === 'Home' ? 0 : event.key === 'End' ? this.tabs.length - 1
            : (index + (event.key === 'ArrowLeft' ? -1 : 1) + this.tabs.length) % this.tabs.length;
          event.preventDefault(); this.activate(this.tabs[next].dataset.informationTab); this.tabs[next].focus();
        });
      });
      this.panels.forEach(panel => {
        panel.setAttribute('role', 'tabpanel');
        panel.setAttribute('aria-labelledby', `product-tab-${panel.dataset.informationPanel}`);
        panel.tabIndex = 0;
      });
      this.activate('description');
      root.querySelector('[data-review-link]')?.addEventListener('click', event => {
        event.preventDefault(); this.activate('reviews');
        const panel = root.querySelector('#product-reviews'); panel.focus(); panel.scrollIntoView({block: 'start'});
      });
      this.openButton.disabled = false;
      this.openButton.addEventListener('click', () => this.dialog.showModal());
      this.dialog.querySelectorAll('[data-size-guide-close]').forEach(button => button.addEventListener('click', () => this.dialog.close()));
      this.dialog.addEventListener('close', () => this.openButton.focus());
      this.dialog.addEventListener('click', event => {
        if (event.target !== this.dialog) return;
        const rect = this.dialog.getBoundingClientRect();
        if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) this.dialog.close();
      });
      this.dialog.querySelectorAll('[data-guide-unit]').forEach(button => button.addEventListener('click', () => this.setUnit(button.dataset.guideUnit)));
      root.addEventListener('catalog:selection', event => this.markSize(event.detail.size));
      const openFromHash = () => {
        if (window.location.hash === '#sizeGuideModal' && !this.dialog.open) this.dialog.showModal();
        const panel = this.panels.find(item => `#${item.id}` === window.location.hash);
        if (panel) this.activate(panel.dataset.informationPanel);
      };
      window.addEventListener('hashchange', openFromHash);
      openFromHash();
    }
    activate(name) {
      this.tabs.forEach(button => {
        const selected = button.dataset.informationTab === name;
        button.setAttribute('aria-selected', String(selected)); button.tabIndex = selected ? 0 : -1;
        button.classList.toggle('bg-surface-container-lowest', selected);
      });
      this.panels.forEach(panel => { panel.hidden = panel.dataset.informationPanel !== name; });
    }
    setUnit(unit) {
      this.dialog.querySelectorAll('[data-guide-unit]').forEach(button => {
        const selected = button.dataset.guideUnit === unit;
        button.setAttribute('aria-pressed', String(selected));
        button.classList.toggle('bg-primary', selected); button.classList.toggle('text-on-primary', selected);
        button.classList.toggle('text-text-muted', !selected); button.classList.toggle('font-bold', selected);
      });
      this.dialog.querySelectorAll('[data-guide-unit-label]').forEach(label => {
        label.textContent = this.dialog.querySelector(`[data-guide-unit="${unit}"]`).textContent;
      });
      this.dialog.querySelectorAll('[data-measurement-cm]').forEach(cell => { cell.textContent = cell.getAttribute(`data-measurement-${unit}`); });
    }
    markSize(size) {
      this.dialog.querySelectorAll('[data-guide-row]').forEach(row => {
        const selected = row.dataset.guideRow === size;
        row.dataset.selected = String(selected); row.querySelector('[data-guide-selected]').hidden = !selected;
      });
    }
  }
  const boot = () => document.querySelectorAll('main[data-catalog-product="pdp"]').forEach(root => new ProductInformation(root));
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
