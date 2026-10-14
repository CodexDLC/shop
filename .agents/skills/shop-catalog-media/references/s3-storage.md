# S3 и видимость

Статус: Пакеты установлены; S3 не подключён. Foundation использует временный local storage.

Целевое хранилище фото — S3. Django использует storage adapter, независимый worker — boto3/свой adapter без Django. Исходник и производные объекты разделены, DB хранит связь и состояние обработки. Публичные product images отделены от приватных invoices/exports. Не раздавать private objects публичным bucket policy. Endpoint/credentials/кодеки проверяются в реальном runtime; presigned URL выдаётся только после проверки доступа.

## Источники и точки входа

- [src/web/config/settings/base.py](../../../../src/web/config/settings/base.py)
- [docs/предварительный-стек/external-api.md](../../../../docs/предварительный-стек/external-api.md)
