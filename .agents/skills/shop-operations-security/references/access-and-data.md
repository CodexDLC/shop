# Доступ и данные

Статус: единый вход и MFA реализованы локально 16.10.2026; commerce endpoints с реальными деньгами/доставкой не активированы.

Проверка владельца на сервере для каждого заказа/счёта/экспорта; UUID и скрытая кнопка не авторизация. Role permissions и обязательный staff MFA уже проверяются в рабочем кабинете и Django admin. Сохранять CSRF/escaping/password/session механизмы Django. Private files не через public media URL. Не логировать secrets/адреса, export/deletion учитывает финансовую историю. Upload limits и безопасное декодирование изображений обязательны до включения импорта.

Приёмка: чужой object ID, гостевой токен, поддельная mutation, опасный upload, отсутствие необязательного tracking до согласия.

## Источники и точки входа

- [docs/project/security-and-correctness.md](../../../../docs/project/security-and-correctness.md)

## Единый вход и MFA

- `/accounts/login/`: Django/allauth, единая сессия сайта/кабинета; legacy login URLs только перенаправляют. Публичная регистрация не выдаёт staff. Текущий email должен быть подтверждён.
- `web.identity` владеет локальными адаптерами/guard; allauth владеет MFA-моделями. Вне этой задачи библиотеки не менять. Общую часть позже вынести в codex-django, shop role policy оставить здесь.
- Guard проверяет текущего пользователя, существующий authenticator, id/type и срок MFA-доказательства; staff/admin mutation без проверки получает 403 и не повторяется автоматически. UI-скрытие не заменяет backend-права.
- Отдельный SHOP_MFA_ENCRYPTION_KEYS обязателен: без plaintext fallback. Не логировать QR/secret/recovery codes. Backup ключа отдельно; смена списка ключей не перешифровывает старые строки.
- Redis обязателен для общих лимитов и TOTP replay prevention. Не подменять production cache на LocMem. В тестах legacy staff suite допускает override guard=False; MFA integration suite проверяет guard=True.
- Auth Referrer-Policy: same-origin, не no-referrer: Chromium иначе отправляет POST с Origin null, CSRF блокирует реальную форму. Не добавлять null в trusted origins и не отключать CSRF.
- Local email: общий Mailpit 127.0.0.1:1025, UI 127.0.0.1:8025; контейнер tbmmorpg-mailpit другого Compose. Внешняя доставка не подключена. .local/emails — только исторические файлы, test settings используют locmem. Защита django.server логов не доказывает защиту proxy logs.
- Проверки: tests/web/test_identity_accounts.py, tests/web/test_identity_mfa.py и браузер реального POST desktop/mobile. На снимках MFA маскировать QR, secret и recovery textarea.
- Точки входа и ограничения: [identity-and-mfa.md](../../../../docs/project/identity-and-mfa.md). Замена потерянного устройства сотрудника/production retention и SMTP пока отдельные задачи.


## Адресная книга покупателя — реализовано локально

CustomerAddress FK(user), scoped queries поrequest.user на всех mutations, чужой ID404 дажеstaff, POST+CSRF/login. User-row lock+atomic и partial UniqueConstraint защищаютединственный default; нельзя приниматьuser/email/permissions из этихформ. Name saves only first_name/last_name, не угадывать фамилию. Страна DE, локальная валидацияPLZ/Packstation не заменяетDHLпроверку. Персональные customer-ответы private/no-store; JSONscript только данныевладельца. Не логироватьPII/Postnummer/POST, не включать аналитику/рассылку при сохранении. Address delete сразуудаляетактивнуюстроку, order snapshotsбудутотдельнымиданными. Паспортхранения/границы и manualchecks в docs/project/customer-account.md; tests/web/test_customer_persistence.py. Миграцияcustomer.0001применена локально, production неразвёрнут.
