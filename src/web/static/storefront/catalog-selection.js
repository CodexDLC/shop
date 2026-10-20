/* Variant presentation and local-cart handoff. Server validation remains authoritative. */
(() => {
  'use strict';
  const boot = () => {
    const source = document.getElementById('catalog-products');
    if (!source) return;
    let products, texts;
    try {
      products = JSON.parse(source.textContent);
      texts = JSON.parse(document.getElementById('catalog-selection-texts')?.textContent || '{}');
    } catch (_) { return; }
    const money = (value, currency = 'EUR') => {
      const amount = Number(value);
      return value !== null && value !== undefined && Number.isFinite(amount)
        ? new Intl.NumberFormat(document.documentElement.lang || 'de', {style: 'currency', currency}).format(amount)
        : String(value || '');
    };
    document.querySelectorAll('[data-catalog-product]').forEach(root => {
      const code = root.dataset.productCode || root.dataset.catalogProduct;
      const product = products[code];
      if (!product) return;
      let color = product.default_color || '', size = product.default_size || '';
      let variant = null, controller, sequence = 0, validated = false;
      const setText = (selector, value) => root.querySelectorAll(selector).forEach(el => { el.textContent = value || ''; });
      const update = async (initial = false) => {
        const requestSequence = ++sequence;
        controller?.abort(); controller = new AbortController(); validated = false;
        variant = product.variants.find(item => item.color === color && item.size === size) || null;
        const selectedColor = product.colors.find(item => item.code === color);
        const gallery = product.galleries[color] || [];
        root.dataset.selectedSku = variant?.sku || '';
        root.dataset.selectedColor = color;
        root.dataset.selectedSize = size;
        root.dataset.gallery = JSON.stringify(gallery);
        setText('[data-color-label], [data-product-color-label]', selectedColor?.label || '');
        setText('[data-product-size-label]', size);
        setText('[data-product-sku]', variant?.sku || '');
        setText('[data-product-price]', money(variant?.price ?? product.price, variant?.currency));
        setText('[data-action-label]', texts.cart_action);
        setText('[data-stock-status], [data-product-availability]', variant ? (variant.available ? texts.available : texts.unavailable) : texts.select_variant);
        root.querySelectorAll('[data-product-photo]').forEach(img => {
          const url = gallery[0];
          img.hidden = !url;
          if (url) img.src = url;
          else img.removeAttribute('src');
          img.alt = [product.name, selectedColor?.label].filter(Boolean).join(' — ');
        });
        root.querySelectorAll('[data-color]').forEach(button => {
          const selected = button.dataset.color === color;
          button.setAttribute(button.getAttribute('role') === 'radio' ? 'aria-checked' : 'aria-pressed', String(selected));
          button.style.outline = selected ? '2px solid #183F30' : '';
          button.style.outlineOffset = selected ? '2px' : '';
        });
        root.querySelectorAll('[data-size]').forEach(button => {
          const selected = button.dataset.size === size;
          const candidate = product.variants.find(item => item.color === color && item.size === button.dataset.size);
          button.setAttribute(button.getAttribute('role') === 'radio' ? 'aria-checked' : 'aria-pressed', String(selected));
          button.dataset.available = String(Boolean(candidate?.available));
          button.style.opacity = candidate?.available ? '' : '0.45';
          button.style.backgroundColor = selected ? '#183F30' : '';
          button.style.color = selected ? '#ffffff' : '';
          button.classList.toggle('active', selected);
          ['bg-[#183F30]', 'text-white', 'border-[#183F30]'].forEach(name => button.classList.toggle(name, selected));
          ['bg-brand-page/50', 'text-brand-dark', 'border-brand-border/80'].forEach(name => button.classList.toggle(name, !selected));
        });
        root.querySelectorAll('[data-product-action]').forEach(button => {
          button.disabled = true;
          button.style.opacity = button.disabled ? '0.5' : '';
          button.style.cursor = button.disabled ? 'not-allowed' : '';
        });
        root.dispatchEvent(new CustomEvent('catalog:selection', {detail: {product, color, size, variant, gallery}}));
        // Listing HTML already contains the server-selected ORM snapshot. Do not
        // multiply the page's bounded SQL reads by fetching every card on boot.
        // The subsequent POST always rechecks SKU, price and available quantity.
        if (initial && root.hasAttribute('data-preview-only')) {
          validated = Boolean(variant);
          root.querySelectorAll('[data-product-action]').forEach(button => {
            button.disabled = !variant?.available;
            button.style.opacity = button.disabled ? '0.5' : '';
            button.style.cursor = button.disabled ? 'not-allowed' : '';
          });
          return;
        }
        setText('[data-stock-status], [data-product-availability]', texts.loading);
        try {
          const url = new URL(product.preview_url, window.location.href);
          url.searchParams.set('color', color); url.searchParams.set('size', size);
          const response = await fetch(url, {signal: controller.signal, headers: {Accept: 'application/json'}});
          const result = await response.json();
          if (requestSequence !== sequence) return;
          if (!response.ok && result.error?.code === 'catalog.variant_not_found') {
            root.dataset.selectedSku = '';
            setText('[data-product-sku]', '');
            setText('[data-stock-status], [data-product-availability]', result.error.message || texts.unavailable);
            return;
          }
          if (!response.ok || !result.variant || result.variant.color !== color || result.variant.size !== size) throw new Error('selection');
          variant = {...result.variant, available: Boolean(result.variant.active && result.variant.demo_available)};
          validated = true;
          root.dataset.selectedSku = variant.sku || '';
          setText('[data-product-sku]', variant.sku);
          setText('[data-product-price]', money(variant.price, variant.currency));
          setText('[data-action-label]', texts.cart_action);
          setText('[data-stock-status], [data-product-availability]', variant.available ? texts.available : texts.unavailable);
          root.querySelectorAll('[data-product-action]').forEach(button => {
            button.disabled = !variant.available; button.style.opacity = button.disabled ? '0.5' : '';
            button.style.cursor = button.disabled ? 'not-allowed' : '';
          });
          const confirmedGallery = result.gallery?.images || [];
          root.querySelectorAll('[data-product-photo]').forEach(img => {
            img.hidden = !confirmedGallery.length;
            if (confirmedGallery.length) img.src = confirmedGallery[0]; else img.removeAttribute('src');
          });
          root.dataset.gallery = JSON.stringify(confirmedGallery);
        } catch (error) {
          if (requestSequence !== sequence || error.name === 'AbortError') return;
          root.dataset.selectedSku = '';
          setText('[data-product-sku]', '');
          setText('[data-stock-status], [data-product-availability]', texts.error);
        }

      };
      root.addEventListener('click', event => {
        const wish = event.target.closest('[data-wishlist-product]');
        if (wish) {
          event.preventDefault();
          const form = document.getElementById('shop-save-wishlist');
          if (form && product.id) { form.elements.product_id.value = String(product.id); form.requestSubmit(); }
          return;
        }
        const quantityStep = event.target.closest('[data-quantity-step]');
        if (quantityStep) {
          const label = root.querySelector('[data-product-quantity]');
          if (label) label.textContent = String(Math.max(1, Math.min(20,
            Number(label.textContent || '1') + Number(quantityStep.dataset.quantityStep))));
          return;
        }
        const colorButton = event.target.closest('[data-color]');
        const sizeButton = event.target.closest('[data-size]');
        if (colorButton && root.contains(colorButton)) { color = colorButton.dataset.color; update(); }
        if (sizeButton && root.contains(sizeButton)) { size = sizeButton.dataset.size; update(); }
        const quickView = event.target.closest('[data-product-quick-view]');
        if (quickView && typeof window.triggerQuickView === 'function') {
          window.triggerQuickView(product.name, money(variant?.price || product.price, variant?.currency));
          const modal = document.getElementById('quick-view-modal');
          if (modal) modal.dataset.detailUrl = product.detail_url;
        }
        if (event.target.closest('[data-product-action]') && validated && variant?.available) {
          event.preventDefault();
          const form = document.getElementById('shop-add-to-cart');
          if (!form) { setText('[data-product-availability]', texts.error); return; }
          form.elements.sku.value = variant.sku;
          form.elements.quantity.value = root.querySelector('[data-product-quantity]')?.textContent.trim() || '1';
          root.querySelectorAll('[data-product-action]').forEach(button => { button.disabled = true; });
          form.requestSubmit();
        }
      });
      // Native buttons keep all options keyboard reachable; arrows follow radio-group conventions.
      root.addEventListener('keydown', event => {
        if (!['ArrowRight', 'ArrowLeft', 'ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
        const current = event.target.closest('[data-color], [data-size]');
        if (!current) return;
        const selector = current.hasAttribute('data-color') ? '[data-color]' : '[data-size]';
        const buttons = Array.from(root.querySelectorAll(selector));
        const step = ['ArrowLeft', 'ArrowUp'].includes(event.key) ? -1 : 1;
        const index = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 : (buttons.indexOf(current) + step + buttons.length) % buttons.length;
        event.preventDefault(); buttons[index].focus(); buttons[index].click();
      });
      update(true);
    });
    const modal = document.getElementById('quick-view-modal');
    modal?.querySelector('.space-y-3 button')?.addEventListener('click', event => {
      if (!modal.dataset.detailUrl) return;
      event.preventDefault(); event.stopImmediatePropagation();
      window.location.href = modal.dataset.detailUrl;
    }, true);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
