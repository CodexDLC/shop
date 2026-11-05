# Контракт склада — шаги 1–8

Дата основания: 01.11.2026; обновление: 05.11.2026. Контракт, учёт, переходы резервов, expiry, TEST checkout и общий источник доступности реализованы; заключения шагов7–8 и границы проверок приведены в конце. Основание: [ТЗ K4 и последовательные шаги](../../tasks/active/2026-11-01-inventory-reservations-spec.md), разделы8–15. Работающая схема/активация отдельно от disposable проверок. Разделы предыдущих шагов ниже исторические; текущие возможности и границы уточняют разделы TEST checkout шага5 и общего источника доступности шага6.

## Словарь и инварианты

- SKU относится к продаваемому варианту цвета/размера. StockKey содержит устойчивый variant_id и location_id; строковые ID непрозрачны для движка, ORM-объекты не передаются.
- on_hand — проверенный пригодный запас. Непроверенный возврат/брак в него не входят. Это не полное количество всех физических объектов в помещении.
- reserved — все ещё действующие обязательства: временные hold и закреплённые за заказом количества. `available = on_hand - reserved`. Закрепление hold не вычитает количество второй раз.
- StockSnapshot — immutable снимок баланса и revision. Ограничения: точные целые числа, bool не количество; on_hand ≥ reserved ≥ 0, revision ≥ 0.
- Отсутствие складской записи передаётся как None; явно настроенный пустой склад — StockSnapshot с нулями. Нельзя брать demo_quantity вместо отсутствующей записи.
- Снимок может устареть после чтения. Успешная чистая проверка available не резервирует товар. Гарантия последней единицы появится только в PostgreSQL adapter последующих шагов.

## Состояние строки резерва

ReservationSnapshot содержит reservation_id, StockKey, original, remaining_reserved, consumed, released, state и expires_at.

Всегда: `original > 0`; все количества целые и неотрицательные; `original = remaining_reserved + consumed + released`. В этом контракте consumed означает списанное при отгрузке, а не оплаченное. released включает отменённое/истёкшее количество; причина освобождения будет храниться отдельной записью ledger.

| Состояние | remaining_reserved | consumed | expires_at | Смысл |
|---|---:|---:|---|---|
| HELD | >0 | 0 | aware datetime | Временный резерв до завершения подтверждения |
| COMMITTED | >0 | ≥0 | None | Закреплённый резерв, в том числе частично отгруженный |
| CLOSED | 0 | ≥0 | None | Обязательство полностью закрыто отгрузкой/освобождением |

CLOSED не означает обязательно «всё отгружено»: возможны полная отмена, полное истечение или смешанная частичная отгрузка/отмена. Их отличают counters и история. Нельзя подменять их одним paid/cancelled флагом.

На шаге1 агрегат StockSnapshot и отдельный ReservationSnapshot не подтверждают равенство общего reserved сумме строк: такой снимок и сверку должен согласованно формировать будущий adapter под транзакцией.

## Таблица команд и переходов

Это спецификация команд будущего application service. Шаг1 не исполняет их и не сохраняет эффекты.

| Команда | Предусловие/вход | Баланс | Новое состояние |
|---|---|---|---|
| Инициализация | Склада ещё нет, проверенное количество ≥0 | Создаётся баланс, reserved=0 | Нет резерва |
| Приход | Положительное q, причина | on_hand +q | Резерв не меняется |
| Корректировка | Целевое количество ≥reserved, expected revision и причина | Изменение on_hand на сохранённую дельту | Резерв не меняется |
| Резерв | Положительное q, StockKey, строка заказа, явный deadline | reserved +q после атомарной проверки available | HELD |
| Закрепление | HELD, now < expires_at | Без изменения on_hand/reserved | COMMITTED, expires_at=None |
| Освобождение | HELD/COMMITTED, q ≤ remaining_reserved | reserved −q | То же состояние либо CLOSED |
| Истечение | HELD, now ≥ expires_at | reserved −весь remaining_reserved | CLOSED, released увеличивается |
| Отгрузка | Только COMMITTED, q ≤ remaining_reserved | on_hand −q и reserved −q | COMMITTED либо CLOSED, consumed увеличивается |
| Приём проверенного возврата | Подтверждённое списание и не возвращённое ранее q, причина | on_hand +q | Старое обязательство не воскресает |

Отмена/истечение и refund — разные события. Refund не является основанием увеличения on_hand. Возврат без исходной отгрузки оформляется отдельным подтверждённым приходом, а не поддельной связью с заказом.

Исторический expires_at закрепления можно сохранять в ledger, но не в активном поле срока COMMITTED: worker не должен повторно освободить такой резерв.

## Время

Чистые проверки получают now аргументом, не читают системное время. Наивные datetime отвергаются. Aware datetime сравниваются как абсолютные моменты; документированный внешний формат будущего adapter — UTC. В точности на границе expires_at временный резерв уже истёк. Для COMMITTED и CLOSED срок не проверяется как активный таймер.

Production TTL не утверждён: 30 минут — предложение ТЗ для следующего шага. Здесь передаётся явный deadline. Refresh корзины не является командой продления. Продление/позднее подтверждение требуют будущего отдельного сервиса и прав; автоматического воскрешения CLOSED нет.

## Командный контекст и идемпотентность

OperationKind перечисляет разрешённые виды операций. OperationContext описывает operation_key, source, owner, reason и expected_revision. Это валидируемые метаданные команды, не хранилище идемпотентности.

Контракт следующего шага:

- Scope ключа: source + owner + operation_key. operation kind, target, quantities и expected_revision входят в нормализованный payload/fingerprint. Смена kind при прежнем ключе должна быть конфликтом, а не новой операцией.
- Первый результат сохраняется атомарно с остатком/ledger. Повтор того же payload возвращает прежний результат после проверки прав. Другой payload с тем же scoped key даёт конфликт.
- expected_revision защищает от применения команды к устаревшему снимку. Для инициализации будущий adapter определяет явную семантику отсутствующей записи, а не трактует revision0 как отсутствие существующего баланса.
- owner/source — безопасные непрозрачные ID, не email/адрес клиента или provider secret. Подлинность actor и разрешение команды устанавливает Django adapter, не DTO.
- Из строки причины нельзя вывести истинность факта прихода/возврата. Сотрудник и доступный сценарий проверяются адаптером. Никаких секретов, персональных адресов или платёжных токенов в ledger.

## Публичный API и ошибки

Публичный импорт: `from codex_ecommerce.inventory import ...`. Экспорты:

- StockKey, StockSnapshot, ReservationSnapshot, ReservationState.
- OperationKind (INITIALIZE, RECEIVE, ADJUST, RESERVE, COMMIT, RELEASE, EXPIRE, FULFILL, CHECKED_RETURN), OperationContext.
- require_stock(snapshot): возвращает корректный StockSnapshot либо ошибку отсутствия/некорректного снимка.
- require_available(snapshot, positive_quantity): возвращает тот же снимок при достаточности либо доменную ошибку. Не создаёт резерв и не обновляет revision.
- InventoryError и восемь конкретных ошибок из таблицы ниже.

ReservationSnapshot.is_expired(at) сравнивает оба момента после нормализации в UTC, включая повторный час DST. Он не освобождает количество и не меняет state.

| Класс ошибки | code | action |
|---|---|---|
| InvalidQuantityError | invalid_quantity | review_input |
| InventoryInvariantError | inventory_invariant | review_input |
| StockNotConfiguredError | stock_not_configured | configure_stock |
| InsufficientStockError | insufficient_stock | reduce_quantity |
| StaleRevisionError | stale_revision | refresh |
| ReservationExpiredError | reservation_expired | review_reservation |
| InvalidTransitionError | invalid_transition | review_reservation |
| IdempotencyConflictError | idempotency_conflict | review_operation |

Базовый InventoryError — ValueError с code=inventory_error и action=review_input. Ошибки не принимают произвольный message/payload. Stale/transition/expired/conflict уже имеют стабильный словарь, но сами операции, которые будут их выдавать, реализуются позже.

Доменные ошибки имеют стабильный код и безопасное действие. Текст/язык/HTTP принадлежат будущему Django adapter. Категории: неверное количество/снимок/идентификатор/время; не настроенный склад; нехватка; недопустимый переход; истёкший резерв; устаревшая версия; конфликт ключа. Последние ошибки определены для будущих операций, но их наличие не доказывает реализацию storage/locking/idempotency.

Не включать в публичный message/context полный payload команды, клиентские сведения, SQL или произвольный текст исключения. Не добавлять retry к бизнес-нехватке; временные DB ошибки и неизвестный исход операции определяются адаптером позже.

## Границы ответственности и проверка

Сейчас разрешены только immutable DTO, структурная валидация, чистые правила и тесты. Django модели, миграции, БД, checkout, UI, worker, eBay/DHL/Stripe и существующее demo поведение не изменяются. Нет dependency/container/runtime изменений.

Проверки шага1: числа и bool/float; conservation; состояния; частичные количества; UTC и граница expiry; неизменяемость; стабильный error code/action и отсутствие framework imports. PostgreSQL гонки, worker cleanup, ledger idempotency, резерв при оплате и ручные browser сценарии не заявляются выполненными.

Новых analytics/advertising событий, cookies, хранения PII или внешних передач нет. DTO содержат только операционные снимки и opaque IDs; они сами ничего не сохраняют. Retention/доступ/дедупликация persistent ledger проектируются и проверяются в шаге2.

Объём следующих шагов и критерии приёмки не удаляются из [полного ТЗ](../../tasks/active/2026-11-01-inventory-reservations-spec.md). Переход к шагу2 — только по отдельному поручению пользователя.


## Проверено 01.11.2026

Ведущий: 61 тест движка и полный набор 821 тест прошли; Ruff новых файлов и diff-check чистые. Независимый ревизор запустил 10 целевых тестов и проверил 1609 комбинаций состояний/количеств/времени отдельным скриптом без сохранения артефактов. Это проверка чистого контракта, не PostgreSQL-атомарности. Детали и окончательный статус — в разделе8 ТЗ.

## Учёт шага2

