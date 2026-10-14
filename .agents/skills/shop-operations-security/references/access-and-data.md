# Доступ и данные

Статус: Требования; кроме стандартного Django wiring не реализованы commerce endpoints.

Проверка владельца на сервере для каждого заказа/счёта/экспорта; UUID и скрытая кнопка не авторизация. Role permissions и staff MFA вводятся с кабинетом. Сохранять CSRF/escaping/password/session механизмы Django. Private files не через public media URL. Не логировать secrets/адреса, export/deletion учитывает финансовую историю. Upload limits и безопасное декодирование изображений обязательны до включения импорта.

Приёмка: чужой object ID, гостевой токен, поддельная mutation, опасный upload, отсутствие необязательного tracking до согласия.

## Источники и точки входа

- [docs/project/security-and-correctness.md](../../../../docs/project/security-and-correctness.md)
