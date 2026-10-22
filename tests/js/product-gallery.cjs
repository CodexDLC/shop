// Exercise interaction state and DOM effects, without network or browser globals.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
class Element {
  constructor() { this.dataset = {}; this.attrs = {}; this.handlers = {}; this.children = []; this.hidden = false; }
  addEventListener(name, handler) { this.handlers[name] = handler; }
  getAttribute(name) { return this.attrs[name] ?? null; }
  setAttribute(name, value) { this.attrs[name] = value; }
  removeAttribute(name) { delete this.attrs[name]; }
  set src(value) { this.attrs.src = value; }
  get src() { return this.attrs.src; }
  set href(value) { this.attrs.href = value; }
  append(child) { this.children.push(child); }
  replaceChildren() { this.children = []; }
  querySelectorAll() { return this.children; }
  contains(child) { return this.children.includes(child); }
  focus() { this.focused = true; }
  showModal() { this.open = true; }
  close() { this.open = false; this.handlers.close?.(); }
}
const elements = {};
for (const name of ['thumbnails', 'main', 'dialog', 'enlarged', 'zoom', 'empty', 'error', 'dialog-error', 'count', 'previous', 'next', 'close']) {
  elements[name] = new Element();
}
const rail = elements.thumbnails;
rail.dataset.galleryPhotoLabel = 'Foto';
for (const url of ['/black-front.jpg', '/black-back.jpg']) { const a = new Element(); a.href = url; rail.append(a); }
elements.main.alt = 'Model — Black';
const product = new Element();
const root = new Element();
root.dataset.galleryColor = 'black';
root.closest = () => product;
root.querySelector = selector => elements[selector.replace('[data-gallery-', '').replace(']', '')];
const document = {readyState: 'complete', querySelectorAll: () => [root], createElement: () => new Element()};
vm.runInNewContext(fs.readFileSync(process.argv[2], 'utf8'), {document});
const click = name => root.handlers.click({target: {closest: selector => selector === `[data-gallery-${name}]` ? elements[name] : null}});
const update = (color, gallery) => product.handlers['catalog:gallery']({detail: {color, gallery, alt: `Model — ${color}`}});
assert.equal(elements.main.src, '/black-front.jpg');
assert.equal(elements.previous.disabled, true);
assert.equal(elements.count.textContent, '1 / 2');
let prevented = false;
const thumbnail = rail.children[1];
root.handlers.click({target: {closest: s => s === '[data-gallery-thumbnail]' ? thumbnail : null}, preventDefault: () => prevented = true});
assert.equal(prevented, true);
assert.equal(elements.main.src, '/black-back.jpg');
assert.equal(rail.children[1].attrs['aria-current'], 'true');
update('black', ['/black-front.jpg', '/black-back.jpg']); // Size update must preserve image.
assert.equal(elements.main.src, '/black-back.jpg');
click('zoom');
assert.equal(elements.dialog.open, true);
assert.equal(elements.enlarged.src, '/black-back.jpg');
elements.dialog.handlers.keydown({key: 'ArrowLeft', preventDefault() {}});
assert.equal(elements.main.src, '/black-front.jpg');
click('close');
assert.equal(elements.dialog.open, false);
assert.equal(elements.zoom.focused, true);
update('navy', ['/navy-front.jpg', '/navy-back.jpg']);
assert.equal(elements.main.src, '/navy-front.jpg');
assert.equal(rail.children[1].attrs['aria-label'], 'Foto 2');
click('next');
assert.equal(elements.main.src, '/navy-back.jpg');
// Same-color authoritative response changes gallery order; selected photo is retained.
update('navy', ['/navy-back.jpg', '/navy-front.jpg', '/navy-side.jpg']);
assert.equal(elements.main.src, '/navy-back.jpg');
assert.equal(elements.count.textContent, '1 / 3');
elements.main.handlers.error();
assert.equal(elements.main.hidden, true);
assert.equal(elements.error.hidden, false);
// Selecting a failed photo again must not erase its error without a new load.
click('previous');
assert.equal(elements.main.hidden, true);
assert.equal(elements.error.hidden, false);
const failedThumbnail = rail.children[0];
root.handlers.click({target: {closest: s => s === '[data-gallery-thumbnail]' ? failedThumbnail : null}, preventDefault() {}});
assert.equal(elements.main.hidden, true);
assert.equal(elements.error.hidden, false);
click('next');
assert.equal(elements.main.src, '/navy-front.jpg');
elements.main.handlers.load();
assert.equal(elements.error.hidden, true);
elements.enlarged.handlers.error();
assert.equal(elements['dialog-error'].hidden, false);
elements.enlarged.handlers.load();
assert.equal(elements['dialog-error'].hidden, true);
click('zoom');
update('red', []);
assert.equal(elements.dialog.open, false);
assert.equal(elements.zoom.disabled, true);
assert.equal(elements.main.hidden, true);
assert.equal(elements.main.getAttribute('src'), null);
assert.equal(rail.children.length, 0);
assert.equal(elements.empty.hidden, false);
update('black', ['/fallback.jpg']);
assert.equal(elements.main.src, '/fallback.jpg');
assert.equal(elements.previous.disabled, true);
assert.equal(elements.next.disabled, true);
assert.equal(elements.empty.hidden, true);
// A cached/early SSR failure precedes deferred script initialization.
elements.main.complete = true;
elements.main.naturalWidth = 0;
vm.runInNewContext(fs.readFileSync(process.argv[2], 'utf8'), {document});
assert.equal(elements.main.hidden, true);
assert.equal(elements.error.hidden, false);