Этот раздел уточняет исторические ограничения шага1 выше. Теперь существуют чистые engine функции `initialize_stock`, `receive_stock`, `adjust_stock` и отдельный Django adapter `web.inventory`. Инициализация требует отсутствующего баланса и expected_revision=0, создаёт revision=1; приход положителен; корректировка задаёт абсолютный on_hand не ниже reserved. Каждая успешная команда повышает revision. Отсутствие склада не превращается автоматически в ноль.

`StockBalance` хранит один main-баланс на ProductVariant с DB unique и constraints. `InventoryMovement` хранит append-only журнал и dedup результат. Django app зарегистрирован, добавочная `inventory.0001_initial` подготовлена и проверена тестовыми миграциями, но **не применена к рабочей inet_mag**. Старые товары, demo_quantity и заказы не пересчитывались. Витрина пока не читает этот баланс.

Публичные backend команды `web.inventory.services.initialize/receive/adjust` принимают keyword-only actor, variant_id, quantity, context и необязательный location_id='main'. Контекст — OperationContext с source='staff', owner=str(actor.pk), непустой причиной, ключом и expected_revision. Причина до500 символов, ключ до160; пробелы по краям нормализуются. Количества ограничены signed bigint. Неизвестные/неактивные варианты и чужие склады отклоняются.

Actor повторно загружается из БД: нужен действующий is_active + is_staff, затем native permission `inventory.initialize_stockbalance`, `receive_stockbalance` или `adjust_stockbalance`. Это относится и к superuser: is_staff обязателен. Source/owner нельзя подставить от другого сотрудника. Группы и права существующих пользователей автоматически не назначаются. Machine principals и eBay adapter отсутствуют.

Порядок блокировок: ProductVariant, затем StockBalance. Parent lock сериализует первое создание отсутствующей строки. Баланс, movement и StaffAuditEvent сохраняются одной транзакцией. Нет HTTP/ожидания пользователя под lock. Только SQLSTATE40001/40P01 повторяют целую транзакцию один раз; прочие ошибки не маскируются. Восстановление после IntegrityError ограничено именованными inventory unique constraints.

Scope dedup — source+owner+operation_key; fingerprint включает kind, variant/location, quantity, expected_revision, нормализованную reason. Проверка прав предшествует replay. Точный повтор возвращает **первоначальный** StockSnapshot даже после следующих движений или деактивации варианта; второй ledger/audit не создаётся. Другой payload конфликтует. Неуспешная транзакция не захватывает ключ; после stale ошибки можно перечитать баланс и повторить неуспешную команду с новой revision. Shared-key конфликт разных SKU откатывает все изменения проигравшего SKU.

Read API: `web.inventory.selectors.stock` возвращает snapshot/None; `balances` и `history` — ограниченные списки с joined variant. Права `inventory.view_stockbalance` и `inventory.view_inventorymovement`; limit1..100, offset0..10000. Query budget истории superuser:2 запроса независимо от количества строк (проверка actor + выборка). Проверки разрешений обычного staff добавляют постоянные запросы. Чтение ничего не инициализирует.

### Операционные данные и доступ

Журнал содержит ID варианта/сотрудника, source/owner/key, reason, fingerprint, before/after/delta, результат/revision и UTC timestamp. Основание — необходимый служебный учёт; advertising/analytics consent не используется. Новых cookies/рекламных событий и внешних передач нет. В reason нельзя вводить адреса, email, секреты или платёжные данные. Полный request/SQL/сырой exception в audit не сохраняется.

Обычные ORM update/delete/bulk пути ledger запрещены; изменения баланса доступны только service scope. Это защита штатных путей, не sandbox для доверенного Python и не запрет SQL администратора: DB triggers/grants не добавлены. Variant и actor защищены PROTECT; сотрудника с журналом можно деактивировать, удаление блокируется. Будущая privacy-очистка требует отдельного решения, а не обхода истории.

Автоматический срок удаления пока не утверждён: журнал и ключи не очищаются, иначе поздний повтор мог бы повторить движение. Правовой срок, архивирование и стратегия tombstone до production требуют отдельного утверждения. Это явное эксплуатационное ограничение. Ни отзыв рекламного согласия, ни refund не удаляют складской журнал и не меняют остаток.

### Ручной QA и PostgreSQL

Воспроизводимый безопасный прогон: `.venv/Scripts/python.exe tools/test_inventory_postgres.py`. Он принимает только локальный PostgreSQL из .env, создаёт UUID-базу `test_inet_inventory_<uuid>`, мигрирует только её и удаляет в finally. Имя рабочей БД и существующее имя запрещены; аргументы keepdb/reuse/settings не принимаются, секреты не печатаются. Рабочая миграция этим runner не применяется.

Для пошагового Python QA использовать только отдельную disposable БД с тестовыми actor и variant, как fixtures в `tests/web/test_inventory_accounting.py`. Внутри теста последовательность:

```python
from codex_ecommerce.inventory import OperationContext
from web.inventory import selectors, services

def ctx(key, revision):
    return OperationContext(key, 'staff', str(actor.pk), 'QA counted stock', revision)

first = services.initialize(actor=actor, variant_id=variant.pk, quantity=0, context=ctx('init', 0))
received = services.receive(actor=actor, variant_id=variant.pk, quantity=7, context=ctx('receipt', 1))
counted = services.adjust(actor=actor, variant_id=variant.pk, quantity=5, context=ctx('count', 2))
assert services.receive(actor=actor, variant_id=variant.pk, quantity=7, context=ctx('receipt', 1)) == received
assert selectors.stock(actor=actor, variant_id=variant.pk) == counted
assert len(selectors.history(actor=actor, variant_id=variant.pk)) == 3
```

`actor` — persisted active staff superuser fixture, `variant` — disposable active variant fixture; это не готовая команда для shell рабочей БД. Затем проверить конфликт того же ключа с другой quantity, stale revision и отказ staff без action permission: баланс/история остаются прежними. UI на этом шаге отсутствует.

Результаты ведущего: полный suite878 passed/6 skipped; отдельный PostgreSQL прогон34 passed, тестовая БД удалена. Шесть пропусков общего SQLite suite — PostgreSQL concurrency tests, выполненные отдельно. Проверены независимые соединения, первое создание, replay, stale races, абсолютные корректировки и rollback cross-SKU collision. Ruff/check/migration drift чистые. Рабочая миграция `[ ]0001_initial`. Независимый ревизор отдельно выполнил PG34 и целевые67; его общий suite завис на завершающей части и был остановлен, поэтому независимый полный прогон не заявляется успешным.

Следующие шаги: реальные reservation строки и reserve/commit/release/fulfill; затем cleanup expiry, checkout, storefront и кабинет. На шаге2 reserved хранится как подготовленный счётчик, но резервов ещё нет. Нет внешних вызовов, outbox delivery, commit/push/deploy.

## Резервы шага3

Статус: reviewed-awaiting-acceptance, независимая ревизия завершена без существенных замечаний. Рабочая БД не мигрируется. Новая попытка бронирования получает отдельный opaque reference; прежний закрытый reference нельзя повторно использовать для нового hold. Reference не содержит email/адрес, ограничен100 символами и уникален глобально в локальном inventory. Допускается `[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}`, URL/email/пробелы отклоняются. Привязка к настоящей строке заказа появится на шаге5.

Добавлены immutable `ReservationResult(stock, reservation)` и trailing revision с default0 в ReservationSnapshot (прежний positional API сохранён). Новая persisted строка начинается с1. Сохранённый `reserved` баланса равен сумме remaining_reserved строк при штатной последовательности service команд. Каждая команда, включая закрепление без изменения количеств, повышает revision баланса и строки. `context.expected_revision` защищает баланс, отдельный `expected_reservation_revision` — строку.

Переходы: `reserve_stock` создаёт HELD после проверки available; `commit_reservation` переводит HELD в COMMITTED; `release_reservation` освобождает положительное q не больше remaining; `fulfill_reservation` списывает положительное q только из COMMITTED. Последние два закрывают строку при remaining=0. Частичная отгрузка сохраняет COMMITTED, увеличивая consumed. Частичная отмена HELD сохраняет прежний deadline; закрепление очищает активный deadline. У CLOSED expires_at=None.

Все команды принимают aware now; reserve дополнительно будущий expires_at. Сравнение по UTC, равенство deadline уже истечение: commit отклоняется. Явная отмена/release допускается и после deadline, чтобы не блокировать освобождение. Автоматическое истечение и поздняя оплата — шаг4; никакого авто-восстановления и скрытого продления.

now задаёт доверенный backend caller, а не поле пользовательской формы. При будущем HTTP/checkout подключении время формируется сервером; произвольное время из запроса передавать нельзя. Сервис сохраняет decision_at отдельно от времени записи журнала created_at. На этом шаге публичного endpoint нет.

now — время решения, не часть fingerprint, иначе безопасный повтор после timeout превратился бы в конфликт. Deadline reserve, reference, количества, версии, reason и target входят в fingerprint; deadline нормализуется по UTC. Успешный replay после deadline возвращает первоначальный результат, не меняя текущий резерв и не закрепляя его заново. Неуспешная команда не занимает ключ и при повторе заново проверяет время и версии.

Новые action permissions: `inventory.reserve_reservationline`, `commit_reservationline`, `release_reservationline`, `fulfill_reservationline`; чтение `view_reservationline`. Проверка active staff и owner/source повторяется как в учёте. Деактивация варианта запрещает новый reserve, но не запирает уже созданное обязательство: commit/release/fulfill существующей строки возможны при остальных предусловиях и правах.

Backend API экспортирован из `web.inventory.services`: reserve(actor,variant_id,reservation_id,quantity,context,expires_at,now,expected_reservation_revision=0,location_id='main'); commit(actor,variant_id,reservation_id,context,expected_reservation_revision,now,location_id='main'); release/fulfill имеют также quantity. Все аргументы keyword-only; результат ReservationResult. Read API `selectors.reservation(actor,reservation_id)` возвращает snapshot/None, `selectors.reservations(actor,variant_id=None,location_id='main',limit=50,offset=0)` — список joined ReservationLine по reference. Обычные пределы пагинации сохраняются; запроса на каждую строку нет.

