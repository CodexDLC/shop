# Изолированный стенд shop.pinlite.dev

Назначение: ручная проверка магазина на HTTPS и приём уведомлений eBay. Это тестовый стенд, не разрешение на live-платежи, вызов DHL или изменение данных eBay. Здесь нет production SMTP: письма перехватывает собственный Mailpit.

## Фактическая проверка 16.10.2026

Стенд опубликован: `https://shop.pinlite.dev`, релиз `stage-b46499e141dc`, ссылка `/srv/shop/current`. Исходный архив и SHA-256 сохранены на сервере; релиз содержит текущие изменения рабочей копии, что само по себе не означает commit/push в Git.

- Все пять отдельных сервисов healthy; worker image не содержит Django. Новая PostgreSQL получила миграции и 4 демонстрационных товара с 32 вариантами; локальные пользователи/БД не переносились.
- Сертификат Let's Encrypt действует до 14.01.2027. Установлен отдельный conditional renewal hook `shop-nginx-reload.sh`, реагирующий только на сертификат shop. HSTS временного стенда осознанно выключен — единственное предупреждение `check --deploy`.
- Без пароля главная, login, health и static возвращают 401. С паролем главная, health и 12 локальных static assets возвращают 200; noindex проверен. Данные доступа находятся только в игнорируемом локальном `.local/staging/access.txt` и серверных приватных настройках.
- Публичный GET callback успешно прошёл challenge-проверку SHA-256. Неподписанный POST возвращает 412. Исходящий клиент допускает только выдачу application token и чтение ключа подписи; остальные пути/методы блокируются до соединения. Настройка портала и настоящее подписанное уведомление eBay ещё не проверены.
- Синтетическое письмо доставлено во внутренний Mailpit. Реальная внешняя SMTP-доставка не включена.
- Конфиги `nginx.conf`, `dlc`, `dlc-bootstrap` сохранили исходные SHA-256; ID и StartedAt четырёх контейнеров DLC не изменились; HTTPS DLC отвечает 200.
- Полный локальный набор: 271 тест прошёл, Ruff чистый, пропущенных миграций нет. Для asyncio на Windows проверка выполнена вне ограниченного sandbox с доступным loopback.

Приём receipt уведомления не означает завершённое удаление данных: дальнейшая процедура review/resolution описана в `ebay-notifications.md` и нужна до импорта персональных данных eBay.

## Границы

- Отдельный Compose-проект `shop-staging`: PostgreSQL 17, Redis, Mailpit, Django и независимый ARQ worker. Собственные сеть и volumes. Worker получает только Redis URL, без секретов Django/eBay.
- Django доступен на сервере только через `127.0.0.1:8030`; PostgreSQL/Redis/SMTP не публикуются. Mailpit UI — только `127.0.0.1:8026`, через SSH-туннель.
- Системный Nginx получает отдельный `sites-available/shop`; работающий конфиг DLC не редактируется. Перезагрузка Nginx только после успешного `nginx -t`.
- Витрина закрыта HTTP Basic Auth. Исключения — точный URL `/integrations/ebay/account-deletion/` (GET-проверка и подписанный POST eBay) и `/integrations/ebay/oauth/` (приглашение, callback и результат подключения продавца). OAuth требует ограниченное приглашение, CSRF и одноразовый browser-bound state. Basic Auth не заменяет обычный login/MFA сотрудников.
- Nginx и staging middleware устанавливают `X-Robots-Tag: noindex, nofollow, noarchive`. Это инструкция добросовестным поисковикам; реальная граница доступа — пароль стенда. HTTPS/HSTS остальных сайтов не меняются; HSTS стенда пока выключен.

## Файлы и секреты

Конфигурация: `deploy/compose.staging.yml`, `deploy/nginx/shop.conf`, `deploy/nginx/shop.bootstrap.conf`, `src/web/config/settings/staging.py`. Шаблон секретов — `.env.staging.example`.

На сервере выделяются `/srv/shop/releases/<release>/` для кода, `/srv/shop/shared/.env.staging` для настроек, `/srv/shop/shared/htpasswd` для пароля стенда, `/var/www/shop-static/` для собранной статики и `/var/www/shop-acme/` для ACME challenge. Файл env имеет права `0600`; htpasswd доступен владельцу и группе Nginx (`0640`), но не посторонним пользователям. Не публиковать эти файлы через HTTP, Git, вывод `docker compose config` или журналы.

В env задаются сильные независимые Django/DB/MFA/eBay verification secrets. MFA Fernet key хранится с резервной копией БД отдельно от публичного кода: его потеря делает TOTP/резервные коды нечитаемыми. При ротации новый ключ ставится первым, предыдущие сохраняются до контролируемого перешифрования. Production eBay App ID/Cert ID нужны только серверному проверяющему подписи для получения публичного ключа eBay; seller OAuth токен и операции записи не настраиваются.

## Порядок первого запуска

