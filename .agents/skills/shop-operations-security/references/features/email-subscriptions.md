# Письма и реклама

Статус 16.10.2026: auth-письма подтверждения email/password reset реализованы HTML+text, доставка локально Mailpit; заказы/подписки/кампании ещё запланированы. Читать [спецификацию писем и подписок](../../../../../docs/project/email-and-subscriptions.md) при формах согласия, email templates, кампании, worker отправке или unsubscribe.

Обязательные решения: отдельная пустая необязательная галочка; проектный DOI; реклама только подтверждённым адресам; покупка/eBay импорт не дают opt-in; отказ без login и проверка suppression перед отправкой; отказ от рекламы не отключает необходимые письма о заказе. GET подтверждения не подписывает автоматически.

Перед использованием библиотеки читать installed codex-django/platform messaging references и проверять контракт. Не создавать собственный campaign engine по предположениям. Email layout отдельный от сайта, HTML+plain text; фактические статусы и минимизация PII. Юридические тексты/retention проверяются провайдером; этот reference не активирует отправку.

Auth email layout: customer/templates/account/email/base_message.html, inline CSS/presentation tables, CID PNG через ShopAccountAdapter (email.message.MIMEPart), без внешних fonts/images/scripts. UI тексты email.*; plaintext URL не HTML-escape. Не менять allauth token flow. Проверки: tests/web/test_identity_emails.py и auth suites; безопасные previews без токенов в docs/project/visuals/emails. Browser/Mailpit evidence не доказывает совместимость всех почтовых клиентов.
