/* Mock reference interactions remain local and never claim a server mutation. */
(() => {
 const notice=window.shopText('customer.account.demo_action');
 const activateTab=()=>{
  const tab=location.hash.slice(1);
  if(/^tab-(profile|addresses|preferences)$/.test(tab)&&typeof window.switchTab==='function')window.switchTab(tab);
 };
 window.addEventListener('hashchange',activateTab);
 document.addEventListener('DOMContentLoaded',activateTab);
 document.addEventListener('submit',event=>{
  if(!event.target.closest('[data-customer-reference]')||event.target.closest('[data-real-auth]'))return;
  event.preventDefault();event.stopImmediatePropagation();
  if(typeof window.showToast==='function')window.showToast(notice);
 },true);
 if(typeof window.showToast==='function'){
  const original=window.showToast;
  window.showToast=()=>original(notice);
 }
 document.querySelectorAll('[data-customer-demo-action]').forEach(link=>link.addEventListener('click',event=>{
  event.preventDefault();if(typeof window.showToast==='function')window.showToast(notice);
 }));
})();