Действия выполняются оператором только внутри магазина; перед запуском сверить SSH-хост/IP, свободный loopback-порт 8030, объём памяти/диска и текущую работоспособность DLC. Не использовать общие имена volumes и не выполнять `docker system prune`, остановку чужих контейнеров или `down -v`.

1. Проверить DNS `shop.pinlite.dev`: A должна вести на сервер; ошибочную AAAA исправить до выпуска сертификата.
2. Создать приватный env по шаблону и htpasswd. Не копировать локальную рабочую БД с персональными данными; для стенда используется пустая БД и синтетические данные.
3. Включить HTTP-only `shop.bootstrap.conf`, проверить `nginx -t`, reload. Выпустить сертификат через webroot `/var/www/shop-acme`, не автоматическим переписыванием чужих vhosts. Настроить renew и проверенный reload hook.
4. В каталоге релиза использовать один env для интерполяции и контейнеров:

```sh
export SHOP_ENV_FILE=/srv/shop/shared/.env.staging
docker compose --env-file "$SHOP_ENV_FILE" -f deploy/compose.staging.yml build web worker
docker compose --env-file "$SHOP_ENV_FILE" -f deploy/compose.staging.yml up -d postgres redis mailpit
docker compose --env-file "$SHOP_ENV_FILE" -f deploy/compose.staging.yml run --rm migrate
docker compose --env-file "$SHOP_ENV_FILE" -f deploy/compose.staging.yml run --rm web python manage.py check --deploy
```

5. Запустить `collectstatic` отдельно, сохранить контейнер до экспорта:

```sh
docker compose --env-file "$SHOP_ENV_FILE" -f deploy/compose.staging.yml run --name shop-static-export collectstatic
docker cp shop-static-export:/app/staticfiles/. /var/www/shop-static/
docker rm shop-static-export
docker compose --env-file "$SHOP_ENV_FILE" -f deploy/compose.staging.yml up -d web worker
```

Каталог статики предварительно создаёт оператор. Он должен быть доступен Nginx на чтение. Коллекция не выполняется одновременно с миграциями автоматически на старте каждого web-процесса. Используется `StaticFilesStorage`, поэтому браузер может держать старый CSS до часа; после изменения статики при ручной проверке сделать hard refresh.

6. Заменить только shop vhost на `shop.conf`, выполнить `nginx -t` и reload. Не включать одновременно bootstrap и окончательный файл с одинаковым server_name. Проверить HTTPS через публичный DNS, не только localhost.
7. Проверить состояние сервисов, недоступность внутренних портов извне, Basic Auth на витрине/статике/admin, noindex на успешных/ошибочных ответах, common login и MFA, статику, почту и callback eBay. HSTS warning в `check --deploy` осознан для временного тестового домена; остальные предупреждения разбираются до открытия стенда.

## Почта и ручная приёмка

```sh
ssh -L 8026:127.0.0.1:8026 test-server-game
```

После установления туннеля открыть `http://127.0.0.1:8026`. Письма регистрации и сброса пароля содержат ссылки на HTTPS-стенд и остаются персональными данными даже в Mailpit; удалить синтетические письма/аккаунты после проверки. UI не публикуется общим Nginx. SMTP relay не настроен.

## Уведомления eBay

В портале eBay указать фиксированный endpoint `https://shop.pinlite.dev/integrations/ebay/account-deletion/` и отдельный verification token из приватного env. Этот токен не равен Cert ID или OAuth token. Проверка endpoint сама по себе не доказывает обработку POST: отдельно проверить подлинную подпись, idempotency и результаты хранения/обработки события. Произвольные POST не должны создавать принятые события.

Уведомления не вызывают изменение/удаление объявлений через API eBay. Сохранённые персональные данные eBay обрабатываются по политике удаления приложения; нельзя считать уведомление основанием для безусловного удаления финансовых документов магазина. Любые последующие операции записи требуют отдельного разрешения.

## Журналы, обновление, восстановление

Доступ Nginx к `/accounts/` (включая `/ru/accounts/`) и callback не журналируется, чтобы URL-токены и challenge не попадали в access/error logs. Ошибки callback должны иметь безопасный структурированный журнал приложения без payload, подписей, секретов, email и URL query. Gunicorn access log не включён. Общие shop access/error logs отдельны от DLC, с ограниченной политикой хранения оператора; контейнеры используют ротацию `10m × 3`.

Обновление: перед миграцией сделать резервную копию только shop PostgreSQL и MFA/config secrets; собрать новый релиз; отдельно выполнить миграции и экспорт статики; обновить только `shop-staging`. Откат образа не отменяет миграцию БД: совместимость схемы проверить заранее. Redis persistence содержит rate limits, MFA replay protection и очередь; не очищать его для обхода MFA. Удаление volumes — только отдельным решением. Эти файлы описывают процедуру; фактическая публикация/проверки фиксируются отдельно по результатам выполнения.