Добавочная `inventory.0002_reservation_lines` создаёт ReservationLine с constraints conservation/state/counters и расширяет ledger nullable полями reservation FK PROTECT, expected_reservation_revision, before_reservation, after_reservation и decision_at. Существующие accounting rows остаются валидны с NULL этих полей; миграция0001 не переписана. Рабочие миграции0001/0002 не применяются.

Штатный порядок блокировок: variant → balance → reservation. Все операции одной строки атомарно обновляют balance, reservation, ledger и audit. Scoped ключ общий с accounting. История дополняется reservation ID и versioned before/after snapshots, без клиентских данных. Reservation identity/original не редактируются штатным ORM; удаление и обход service запрещены. Администратор raw SQL по-прежнему вне этой гарантии.

JSON результата имеет строгий набор внутренних полей: reservation_id,variant_id,location_id,original,remaining_reserved,consumed,released,state,expires_at,revision. Неверная форма/снимок приводят к отказу, а не восстановлению результата из текущего состояния. Сохраняется именно оригинальная revision строки. Отдельного общего JSON editor или произвольного пользовательского JSON нет.

Данные резерва — reference/variant/main, counters/state, deadline/revision; ID сотрудника хранится в общей истории. Это служебный учёт, новые аналитические/рекламные события и внешняя передача не добавляются. Срок архивирования закрытых строк и tombstone reference ещё не утверждён; автоматического удаления нет, иначе повтор мог бы создать вторую бронь. Отзыв рекламы не отменяет обязательства заказа. До production необходимы утверждённые сроки и privacy-процесс вместе с ledger.

### QA переходов: ожидаемый сценарий

Только в disposable fixture БД, после инициализации5 единиц (revision1), с тем же active staff actor и ctx(key,revision) из примера выше:

```python
from datetime import UTC, datetime, timedelta
from codex_ecommerce.inventory import ReservationState

now = datetime(2026, 11, 1, 12, tzinfo=UTC)
held = services.reserve(actor=actor, variant_id=variant.pk, reservation_id='qa-line-1',
    quantity=3, context=ctx('hold', 1), expires_at=now + timedelta(minutes=30), now=now)
committed = services.commit(actor=actor, variant_id=variant.pk, reservation_id='qa-line-1',
    context=ctx('commit', 2), expected_reservation_revision=1, now=now)
shipped = services.fulfill(actor=actor, variant_id=variant.pk, reservation_id='qa-line-1',
    quantity=2, context=ctx('ship', 3), expected_reservation_revision=2, now=now)
closed = services.release(actor=actor, variant_id=variant.pk, reservation_id='qa-line-1',
    quantity=1, context=ctx('cancel-rest', 4), expected_reservation_revision=3, now=now)
assert (closed.stock.on_hand, closed.stock.reserved) == (3, 0)
assert closed.reservation.state is ReservationState.CLOSED
assert (closed.reservation.original, closed.reservation.consumed, closed.reservation.released) == (3, 2, 1)
assert services.fulfill(actor=actor, variant_id=variant.pk, reservation_id='qa-line-1',
    quantity=2, context=ctx('ship', 3), expected_reservation_revision=2,
    now=now + timedelta(hours=1)) == shipped
```

После replay текущее состояние должно остаться closed, on_hand3/reserved0: возвращается прежний результат команды ship, а не текущее состояние. Дополнительно проверить commit точно на deadline, release сверх remaining, повтор закрытого reference с другим ключом, устаревшую версию, staff без разрешения и rollback после сбоя audit. Эти проверки не выполняются в shell рабочей БД и не являются оформлением реального заказа.

### Проверки реализации шага3

Ведущий: полный suite **935 passed/13 skipped**; отдельный safe PostgreSQL runner **86 passed**, disposable DB удалена. Все13 PG cases общего suite были выполнены в этом runner на настоящих отдельных соединениях. Покрыты последняя единица, same-key reserve/commit и старый replay после cancellation, конкурирующие release/fulfill, accounting-vs-reserve CAS, forced cross-target key collision и global reference race с rollback проигравшего, многолинейная conservation. Проверены ledger/audit rollback, ограниченный transient retry и permissions. Ruff/check/migration drift/diff-check чистые.

Первый PG прогон ведущего выявил неправильный приоритет shortage над stale revision, без oversell. После падающего regression порядок исправлен: структура/положительность → версия → availability; fresh version с нехваткой по-прежнему даёт InsufficientStock. Финальные86 прошли после исправления. Read-only проверка ведущего: рабочая БД показывает неприменённые0001/0002.

Независимый ревизор отдельно получил124 targeted,86 PostgreSQL и935 passed/13 skipped полного suite; check/drift/Ruff/diff pass. Все S3-R1..R7 и финальные существенные claims подтверждены, новых замечаний нет. Это проверка backend и disposable schema, не подключение к UI/checkout, не эксплуатация рабочей БД и не пользовательская приёмка. Следующий шаг4 — expiry cleanup и гонка с подтверждением — не начат.

## Истечение шага4

Статус: reviewed-awaiting-acceptance, независимая ревизия завершена без существенных замечаний. Последняя запись уточняет исторические границы шага3. Рабочая схема не применяется и автозапуск сейчас не включается. Публичный engine `expire_reservation(stock,reservation,context,expected_reservation_revision=...,now=...)` принимает только due HELD. Он освобождает весь remaining, увеличивает released, закрывает строку и очищает deadline; on_hand не меняется. Обе версии повышаются. COMMITTED, включая частично отгруженный, не истекает; CLOSED не открывается заново.

### Backend и конкуренция

`web.inventory.expiry_service.expire_due_reservations(*,actor,now,batch_size=100)` возвращает frozen `ExpirySummary(scanned,expired,skipped,has_more)`. Нужен persisted active staff с `inventory.expire_reservationline`. `due_reservations` с теми же аргументами делает только preview: scanned — число кандидатов в пределах лимита, expired=0, skipped=scanned, has_more показывает превышение лимита. Никаких записей из GET/selector/preview.

Batch1..100, UTC cutoff фиксирован для запуска. Кандидаты упорядочены по deadline/variant/reference; каждый резерв меняется своей короткой top-level транзакцией с блокировками variant→balance→reservation. NOWAIT не ждёт занятую строку: SQLSTATE55P03 даёт skipped, остальные неизвестные ошибки не скрываются. Budget5s ограничивает начало обработки следующих строк, а не гарантирует жёсткие5 секунд для любого сетевого/дискового сбоя БД. Настройки DB statement/lock timeout и HTTP timeout остаются отдельными пределами.

Одна транзакция содержит баланс, закрытие строки, EXPIRE movement и audit. Устойчивый scope `inventory_expiry/system/expire:<reference>` не принимается из staff OperationContext. Референс не переиспользуется, продление не добавлено. Повтор и параллельный cleanup после блокировки перечитывают состояние; закрытый/закреплённый резерв не меняют. Отдельные уже закрытые строки batch остаются закрытыми, если следующая строка дала ошибку. Повтор запуска продолжает due строки. Автоудаления истории/ключей нет.

Если закрепление успело до deadline и сохранило COMMITTED, очистка не освобождает его по старому времени. Если истечение выиграло, новое подтверждение получает `reservation_expired`/`review_reservation`; автоматического re-hold, refund или списания денег нет. Если выполняется повтор ранее успешного commit с тем же ключом, возвращается исходный результат без нового эффекта. Это исход команды, а не подтверждение текущего активного состояния: новый checkout обязан перечитывать данные.

### Остановленный worker и изменения SKU

После проверки основного action permission и successful replay, перед новой мутацией выполняется cleanup затронутого SKU: максимум20 строк и тот же budget. Incidental maintenance не выдаёт сотруднику ручное глобальное право expiry. Явный release исключает собственный target из precleanup: отмена истёкшего HELD продолжает работать и конкурирует с EXPIRE. Другие due строки того же SKU чистятся обычным путём.

Accounting `services.initialize/receive/adjust` теперь допускает дополнительный keyword `now=None`: по умолчанию backend берёт `django.utils.timezone.now()`. Для детерминированных QA передаётся явный aware UTC; now не входит в fingerprint. Reservation команды по-прежнему получают now явно от доверенного caller. Передавать клиентский timestamp напрямую нельзя.

Expiry сохраняется независимо от последующей ошибки основной команды. Переданный expected_revision не заменяется свежим: после cleanup возможен `stale_revision`, нужно перечитать остаток. Если backlog/занятые due строки остались — `expiry_backlog`/`retry_cleanup`, без бесконечного drain. Сама основная транзакция повторно проверяет отсутствие due work, появившегося между scan и lock. Переданная временная точка — доверенный backend cutoff, не пользовательское поле.

Нельзя обещать отдельный commit внутри чужого atomic: batch всегда требует autocommit, opportunistic path отклоняет внешний atomic при наличии due work до записи (`expiry_requires_autocommit`/`retry_outside_transaction`). Старые no-work операции остаются совместимыми с atomic, но будущий checkout UoW проектируется отдельно на шаге5.

### Ручной запуск и автоматизация

Команда `expire_inventory_reservations --actor <staff-id> --batch-size 100` по умолчанию dry-run. `--apply` явно включает изменения. Время формирует сервер, аргумента произвольного now нет. Использовать на текущем этапе только отдельную disposable БД с подготовленной schema/fixtures. Не запускать apply на рабочей inet_mag: миграции0001/0002/0003 там не применялись в рамках задачи. Preview и apply проверяют действующие native права; superuser для automation не требуется и не рекомендуется.

Автоматический путь: ARQ cron раз в минуту → ограниченный POST `/internal/inventory/expiry/` → тот же сервис. Отдельной задачи/таймера на каждую строку нет. Worker image по-прежнему содержит только workers и независимый engine, без Django/ORM/копирования web. HTTP вынесен в executor и не блокирует event loop. Redis не хранит истину о сроках и остатке: после пропуска тиков due строки остаются в PostgreSQL.

Настройки `.env.example` и Compose template:

