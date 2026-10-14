"""Rebuild static pages from user HTML, preserving body markup and inline handlers."""
from pathlib import Path
import json
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/prototype'
SOURCES = {
 'index.html':'product-cards/source.html',
 'catalog.html':'catalog/desktop-01.html',
 'catalog-empty.html':'catalog/desktop-02.html',
 'catalog-mobile.html':'catalog/mobile.html',
 'search.html':'search/reference-01.html',
 'search-empty.html':'search/reference-02.html',
 'product.html':'product-modal/reference.html',
 'cart.html':'cart/reference.html',
 'empty-cart.html':'empty-and-errors/empty-cart.html',
 'checkout-address.html':'checkout-address-shipping/reference.html',
 'checkout-address-errors.html':'emails/address-errors.html',
 'checkout-payment.html':'checkout-payment-review/reference.html',
 'confirmation.html':'order-confirmation/reference.html',
 'payment-error.html':'emails/payment-error.html',
 'auth.html':'auth/login-desktop.html',
 'auth-mobile.html':'auth/login-mobile.html',
 'register.html':'auth/register-desktop.html',
 'register-mobile.html':'auth/register-reset-mobile.html',
 'password-reset.html':'auth/password-reset-desktop.html',
 'account.html':'customer-account/overview-desktop.html',
 'account-mobile.html':'customer-account/overview-mobile.html',
 'account-orders.html':'customer-account/orders-empty-desktop.html',
 'account-order-detail.html':'customer-account/order-detail-desktop.html',
 'account-profile.html':'customer-account/profile-addresses-security-marketing-desktop.html',
 'help.html':'help/desktop.html',
 'help-mobile.html':'help/mobile.html',
 'legal.html':'legal/reference-02.html',
 'legal-mobile.html':'legal/reference.html',
 'emails.html':'emails/email-hub.html',
 '404.html':'empty-and-errors/404.html',
}

