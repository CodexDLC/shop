"""Import approved static compositions into Django; never edit the reference site.

Run after intentional source design changes. Key hashes keep translations stable
when unrelated blocks move. Existing named keys and translations are preserved.
"""
import json
import re
import shutil
from hashlib import sha1
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'docs/prototype'
WEB = ROOT / 'src/web'
PAGES = {
    'index.html': ('shop', 'home', ''),
    'catalog.html': ('catalog', 'list', 'katalog/'),
    'catalog-empty.html': ('catalog', 'empty', 'katalog/leer/'),
    'catalog-mobile.html': ('catalog', 'mobile', 'katalog/mobil/'),
    'search.html': ('catalog', 'search', 'katalog/suche/'),
    'search-empty.html': ('catalog', 'search_empty', 'katalog/suche/leer/'),
    'product.html': ('catalog', 'product', 'produkt/demo/'),
    'cart.html': ('cart', 'detail', 'warenkorb/'),
    'empty-cart.html': ('cart', 'empty', 'warenkorb/leer/'),
    'checkout-address.html': ('orders', 'address', 'bestellung/adresse/'),
    'checkout-address-errors.html': ('orders', 'address_errors', 'bestellung/adresse/fehler/'),
    'checkout-payment.html': ('payments', 'review', 'bestellung/zahlung/'),
    'confirmation.html': ('orders', 'confirmation', 'bestellung/bestaetigung/'),
    'payment-error.html': ('payments', 'error', 'bestellung/zahlung/fehler/'),
    'auth.html': ('customer', 'login', 'konto/anmelden/'),
    'auth-mobile.html': ('customer', 'login_mobile', 'konto/anmelden/mobil/'),
    'register.html': ('customer', 'register', 'konto/registrieren/'),
    'register-mobile.html': ('customer', 'register_mobile', 'konto/registrieren/mobil/'),
    'password-reset.html': ('customer', 'password_reset', 'konto/passwort/'),
    'account.html': ('customer', 'overview', 'konto/'),
    'account-mobile.html': ('customer', 'mobile', 'konto/mobil/'),
    'account-orders.html': ('customer', 'orders', 'konto/bestellungen/'),
    'account-order-detail.html': ('customer', 'order_detail', 'konto/bestellungen/demo/'),
    'account-profile.html': ('customer', 'profile', 'konto/profil/'),
    'help.html': ('support', 'help', 'service/'),
    'help-mobile.html': ('support', 'help_mobile', 'service/mobil/'),
    'legal.html': ('support', 'legal', 'rechtliches/'),
    'legal-mobile.html': ('support', 'legal_mobile', 'rechtliches/mobil/'),
    'emails.html': ('support', 'emails', 'vorschau/emails/'),
    '404.html': ('support', 'not_found', 'vorschau/404/'),
}
CATALOG = WEB / 'localization/messages/de.json'
messages = json.loads(CATALOG.read_text(encoding='utf-8'))


def key_for(value, namespace):
    value = unescape(value)
    named = {'Neuheiten': 'navigation.new', 'Unterwäsche': 'navigation.underwear',
             'Bademode': 'navigation.swimwear', 'Marken': 'navigation.brands', 'Sale': 'navigation.sale',
             'Dein Stil.': 'home.hero.title.first', 'Deine Underwear.': 'home.hero.title.second',
             'Jetzt shoppen': 'home.hero.action', 'Unsere Kategorien': 'home.categories.title'}
    if value in named:
        messages[named[value]] = value
        return named[value]
    key = namespace + '.' + sha1(value.encode()).hexdigest()[:12]
    messages[key] = value
    return key


def localize_script(script, namespace):
    """Translate UI literals, not selectors, class names or provider identifiers."""
    def literal(match):
        value = match.group(2)
        if re.match(r'^(Bitte|Wird |Hinzugefügt|Auf Lager|Auf Anfrage|Fehler|Ungültig|Passwort|'
                    r'Erfolgreich|Vielen Dank|Gespeichert|Nicht verfügbar|Keine Artikel)', value):
            key=key_for(value,namespace+'.script')
            return "window.shopText('"+key+"')"
        return match.group(0)
    script=re.sub(r"(['\"])([^'\"\n<>]+)\1",literal,script)
    def html_text(match):
        key=key_for(match.group(1),namespace+'.script')
        return '>${window.shopEscapeText(window.shopText(\''+key+'\'))}<'
    return re.sub(r'>(Wird hinzugefügt\.\.\.|Hinzugefügt! ✓)<',html_text,script)


