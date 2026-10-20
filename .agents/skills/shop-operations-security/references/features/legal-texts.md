# Юридические тексты

Статус 20.10.2026: локальные немецкие ENTWURF-документы доступны. Проверенный provider contract/юридическая публикация/API обновлений не получены; нижеследующий provider lifecycle остаётся планом.

IT-Recht/Händlerbund кандидаты. Документы имеют стабильные URL, язык, историю версии/checksum и действующую публикацию. API обновления аутентифицировано и атомарно; невалидный текст не заменяет текущий, ошибка видна staff. В HTML разрешённое содержимое, не произвольный mark_safe. Checkout связывается с версией условий где необходимо; согласия отдельны от принятия условий. Фактический список документов/вложения подтверждает legal provider.

Приёмка: update failure сохраняет предыдущую версию; документы без login; tracking opt-in реально управляет script loading. Не утверждать, что пакет consent или файлы обеспечивают весь Datenschutz.

## Источники и точки входа

- [docs/предварительный-стек/datenschutz.md](../../../../../docs/предварительный-стек/datenschutz.md)
- [docs/project/security-and-correctness.md](../../../../../docs/project/security-and-correctness.md)


## Текущая реализация черновиков

`web.support.legal_documents` содержит структурированные документы/секции с ключами, `LegalDocumentView`/`LegalDownloadView` — публичные стабильные URL и настоящий TXT attachment. Reference reader сохраняет tabs/TOC/progress/print/related cards; mobile alias использует тот же responsive шаблон. Не заменять это самодельным упрощённым legal layout и не выдавать фиктивный PDF.

Impressum, Datenschutz, AGB, Widerruf/форма, Versand/Zahlung — полные рабочие черновики с явно открытыми реквизитами. Не подставлять вымышленные фирмы/адреса/номера, обещания доставки/30дней/free returns/SSL256. Текущий код account/cart/testorders/wishlist/contact хранит реальные локальные записи; privacy описывает цели/доступ/неутверждённые сроки, отсутствие внешних оплат и фактические внешние шрифты/картинки. API/legal-provider и полноценное preference center сейчас отсутствуют.

`web.support.ContactTicket` хранит локальные обращения, только разрешённые поля; стандартные admin permissions, POST CSRF/honeypot/session limits, без внешней почты. `web.wishlist` — до50 моделей в сессии с principal isolation, активные EUR-варианты, не межустройственное хранение. Автоматическое удаление обращений и production retention не реализованы; не утверждать обратное.

Проверять tests/web/test_legal_documents.py, test_support_interactions.py, test_support_contact.py и test_wishlist.py. Тексты не являются юридическим допуском магазина; первичные источники/пределы проверки: [legal-documents.md](../../../../../docs/project/legal-documents.md).
