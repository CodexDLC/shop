/* Django gettext resolves keys before emitting this escaped JSON dictionary. */
(() => {
  const messages = JSON.parse(document.getElementById('shop-texts').textContent);
  window.shopText = key => messages[key] || '[' + key + ']';
  window.shopEscapeText = value => String(value).replace(/[&<>"']/g, char => ({
    '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'
  })[char]);
})();
