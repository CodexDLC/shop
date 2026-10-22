/* Navigation only: preserve the original page components and their scripts. */
(() => {
 'use strict';
 const page=document.body.dataset.demoPage;
 const routeMap=JSON.parse(document.getElementById('shop-routes').textContent);
 const route=name=>routeMap[name]||name;
 const routes={home:route('index.html'),'home-boutique':route('index.html'),atelier:route('index.html'),startseite:route('index.html'),neuheiten:route('catalog.html'),unterwaesche:route('catalog.html'),bademode:route('catalog.html'),marken:route('catalog.html'),sale:route('catalog.html'),bestseller:route('catalog.html'),'collections-catalog':route('catalog.html'),katalog:route('catalog.html'),suche:route('search.html'),'search-filter':route('search.html'),cart:route('cart.html'),'cart-review':route('cart.html'),warenkorb:route('cart.html'),'customer-account':route('account.html'),konto:route('account.html'),kundenkonto:route('account.html'),'mein-konto':route('account.html'),uebersicht:route('account.html'),'uebersicht-dashboard':route('account.html'),bestellungen:route('account-orders.html'),'bestellungen-sendungsverfolgung':route('account-order-detail.html'),'persoenliche-daten-sicherheit':route('account-profile.html')+'#tab-profile','profil-einstellungen':route('account-profile.html')+'#tab-profile',adressen:route('account-profile.html')+'#tab-addresses','liefer-rechnungsadressen':route('account-profile.html')+'#tab-addresses','kommunikation-atelier-club':route('account-profile.html')+'#tab-preferences',abmelden:route('auth.html'),login:route('auth.html'),registrieren:route('register.html'),'passwort-vergessen':route('password-reset.html'),faq:route('help.html'),'faq-hilfe':route('help.html'),'hilfe-kontakt':route('help.html'),kontakt:route('help.html'),'kontakt-beratung':route('help.html'),'versand-lieferung':route('help.html'),'versand-und-zahlung':route('help.html'),'versand-zahlung':route('help.html'),'lieferung-zahlung':route('help.html'),'widerruf-retoure':route('help.html'),groessenberater:route('product.html')+'#sizeGuideModal',groessentabelle:route('product.html')+'#sizeGuideModal',passformberater:route('product.html')+'#sizeGuideModal',impressum:route('legal.html'),datenschutz:route('legal.html'),agb:route('legal.html'),widerrufsbelehrung:route('legal.html'),'cookie-einstellungen':route('legal.html')};
 const anchors={'checkout-step-2':route('checkout-address.html'),'warenkorb':route('cart.html'),'back-to-shipping':route('checkout-address.html'),'shop':route('catalog.html'),'neuheiten':route('catalog.html'),'unterwaesche':route('catalog.html'),'bademode':route('catalog.html'),'marken':route('catalog.html'),'sale':route('catalog.html'),'boxershorts':route('catalog.html'),'slips':route('catalog.html'),'strings':route('catalog.html'),'bodies':route('catalog.html')};
 document.querySelectorAll('a').forEach(a=>{
  if(a.closest('[data-real-navigation]'))return;
  const href=a.getAttribute('href')||'';const data=a.dataset.path;
  if(data&&routes[data]){a.href=routes[data];return;}
  if(href.startsWith('#')&&href.length>1&&document.getElementById(href.slice(1)))return;
  if(href.startsWith('#')&&routes[href.slice(1)]){a.href=routes[href.slice(1)];return;}
  if(href==='#slips-pants'){a.href=route('catalog.html');return;}
  if(href==='#change-address'||href==='#change-packaging'){a.href=route('checkout-address.html');return;}
  if(href.startsWith('#')&&anchors[href.slice(1)]){a.href=anchors[href.slice(1)];return;}
  if(/^#product-/.test(href)){a.href=route('product.html');return;}
  if(href!=='#')return;
  const text=(a.getAttribute('aria-label')||a.textContent).trim().toLocaleLowerCase('de');
  if(/startseite|männermasche/.test(text)){a.href=route('index.html');return;}
  if(/passwort.*vergessen/.test(text)){a.href=route('password-reset.html');return;}
  if(/registrier|konto erstellen/.test(text)){a.href=route('register.html');return;}
  if(/anmeld|login/.test(text)){a.href=route('auth.html');return;}
  if(/datenschutz|impressum|widerruf|agb/.test(text)){a.href=route('legal.html');return;}
  if(/versand|retour|kontakt|hilfe|größen/.test(text)){a.href=route('help.html');return;}
  if(/bestell.*detail|sendung.*verfolg/.test(text)){a.href=route('account-order-detail.html');return;}
  if(/warenkorb|tasche/.test(text)){a.href=route('cart.html');return;}
  if(/konto|profil/.test(text)){a.href=route('account.html');return;}
  if(/kollektion|boxer|slips|strings|bodies|manstore|olaf|calida|ansehen|entdecken|shoppen/.test(text))a.href=route('catalog.html');
 });
 document.querySelectorAll('button').forEach(button=>{
  if(button.closest('[data-real-navigation]'))return;
  const label=button.getAttribute('aria-label')||'';
  if(/warenkorb|shopping bag/i.test(label))button.addEventListener('click',()=>location.href=route('cart.html'));
  if(/mein konto|profil/i.test(label))button.addEventListener('click',()=>location.href=route('account.html'));
  if(/suche öffnen/i.test(label))button.addEventListener('click',()=>location.href=route('search.html'));
  const text=button.textContent.trim();
  if(/Zum Produkt/.test(text))button.addEventListener('click',()=>location.href=route('product.html'));
  if(page==='checkout-payment.html'&&/Zahlungspflichtig bestellen/.test(text))button.addEventListener('click',()=>location.href=route('confirmation.html'));
  if(page==='payment-error.html'&&/erneut durchführen|erneut versuchen/i.test(text))button.addEventListener('click',()=>location.href=route('checkout-payment.html'));
 });
 document.addEventListener('submit',event=>{
  if(event.target.closest('[data-real-auth], [data-real-catalog], [data-real-commerce], [data-real-support]'))return;
  event.preventDefault();
  const form=event.target;if(!form.checkValidity()){form.reportValidity();return;}
  if(page==='checkout-address.html'||page==='checkout-address-errors.html')location.href=route('checkout-payment.html');
  else if(page==='auth.html'||page==='register.html')location.href=route('account.html');
  // Reset/contact/profile original interactions remain local, no requests are sent.
 },true);
 const tab=location.hash.slice(1);
 if(page==='account-profile.html'&&/^tab-/.test(tab)&&typeof window.switchTab==='function')setTimeout(()=>window.switchTab(tab),0);
})();