def build():
    # A recoverable snapshot of the previous attempt; never overwrite originals.
    backup = ROOT / 'docs/design/archive/replaced-static-prototype'
    if not backup.exists():
        shutil.copytree(OUT, backup)
    # Shared config supplies missing token classes without removing page-specific extensions.
    catalog = (ROOT/'design-handoff/catalog/desktop-01.html').read_text(encoding='utf-8')
    scripts = re.findall(r'<script\b[^>]*>(.*?)</script>',catalog,re.S)
    config = next(s for s in scripts if 'tailwind.config' in s)
    (OUT/'assets/reference-tokens.js').write_text(
        'const originalPageConfig = tailwind.config || {};\n'+
        config+'\nconst shared = tailwind.config;\n'+
        "shared.theme.extend.colors.brand={page:'#F8F8F3',surface:'#F1F1EB',surfaceCard:'#EBEBE3',dark:'#171E19',muted:'#626960',accent:'#183F30',accentHover:'#133327',border:'#DCDED5'};\n"+
        'tailwind.config={...shared,...originalPageConfig,theme:{...shared.theme,...originalPageConfig.theme,extend:{...shared.theme.extend,...originalPageConfig.theme?.extend,colors:{...shared.theme.extend.colors,...originalPageConfig.theme?.extend?.colors},spacing:{...shared.theme.extend.spacing,...originalPageConfig.theme?.extend?.spacing},fontSize:{...shared.theme.extend.fontSize,...originalPageConfig.theme?.extend?.fontSize},fontFamily:{...shared.theme.extend.fontFamily,...originalPageConfig.theme?.extend?.fontFamily}}}};\n',encoding='utf-8')
    report=[]
    homepage=(ROOT/'design-handoff/product-cards/source.html').read_text(encoding='utf-8-sig')
    header=re.search(r'<header\b.*?</header>',homepage,re.S).group(0)
    announcement=re.search(r'<aside\b.*?</aside>',homepage,re.S).group(0)
    footer=re.search(r'<footer\b.*?</footer>',homepage,re.S).group(0)
    header=header.replace('<header ', '<header data-shared-chrome="header" ',1)
    footer=footer.replace('<footer ', '<footer data-shared-chrome="footer" ',1)
    header=re.sub(r'(<a\b[^>]*aria-label="Männermasche Startseite"[^>]*>).*?</a>',
                  lambda m:m.group(1)+'<img class="shop-brand-logo" src="assets/brand/logo-horizontal.png" alt="Männermasche – Herrenunterwäsche &amp; Bademode" width="900" height="172"></a>',header,count=1,flags=re.S)
    footer=re.sub(r'<div class="flex items-center gap-3 mb-4">.*?</div>',
                  '<a class="shop-footer-brand" href="index.html"><img class="shop-brand-logo-light" src="assets/brand/logo-horizontal-light.png" alt="Männermasche – Herrenunterwäsche &amp; Bademode" width="900" height="191"></a>',footer,count=1,flags=re.S)
    (OUT/'components').mkdir(exist_ok=True)
    (OUT/'components/header.html').write_text(announcement+'\n'+header,encoding='utf-8')
    (OUT/'components/footer.html').write_text(footer,encoding='utf-8')
    for name, source in SOURCES.items():
        original=(ROOT/'design-handoff'/source).read_text(encoding='utf-8-sig')
        html=re.sub(r'<script\b[^>]*src=["\']https://cdn\.tailwindcss\.com[^"\']*["\'][^>]*></script>',
                    '<script src="assets/vendor/tailwind-runtime.js?plugins=forms,container-queries"></script>',original,flags=re.I)
        html=html.replace('</head>','<script src="assets/reference-tokens.js"></script>\n</head>',1)
        html=html.replace('</body>','<script src="assets/reference-navigation.js"></script>\n</body>',1)
        # Body equality ensures that no component, text, image or script was discarded.
        body=lambda s:re.search(r'<body\b[^>]*>(.*?)</body>',s,re.S|re.I).group(1)
        actual=body(html).replace('<script src="assets/reference-navigation.js"></script>\n','')
        assert actual==body(original),name
        if name=='index.html':
            body_source=(ROOT/'design-handoff/product-page/reference.html').read_text(encoding='utf-8-sig')
            body_image=re.search(r'<img[^>]*data-alt="Studio photograph of a luxury men\x27s body suit[^>]*src="([^"]+)"',body_source).group(1)
            chosen={
                'Boxershorts Kollektion':('https://i.ebayimg.com/images/g/f98AAeSwBGFqxLls/s-l1600.webp','CALIDA Cotton Code Boxer Brief'),
                'Slips und Pants Kollektion':('https://i.ebayimg.com/images/g/R0wAAeSwAGRqvDOf/s-l1600.webp','MANSTORE M2223 Bungee Pants'),
                'Herren Strings Kollektion':('https://i.ebayimg.com/images/g/SN0AAeSwwD1qv9bW/s-l1600.webp','Olaf Benz RED2059 Ministring'),
                'Bodies Kollektion':(body_image,'Herrenbody – vorläufiges Motiv aus der Designvorlage'),
                'p1-img':('https://i.ebayimg.com/images/g/R0wAAeSwAGRqvDOf/s-l1600.webp','MANSTORE M2223 Bungee Pants'),
                'p2-img':('https://i.ebayimg.com/images/g/lrQAAeSw-UZqvsIf/s-l1600.webp','Olaf Benz RED2260 Minipants'),
                'p3-img':('https://i.ebayimg.com/images/g/f98AAeSwBGFqxLls/s-l1600.webp','CALIDA Cotton Code Boxer Brief'),
                'p4-img':(body_image,'Herrenbody – vorläufiges Motiv aus der Designvorlage'),
            }
            def replace_photo(match):
                tag=match.group(0)
                key=next((key for key in chosen if f'id="{key}"' in tag or f'alt="{key}"' in tag),None)
                if key is None:return tag
                image,alt=chosen[key]
                tag=re.sub(r'src="[^"]*"',lambda _:f'src="{image}"',tag)
                tag=re.sub(r'alt="[^"]*"',lambda _:f'alt="{alt}"',tag)
                return tag.replace('<img ', '<img data-shop-photo="true" ',1)
            html=re.sub(r'<img\b[^>]*>',replace_photo,html)
        # Replace only the outer storefront shell. Nested component headers and
        # the email examples stay untouched, as does every other source block.
        if name!='emails.html':
            html=re.sub(r'<aside\b[^>]*data-purpose="top-announcement-bar".*?</aside>', '',html,count=1,flags=re.S)
            if re.search(r'<header\b',html):
                html=re.sub(r'<header\b.*?</header>',lambda _:announcement+'\n'+header,html,count=1,flags=re.S)
            else:
                html=re.sub(r'(<body\b[^>]*>)',lambda m:m.group(1)+announcement+'\n'+header,html,count=1)
            if re.search(r'<footer\b',html):
                html=re.sub(r'<footer\b.*?</footer>',lambda _:footer,html,count=1,flags=re.S)
            else:
                html=html.replace('<script src="assets/reference-navigation.js">',footer+'\n<script src="assets/reference-navigation.js">',1)
            html=html.replace('</head>','<link rel="stylesheet" href="assets/shared-chrome.css">\n<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&amp;display=swap">\n</head>',1)
            html=html.replace('</head>','<link rel="icon" href="assets/brand/favicon.ico"><link rel="apple-touch-icon" href="assets/brand/apple-touch-icon.png">\n</head>',1)
        (OUT/name).write_text(html,encoding='utf-8')
        report.append({'page':name,'source':'design-handoff/'+source,'shared_homepage_chrome':name!='emails.html','original_body_verified_before_shell_replacement':True})
    (OUT/'source-map.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Restored {len(report)} pages; homepage chrome shared across storefront; email examples unchanged.')

if __name__=='__main__':build()