| Переменная | Назначение |
|---|---|
| INVENTORY_EXPIRY_ENABLED=0 | Только значение1 включает backend endpoint и ARQ cron; по умолчанию выключено |
| INVENTORY_EXPIRY_TOKEN | Один выделенный случайный Bearer secret минимум32 символа у web/worker; не Git/URL/job args |
| INVENTORY_EXPIRY_ACTOR_ID | Серверный persisted active staff с единственным нужным expire permission |
| INVENTORY_EXPIRY_BATCH_SIZE=100 | Серверный предел1..100 |
| INVENTORY_EXPIRY_URL | Явный URL worker; для local Compose http://web:8000/internal/inventory/expiry/ |

Endpoint не принимает actor/time/batch из запроса; тело пустое или `{}`. Cookie login и CSRF token не дают доступ: единственная аутентификация — dedicated Bearer с constant-time сравнением. CSRF exemption только на этой функции, остальные формы не затронуты. Disabled404, метод405, неверный Bearer403, неверный/избыточный payload400/413, безопасная ошибка сервиса503; ответы no-store и не содержат SQL/секретов/товаров/адресов.

Worker не следует redirect и не использует environment HTTP proxy. Разрешены HTTPS и HTTP только к literal loopback/hostnameweb внутри Docker. Для web нужен соответствующий ALLOWED_HOSTS (в local example добавленweb). Учётные данные не пересылаются в redirect location. Ответ ограничен8KiB, проверяется точная форма четырёх счётчиков. HTTP socket timeout8s и общий read deadline8s ограничивают чтение; последний блокирующий read может добавить до одного socket timeout, то есть это не строгие8 секунд wall time. Cron timeout15s может завершить job раньше остаточного потока; результат backend тогда неизвестен, повтор безопасен благодаря строкам/журналу, а не предположению «ничего не произошло».

Это также не гарантированный общий предел16 секунд: DNS/getaddrinfo, перебор адресов и фазы открытия соединения не ограничены одним общим wall-clock deadline. Не трактовать socket/read limits как гарантию завершения всей сетевой операции к фиксированной секунде.

Для будущего включения: отдельно применить проверенную schema, создать/назначить служебного actor и expire permission, сохранить token вне Git, проверить URL/Host/TLS, выполнить dry-run и apply на тестовом запасе, затем включить flag1 на web и worker. Выключение flag0 на worker останавливает новые cron-запуски; backend flag0 запрещает новые HTTP операции. Уже начатая транзакция может завершиться. После простоя повторный batch продолжает очистку; не требуется восстанавливать Redis-таймеры.

Существующий HTTPS staging дополнительно имеет SSL redirect, Basic Auth и ограниченный Host. Они не отключаются и не обходятся поддельными proxy headers. Его внутренний маршрут/разрешения и worker env должны настраиваться отдельным разрешённым deployment; текущая задача не включает эту активацию. Реальная .env, working data, существующие containers и staging не меняются.

### Данные, наблюдаемость и QA

Новые данные — EXPIRE movement, before/after counters/deadline/revisions и timestamp решения; actor первого действия связан FK PROTECT. Клиентские сведения/платёжные данные не добавляются. Служебные логи содержат UTC success/error и scanned/expired/skipped/has_more, без Bearer/URL/body/SQL. Это необходимая эксплуатационная диагностика, не advertising analytics; новых SDK/cookies/внешних получателей нет. История и refs не удаляются автоматически; production сроки/архив/tombstone и retention логов/backup требуют утверждения до live. В staging уже настроена ограниченная ротация container logs, отдельный analytics stack не создаётся.

Проверочный сценарий в disposable DB: создать две HELD строки с due deadline и одну COMMITTED → preview без изменений → apply с batch1 закрывает только одну due → повтор закрывает следующую → повтор пустой, COMMITTED сохранён. Для гонки запускать cleanup и commit на разных PostgreSQL connections; допустим только один итог. Затем остановленный-worker path: новая мутация SKU сама освобождает due, основной stale/failed command не откатывает EXPIRE. После перечитывания допустима новая операция, но старый reference не воскресает. Тесты transport отдельно проверяют auth, body bounds, disabled, redirect, safe error и настоящую worker→HTTP→Django→disposable DB цепочку. Доставка через реально запущенный ARQ/Redis и включение рабочего cron не выводятся из HTTP теста.

### Результаты ведущего шага4

Полный suite993 passed/19 skipped; safe PostgreSQL runner129 passed с удалением UUID DB. В runner вошла настоящая HTTP-цепочка на PostgreSQL и все19 PG cases: два cleanup, commit/expiry и cancel/expiry, NOWAIT при удержанном commit lock и сохранение COMMITTED после partial fulfillment, stopped-worker opportunistic cleanup с независимым commit и batch failure recovery. Проверены native permissions, bound/time/backlog/outeratomic, ошибки/rollback, ручной dry-run/apply, transport negative cases и no-Django worker import. Ruff src/tests/runner, check/drift/localCompose validation pass. Эти числа — проверки ведущего, не deployment/working activation.

Независимый ревизор отдельно получил993 passed/19 skipped и129 PostgreSQL passed с удалением базы, подтвердил все S4-R1..R8 и финальные существенные claims с указанной оговоркой о сетевом времени. Рабочая схема0001/0002/0003 остаётся неприменённой по read-only проверке ведущего. Доставка реально запущенной ARQ/Redis и активация cron не подтверждаются; подтверждён настоящий task→HTTP→Django→тестовый PostgreSQL. Шаг5 оформления не начинался.

## TEST checkout шага5

Статус: reviewed-awaiting-acceptance в disposable контуре. Существующий `web.orders.persistence.create_test_order(request, token)` — точка входа атомарного inventory TEST checkout. В режиме inventory_test Order, snapshots всех строк, HELD, balance RESERVE movements и audit сохраняются одной транзакцией. Нехватка любого SKU или ошибка сохранения откатывают все **новые** эффекты заказа. Корзина, купон, адрес и intent остаются у покупателя. Обычное добавление в корзину, GET и review ничего не удерживают. On_hand при checkout не списывается, статус не обозначает реальную оплату/отгрузку.

Режимы явные: `SHOP_CHECKOUT_STOCK_MODE=demo|inventory_test`, defaultdemo; `SHOP_CHECKOUT_RESERVATION_TTL_SECONDS=1800`, пределы60..3600 для TEST. Этот TTL не является live policy. Inventory_test quote читает StockBalance.available и не подставляет demo_quantity при отсутствии записи/нуле/ошибке БД. Demo остаётся отдельным режимом без резервов. Не копировать старые demo/заказы в склад миграцией. Общий каталог/PDP пока не переключаются — это шаг6.

Перед основной транзакцией выполняется bounded очистка due затронутых SKU в autocommit. Она может сохраниться даже при последующей нехватке нового заказа: это освобождение старых истёкших обязательств, а не частичный резерв нового. Лимиты≤50SKU/≤100 кандидатов/≤20 на SKU, soft5s между обработками; backlog требует повтора. Основная транзакция только перечитывает/проверяет отсутствие новой due работы, не вызывает public staff reserve и не обещает независимый commit внутри чужого atomic.

Порядок locks: variant parents ascendingID → balances ascendingvariantID → product parents ascendingID → coupon → order/lines/reservations. Значения баланса и deadline задаёт сервер после lock, не browser. Quote ограничен товарами корзины, joined variant locks только self, чтобы не захватывать brand/product неявно. Повтор intent перечитывается после quote с locks, но до проверки can_checkout, поэтому не отклоняется из-за своих же резервов.

Order хранит stock_mode, checkout_fingerprint и inventory_hold_expires_at как исторический снимок. ReservationLine получает nullable OneToOne/PROTECT на OrderLine; старые строки NULL, связь входит в immutable identity. Canonical source checkout_test, owner order UUID, key reserve:<line.pk>, reference orderline:<orderUUIDhex>:<line.pk>. InventoryMovement.actor nullable PROTECT; guest/customer checkout и его housekeeping используют actorNone без фиктивного сотрудника. Реальный user/session owner остаётся в существующем Order. Public staff/cleanup permissions не ослабляются.

Owner+подпись+max_age+nonce+fingerprint и native CSRF сохраняются. Новая операция требует текущий nonce; одна identity с иным непустым сохранённым fingerprint отклоняется. Точный успешный replay возвращает оригинальный заказ, не создаёт hold, не продлевает срок и не меняет новую корзину. Старые owned orders с пустым историческим fingerprint допускают только чтение прежнего результата, без backfill. Inventory reservation не является доказательством платежа.

После commit очищаются только всё ещё совпадающие intent/cart/coupon/address. Для inventory_test используется штатная DB session с SAVE_EVERY_REQUEST=False: post-commit finalizer блокирует session row, перечитывает persisted payload, сохраняет только условное удаление checkout keys и обновляет request session так, чтобы middleware не записал старый cache поверх новой корзины. Несовпадение сохранённого intent/данных — без очистки. Это не общая транзакционность всех параллельных cart запросов: запрос, ранее загрузивший старую сессию, всё ещё может записаться позже. Не обещать атомарность DB заказа и session; повтор после post-commit/session сбоя возвращает тот же заказ без второго резерва.

Тексты DE/RU различают корзину до резервирования и исторически созданный hold. Подтверждение использует сохранённый stock_mode заказа, а не текущую настройку, и не заявляет, что hold ещё активен после expiry. Ошибки inventory_unconfigured/inventory_shortage/inventory_retry/inventory_unavailable не раскрывают SQL и сохраняют корзину. Визуальные компоненты и CSS остаются reference.

Новые данные — режим/хэш review snapshot/deadline и ID связи orderline. Это служебный TEST учёт; хэш не объявляется анонимизацией. Клиентские адреса/email/raw token/session cookie не попадают в inventory ledger/reason/logs; маркетинговых событий/SDK/cookies/передач не добавлено. История/ссылки PROTECT не удаляются автоматически. Production retention/архивирование/subject deletion для связанных Order/Reservation и backup требуют отдельного утверждения до live.

Текущая проверка — disposable PostgreSQL/schema и нативный POST checkout. Рабочая активация/схема/начальные реальные остатки не выводятся из успешных тестов. Новые поля существующего Order требуют стандартных добавочных миграций перед использованием обновлённого checkout в работающей БД; не обходить это скрытым fallback или переносом метаданных в адрес. Оплата, письма, DHL/eBay, авто-подтверждение платежа и шаг6 не входят в этот пункт.

