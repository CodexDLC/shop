# Проверка склада — этапы 7–8

Задача: изолированная ручная и визуальная проверка RU/DE без рабочей базы.

Оставленные временные снимки с вымышленными данными:
- tmp/inventory-qa/step7-desktop-ru.png
- tmp/inventory-qa/step7-mobile-ru.png
- tmp/inventory-qa/step7-mobile-de-error.png
- tmp/inventory-qa/step8-return-history-ru.png
- tmp/inventory-qa/step8-return-mobile-de.png

Все собственные QA-процессы остановлены. Их точные run-папки удалены после проверки принадлежности tmp/inventory-qa и отсутствия listener8047. Базы и fake accounts не сохранены. Основной local web8030 не относится к временным QA-процессам и оставлен работающим.

Повторно используемый launcher: tools/serve_inventory_qa.py. Принудительные test settings/fresh SQLite/loopback и отдельные inventory_qa_* cookie, без загрузки .env. Нормальный выход удаляет свой TemporaryDirectory; принудительное завершение инструмента может потребовать адресной очистки зарегистрированной run-папки. Снимки оставлены для проверки итогового отчёта.
