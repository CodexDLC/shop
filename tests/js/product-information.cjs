const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
class Element {
  constructor(dataset = {}) { this.dataset = dataset; this.attrs = {}; this.handlers = {}; this.classList = {toggle() {}}; }
  addEventListener(name, handler) { this.handlers[name] = handler; }
  setAttribute(name, value) { this.attrs[name] = value; }
  getAttribute(name) { return this.attrs[name] ?? null; }
  focus() { this.focused = true; }
  scrollIntoView() { this.scrolled = true; }
  showModal() { this.open = true; }
  close() { this.open = false; this.handlers.close?.(); }
}
const tabs = ['description', 'material', 'delivery', 'reviews'].map(name => new Element({informationTab: name}));
const panels = tabs.map(tab => new Element({informationPanel: tab.dataset.informationTab}));
panels.forEach(panel => { panel.id = `product-${panel.dataset.informationPanel}`; });
const units = ['cm', 'inch'].map(unit => { const el = new Element({guideUnit: unit}); el.textContent = unit; return el; });
const unitLabel = new Element();
const measurement = new Element(); measurement.attrs = {'data-measurement-cm': '80–90', 'data-measurement-inch': '31.5–35.4'};
const selected = new Element();
const sizeRow = new Element({guideRow: 'M'}); sizeRow.querySelector = () => selected;
const closer = new Element(), opener = new Element(), link = new Element(), tablist = new Element();
const dialog = new Element();
dialog.querySelectorAll = selector => ({'[data-size-guide-close]': [closer], '[data-guide-unit]': units,
  '[data-guide-unit-label]': [unitLabel], '[data-measurement-cm]': [measurement], '[data-guide-row]': [sizeRow]})[selector];
dialog.querySelector = selector => units.find(unit => selector === `[data-guide-unit="${unit.dataset.guideUnit}"]`);
const tabsRoot = {querySelector: () => tablist};
const root = new Element();
root.querySelectorAll = selector => selector === '[data-information-tab]' ? tabs : panels;
root.querySelector = selector => ({'[data-product-tabs]': tabsRoot, '[data-review-link]': link, '#product-reviews': panels[3]})[selector];
const document = {readyState: 'complete', querySelectorAll: () => [root],
  getElementById: id => id === 'sizeGuideModal' ? dialog : opener};
const window = {location: {hash: ''}, addEventListener: (name, handler) => { window[name] = handler; }};
vm.runInNewContext(fs.readFileSync(process.argv[2], 'utf8'), {document, window});
assert.equal(tablist.attrs.role, 'tablist');
assert.equal(tabs[0].attrs['aria-selected'], 'true');
assert.deepEqual(panels.map(panel => panel.hidden), [false, true, true, true]);
tabs[1].handlers.click();
assert.equal(panels[1].hidden, false);
assert.equal(panels[0].hidden, true);
tabs[1].handlers.keydown({key: 'End', preventDefault() {}});
assert.equal(tabs[3].focused, true);
assert.equal(panels[3].hidden, false);
link.handlers.click({preventDefault() {}});
assert.equal(panels[3].focused, true);
assert.equal(panels[3].scrolled, true);
opener.handlers.click();
assert.equal(dialog.open, true);
tabs[0].handlers.click();
assert.equal(panels[3].hidden, true);
window.location.hash = '#product-reviews'; window.hashchange();
assert.equal(panels[3].hidden, false);
assert.equal(panels[0].hidden, true);
units[1].handlers.click();
assert.equal(measurement.textContent, '31.5–35.4');
assert.equal(unitLabel.textContent, 'inch');
assert.equal(units[1].attrs['aria-pressed'], 'true');
units[0].handlers.click();
assert.equal(measurement.textContent, '80–90');
root.handlers['catalog:selection']({detail: {size: 'M'}});
assert.equal(sizeRow.dataset.selected, 'true');
assert.equal(selected.hidden, false);
root.handlers['catalog:selection']({detail: {size: 'XL'}});
assert.equal(selected.hidden, true);
closer.handlers.click();
assert.equal(dialog.open, false);
assert.equal(opener.focused, true);
window.location.hash = '#sizeGuideModal'; window.hashchange();
assert.equal(dialog.open, true);