### Ручной QA шага5 в изолированном контуре

Безопасный пошаговый Python QA использует штатный pytest debugger с готовыми fixture, **только SQLite test settings**. Рабочая .env не загружается; перед вводом убедиться, что banner показывает `web.config.settings.test`. Команда:

```console
.venv/Scripts/python.exe -m pytest -s --trace tests/web/test_inventory_checkout.py::test_native_guest_inventory_checkout_is_atomic_and_does_not_use_demo --ds=web.config.settings.test
```

На остановке `(Pdb)` fixture `client,records` уже готовы: два варианта с реальным остатком3 и demo_quantity0. Все команды ниже начинаются `!` (Python), модели/помощники импортированы в тесте. Это ручной прогон HTTP через Django test client, **не browser acceptance**. Не заменять settings на local/staging и не запускать данный сценарий в manage_local shell.

1. `!actor, variants = records`, затем `!token = prepare(client, variants, quantity=2)`. GET/review не создали Order/Reservation; проверить `!print(Order.objects.count(), ReservationLine.objects.count())` → `0 0`.
2. Создать нехватку второго SKU: `!services.adjust(actor=actor, variant_id=variants[1].pk, quantity=1, context=OperationContext('qa-shortage', 'staff', str(actor.pk), 'Manual QA', 1))`. Затем `!result = post(client, token)`. Ожидается409; `Order/OrderLine/ReservationLine` остаются0, `client.session['local_cart_guest']` содержит оба SKU по2. Staff ADJUST/initial ledger существуют и не относятся к откату нового заказа.
3. Восстановить только fixture остаток: `!services.adjust(actor=actor, variant_id=variants[1].pk, quantity=3, context=OperationContext('qa-restore', 'staff', str(actor.pk), 'Manual QA', 2))`. `!result = post(client, token)` →302; один Order, две OrderLine и две HELD. `!print(list(StockBalance.objects.values_list('on_hand', 'reserved')))` → обе пары `(3,2)`; корзина очищена после commit, on_hand не списан.
4. Проверить expiry/replay и новую корзину: `!order = Order.objects.get()`, `!client.post(reverse('cart:add'), {'sku': variants[0].sku, 'quantity': 1})`, `!expire_due_reservations(actor=actor, now=order.inventory_hold_expires_at)`, затем `!post(client, token)`. Это тот же один заказ, все его строки CLOSED, новый hold не появился, новая корзина содержит первый SKU по1.
5. Проверить независимый cleanup при провале нового заказа. `!t0 = timezone.now()`, `!balance = StockBalance.objects.get(variant=variants[0])`; создать staff hold1 с reference/key `manual-stale-hold`, expected_revision=balance.revision, now=t0, expires_at=t0+timedelta(seconds=1). Новый клиент: `!other = Client()`, `!other_token = prepare(other, variants)`. Изменить цену второго fixture SKU: `!ProductVariant.objects.filter(pk=variants[1].pk).update(price='99.00')`. Выполнить `!with patch('web.orders.persistence.timezone.now', return_value=t0+timedelta(seconds=2)): failed = post(other, other_token)`. Ожидается409 stale: старый staff hold CLOSED через EXPIRE, нового Order/checkout holds нет, оба SKU по1 остаются в `other.session['local_cart_guest']`.
6. Для завершения ввести `q`, не `c`: тестовый сценарий после ручных изменений не продолжается с начала. Pytest завершит fixture/память тестовой БД. Ненулевой код при сознательном выходе из debugger не является провалом уже наблюдённых ручных assert.

Ведущий отдельно прошёл эту последовательность с assert shortage/success/expired replay/cleanup+failure. На Windows первый sandbox TTY запуск ограничил доступ Django formatter к Console registry; повтор с разрешённым локальным terminal runtime прошёл. Это ограничение окружения, не причина менять код приложения. Ручной SQLite прогон не доказывает locks: concurrency независимо проверяется safe PostgreSQL runner, где те же case requirements используют отдельные connections.

### Итог проверки шага5

Ведущий:1036 passed/26 skipped полного suite и179 PostgreSQL passed с удалением UUID DB; scoped Ruff/check/drift/Compose validation/diff-check pass. Ревизор отдельно получил1036/26 и179+cleanup, подтвердил S5-R1..R8 и финальные claims. Исправлены только замечания документации: явный manual QA и точный формат reference. Layout/CSS сохранены по template diff, browser acceptance не заявляется.

В PostgreSQL проверены разные checkout последней единицы, same intent, disjoint SKU с одним intent/разными подписанными payloads (реальная unique-constraint recovery), обратный порядок SKU, checkout-vs-staff, поздний audit failure с rollback всех строк и expired original replay с сохранением новой корзины. Старая рабочая schema/активация отдельно: source требует стандартного orders0005 иinventory0004 с зависимостями; defaultdemo не является обходом миграции. Начальные реальные остатки не создаются автоматически. Шаг6 не начат.

### Текущая локальная dev-схема после уточнения владельца

Проект разрабатывается с нуля и не обслуживает live-продажи. Владелец уточнил: shop.pinlite.dev — демонстрация интерфейса соучредителю; текущая задача туда не разворачивается. Обычные проверенные добавочные миграции локальной dev-базы выполняются вместе с задачей, без отдельного backup/approval gate. Удаление/reset данных и публикация демонстрационного стенда этим не разрешаются.

Локально применены orders0005 и inventory0001–0004, Django check чистый, Order новые поля читаются. Сохранены прежние2 заказа/2 позиции/4 товара/32 варианта/1 пользователь. Складские таблицы пустые: demo_quantity не копировался в stock. Mode остаётсяdemo, expiry выключен. Для включения inventory_test нужен явно подготовленный тестовый/подтверждённый запас, это не fallback по отсутствующей записи. Запущен local Django127.0.0.1:8030; health/cart/payment GET smoke200, последний следует обычному redirect пустой корзины. Ранее в разделах1–5 заявления о неприменённой схеме описывают историческое состояние до этого уточнения.

## Шаг6 — общий источник доступности (05.11.2026, reviewed-awaiting-acceptance)

Единый read-only снимок доступности должен использоваться в публичном каталоге, выборе варианта, PDP, корзине и существующих staff-представлениях остатков. Режим выбирается серверной конфигурацией SHOP_CHECKOUT_STOCK_MODE: demo использует только демонстрационные количества; inventory_test — только main StockBalance и available=on_hand-reserved. Отсутствующая запись не превращается в demo fallback. Настроенный ноль и отсутствующая настройка различаются на уровне projection/checkout; публичная доступность в обоих случаях false.

GET не создаёт, не продлевает и не освобождает резерв; истёкший HELD остаётся учтённым в reserved до установленного cleanup. Это консервативная доступность, а не скрытая запись при просмотре. Финальный POST шага5 остаётся авторитетным: блокировки, cleanup/recheck и атомарный hold. Страница показывает снимок, который может измениться до оформления.

Фильтры цвета, размера, цены, sale и in_stock должны совпадать у одного активного подходящего варианта. При сортировке по цене и первоначальном выборе используется тот же matching SKU. На странице не выбирается автоматически другой размер после явного выбора покупателем. Нет loading всех movements/reservations на карточки или скрытого запроса на каждый вариант.

Для шага6 не нужны новые клиентские события/SDK/cookies/персональные данные: это вычисление из уже существующих товарных и складских записей для работы магазина. Дополнительная аналитика и её сроки не вводятся. Доступность товара публичная; внутренние складские журналы, причины корректировок и идентичности сотрудников не передаются в projection страницы. Настройки доступа staff и прежний юридический/SEO noindex сохраняются. JSON-LD по-прежнему не обещает live Offer для TEST-магазина.

План и критерии S6-R1..R7: tasks/active/2026-11-01-inventory-reservations-spec.md раздел13. Фактические API, проверки и ограничения будут зафиксированы после реализации и независимой ревизии. Удалённый shop.pinlite.dev не изменяется; локальные остатки не заполняются из demo.

### Реализация projection и ручная проверка шага6

`web.inventory.availability.InventoryAvailability` — frozen/slots web read model: mode, quantity (None при отсутствии настройки), eligible, свойства configured/available. Это Django presentation boundary, не новый ORM-контракт независимого engine. `with_availability(queryset)` добавляет scalar annotation main balance через коррелированный Subquery; demo не обращается к inventory таблицам. Нужен свежий queryset в текущем режиме: property не делает скрытый SELECT на вариант. Snapshot уже прочитанного объекта не обещает realtime обновление.

Locked checkout передаёт projection уже заблокированные balance rows; annotation не заменяет locks и не добавляет повторное независимое чтение в критический расчёт. Обычные catalog prefetch/selectors загружают annotated rows пакетно. Preview API передаёт нейтральный variant.available и mode; старое demo_available относится только к явному demo ответу. `inventory_test` не превращается в live режим.

Безопасный ручной QA: использовать disposable fixture `tests/web/test_inventory_availability.py`, settings `web.config.settings.test`, не менять local .env и не инициализировать рабочий запас. Команда `.venv/Scripts/python.exe -m pytest -s --trace tests/web/test_inventory_availability.py::test_projection_distinguishes_missing_zero_and_reserved_without_demo_fallback --ds=web.config.settings.test` останавливается перед проверками с подготовленными fixture. В Pdb изучить `inventory` (actor/product/variants), затем получить rows через `with_availability(ProductVariant.objects.all())` и snapshot через `InventoryAvailability.from_variant(row)`: ожидаемые quantity None/0/0/3 при demo_quantity90 у всех. Продолжить `c`, чтобы штатный тест закончил свои assert и очистил test DB. Для HTTP-потока запустить test_pdp_preview_home_recommendations_cart_agree_and_reads_do_not_expire; он проверяет реальные Django GET/POST с тестовой сессией и не является browser acceptance. Дополнительные проверки позднего expiry/fresh read и бюджета находятся рядом. Не выполнять эти fixture-операции в manage_local shell или на shop.pinlite.dev.

