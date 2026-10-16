"use strict";
(() => {
 const products = [
 {id:"m1",brand:"MANSTORE",name:"M107 · Micro Pants",price:39.9,category:"boxer",image:"assets/images/boxer.svg"},
 {id:"o1",brand:"Olaf Benz",name:"RED 2320 · Mini Slip",price:29.9,category:"slip",image:"assets/images/slip.svg"},
 {id:"m2",brand:"MANSTORE",name:"M102 · Micro String",price:24.9,category:"string",image:"assets/images/string.svg"},
 {id:"m3",brand:"MANSTORE",name:"M101 · Body",price:59.9,category:"body",image:"assets/images/body.svg"},
 {id:"c1",brand:"CALIDA",name:"Natural · Slip",price:32.9,category:"slip",image:"assets/images/slip.svg"}
 ].map(p=>({...p,colors:["Schwarz","Waldgrün","Sand"],sizes:["S","M","L","XL"]}));
 let fallbackCart=[];
 const money=value=>new Intl.NumberFormat('de-DE',{style:'currency',currency:'EUR'}).format(value);
 function getCart(){try{const data=JSON.parse(localStorage.getItem('mm-demo-cart')||'[]');return Array.isArray(data)?data.filter(x=>products.some(p=>p.id===x.id&&p.colors.includes(x.color)&&p.sizes.includes(x.size))&&Number.isInteger(x.qty)&&x.qty>0&&x.qty<=20):[];}catch{return fallbackCart;}}
 function saveCart(items){fallbackCart=items;try{localStorage.setItem('mm-demo-cart',JSON.stringify(items));}catch{}window.dispatchEvent(new Event('cart-updated'));updateCount();}
 function addItem(id,color,size,qty=1){const p=products.find(x=>x.id===id);if(!p||!p.colors.includes(color)||!p.sizes.includes(size))return false;qty=Number(qty);if(!Number.isInteger(qty)||qty<1||qty>20)return false;const items=getCart();const existing=items.find(x=>x.id===id&&x.color===color&&x.size===size);if(existing)existing.qty=Math.min(20,existing.qty+qty);else items.push({id,color,size,qty});saveCart(items);return true;}
 function setQty(id,color,size,qty){qty=Number(qty);if(!Number.isInteger(qty)||qty<1||qty>20)return;const items=getCart();const item=items.find(x=>x.id===id&&x.color===color&&x.size===size);if(item){item.qty=qty;saveCart(items);}}
 function removeItem(id,color,size){saveCart(getCart().filter(x=>!(x.id===id&&x.color===color&&x.size===size)));}
 function showToast(message){const toast=document.querySelector('#demo-toast');toast.textContent=message;toast.hidden=false;clearTimeout(window.demoToastTimeout);window.demoToastTimeout=setTimeout(()=>toast.hidden=true,3500);}
 function updateCount(){document.querySelectorAll('[data-cart-count]').forEach(el=>el.textContent=getCart().reduce((n,x)=>n+x.qty,0));}
 window.ShopDemo={products,getCart,addItem,setQty,removeItem,money,showToast};
 window.showToast=showToast;
 try{document.documentElement.dataset.theme=localStorage.getItem('mm-demo-theme')||'editorial';}catch{}
 const header=document.querySelector('[data-site-header]');
 if(header)header.innerHTML=`<a class="skip-link" href="#main">Zum Inhalt</a><div class="demo-banner">Interaktiver Design-Prototyp · Keine echten Bestellungen oder Zahlungen</div><div class="brand-strip">MANSTORE · Olaf Benz · CALIDA</div><header class="site-header"><div class="container header-row"><a class="site-logo" href="index.html">Männermasche<small>Herrenunterwäsche & Bademode</small></a><button class="menu-toggle" aria-expanded="false" aria-controls="site-navigation">Menü</button><nav class="site-nav" id="site-navigation" aria-label="Hauptnavigation"><a href="catalog.html">Neuheiten</a><a href="catalog.html">Unterwäsche</a><a href="catalog.html?category=body">Bodies</a><a href="help.html">Service</a></nav><div class="header-tools"><button class="theme-toggle" title="Design A/B wechseln">Stil A/B</button><a class="icon-link" href="account.html">Konto</a><a class="icon-link" href="cart.html">Tasche (<span data-cart-count>0</span>)</a></div></div></header>`;
 const footer=document.querySelector('[data-site-footer]');if(footer)footer.innerHTML=`<footer class="site-footer"><div class="container"><div class="footer-grid"><div><strong>Männermasche</strong><p>Besondere Styles. Dein gutes Gefühl.</p><small>Alle Produkte, Preise und Verfügbarkeiten sind Beispiele.</small></div><nav aria-label="Service"><a href="help.html">Hilfe & Kontakt</a><a href="legal.html">Rechtliche Informationen</a><a href="emails.html">E-Mail-Vorschau</a></nav><nav aria-label="Prototyp"><a href="catalog.html">Kollektion</a><a href="auth.html">Anmelden</a><a href="index.html#screens">Alle Demo-Seiten</a></nav></div><p class="footer-small">Designvorschau · Keine rechtlichen oder kommerziellen Zusagen</p></div></footer>`;
 const toast=document.createElement('div');toast.id='demo-toast';toast.className='toast';toast.hidden=true;toast.setAttribute('role','status');document.body.append(toast);
 document.querySelector('.menu-toggle')?.addEventListener('click',e=>{const open=e.currentTarget.getAttribute('aria-expanded')!=='true';e.currentTarget.setAttribute('aria-expanded',String(open));document.querySelector('.site-nav').classList.toggle('open',open);});
 document.querySelector('.theme-toggle')?.addEventListener('click',()=>{const theme=document.documentElement.dataset.theme==='soft'?'editorial':'soft';document.documentElement.dataset.theme=theme;try{localStorage.setItem('mm-demo-theme',theme);}catch{}showToast(theme==='soft'?'Stil A: Sans & weiche Ecken':'Stil B: Editorial & klare Kanten');});
 document.querySelectorAll('[data-quick-add]').forEach(btn=>btn.addEventListener('click',()=>{addItem(btn.dataset.quickAdd,'Schwarz','M',1);showToast('Demovariante Schwarz / M zur Tasche hinzugefügt');}));updateCount();
})();