def localize(markup, namespace):
    def accessible_image(match):
        tag=match.group(0)
        if 'data-alt=' in tag and not re.search(r'(?<!-)\balt=',tag):
            return tag.replace('data-alt=', 'alt=', 1)
        return tag
    markup = re.sub(r'<img\b[^>]*>',accessible_image,markup)
    markup = re.sub(r'\b(src|href)="assets/([^"]+)"',
                    lambda m:m.group(1)+'="{% static \'storefront/'+m.group(2).split('?')[0]+"' %}"+
                    ('?'+m.group(2).split('?',1)[1] if '?' in m.group(2) else '')+'"',markup)
    # Script/style blocks remain code. Text nodes and accessible attributes are
    # translated individually without reserializing the supplied HTML.
    chunks = re.split(r'(<script\b.*?</script>|<style\b.*?</style>|<!--.*?-->|<[^>]+>|{%.*?%}|{{.*?}})', markup, flags=re.S|re.I)
    output = []
    for chunk in chunks:
        if chunk.startswith('<script'):
            output.append(localize_script(chunk,namespace))
        elif chunk.startswith(('<style', '<!--', '{%', '{{')):
            output.append(chunk)
        elif chunk.startswith('<'):
            def attribute(match):
                name, value = match.group(1), match.group(2)
                if not value.strip() or not re.search(r'[A-Za-zÄÖÜäöüß]', value):
                    return match.group(0)
                key = key_for(value, namespace + '.label')
                return name + '="{% text \'' + key + '\' %}"'
            chunk = re.sub(r'\b(alt|title|aria-label|placeholder)="([^"]*)"', attribute, chunk)
            chunk = re.sub(r'onclick="([^"]*)"',
                           lambda m:'onclick="'+localize_script(m.group(1),namespace)+'"',chunk)
            chunk = re.sub(r'\b(src|href)="assets/([^"]+)"',
                           lambda m:m.group(1)+'="{% static \'storefront/'+m.group(2)+'\' %}"',chunk)
            def link(match):
                target, suffix = match.group(1), match.group(2) or ''
                if target not in PAGES:
                    return match.group(0)
                feature, route, _ = PAGES[target]
                return 'href="{% url \''+feature+':'+route+'\' %}'+suffix+'"'
            chunk = re.sub(r'href="([\w-]+\.html)([?#][^"]*)?"',link,chunk)
            output.append(chunk)
        elif chunk.strip() and re.search(r'[A-Za-zÄÖÜäöüß]',unescape(chunk)):
            leading=chunk[:len(chunk)-len(chunk.lstrip())]
            trailing=chunk[len(chunk.rstrip()):]
            key=key_for(chunk.strip(),namespace+'.text')
            output.append(leading+"{% text '"+key+"' %}"+trailing)
        else:
            output.append(chunk)
    return ''.join(output)