В Pdb импорты для предыдущего примера задаются явно: `!from web.inventory.availability import InventoryAvailability` и `!from web.inventory.availability_queries import with_availability`, затем `!print([(s.quantity, s.configured, s.available) for s in [InventoryAvailability.from_variant(row) for row in with_availability(ProductVariant.objects.all()).order_by('pk')]])`. Ожидается `[(None,False,False),(0,True,False),(0,True,False),(3,True,True)]`.

### Проверки и текущий результат шага6

Исполнитель: полный `python -m pytest -q` — **1053 passed,26 skipped in50.97s**. Безопасный `tools/test_inventory_postgres.py` — **196 passed in44.85s**, UUID disposable database удалена; включает17 новых availability tests и прежние179 проверок adapters/concurrency/transport. Scoped Ruff src/tests/runner, Django check, migration drift и diff-check pass. Repo-wide Ruff не объявляется чистым:5 ранее существовавших ошибок в tools/prepare_brand_assets.py и tools/restore_reference_prototype.py вне шага6.

Ведущий: отдельно scoped Ruff pass; `tools/manage_local.py makemigrations --check --dry-run` No changes detected; `tools/manage_local.py check`0 issues. Docker уже работал: inet-mag-postgres-1 иredis healthy. Local Django запущен командой runserver127.0.0.1:8030 --noreload (exec2584); GET health/home/catalog?in_stock=1/cart/первая связанная PDP →200. HTTP smoke не является browser/pixel приёмкой. .env/рабочие количества не менялись, миграции шага6 не требуются.

Ручная проверка описанного выше SQLite QA проведена ведущим через pytest --trace: напечатаны `[(None,False,False),(0,True,False),(0,True,False),(3,True,True)]`; затем c и штатный test завершился1 passed in15.57s. Ни working schema, ни рабочие stock rows этим не изменены.

Бюджеты новых тестов: ListingContext12 SQL для1/12 карточек; storefront+presentation4 SQL для1/12; wishlist4 SQL; standalone cart quote2 SQL для1/50 SKU (RequestFactory/session dict без SQL сессии и coupon). Это конкретные контуры, не бюджет полного HTTP-запроса и не гарантия latency на большом production dataset. Scalar subquery использует unique variant/location, movements/reservations не подгружаются. Полный production load test не выполнялся.

Независимая ревизия и сверка итоговых claims ещё выполняются. Статус in-progress; шаг7 не начат, commit/push/deploy не выполнялись.

### Уточнение JS-проверки после первого замечания ревизора

Ревизор обнаружил, что gallery-only JS fixture ещё отвечала старым demo_available и не моделировала CTA: это пробел доказательства, не выявленный production-code defect. Обновлён только tests/js/catalog-gallery-selection.cjs: neutral available, M=true/L=false, stub действия. Проверяются enabled после M, disabled во время preview, disabled для L, enabled при возврате M; прежние gallery assert сохранены. Исполнитель: tests/web/test_product_gallery_behavior.py +test_catalog_listing_templates.py —7 passed in2.86s. Source не изменился; полный suite/PG выше относятся к той же source версии до этого test-only уточнения. Полный повтор не требовался по новому production-коду; ревизор проверяет delta отдельно.

### Независимая ревизия шага6

S6-R1..R7 pass: общий snapshot/no fallback/read-only, все потребители, sameSKU filters/sort, staff source/missing, query budgets, regression/DE-RU и documentation. Ревизор независимо:64 targeted tests,196 PostgreSQL in44.94s с удалением UUID DB,10 wrapper tests in3.29s; scoped Ruff/check/drift/diff pass. Исправлено единственное low замечание в JS test fixture (actual available + CTA enable/disable), production source не менялся. Final claims отдельно сверены; полные/ручные прогоны ведущего/исполнителя не приписываются ревизору. Независимый full suite отдельным повтором будет записан ниже при завершении. Ручной HTTP/Pdb QA ведущего и его пределы приведены выше.

Статус reviewed-awaiting-acceptance. Сохранены дизайн/CSS и explicit TEST/demo границы; browser/pixel/production load acceptance не заявляются. Последний личный read-only контроль ведущего: stockmode demo, expiryFalse, все три inventory таблицы0. Никакого копирования demo в stock, активации, migrations шага6, удалённого deploy, provider calls, commit/push нет. Следующий шаг7 отдельно разрешается владельцем.

Финальный независимый полный прогон завершился: **1053 passed,26 skipped in47.21s** (разрешённый local runtime). Предыдущий sandbox запуск не считается результатом. Documentation-only path correction: web.inventory.availability.InventoryAvailability и web.inventory.availability_queries.with_availability, package exports не добавлялись. Требования S6-R1..R7 и final claims подтверждены; reviewed-awaiting-acceptance.

## Шаг7 — управление складом в кабинете (05.11.2026, reviewed-awaiting-acceptance)

Раздел «Операции → Остатки» предназначен для inventory main независимо от режима demo витрины. Изменение demo_quantity остаётся в товарном DEMO-редакторе; складские действия вызывают только существующие inventory services. Исходный интерфейс кабинета codex-django/его токены и RU/DE сохраняются. Не выдавать складскому пользователю права просмотра покупателей/адресов/заказов ради работы с SKU.

Список: поиск SKU/товара, цвет/размер, on_hand/reserved/available, missing/zero; bounded пагинация и фильтры missing/zero/reserved/low с явным порогом. Карточка: компактный баланс, явная инициализация отсутствующего balance, приход и абсолютная корректировка с причиной. Signed intent привязан к persisted actor, SKU, action, исходной revision; OperationContext source/owner/key серверные. Успешный replay не повторяет movement. Не менять revision автоматически при stale/cleanup и не выдавать свежий intent старому bound payload: оператор перечитывает баланс и подтверждает новый расчёт.

История и резервы доступны только по отдельным native permissions; permission-gated sections не заменяют endpoint checks. Вывод ограничен необходимыми количествами, состояниями, временем и ответственным, технические IDs вторично. Нет raw snapshot JSON, клиентских email/адресов или обещания реальной оплаты/отгрузки. Сверка read-only: заметное расхождение balance/reserved lines/ledger и просроченные HELD, без silent repair. Ограниченный ручной cleanup — отдельный явный POST с expire permission; если сервис чистит main глобально, интерфейс обязан обозначать именно global bounded scope.

### Паспорт данных шага7

Новых аналитических событий/SDK/cookies/рекламных передач не добавляется: цель фичи — операционный учёт товара. Действия используют существующий ledger: SKU/variant ID, main, kind, quantity/delta, before/after/revision, operation key/fingerprint, actor ID, причина и UTC время. Причина обязательна для объяснения складского изменения, подсказка запрещает клиентские адреса/платёжные данные. Это не анонимные данные и не новое согласие на маркетинг; доступ только по соответствующим staff permissions. Идентификаторы request/session/raw signed token в ledger/log не добавляются.

Подписанные UI intents не создают отдельного хранилища персональных payloads; подпись без срока, replay ограничен текущими правами, persisted operation key и CAS; правила идемпотентности и хранения existing movement/audit остаются шагов2–5. До live production сроки хранения/архив/subject deletion и backup retention утверждаются отдельно. Сейчас test/dev без реальных заказов, UI QA использует fake users/fresh disposable SQLite; PG concurrency только UUID DB. Отказ/отзыв optional consent не влияет на необходимую складскую операцию и не включается этой фичей; никакого optional tracking нет.

### Изолированный визуальный QA

`tools/serve_inventory_qa.py` — постоянный локальный launcher: не читает .env, принудительно test settings, временная SQLite под tmp/inventory-qa, loopback8040–8099, locmem email, expiry выключен, no auto-reloader. Fake verified owner/read-only warehouse accounts и примеры missing/zero/available/reserved создаются только в этой БД. Остановка Ctrl-C закрывает connections/удаляет runtime. Это не рабочая настройка и не deployment. Точные QA действия/наблюдения будут записаны после sourcefreeze.

Предел cleanup QA launcher: нормальный Python exit удаляет TemporaryDirectory; принудительное завершение session tool может прервать finally. Тогда остановить свой listener, проверить точный абсолютный runtime path внутри tmp/inventory-qa и удалить только этот зарегистрированный run-directory. Это наблюдено ведущим на первом baseline запуске, данные были только fixture. Не обещать автоматическое удаление при произвольном kill.

### Реализованный интерфейс и проверки шага7

Routes сохранены: staff:stock (/ru/staff/stock/ либо /staff/stock/), staff:stock_detail; POST staff:stock_command <SKU PK>/commands/<initialize|receive|adjust|expire>/. UI живёт в web.staff.inventory_workspace (access/intents/forms/selectors/list/detail/command), шаблоны staff/inventory. Старые generic stock endpoints переведены на inventory guards, навигация/quick access/ссылка в настройках больше не использует catalog.view_productvariant как разрешение склада.

Read permissions независимы: view_stockbalance, view_inventorymovement, view_reservationline. Сотрудник с history-only/reservations-only выбирает соответствующую секцию без получения баланса. Reconciliation требует все3 read permissions. Изменяющие actions дополнительно требуют собственного initialize/receive/adjust_stockbalance или expire_reservationline; expired cleanup также reservation read. Warehouse-only topbar ведёт на доступный склад, а не orders403. Группы/роли не создаются, customer/order права не выдаются.

Формы используют реальные prefixed имена (action-intent/action-quantity/action-reason), Django CSRF и PRG. Signed actor/target/action/revision/key перепроверяются, ключ серверный UUID. Подпись намеренно **без срока истечения** ради повтора операции; отдельной таблицы intents нет. Current persisted active staff и permissions проверяются перед каждым replay; ключ/фактический payload сверяет журнал, CAS защищает новую операцию. Это не бессрочное право выполнять действие. На stale ввод/старый intent сохраняются, оператор явно загружает свежий snapshot. Below-reserved сообщение после authoritative service отказа показывает target/current reserved и ссылку на доступные резервы; не подменяет CAS frontend-проверкой. BigInt preview только показывает текущий→введённый абсолютный остаток и delta, не определяет допустимость записи.

