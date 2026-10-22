from xml.etree.ElementTree import Element, SubElement, tostring

from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import Http404, HttpResponse
from django.urls import reverse
from django.utils.translation import override

from .origin import indexing_enabled, public_origin
from .sitemap_products import sitemap_products

SITEMAP_PAGE_SIZE = 1000
SITEMAP_MAX_PAGE = 10000


def robots(request):
    if not indexing_enabled():
        body = 'User-agent: *\nDisallow: /\n'
    else:
        # Crawlable private pages retain their meta/header noindex directive.
        body = ('User-agent: *\nDisallow: /*?*sort=\nDisallow: /*?*color=\nDisallow: /*?*size=\n'
                f'Sitemap: {public_origin()}/sitemap.xml\n')
    return HttpResponse(body, content_type='text/plain; charset=utf-8')


def sitemap(request):
    raw_page = request.GET.get('page', '1')
    if (set(request.GET) - {'page'} or len(request.GET.getlist('page')) > 1 or not raw_page.isascii()
            or not raw_page.isdigit() or len(raw_page) > 5 or not 1 <= int(raw_page) <= SITEMAP_MAX_PAGE):
        raise Http404
    number = int(raw_page)
    root = Element('urlset', xmlns='http://www.sitemaps.org/schemas/sitemap/0.9')
    if indexing_enabled():
        paginator = Paginator(sitemap_products(), SITEMAP_PAGE_SIZE)
        try:
            page = paginator.page(number)
        except (EmptyPage, PageNotAnInteger) as exc:
            raise Http404 from exc
        if 'page' not in request.GET and paginator.num_pages > 1:
            root = Element('sitemapindex', xmlns='http://www.sitemaps.org/schemas/sitemap/0.9')
            for index in range(1, min(paginator.num_pages, SITEMAP_MAX_PAGE) + 1):
                SubElement(SubElement(root, 'sitemap'), 'loc').text = (
                    f'{public_origin()}/sitemap.xml?page={index}')
            return HttpResponse(tostring(root, encoding='utf-8', xml_declaration=True), content_type='application/xml')
        with override('de'):
            paths = [reverse(name) for name in ('shop:home', 'catalog:list', 'catalog:brands')] if number == 1 else []
            paths += [reverse('catalog:detail', kwargs={'slug': slug}) for slug in page.object_list]
        for path in paths:
            SubElement(SubElement(root, 'url'), 'loc').text = public_origin() + path
    elif number != 1:
        raise Http404
    return HttpResponse(tostring(root, encoding='utf-8', xml_declaration=True), content_type='application/xml')
