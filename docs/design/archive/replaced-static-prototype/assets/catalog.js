(() => {
  'use strict';
  const api = window.ShopDemo;
  if (!api) return;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const colors = {Schwarz:'#202720', Waldgrün:'#365743', Sand:'#c7b99d'};
  const image = (product, color) => product.image.replace('.svg', `-${color === 'Schwarz' ? 'schwarz' : color === 'Waldgrün' ? 'waldgrun' : 'sand'}.svg`);
  function variantControls(product) {
    return `<p class="variant-label" data-color-label>Farbe: ${esc(product.colors[0])}</p><div class="color-options" aria-label="Farbe">${product.colors.map((c,i)=>`<button class="color-option" type="button" data-color="${esc(c)}" aria-label="${esc(c)}" aria-pressed="${i===0}"><span style="--swatch:${colors[c] || '#777'}"></span></button>`).join('')}</div><p class="variant-label">Größe wählen</p><div class="size-options" aria-label="Größe">${product.sizes.map(s=>`<button class="size-option" type="button" data-size="${esc(s)}" aria-pressed="false">${esc(s)}</button>`).join('')}</div>`;
  }
  function bindVariants(element, product) {
    let color = product.colors[0], size = '';
    const add = element.querySelector('[data-add]');
    element.querySelectorAll('[data-color]').forEach(button => button.addEventListener('click', () => {
      color = button.dataset.color;
      element.querySelectorAll('[data-color]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
      element.querySelector('[data-color-label]').textContent=`Farbe: ${color}`;
      element.querySelectorAll('[data-product-image]').forEach(img=>{img.src=image(product,color);img.alt=`${product.brand} ${product.name} – ${color} (Illustration)`;});
      const galleryLabel=element.querySelector('[data-gallery-label]');
      if(galleryLabel) galleryLabel.textContent=`Galerie: ${color} · Beispielabbildung`;
    }));
    element.querySelectorAll('[data-size]').forEach(button=>button.addEventListener('click',()=>{
      size=button.dataset.size;
      element.querySelectorAll('[data-size]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
      add.disabled=false;add.textContent='In den Warenkorb';
      const status=element.querySelector('[data-availability]');if(status)status.textContent=`${color} / ${size} · im Demo verfügbar`;
    }));
    add.addEventListener('click',()=>{
      if(!size)return;
      const quantity=element.querySelector('[data-quantity]');
      const qty=quantity ? Math.min(10,Math.max(1,parseInt(quantity.value,10)||1)) : 1;
      api.addItem(product.id,color,size,qty);api.showToast(`${product.name} (${color}, ${size}) im Demo-Warenkorb`);
    });
  }
  function card(product) {
    const el=document.createElement('article');el.className='product-card';
    el.innerHTML=`<a class="product-photo" href="product.html?id=${encodeURIComponent(product.id)}"><img data-product-image src="${esc(product.image)}" alt="${esc(product.brand+' '+product.name)} – Beispielillustration" loading="lazy"></a><div class="product-card-content"><p class="eyebrow">${esc(product.brand)}</p><h2 class="product-name"><a href="product.html?id=${encodeURIComponent(product.id)}">${esc(product.name)}</a></h2><p class="product-price">${api.money(product.price)}</p>${variantControls(product)}<button class="button card-add" data-add disabled type="button">Bitte Größe wählen</button></div>`;
    bindVariants(el,product);return el;
  }
  const featured=document.querySelector('#featured-grid');if(featured)featured.replaceChildren(...api.products.slice(0,4).map(card));
  const grid=document.querySelector('#product-grid');
  if(grid){
    const params=new URLSearchParams(location.search);
    const form=document.querySelector('#filter-form');
    const query=document.querySelector('#search-query');query.value=params.get('q')||'';
    const categoryLabels={boxer:'Boxershorts',slip:'Slips & Pants',string:'Strings',body:'Bodies'};
    form.elements.category.value=categoryLabels[params.get('category')]||params.get('category')||'';
    let active={brand:'',size:'',category:form.elements.category.value};
    const render=()=>{
      const q=query.value.trim().toLocaleLowerCase('de');
      const products=api.products.filter(p=>(!q || `${p.brand} ${p.name} ${p.category}`.toLocaleLowerCase('de').includes(q)) && (!active.brand || p.brand===active.brand) && (!active.category || (categoryLabels[p.category]||p.category)===active.category) && (!active.size || p.sizes.includes(active.size)));
      const sort=document.querySelector('#sort').value;
      if(sort==='price-up')products.sort((a,b)=>a.price-b.price);
      if(sort==='price-down')products.sort((a,b)=>b.price-a.price);
      if(sort==='name')products.sort((a,b)=>a.name.localeCompare(b.name,'de'));
      grid.replaceChildren(...products.map(card));
      document.querySelector('#empty-results').hidden=products.length>0;
      document.querySelector('#result-count').textContent=`${products.length} ${products.length===1?'Produkt':'Produkte'}`;
      document.querySelector('#catalog-title').textContent=q?`Suche: „${query.value.trim()}“`:(active.category||'Die Kollektion');
      const count=Object.values(active).filter(Boolean).length;
      document.querySelector('#filter-count').textContent=count?`(${count})`:'';
    };
    const dialog=document.querySelector('#filter-dialog');
    document.querySelector('#open-filters').addEventListener('click',()=>dialog.showModal());
    form.addEventListener('submit',e=>{e.preventDefault();active={brand:form.elements.brand.value,size:form.elements.size.value,category:form.elements.category.value};dialog.close();render();});
    const reset=()=>{form.reset();active={brand:'',size:'',category:''};render();};
    document.querySelector('#reset-filters').addEventListener('click',reset);
    document.querySelector('#reset-results').addEventListener('click',()=>{query.value='';reset();});
    document.querySelector('#sort').addEventListener('change',render);
    document.querySelector('#catalog-search').addEventListener('submit',e=>{e.preventDefault();const url=new URL(location.href);query.value.trim()?url.searchParams.set('q',query.value.trim()):url.searchParams.delete('q');history.replaceState(null,'',url);render();});
    render();
  }
  const detail=document.querySelector('#product-detail');
  if(detail){
    const requested=new URLSearchParams(location.search).get('id');
    const product=api.products.find(p=>String(p.id)===requested)||(!requested?api.products[0]:null);
    if(!product){detail.innerHTML='<div class="panel empty-results"><h1 class="page-title">Produkt nicht gefunden</h1><p>Dieser Style ist im Demo nicht vorhanden.</p><a class="button" href="catalog.html">Zur Kollektion</a></div>';}
    else{
      document.title=`${product.brand} ${product.name} · Männermasche`;
      document.querySelector('#breadcrumb-product').textContent=product.name;
      detail.innerHTML=`<div class="product-layout"><div><img class="product-gallery-main" data-product-image src="${esc(product.image)}" alt="${esc(product.brand+' '+product.name)} – Beispielillustration"><p class="variant-label" data-gallery-label>Galerie: ${esc(product.colors[0])} · Beispielabbildung</p><p class="muted">Originalfotos des Herstellers folgen im fertigen Shop.</p></div><div class="product-info"><p class="eyebrow">${esc(product.brand)} · ${esc(product.category)}</p><h1 class="page-title">${esc(product.name)}</h1><p class="detail-price">${api.money(product.price)}</p><p class="muted">Demopreis, keine verbindlichen Versand- oder Steuerangaben.</p>${variantControls(product)}<button type="button" class="size-guide-link" id="open-size-guide">Größenberatung ↗</button><p class="variant-label" data-availability aria-live="polite">Wählen Sie Ihre Größe.</p><div class="product-add-row"><label><span class="sr-only">Menge</span><input class="field" data-quantity type="number" min="1" max="10" value="1" aria-label="Menge"></label><button class="button" type="button" data-add disabled>Bitte Größe wählen</button></div><a href="cart.html">Demo-Warenkorb ansehen →</a></div></div>`;
      bindVariants(detail,product);
      document.querySelector('#open-size-guide').addEventListener('click',()=>document.querySelector('#size-guide').showModal());
    }
  }
  document.querySelectorAll('[data-close-dialog]').forEach(button=>button.addEventListener('click',()=>button.closest('dialog').close()));
})();