Reconciliation одним SQL и для missing, и для configured сопоставляет on_hand/reserved с суммой remaining lines, ledger delta totals/count и последним snapshot/revision. Это проверка текущего согласования, не полный forensic scan каждой пары исторических строк. Список/история/резервы по25, page cap401 (offset≤10000), search200; threshold явный. Selector row loading1SQL, bounded page count+rows2SQL на малом/большом наборе; reconciliation1SQL. Это не бюджет полного HTTP с auth/nav.

Ручной cleanup глобальный по main, максимум20 due lines и существующий soft timebudget; подпись привязана к показанному SKU/actor/action, но надпись явно сообщает all-SKU scope. Повторный запуск может обработать следующую пачку, per-line canonical expiry key предотвращает двойное освобождение. Счётчик expired и lastsuccessful expiry timestamp относятся к текущему SKU, а не last scheduler run. Ошибка текущего POST выводится безопасно; durable scheduler error telemetry не добавляется.

### Ручной browser QA ведущего

Изолированный tools/serve_inventory_qa.py, fresh SQLite/fake users, рабочая БД не менялась. Desktop1280×720 RU: missing SKU→initialize5→receive2 (7)→absoluteadjust4; preview7→4/delta−3 и история0→5→7→4, revisions1/2/3. Reserved SKU3/2→target1 отклонён, ввод/причина сохранены, баланс3/2/1 unchanged. По reservations глобальный cleanup закрыл другой истёкший fixture HELD, active hold остался; после исправления видна сводка scanned1/expired1/skipped0/moreНет и CLOSED1/0/0/1.

390×844 RU/DE: fullwidth layout, body/content width390, readable wrapping, service forms/help/errors. Переключатель RU→DE сохраняет текущую страницу/section. German belowreserve error показывает target1/reserved2, reason сохранён; Tab из adjust quantity переводит focus на id_adjust-reason. Повтор RU ошибки также проверен. Read-only inventory-reader: topbar/left nav только разрешённые Обзор/Остатки, Операции ведёт наstock; detail показывает баланс+readonly notice, без mutation forms и без клиентских разделов. Это конкретные проверенные состояния, не полный accessibility audit.

В первом мобильном screenshot сразу после resize был переходный layout; свежий DOM/screenshot подтвердил правильные x0/width390, source CSS не менялся. Во время QA найденные3 дефекта закрыты: messages include послеPRG, конкретная ошибка reserved floor, nativepermission link вsettings. После исправлений server был перезапущен с чистой fixture и случаи перепроверены. Screenshots: tmp/inventory-qa/step7-desktop-ru.png, step7-mobile-ru.png, step7-mobile-de-error.png (только fake fixtures).

Selfcheck initialfreeze:1083 passed/26 skipped и226 PostgreSQL passed+UUIDcleanup. После UI fixes57 focused passed/7.73s, scoped Ruff pass. Независимый finalfreeze:1088 passed/26 skipped58.38s; focused57/8.09s; PostgreSQL226/58.87s initialfreeze, stock services не менялись UIdelta. Scoped Ruff/check/drift pass. Промежуточный full во время записи исправлений был mixed snapshot, его failures не объявляются финальным результатом. Browser evidence принадлежит ведущему, не ревизору. Final claims сверяются отдельно перед переходом8.

Итог7: S7-R1..R7 pass, finalclaims сверены; reviewed-awaiting-acceptance. Причина — свободный текстmax500 с подсказкой не вводитьPII и HTMLescaping; не заявляется автоматическая PIIочистка. Ревизор изучил снимки ведущего, не проводил отдельный browserQA. После закрытия7 по поручению закончитьвсеэтапы начинаем8; production/remote/live readiness не выводится изприёмки.

## Шаг8 — локальный финальный контракт и приёмка (05.11.2026, reviewed-awaiting-acceptance)

После закрытия independentreview7 по поручению завершитьвсеэтапы сверена исходная матрицаK4. Enum checked_return, обычный movement ledger и HTTP-test worker сами по себе не доказывают возврат/устойчивое событие/fakechannelcontract. Поэтому в8 реализуются эти минимальные локальные требования до сквозной приёмки. Scope не включает live provider/eBay/OAuth/dispatcher/fullRMA/refund/реальную доставку, и не меняет принятую S4 политику latecommit→review_reservation безauto-rehold.

### Проверенный возврат

Подтверждённый расход consumed сохраняет исходный исторический смысл; returned — отдельное количество ранее списанного, полученного и проверенного товара. original=remaining_reserved+consumed+released остаётся неизменным, returned≤consumed. Положительный приём≤consumed−returned увеличивает пригодный on_hand, не возвращает старый резерв и не меняет reserved. Attestation received/inspected задаёт уполномоченный trustedstaff/testcaller; ПО не доказывает физический факт получения/осмотра. Refund не вызывает эту команду. Старые снимки безreturned читаются как0 по явно описанному контракту, не переписываются.

### Устойчивые события

Новый InventoryChanged — минимальный immutable DTO engine и durable record, связанный с новой movement. Запись в том же atomic UoW; ошибочный event-write откатывает balance/line/movement/audit/order. EventID/version/target/revision/количества позволяют будущему потребителю безопасно перечитать свежую проекцию. Нет reason/customer/address/session/token в экспортируемом payload. Это устойчивый журнал факта для будущей доставки, не уже доставленный webhook/ARQ message. Historical movement не превращается миграцией в новую внешнюю публикацию; cutover/старые события описываются отдельно. Dispatcher/ack/retry delivery в будущей интеграции, не скрытый network effect на save.

### Поддельный внешний источник

Локальный synthetic вход работает только в inventory_test у activepersistedstaff с отдельным permission и без HTTP/API endpoint. StableexternalfactID+fingerprint делает повтор no-op и не допускает другойpayload под темжеID. Stalesnapshot не затирает свежий localstock; поздняя внешняя продажа при нехватке фиксируется needs_attention, а не пропадает с исключением и не создаёт отрицательное количество. Маппинг по устойчивому variantID, не названию. В payload нет настоящих eBay customer/orderданных; это проверка локального контракта с fakeadapter, не готовая синхронизация.

### Данные и границы

Новый returned counter, durable changefacts и synthetic receipts служат операционной корректности/идемпотентности, не рекламе. Новых behavioral events/SDK/cookies/marketing optin не добавляется. История связана с IDs и может быть персональными служебными данными; ограничения хранения из прежнего ledger распространяются на связанныеfactIDs, автоматическойочистки/tombstone и юридическиутверждённыхproductionсроков нет. Доступ nativepermissions; publicavailability не экспортирует private receipts/reasons/actors. Позднее подключениепровайдера требуетсвоихоснований, retention, cancellation, транспортнойаутентификации иlivepermission, которых fakecontract не даёт.

Реализация/схема/API/evidence/финальнаяматрица будут дополнены после sourcefreeze. Working.env/mode/quantities не меняются; проверенные additive dev migrations выполняются штатно, без backup-gate/auto stockseed.

### Матрица исходной приёмки K4 — сверка после финального freeze8

Ниже source/test pointers после finalfreeze8. Автоматические локальные случаи исполнены в final full и guarded PostgreSQL, ограничения provider/delivery и замена case11 указаны явно. Browser/Pdb наблюдения принадлежат ведущему; финальная матрица не означает production/user acceptance.

| Case исходного ТЗ | Проверяемое поведение / основной источник доказательств |
|---|---|
| 1 lastunit | postgres/test_inventory_checkout_concurrency.py two_customers...; reservations_concurrency last_unit_race |
| 2 wholeorderrollback | checkout last_line_shortage...; PG late_audit_failure... |
| 3 repeatedSKU | inventory_checkout repeated_add_of_one_sku... |
| 4 concurrentinitialize | PG accounting_concurrency concurrent_first_creation... |
| 5 exactreplay/conflict | accounting scoped_key_conflicts...; reservation shared_dedup...; PG concurrent_same_key... |
| 6 receive/adjust/release/commit/fulfill/return repeat | accounting/reservations + final_contract test_return_replay_cap_history_and_event; PG same_return_key_replays_under_contention |
| 7 expiryboundary/twocleanup | inventory_expiry batch_boundary...; PG two_cleanup_calls... |
| 8 expiryvsconfirm/cancel/fulfill | PG expiry_concurrency commit_and_expiry..., cancel_and_expiry..., cleanup_nowait... |
| 9 partialfulfill/release | inventory_reservations reserve_commit_partial_fulfill_release...; PG multi_line_partial_operations... |
| 10 quantitycaps/refunddoesnotrestock | reservations validation + final_domain test_return_requires_explicit_true_attestations / final_contract test_return_partial_shipment_keeps_remaining_obligation_and_overflow_rolls_back; refund integration не существует и не оприходует |
| 11 lateconfirmation | S4 accepted review_reservation policy, not original proposed auto-rehold; inventory_expiry failed_late_commit... |
| 12 belowreserved/staleabsolute | accounting stale...; staff_inventory below_reserved...; PG concurrent_absolute_adjust... |
| 13 reverseSKUlocks/boundedretry | PG checkout opposite_cart_order...; reservation_database_retry... |
| 14 failureledger/audit/event | every_mutation_rolls_back + final_contract test_event_failure_rolls_back_each_reservation_transition / test_checkout_event_failure_rolls_back_order_and_keeps_native_cart / test_expiry_event_failure_rolls_back_line_balance_history_audit / test_synthetic_failure_rolls_back_fact_stock_reservation_movements_events_and_audit |
| 15 commitbeforeenqueue | PG final_concurrency test_committed_event_survives_no_enqueue_and_replay_visible_on_new_connection; actualdispatcher/ARQdelivery не заявляется |
| 16 invalidSKU/location/quantity | enginecontract/domainvalidation; inventory_accounting/reservations validation matrices |
| 17 missingnoDemo/oldrecordssafe | inventory_availability projection...; checkout prepared_schema...; localmigrationcounts recorded separately |
| 18 consistentavailability | test_inventory_availability / atomiccheckout / final_contract test_full_receipt_two_ab_c_shortage_release_a_d_ship_b_repeat |
| 19 boundedqueries/noPII | availability12/4/2 budgets; reservationsselectors; staff1/2query/reconciliation + independentpermissions |
| 20 fakechannelduplicate/stale/shortage | final_contract fake duplicate/stale/shortage, stopped-worker/backlog/replay tests; PG final_concurrency duplicate_external_fact / cross_variant_same_external_id / synthetic_sale_and_local_hold / due_hold_commits_after_fake_preflight; no live API |
| 21 CSRF/permissions/forgery/GETnoDML | checkout native_csrf...; staff_inventory permissionmatrix/forgedintent; expiryendpoint/availability GETnowrites |
| 22 UTC/DST/RUDE/escaping/mobile | enginetemporaltests; staff_inventory locales/XSS; rootbrowser7 desktopRU/mobileRUDEkeyboard и browser8 returnedhistory/counterRUDE390; снимки описаны ниже |

