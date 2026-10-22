const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const handlers = {}, galleryEvents = [];
const root = {
  dataset: {catalogProduct: 'pdp'}, hasAttribute: () => false,
  querySelectorAll: () => [], querySelector: () => null, contains: () => true,
  addEventListener: (name, handler) => { handlers[name] = handler; },
  dispatchEvent: event => { if (event.type === 'catalog:gallery') galleryEvents.push(event.detail); },
};
const product = {default_color: 'navy', default_size: 'M', price: '20.00',
  colors: [{code: 'navy', label: 'Navy'}], galleries: {navy: ['/front.jpg']},
  variants: ['M', 'L'].map(size => ({color: 'navy', size, sku: size, price: '20.00', available: true})),
  preview_url: '/variant/'};
const document = {readyState: 'complete', documentElement: {lang: 'de'}, querySelectorAll: () => [root],
  getElementById: id => id === 'catalog-products' ? {textContent: JSON.stringify({pdp: product})}
    : id === 'catalog-selection-texts' ? {textContent: '{}'} : null};
const confirmed = ['/front.jpg', '/back.jpg', '/side.jpg'];
const context = {document, URL, AbortController, Intl, window: {location: {href: 'http://localhost/product/'}},
  CustomEvent: class { constructor(type, options) { this.type = type; this.detail = options.detail; } },
  fetch: async url => ({ok: true, json: async () => ({variant: {color: 'navy', size: url.searchParams.get('size'),
    sku: url.searchParams.get('size'), price: '20.00', currency: 'EUR', active: true, demo_available: true},
    gallery: {images: confirmed}})}),
};
async function run() {
  vm.runInNewContext(fs.readFileSync(process.argv[2], 'utf8'), context);
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(galleryEvents.at(-1).gallery, confirmed);
  const previousCount = galleryEvents.length;
  const size = {dataset: {size: 'L'}};
  handlers.click({target: {closest: selector => selector === '[data-size]' ? size : null}});
  await new Promise(resolve => setImmediate(resolve));
  const nextEvents = galleryEvents.slice(previousCount);
  assert.equal(nextEvents.length, 2);
  for (const event of nextEvents) assert.deepEqual(Array.from(event.gallery), confirmed);
  assert.equal(root.dataset.selectedSku, 'L');
}
run().catch(error => { console.error(error); process.exitCode = 1; });
