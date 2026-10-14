# Окружение и структура

Текущий рабочий каталог: `D:\Workspace\clients\inet_mag`.

```text
docs/                     # Требования, архитектура, стек, план
analysis/                 # Исследования рынка, скрипты, выгрузки и их тесты
assets/hero/              # Сохранённый исходник hero
src/                      # Будущий код магазина
tests/                    # Будущие тесты магазина
deploy/                   # Будущий Docker/runtime
```

`analysis/tests` относится к сборщику запросов; это не тесты будущего магазина. SQLite в analysis — исследовательское хранилище, не commerce DB.

## Предлагаемый runtime

Python + Django + PostgreSQL, uv для фиксации Python-зависимостей, Docker Compose для воспроизводимого окружения. Версии Python/Django/PostgreSQL, опубликованных codex-пакетов и ARQ проверяем перед необязательным scaffold и фиксируем в pyproject/lock. Эти файлы пока не создаём с произвольными версиями.

Этапы окружений: local → sandbox интеграций → staging → production. Для local используем вымышленные данные; production credentials не нужны для первого каталога.

Планируемые группы конфигурации: Django secret/debug/hosts, database, почта, S3 endpoint/bucket/credentials, платёжный sandbox, eBay OAuth и включение синхронизации, worker. Конкретные имена ключей и `.env.example` создаём вместе с settings, чтобы не документировать неработающие настройки.

Секреты, токены, исходный архив фотографий и персональные данные не коммитим. Запись в реальный eBay включается отдельно после read-only сверки и теста выбранного варианта. Проверку можно вести с заглушками адаптеров без аккаунтов провайдеров.

## Работающая проверка сейчас

```powershell
cd D:\Workspace\clients\inet_mag\analysis
python -m unittest discover -s tests -v
```

Подготовка документов не запускает сбор новых запросов, платежи или синхронизацию магазина.

Worker: ARQ + Redis, отдельный код/контейнер без Django. Фото: S3; web использует django-storages, независимый worker — boto3/adapter без Django. Перед scaffold проверяем booking и удаляем ненужные подключения корректно.