def build():
    target=WEB/'static/storefront'
    shutil.copytree(SRC/'assets',target,dirs_exist_ok=True)
    # Only the reference runtime and shared shell are used. No old feature mock
    # JS is injected. Original inline interactions remain in each composition.
    script=(SRC/'assets/reference-navigation.js').read_text(encoding='utf-8')
    script=script.replace("const page=location.pathname.split('/').pop()||'index.html';",
        "const page=document.body.dataset.demoPage;\n const routeMap=JSON.parse(document.getElementById('shop-routes').textContent);\n const route=name=>routeMap[name]||name;")
    script=re.sub(r"'([\w-]+\.html)(#[^']*)?'",lambda m:"route('"+m.group(1)+"')"+("+'"+m.group(2)+"'" if m.group(2) else ''),script)
    script=re.sub(r"page===route\('([\w-]+\.html)'\)",lambda m:"page==='"+m.group(1)+"'",script)
    (target/'reference-navigation.js').write_text(script,encoding='utf-8')
    homepage=(SRC/'index.html').read_text(encoding='utf-8')
    header=re.search(r'<aside\b.*?</aside>.*?<header\b.*?</header>',homepage,re.S).group(0)
    footer=re.search(r'<footer\b.*?</footer>',homepage,re.S).group(0)
    includes=WEB/'templates/includes'
    (includes/'header.html').write_text('{% load static shop_i18n %}\n'+localize(header,'layout.header'),encoding='utf-8')
    (includes/'footer.html').write_text('{% load static shop_i18n %}\n'+localize(footer,'layout.footer'),encoding='utf-8')
    manifest=[]
    for filename,(feature,route,path) in PAGES.items():
        html=(SRC/filename).read_text(encoding='utf-8')
        head=re.search(r'<head\b[^>]*>(.*?)</head>',html,re.S).group(1)
        body_match=re.search(r'<body\b([^>]*)>(.*?)</body>',html,re.S)
        attrs,body=body_match.groups()
        if filename!='emails.html':
            body=re.sub(r'<aside\b[^>]*data-purpose="top-announcement-bar".*?</aside>','',body,count=1,flags=re.S)
            body=re.sub(r'<header\b.*?</header>',"{% include 'includes/header.html' %}",body,count=1,flags=re.S)
            body=re.sub(r'<footer\b.*?</footer>',"{% include 'includes/footer.html' %}",body,count=1,flags=re.S)
        # Shared runtime loads after json_script config, not from each page.
        body=body.replace('<script src="assets/reference-navigation.js"></script>','')
        head=localize(head,feature+'.'+route)
        body=localize(body,feature+'.'+route)
        if feature in {'cart','orders','payments'}:
            # Amounts are presentation fixtures, not executable checkout totals.
            for amount, variable in [('139,80 €','cart.total'),('49,95 €','cart.lines.0.line_amount'),
                                     ('44,95 €','cart.lines.1.line_amount'),('44,90 €','cart.lines.2.line_amount')]:
                text_key=key_for(amount,feature+'.'+route+'.text')
                body=body.replace("{% text '"+text_key+"' %}",'{{ '+variable+'|floatformat:2 }} €')
            for label, variable in [('M107 Zoned Low Cut Boxer Brief','cart.lines.0.name'),
                                    ('Natural Skin Boxer Brief','cart.lines.1.name'),
                                    ('RED 2004 Mini-Pant','cart.lines.2.name'),
                                    ('#MM-849204','order.reference')]:
                text_key=key_for(label,feature+'.'+route+'.text')
                body=body.replace("{% text '"+text_key+"' %}",'{{ '+variable+' }}')
        if filename=='index.html':
            def bind_home_card(match):
                card=match.group(0)
                code=re.search(r'data-product-id="(p\d)"',card).group(1)
                card=re.sub(r'(<h3\b[^>]*>).*?(</h3>)',
                    lambda m:m.group(1)+'{{ products.'+code+'.name }}'+m.group(2),card,count=1,flags=re.S)
                old_prices={'p1':'49,95 €','p2':'44,90 €','p3':'29,95 €','p4':'79,00 €'}
                price_key=key_for(old_prices[code],'shop.home.text')
                card=card.replace("{% text '"+price_key+"' %}", '{{ products.'+code+'.price|floatformat:2 }} €')
                if code!='p4':
                    card=re.sub(r'(<img\b[^>]*id="'+code+r'-img"[^>]*src=")[^"]*',
                        lambda m:m.group(1)+'{{ products.'+code+'.photo_url }}',card)
                card=re.sub(r'onclick="(quickAddToCart|triggerQuickView)\((.*?)\)"',
                    lambda m:'onclick="'+m.group(1)+'('+
                    ("'"+code+"', " if m.group(1)=='quickAddToCart' else '')+
                    "this.closest('article').querySelector('h3').textContent, '"+old_prices[code]+"')\"",card)
                return card
            body=re.sub(r'<article\b[^>]*data-product-id="p\d".*?</article>',bind_home_card,body,flags=re.S)
        # Keep data fixtures visible at the boundary before real services replace
        # them. No payment form can be mistaken for active Stripe integration.
        template="{% extends 'base.html' %}\n{% load static shop_i18n %}\n"
        template+='{% block page_head %}'+head+'{% endblock %}\n'
        template+='{% block body_attrs %}'+attrs+' data-demo-page="'+filename+'"{% endblock %}\n'
        template+='{% block content %}'+body+'{% endblock %}\n'
        out=WEB/feature/'templates'/feature/(route+'.html')
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(template,encoding='utf-8')
        manifest.append({'source':filename,'feature':feature,'name':route,'path':path,'template':feature+'/'+route+'.html'})
    messages.update({
        'demo.notice':'Designvorschau · Testdaten · Keine echten Zahlungen oder Bestellungen',
        'demo.payment.notice':'Stripe Checkout + PayPal über Stripe · Lokale Demo, noch keine Verbindung zur Stripe-Sandbox',
        'demo.action.unavailable':'Demonstration: Diese Aktion ist noch nicht mit dem Backend verbunden.',
    })
    CATALOG.write_text(json.dumps(messages,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (WEB/'storefront/page_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(f'Imported {len(manifest)} templates, {len(messages)} German text keys.')


if __name__=='__main__':
    build()
