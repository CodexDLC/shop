/* Navigation only: preserve the original page components and their scripts. */
(() => {
 'use strict';
 const page=location.pathname.split('/').pop()||'index.html';
 const routes={home:'index.html','home-boutique':'index.html',atelier:'index.html',startseite:'index.html',neuheiten:'catalog.html',unterwaesche:'catalog.html',bademode:'catalog.html',marken:'catalog.html',sale:'catalog.html',bestseller:'catalog.html','collections-catalog':'catalog.html',katalog:'catalog.html',suche:'search.html','search-filter':'search.html',cart:'cart.html','cart-review':'cart.html',warenkorb:'cart.html','customer-account':'account.html',konto:'account.html',kundenkonto:'account.html','mein-konto':'account.html',uebersicht:'account.html','uebersicht-dashboard':'account.html',bestellungen:'account-orders.html','bestellungen-sendungsverfolgung':'account-order-detail.html','persoenliche-daten-sicherheit':'account-profile.html#tab-profile','profil-einstellungen':'account-profile.html#tab-profile',adressen:'account-profile.html#tab-addresses','liefer-rechnungsadressen':'account-profile.html#tab-addresses','kommunikation-atelier-club':'account-profile.html#tab-preferences',abmelden:'auth.html',login:'auth.html',registrieren:'register.html','passwort-vergessen':'password-reset.html',faq:'help.html','faq-hilfe':'help.html','hilfe-kontakt':'help.html',kontakt:'help.html','kontakt-beratung':'help.html','versand-lieferung':'help.html','versand-und-zahlung':'help.html','versand-zahlung':'help.html','lieferung-zahlung':'help.html','widerruf-retoure':'help.html',groessenberater:'product.html#sizeGuideModal',groessentabelle:'product.html#sizeGuideModal',passformberater:'product.html#sizeGuideModal',impressum:'legal.html',datenschutz:'legal.html',agb:'legal.html',widerrufsbelehrung:'legal.html','cookie-einstellungen':'legal.html'};
 const anchors={'checkout-step-2':'checkout-address.html','warenkorb':'cart.html','back-to-shipping':'checkout-address.html','shop':'catalog.html','neuheiten':'catalog.html','unterwaesche':'catalog.html','bademode':'catalog.html','marken':'catalog.html','sale':'catalog.html','boxershorts':'catalog.html','slips':'catalog.html','strings':'catalog.html','bodies':'catalog.html'};
 document.querySelectorAll('a').forEach(a=>{
  const href=a.getAttribute('href')||'';const data=a.dataset.path;
  if(data&&routes[data]){a.href=routes[data];return;}
  if(href.startsWith('#')&&href.length>1&&document.getElementById(href.slice(1)))return;
  if(href.startsWith('#')&&anchors[href.slice(1)]){a.href=anchors[href.slice(1)];return;}
  if(/^#product-/.test(href)){a.href='product.html';return;}
  if(href!=='#')return;
  const text=(a.getAttribute('aria-label')||a.textContent).trim().toLocaleLowerCase('de');
  if(/startseite|männermasche/.test(text)){a.href='index.html';return;}
  if(/passwort.*vergessen/.test(text)){a.href='password-reset.html';return;}
  if(/registrier|konto erstellen/.test(text)){a.href='register.html';return;}
  if(/anmeld|login/.test(text)){a.href='auth.html';return;}
  if(/datenschutz|impressum|widerruf|agb/.test(text)){a.href='legal.html';return;}
  if(/versand|retour|kontakt|hilfe|größen/.test(text)){a.href='help.html';return;}
  if(/bestell.*detail|sendung.*verfolg/.test(text)){a.href='account-order-detail.html';return;}
  if(/warenkorb|tasche/.test(text)){a.href='cart.html';return;}
  if(/konto|profil/.test(text)){a.href='account.html';return;}
  if(/kollektion|boxer|slips|strings|bodies|manstore|olaf|calida|ansehen|entdecken|shoppen/.test(text))a.href='catalog.html';
 });
 document.querySelectorAll('button').forEach(button=>{
  const label=button.getAttribute('aria-label')||'';
  if(/warenkorb|shopping bag/i.test(label))button.addEventListener('click',()=>location.href='cart.html');
  if(/mein konto|profil/i.test(label))button.addEventListener('click',()=>location.href='account.html');
  const text=button.textContent.trim();
  if(page==='checkout-payment.html'&&/Zahlungspflichtig bestellen/.test(text))button.addEventListener('click',()=>location.href='confirmation.html');
  if(page==='payment-error.html'&&/erneut durchführen|erneut versuchen/i.test(text))button.addEventListener('click',()=>location.href='checkout-payment.html');
 });
 document.addEventListener('submit',event=>{
  event.preventDefault();
  const form=event.target;if(!form.checkValidity()){form.reportValidity();return;}
  if(page==='checkout-address.html'||page==='checkout-address-errors.html')location.href='checkout-payment.html';
  else if(page==='auth.html'||page==='register.html')location.href='account.html';
  // Reset/contact/profile original interactions remain local, no requests are sent.
 },true);
 const tab=location.hash.slice(1);
 if(page==='account-profile.html'&&/^tab-/.test(tab)&&typeof window.switchTab==='function')setTimeout(()=>window.switchTab(tab),0);
 if(page==='product.html'&&location.hash==='#sizeGuideModal')document.getElementById('openSizeGuideBtn')?.click();
})();
