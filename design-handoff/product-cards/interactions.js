
  // Quick Size selection handler
  function selectSize(productId, size, stockText, btnElement) {
    const card = document.querySelector(`[data-product-id="${productId}"]`);
    if (!card) return;
    const sizeBtns = card.querySelectorAll('.size-btn');
    sizeBtns.forEach(b => {
      b.classList.remove('active', 'bg-[#183F30]', 'text-white', 'border-[#183F30]');
      b.classList.add('bg-brand-page/50', 'text-brand-dark', 'border-brand-border/80');
      b.setAttribute('aria-checked', 'false');
    });
    btnElement.classList.add('active', 'bg-[#183F30]', 'text-white', 'border-[#183F30]');
    btnElement.classList.remove('bg-brand-page/50', 'text-brand-dark', 'border-brand-border/80');
    btnElement.setAttribute('aria-checked', 'true');
    const statusEl = document.getElementById(`${productId}-stock-status`);
    if (statusEl) {
      statusEl.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-[#183F30]"></span> ${stockText}`;
    }
  }

  // Quick Color selection handler
  function selectColor(productId, colorName, swatchElement) {
    const card = document.querySelector(`[data-product-id="${productId}"]`);
    if (!card) return;
    const swatches = card.querySelectorAll('.color-swatch-btn');
    swatches.forEach(s => {
      s.classList.remove('ring-2', 'ring-offset-2', 'ring-[#183F30]', 'ring-neutral-900', 'ring-[#1A2634]', 'ring-[#1E293B]');
      s.setAttribute('aria-checked', 'false');
    });
    swatchElement.classList.add('ring-2', 'ring-offset-2', 'ring-[#183F30]');
    swatchElement.setAttribute('aria-checked', 'true');
    const labelEl = document.getElementById(`${productId}-color-label`);
    if (labelEl) {
      labelEl.textContent = colorName;
    }
  }

  // Wishlist heart toggle
  function toggleWishlist(btn) {
    const svg = btn.querySelector('svg');
    if (!svg) return;
    const isFavorited = svg.getAttribute('fill') === 'currentColor';
    if (isFavorited) {
      svg.setAttribute('fill', 'none');
      svg.classList.remove('text-red-600');
      svg.classList.add('text-brand-dark');
    } else {
      svg.setAttribute('fill', 'currentColor');
      svg.classList.add('text-red-600');
      svg.classList.remove('text-brand-dark');
    }
  }

  // Quick Buy Add-to-Cart with visual instant feedback & Toast
  function quickAddToCart(productId, title, price) {
    const btn = document.getElementById(`${productId}-add-btn`);
    if (!btn) return;
    const originalHtml = btn.innerHTML;
    btn.innerHTML = `
      <svg class="w-4 h-4 animate-spin text-white" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
      </svg>
      <span>Wird hinzugefügt...</span>
    `;
    btn.disabled = true;
    
    setTimeout(() => {
      btn.innerHTML = `
        <svg class="w-4 h-4 stroke-[2.5] text-[#5CB38C]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"></path>
        </svg>
        <span>Hinzugefügt! ✓</span>
      `;
      btn.classList.add('bg-[#133327]');
      
      // Show Toast
      const toast = document.getElementById('cart-notification-toast');
      const toastTitle = document.getElementById('toast-title');
      const toastDesc = document.getElementById('toast-desc');
      if (toast && toastTitle && toastDesc) {
        toastDesc.textContent = `${title} (${price})`;
        toast.classList.remove('translate-y-24', 'opacity-0');
        toast.classList.add('translate-y-0', 'opacity-100');
        setTimeout(() => {
          toast.classList.add('translate-y-24', 'opacity-0');
          toast.classList.remove('translate-y-0', 'opacity-100');
        }, 3400);
      }
      
      setTimeout(() => {
        btn.innerHTML = originalHtml;
        btn.classList.remove('bg-[#133327]');
        btn.disabled = false;
      }, 2000);
    }, 400);
  }

  // Quick View Modal triggers
  function triggerQuickView(title, price) {
    const modal = document.getElementById('quick-view-modal');
    const box = document.getElementById('quick-view-box');
    const titleEl = document.getElementById('modal-product-title');
    const priceEl = document.getElementById('modal-product-price');
    if (modal && box && titleEl && priceEl) {
      titleEl.textContent = title;
      priceEl.textContent = price;
      modal.classList.remove('hidden');
      setTimeout(() => {
        box.classList.remove('scale-95');
        box.classList.add('scale-100');
      }, 10);
    }
  }

  function closeQuickView() {
    const modal = document.getElementById('quick-view-modal');
    const box = document.getElementById('quick-view-box');
    if (modal && box) {
      box.classList.remove('scale-100');
      box.classList.add('scale-95');
      setTimeout(() => {
        modal.classList.add('hidden');
      }, 200);
    }
  }
