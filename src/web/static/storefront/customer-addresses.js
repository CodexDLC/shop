/* Real address forms retain the reference modal; all mutations are Django POSTs. */
(() => {
 const form=document.getElementById('customer-address-form');
 if(!form)return;
 const modal=document.getElementById('address-modal');
 const records=JSON.parse(document.getElementById('customer-address-data').textContent);
 let opener=null;
 const field=name=>form.elements.namedItem(name);
 const mode=kind=>{
  field('kind').value=kind;
  const pack=kind==='packstation';
  document.getElementById('field-street').classList.toggle('hidden',pack);
  document.getElementById('field-packstation').classList.toggle('hidden',!pack);
  field('street_address').disabled=pack;
  field('street_address').required=!pack;
  for(const name of ['post_number','station_number']){
   field(name).disabled=!pack;field(name).required=pack;
  }
  for(const [id,selected] of [['btn-type-std',!pack],['btn-type-pack',pack]]){
   const button=document.getElementById(id);
   button.className='flex-1 py-2 font-label-sm text-label-sm uppercase tracking-wider '+(selected?'bg-brand-deep text-on-primary':'bg-surface-muted text-text-muted');
   button.setAttribute('aria-pressed',String(selected));
  }
 };
 window.setAddressType=mode;
 window.openAddressModal=(id,updateUrl)=>{
  opener=document.activeElement;
  const address=records.find(record=>String(record.id)===String(id));
  form.action=address?updateUrl:form.dataset.createUrl;
  for(const name of ['recipient','street_address','post_number','station_number','postal_code','city','country']){
   field(name).value=address?address[name]:(name==='recipient'?form.dataset.recipient:(name==='country'?'DE':''));
  }
  field('is_default').checked=address?address.is_default:records.length===0;
  // Remove only stale validation output, never render user input as HTML.
  form.querySelectorAll('.errorlist').forEach(errors=>errors.remove());
  mode(address?address.kind:'standard');
  document.getElementById('modal-title').textContent=window.shopText(address?'customer.address.edit_title':'customer.address.create_title');
  modal.classList.remove('hidden');modal.classList.add('flex');
  field('recipient').focus();
 };
 window.closeAddressModal=()=>{
  modal.classList.add('hidden');modal.classList.remove('flex');
  if(opener)opener.focus();
 };
 modal.addEventListener('keydown',event=>{
  if(event.key==='Escape'){event.preventDefault();window.closeAddressModal();}
  if(event.key==='Tab'){
   const focusable=[...modal.querySelectorAll('button,input,select,a[href]')].filter(element=>!element.disabled&&element.getClientRects().length);
   const first=focusable[0],last=focusable[focusable.length-1];
   if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
   else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
  }
 });
 const initialize=()=>{
  mode(field('kind').value||'standard');
  const active=document.querySelector('[data-active-customer-tab]')?.dataset.activeCustomerTab;
  if(!location.hash&&active&&typeof window.switchTab==='function')window.switchTab(active);
  if(!modal.classList.contains('hidden'))(form.querySelector('[aria-invalid="true"]')||field('recipient')).focus();
 };
 document.addEventListener('DOMContentLoaded',initialize);
})();
