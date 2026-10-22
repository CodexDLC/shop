/* PDP-only photo controls. Mini-card horizontal gestures remain product navigation. */
(() => {
  'use strict';
  class ProductGallery {
    constructor(root) {
      this.root = root;
      this.product = root.closest('[data-catalog-product]');
      this.rail = root.querySelector('[data-gallery-thumbnails]');
      this.main = root.querySelector('[data-gallery-main]');
      this.dialog = root.querySelector('[data-gallery-dialog]');
      this.enlarged = root.querySelector('[data-gallery-enlarged]');
      this.zoom = root.querySelector('[data-gallery-zoom]');
      this.color = root.dataset.galleryColor;
      this.images = Array.from(this.rail.querySelectorAll('[data-gallery-thumbnail]'), a => a.getAttribute('href'));
      this.index = 0;
      this.alt = this.main.alt;
      this.alts = {};
      this.root.addEventListener('click', event => this.click(event));
      this.product.addEventListener('catalog:gallery', event => this.update(event.detail));
      this.dialog.addEventListener('keydown', event => {
        if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
          event.preventDefault(); this.select(this.index + (event.key === 'ArrowLeft' ? -1 : 1));
        }
      });
      this.dialog.addEventListener('close', () => this.zoom.focus());
      this.dialog.addEventListener('click', event => {
        if (event.target !== this.dialog) return;
        const rect = this.dialog.getBoundingClientRect();
        if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) this.dialog.close();
      });
      this.main.addEventListener('error', () => { this.main.hidden = true; this.message('[data-gallery-error]', true); });
      this.main.addEventListener('load', () => { this.main.hidden = !this.images.length; this.message('[data-gallery-error]', false); });
      this.enlarged.addEventListener('error', () => { this.enlarged.hidden = true; this.message('[data-gallery-dialog-error]', true); });
      this.enlarged.addEventListener('load', () => { this.enlarged.hidden = !this.images.length; this.message('[data-gallery-dialog-error]', false); });
      this.select(0);
      // A server-rendered image can fail before deferred handlers are attached.
      if (this.main.getAttribute('src') && this.main.complete && this.main.naturalWidth === 0) {
        this.main.hidden = true;
        this.message('[data-gallery-error]', true);
      }
    }
    message(selector, visible) { this.root.querySelector(selector).hidden = !visible; }
    update({color, gallery, alt, alts = {}}) {
      const previous = this.images[this.index];
      const colorChanged = color !== this.color;
      const changed = colorChanged || JSON.stringify(gallery) !== JSON.stringify(this.images);
      this.alt = alt;
      this.alts = alts;
      if (!changed) { this.select(this.index); return; }
      this.color = color;
      this.images = [...gallery];
      this.rail.replaceChildren();
      this.images.forEach((url, index) => {
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.dataset.galleryThumbnail = '';
        anchor.className = 'relative w-16 h-20 sm:w-20 sm:h-24 bg-surface-muted p-1 transition-all shrink-0';
        anchor.setAttribute('aria-label', `${this.rail.dataset.galleryPhotoLabel} ${index + 1}`);
        const image = document.createElement('img');
        image.src = url; image.alt = alts[url] || alt; image.loading = 'lazy'; image.className = 'w-full h-full object-cover';
        anchor.append(image); this.rail.append(anchor);
      });
      this.select(colorChanged ? 0 : Math.max(0, this.images.indexOf(previous)));
    }
    select(index) {
      this.index = Math.max(0, Math.min(index, this.images.length - 1));
      const url = this.images[this.index];
      this.message('[data-gallery-empty]', !url);
      this.zoom.disabled = !url;
      [[this.main, '[data-gallery-error]'], [this.enlarged, '[data-gallery-dialog-error]']].forEach(([image, error]) => {
        image.alt = this.alts[url] || this.alt;
        // A failed source stays failed until a different source or a load event.
        // Reselecting the same thumbnail must not expose a broken image.
        if (!url || image.getAttribute('src') !== url) {
          image.hidden = !url;
          this.message(error, false);
          if (url) image.src = url;
          else image.removeAttribute('src');
        }
      });
      this.rail.querySelectorAll('[data-gallery-thumbnail]').forEach((anchor, i) => {
        anchor.setAttribute('aria-current', String(i === this.index));
      });
      this.root.querySelector('[data-gallery-count]').textContent = url ? `${this.index + 1} / ${this.images.length}` : '';
      this.root.querySelector('[data-gallery-previous]').disabled = this.index === 0;
      this.root.querySelector('[data-gallery-next]').disabled = this.index >= this.images.length - 1;
      if (!url && this.dialog.open) this.dialog.close();
    }
    click(event) {
      const thumbnail = event.target.closest('[data-gallery-thumbnail]');
      if (thumbnail && this.rail.contains(thumbnail)) {
        event.preventDefault(); this.select(Array.from(this.rail.children).indexOf(thumbnail));
      } else if (event.target.closest('[data-gallery-zoom]') && this.images.length) {
        this.dialog.showModal();
      } else if (event.target.closest('[data-gallery-close]')) this.dialog.close();
      else if (event.target.closest('[data-gallery-previous]')) this.select(this.index - 1);
      else if (event.target.closest('[data-gallery-next]')) this.select(this.index + 1);
    }
  }
  const boot = () => document.querySelectorAll('[data-product-gallery]').forEach(root => new ProductGallery(root));
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
