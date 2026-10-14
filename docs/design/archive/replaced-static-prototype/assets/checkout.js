(() => {
'use strict';
const shop = window.ShopDemo;
if (!shop) return;
const page = document.body.dataset.checkoutPage;
const money = shop.money;
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const read = key => { try { return JSON.parse(sessionStorage.getItem(key) || 'null'); } catch { return null; } };
const lines = () => shop.getCart().map(item => ({...item, product: shop.products.find(p => p.id === item.id)})).filter(item => item.product);
const subtotal = items => items.reduce((sum,item) => sum + Math.round(item.product.price * 100) * item.qty, 0) / 100;
const shipping = 4.90;
function summary(items) {
 const element = document.querySelector('#order-summary'); if (!element) return;
 const sub = subtotal(items);
 element.innerHTML = `<h2 class="section-title">Zusammenfassung</h2><dl class="sum-lines"><div><dt>Artikel</dt><dd>${money(sub)}</dd></div><div><dt>Versand (Demo)</dt><dd>${items.length ? money(shipping) : money(0)}</dd></div><div class="sum-total"><dt>Gesamt</dt><dd>${money(sub + (items.length ? shipping : 0))}</dd></div></dl><p class="muted">Demopreise; keine verbindliche Steuer- oder Versandberechnung.</p>${page === 'cart' && items.length ? '<a class="button" href="checkout-address.html">Zur Adresse</a>' : ''}`;
}
function emptyGuard(items) {
 if (items.length) return false;
 const guard = document.querySelector('#checkout-guard'); if (guard) guard.innerHTML = '<section class="panel"><h2>Ihr Warenkorb ist leer.</h2><a class="button" href="catalog.html">Artikel entdecken</a></section>';
 const content = document.querySelector('#checkout-content'); if (content) content.hidden = true;
 return true;
}
function renderCart() {
 const items = lines(); const container = document.querySelector('#cart-items'); summary(items);
 if (!items.length) { container.innerHTML = '<section class="panel empty-cart"><h2 class="section-title">Noch nichts ausgewählt?</h2><p class="muted">Entdecken Sie unsere Beispielkollektion und stellen Sie Ihre Auswahl zusammen.</p><a class="button" href="catalog.html">Zum Katalog</a></section>'; return; }
 container.innerHTML = items.map((item,index) => `<article class="panel cart-item"><a href="product.html?id=${encodeURIComponent(item.id)}"><img src="${esc(item.product.image)}" alt="${esc(item.product.name)}"></a><div><p class="eyebrow">${esc(item.product.brand)}</p><h2><a href="product.html?id=${encodeURIComponent(item.id)}">${esc(item.product.name)}</a></h2><p class="muted">${esc(item.color)} · Größe ${esc(item.size)}</p><label class="quantity-label">Menge <input type="number" min="1" max="10" value="${item.qty}" data-quantity="${index}" aria-label="Menge für ${esc(item.product.name)}"></label><button type="button" class="text-button" data-remove="${index}">Entfernen</button></div><strong>${money(item.product.price * item.qty)}</strong></article>`).join('');
 container.querySelectorAll('[data-remove]').forEach(button => button.addEventListener('click', () => { const item = items[Number(button.dataset.remove)]; shop.removeItem(item.id,item.color,item.size); renderCart(); }));
 container.querySelectorAll('[data-quantity]').forEach(input => input.addEventListener('change', () => { const item = items[Number(input.dataset.quantity)]; const qty = Math.min(10,Math.max(1,Math.floor(Number(input.value)||1))); shop.setQty(item.id,item.color,item.size,qty); renderCart(); }));
}
const items = lines();
if (page === 'cart') renderCart();
if (page === 'address') {
 summary(items); if (emptyGuard(items)) return;
 const form = document.querySelector('#address-form'); const previous = read('mm-demo-address');
 if (previous && typeof previous === 'object') Object.keys(previous).forEach(name => { const field = form.elements.namedItem(name); if (field && name !== 'shipping') field.value = String(previous[name]); });
 form.addEventListener('submit', event => {
  event.preventDefault(); let valid = true; const data = Object.fromEntries(new FormData(form));
  ['email','firstName','lastName','street','houseNumber','postcode','city'].forEach(name => {
   const value = String(data[name]||'').trim(); data[name] = value;
   let message = value ? '' : 'Bitte ausfüllen.';
   if (name === 'email' && value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) message = 'Bitte eine gültige E-Mail eingeben.';
   if (name === 'postcode' && value && !/^\d{5}$/.test(value)) message = 'Bitte fünf Ziffern eingeben.';
   if (name === 'houseNumber' && value && !/\d/.test(value)) message = 'Bitte eine Hausnummer eingeben.';
   form.querySelector(`[data-error="${name}"]`).textContent = message;
   form.elements.namedItem(name).setAttribute('aria-invalid', message ? 'true' : 'false'); if (message) valid = false;
  });
  sessionStorage.setItem('mm-demo-address',JSON.stringify(data));
  if (!valid) { document.querySelector('#address-status').textContent = 'Bitte prüfen Sie die markierten Felder.'; form.querySelector('[aria-invalid="true"]').focus(); return; }
  location.href = 'checkout-payment.html';
 });
}
if (page === 'payment') {
 summary(items); if (emptyGuard(items)) return;
 const address = read('mm-demo-address'); if (!address || !address.email || !address.postcode) { location.replace('checkout-address.html'); return; }
 document.querySelector('#address-review').innerHTML = `<p>${esc(address.firstName)} ${esc(address.lastName)}<br>${esc(address.street)} ${esc(address.houseNumber)}<br>${esc(address.postcode)} ${esc(address.city)}<br>Deutschland</p><p class="muted">${esc(address.email)}</p>`;
 document.querySelector('#review-items').innerHTML = items.map(item => `<div class="review-line"><div>${esc(item.product.name)}<small>${esc(item.color)} · ${esc(item.size)} · ${item.qty} Stück</small></div><strong>${money(item.product.price*item.qty)}</strong></div>`).join('');
 document.querySelector('#simulate-error').addEventListener('click', () => { location.href = 'payment-error.html'; });
 document.querySelector('#simulate-order').addEventListener('click', event => {
  const status = document.querySelector('#payment-status'); if (!document.querySelector('#demo-consent').checked) { status.textContent = 'Bitte bestätigen Sie, dass Sie den Demo-Ablauf testen möchten.'; return; }
  const current = lines(); if (!current.length) { location.href='cart.html'; return; }
  event.currentTarget.disabled = true;
  const receipt = {number:'DEMO-'+Date.now(),items:current.map(({id,color,size,qty}) => ({id,color,size,qty})),total:subtotal(current)+shipping,date:new Date().toISOString(),paymentMethod:document.querySelector('[name="payment"]:checked').value};
  sessionStorage.setItem('mm-demo-receipt',JSON.stringify(receipt));
  current.forEach(item => shop.removeItem(item.id,item.color,item.size));
  location.href = 'confirmation.html';
 });
}
if (page === 'confirmation') {
 const receipt = read('mm-demo-receipt'); const target = document.querySelector('#confirmation-content');
 if (!receipt || !Array.isArray(receipt.items)) { target.innerHTML = '<p class="muted">Es liegt noch kein Demo-Abschluss vor.</p>'; return; }
 target.innerHTML = `<p class="receipt-number">${esc(receipt.number)}</p><p>Simulierte Methode: ${esc(receipt.paymentMethod)}</p><div>${receipt.items.map(item => { const product = shop.products.find(p => p.id===item.id); return `<div class="review-line"><div>${esc(product?.name || item.id)}<small>${esc(item.color)} · ${esc(item.size)} · ${item.qty} Stück</small></div></div>`; }).join('')}</div><p class="receipt-total">Demo-Gesamt: ${money(receipt.total)}</p><p class="muted">Versand und Tracking werden in dieser Vorschau nicht ausgelöst.</p>`;
}
})();