Сквозной ручной маршрут и helper/API описаны в финальном QA разделе ниже. Все эти pointers относятся к заново проверенному finalfreeze после schema/event changes, не только к старым отчётам шагов1–7.

### Границы cursor и synthetic snapshots

Локальный event PK/cursor пригоден для постраничного просмотра, **не является безопасным checkpoint доставки**: последовательность выделения PK не равна порядку commit, и поздний commit с меньшим ID можно пропустить при слепом after_id. Событие при этом остаётся durable в журнале. Будущий dispatcher должен иметь свою ack/claim/commit-safe стратегию и idempotent consumer; этот шаг не заявляет очередь exactly-once или готовую доставку. Тест crash-before-enqueue доказывает сохранённый факт, не подтверждение отправки.

Fake snapshot — искусственное наблюдение абсолютного пригодного on_hand с явным local revision fence; это не реальный eBay listing quantity/available. Старые source revisions и изменение local revision после базового снимка должны отклоняться/фиксироваться; количество ниже reserved не переписывает обязательства. Полноценная dirty/outbox acknowledgment reconciliation живого канала потребует отдельного adapter контракта. Продажа fakeисточника создаёт закреплённый резерв без физического списания; shipment не угадывается по имени completed_sale.

### Финальные API и эксплуатация8

- Engine public: `InventoryChanged`, `checked_return_reservation`; `ReservationSnapshot.returned` trailing default0. Returncommand требует exactlyTrue received/inspected, положительноеq≤consumed−returned, неизменныйstate/originalcounterequation; отдельные stock/reservationCAS.
- Django: `services.checked_return(actor,variant_id,reservation_id,quantity,context,expected_reservation_revision,now,received,inspected)`; permission inventory.checked_return_reservationline. Existing inactiveобязательство можно завершить/принять послеосмотра, новыйтоварныйhold inactive нельзя. НовыйполныйRMA/UIrefund отсутствует.
- `InventoryMovement.save` требует servicewrite+enclosingatomic и nested savepoint; создаёт OneToOne `InventoryChangeEvent`. При ошибке eventinsert нельзя оставить orphan movement даже если trustedcaller поймалисключение. Everynewofficialmovement получаетevent, replayнепишетновый. Eventpayloadversion1/UTC/variant/main/revision/on_hand/reserved/available/movementID, безreason/actor/customerPII. Старыеmovements не backfill.
- `selectors.change_events(actor,after_id=0,limit=50)` nativeview_inventorychangeevent; `fake_receipts` view_externalinventoryreceipt; limit1..100,2SQL для superuser actor (activeactorreload+boundedquery); обычному staff добавляются постоянные native permission queries Django, не N+1, displaypaginationonly. Neither selector ack/deliveryqueue.
- `FakeSourceFact(external_id,variant_id,kind,quantity,source_revision,expected_stock_revision=None)` / `ingest_fake_fact(actor,fact,now)` и frozen FakeSourceResult. Только syntheticglobalnamespace, kinds snapshot/completed_sale, id≤100strictcharacters, typedintegerbounds; **не реальная многопользовательская eBay binding/integration**. Access currentpersistedstaff+inventory.ingest_fake_inventory и modeinventory_test, безHTTProute. Receipt.result — original immutable decision; changedpayload sameID сохраняет uniqueconflictfingerprint перед IdempotencyConflictError. Completed sale reserve+commit однойтранзакцией, deterministictargetboundreference/keys, sourcefake_external/ownersynthetic; receipt.reservation_id позволяет явнуюTESTfulfill отдельно.
- Snapshot — абсолютное on_hand fakeнаблюдение: stale source/localrevision fences отклоняются, reservedfloor защищён. Genuine shortage/missing/inactive сохраняетneeds_attentionбезnegative/partialhold. После последующего прихода такой **уже принятый** конфликт не переигрывается сам; разбор/новыйбизнесфакт отдельно. Нехватка из-за ещёнеочищенногоexpiredHELD не должна становитьсяreceipt: permission+replay/conflict преждеmaintenance, затем отдельныйbounded20/SKU/soft5scleanup, locks Variant→Balance, replayagain+locked no-due fence. Backlog/гонка→retryбезclaimreceipt, expiredcleanupcommitможетсохранитьсяпривроваленовойоперации, outeratomic+due отклоняется. Oldsuccessreplay2queries инечитаетlines/нечиститexpired.

Nativepermissions дополнены view_inventorychangeevent/view_externalinventoryreceipt/view_externalinventoryconflict и checked_return_reservationline/ingest_fake_inventory. Роли не создавались. Существующий staff UI показывает новыйkind «Проверенный возврат» / «Geprüfte Rücknahme» и отдельный returnedcounter в резервах; финансоваяоперация/refund отсюданевыполняется.

### Миграция и сохранность

Local inventory0005_final_inventory_contract применена штатно, check0, inventory0001–0005allX. НетRunPython/backfill. До/после Order2/Line2/Product4/Variant32/User1; все6inventorytables0; mode demo/expiryFalse. Это не активацияработающегосклада/реальныхпродаж, .envнеизменён. Ревизор независимо read-only проверил schema/counts/flags (default_transaction_read_only). shop.pinlite.dev неразворачивался. Порт8030 былсвободен; запущен currentlocal Django --noreload exec12225. health/home/catalog in_stock/PDP/cart HTTP200, защищённый /ru/staff/stock/ безсессии штатно направляетналогин. Native roles/grants и customerdataнепереписывались.

### Сквозной QA и доказательства

Ведущий выполнил описанный в tasksection15 PDB flow в settings.test на `[0]`fixture: A/B302, C409sessionpreserved, releaseA/D302, commit/fulfillB/replay, checkedreturn1CLOSED/consumed1returned1, excessreturnrejected, fake5needsattention/replay и stale snapshot, finalstock2/reserved1rev9, movements/events9 иreceipts2, reconcileTrue. qнамеренноостановилautotestпослеручныхassert,73.21s/no testsran — неавтоматическийpass. Послеfixstoppedworkerпутьдоказанновыми37focused+PGinterleaving.

Browser8 свежий tools/serve_inventory_qa.py SQLitefixture: RU history checkedreturn+1 после явногоfulfill−1, correctrevisions; reservationsCLOSED original1/remaining0/consumed1/released0 иreturned1. DE тотжесчётчик/история,390×844readable,tablecontainedscroll. Screenshotstep8-return-history-ru.png/step8-return-mobile-de.png зарегистрированы в temp-index. Ревизор осмотрелснимки; взаимодействиябраузера — ведущий. SDK/нешнихHTTPproviderвызовов нет; обычныеstaticassetsбраузера неявляютсяcommerceintegration.

Final executor correctedfreeze:1125passed34skipped131.32s; safePG270passed162.02s+UUIDremoved. Reviewer independently correctedfreeze:1125passed34skipped124.52s; PG270passed148.54s+exactUUIDremoved; runnerguards9passed1.10s; scopedRuff/check/driftpass. Initialfreeze1120/33+264PG невыдаютсязаисправленныйрезультат. Единственныйmaterialfinding8 — fakeexpirymaintenance — закрыт/retested5web+1PG race. Исходные34PGcases действительноисполнены вPG, невыводятсяизSQLite. FullrepoRuff5старыхошибокдвухнезатронутыхtools остаютсязаscopedcheck. РеальныйARQ/Redisdelivery,dispatcher,liveproviders/loadtest/productionacceptance не заявляются.

### Исходные cases1–22 после8

Все применимые локальные case из матрицы выше имеютsource+автоматическиепроверкивfinalfull/PG; gaps6/10 возврат,14eventfailure,15commitbeforeenqueue,20fakecontract закрыты new test_inventory_final_domain/final_contract/final_concurrency. Case11 явнозаменёнпринятойполитикойS4reviewonly. Case22дополненmanualRUDE/rootbrowser. Case15доказываетdurablejournalнаfreshPGconnectionпослеcommit/replay, **не delivery**; fakecontract20неявляетсяреальнойинтеграцией. Будущиепровайдеры/полныйRMA/внешнийdispatcher/productionretention не считаются выполненнымиэтим блоком. ФинальныеR-ID/claimsматрица — tasksection15; сверкаревизором выполняетсяотдельнопосленаписанияитога.

### Итог финальной проверки

Этапы 7 и 8 реализованы; отдельная независимая ревизия выполнена после каждого этапа. Все существенные замечания исправлены до перехода дальше. Для финального снимка ревизор получил 1125 passed / 34 skipped и отдельно 270 PostgreSQL passed с удалением временной базы; проверки runner guards, scoped Ruff, Django check и migration drift прошли. Итоговые ограничения и доказательства сведены в section15 файла задачи. Сейчас выполняется последняя сверка формулировок отчёта; это не production deployment и не пользовательская приёмка.

QA-серверы остановлены и их SQLite run-папки удалены после проверки абсолютных путей. Оставлены пять снимков fake fixtures. Launcher использует отдельные inventory_qa_* cookie; header smoke подтвердил отдельное CSRF-имя без вывода значений. Нормальный local Django на8030 оставлен работающим с обновлённой схемой, demo/expiryFalse и прежними записями. Remote/Git/provider операции не выполнялись.

Финальная сверка точных claims завершена независимым ревизором: S8-R1..R7 PASS, обязательной незавершённой работы в согласованном локальном объёме нет. Этапы7–8 reviewed-awaiting-acceptance. Цель разработки/проверки завершена; live deployment и пользовательская приёмка не заявляются. Все применимые local cases1–22 проверены с описанными границами. Изменения остаются в рабочем дереве без commit/push/deploy.
