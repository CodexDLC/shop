# Шаблоны и визуальная основа

Статус: 13.10.2026 реализована демонстрационная главная, без commerce-функций.

## Размещение

Шаблоны фичи находятся внутри её Django-приложения: `src/web/catalog/templates/catalog/`, `src/web/cart/templates/cart/`. Дополнительный namespace приложения обязателен для предотвращения совпадения имён. Полные страницы и HTMX fragments различаются: `product_detail.html` и `partials/variant_selector.html`, `partials/color_gallery.html`.

Общий каркас — `src/web/templates/base.html`, `components/`, `includes/header.html`, `includes/footer.html`. Общие CSS/JS/логотип — `src/web/static/shop/`. Общие templates и static directories подключены в settings. Текущая демонстрационная фича находится в web.shop/templates/shop/home.html; отдельные catalog/cart apps ещё не созданы.

Компонент выносится в общий слой, когда реально используется несколькими фичами; не создавать универсальный набор заранее. Бизнес-логика не переносится в templates. В независимом codex_ecommerce и ARQ worker шаблонов сайта нет. Будущие Jinja2-шаблоны писем worker — отдельная ответственность, не UI магазина.

Кабинет использует шаблоны codex-django с проектными расширениями; точные блоки и контексты проверяем по установленному библиотечному навыку. Сохраняем Django Templates, HTMX и Alpine.

## Направление дизайна

Первая демонстрация опирается на обсуждённый макет: светлый фон, тёмно-зелёные акценты, сохранённый hero, категории и карточки товаров. Исходник hero находится в `assets/hero/maennermasche-hero-source.png`. Männermasche остаётся рабочим названием. Это визуальное направление, не утверждённый набор размеров/токенов и не готовая страница.

Начальная страница использует демонстрационные данные; затем подключаем каталог. Не представлять вымышленные цены, наличие или обещания доставки как реальные. Смена цвета/размера следует требованиям карточки из shop-catalog-media.

## Приёмка

- Шаблоны фичи разрешаются по namespace, общий base доступен всем web-приложениям.
- Полная страница и HTMX partial возвращают соответствующее содержимое.
- Общие элементы не дублируются между фичами; engine/worker не получают web templates.
- Desktop/mobile и клавиатурная навигация проверяются при реализации.

Источники: [архитектура](../../../../docs/project/architecture.md), [исходник hero](../../../../assets/hero/maennermasche-hero-source.png).

## Текущая демонстрация

HomeView и web.shop.demo поставляют presentation-only товары; shop.js управляет фильтрами, mobile menu и native dialog. Hero PNG сохранён локально, SVG товаров — иллюстрации, не фото производителя. Цвет SVG в диалоге меняется визуальным фильтром только как demo; реальные фото впоследствии переключаются по галереям. URL /, preview settings web.config.settings.preview, loopback 127.0.0.1:8013. Проверки: tests/web/test_homepage.py; desktop/mobile screenshots в docs/project/visuals. Четыре предупреждения visual lint про пустой alt декоративных изображений категорий приняты: название уже озвучивается текстом кнопки.

## Пробный editorial-вариант

13.10.2026 по запросу пользователя применена интерпретация Gemini: Bodoni Moda для заголовков, Plus Jakarta Sans для UI, прямые углы, квадратные swatches. Это проба для сравнения, не окончательный дизайн. Шрифты локальные с OFL. CSS entry shop.css импортирует css/tokens.css, fonts.css, foundations.css, components.css и pages/home.css; редактировать соответствующий source. Подробности и прежний CSS: docs/design/README.md и docs/design/archive. Не менять название магазина на Atelier Masculin из исходного документа.

## Статический прототип для показа

14.10.2026 создан docs/prototype: самостоятельные HTML страницы, local fonts/assets, общие theme.css/app.js и feature assets. GitHub Pages вход docs/index.html при публикации /docs. Запуск отдельно от Django: python -m http.server 8020 --bind 127.0.0.1 --directory docs. Cart localStorage, checkout sessionStorage и демо-платежи не являются backend-реализацией. README в папке описывает проверки, текущие ограничения и порядок публикации. Не переносить source generator CDN/claims в runtime.
