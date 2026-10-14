# Пробный editorial-дизайн

13.10.2026: применена присланная интерпретация Gemini. Рабочий бренд остаётся Männermasche, а Atelier Masculin — имя исходной концепции.

Канонические CSS-исходники: `src/web/static/shop/css/`. `shop.css` — entry с imports, не compiled output. Файлы: tokens, fonts, foundations, components, pages/home. Compiler пока не добавлен.

Основной фон #F8F8F3, поверхности #EEEEE7, CTA #1F4A39, тёмная брендовая полоса #183F30. Из исходника не перенесён параллельный зеленоватый Material palette, чтобы значения не конфликтовали.

Bodoni Moda — заголовки, Plus Jakarta Sans — интерфейс. Шрифты получены из официального google/fonts, хранятся локально с OFL-лицензиями в static/shop/fonts. Посетитель не обращается к Google Fonts. [Bodoni](https://github.com/google/fonts/tree/main/ofl/bodonimoda), [Jakarta](https://github.com/google/fonts/tree/main/ofl/plusjakartasans).

Прямые углы, без теней/blur; квадратные образцы цвета. Образцы в карточках декоративные; реальные interactive swatches пока не реализованы. Hero сохраняет светлый градиент ради читаемости поверх фотографии. Функции фильтрации/dialog продолжают работать, покупки нет.

Исходный документ и предыдущий CSS сохранены в archive. Этот вариант предназначен для визуального сравнения; не считается окончательно утверждённым дизайном.
