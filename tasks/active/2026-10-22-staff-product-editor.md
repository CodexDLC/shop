# Кабинет: редактор товара и управляемая публикация

Дата22.10.2026. Статус reviewed-awaiting-acceptance. Режим: независимый ревизор (выбран в запросе).

## Исходное поручение

«доводить существующий кабинет: сначала редактор товара с фото, характеристиками и процессом черновик — проверка — публикация. стиль сохраняем, с независимым ревизором и вообще составь план где я буду давать тебе следующую задачу. и работаем с проверками».

## Требования

- R1: расширять существующий staff cabinet/codex-django shell, не пересоздавать навигацию/стиль. Понятные вкладки основной информации, вариантов, характеристик, фото и проверки/публикации. Остальные отделы — план следующих заданий, не реализовывать все сразу.
- R2: основной редактор включает реально сохраняемые материалы/свойства и немецкое описание/состав/уход/посадку/происхождение/сертификацию ProductInformation. Не создавать фиктивные значения, не редактировать translation keys вместо обычного описания; существующий ключ/fallback сохранить как legacy. Размерные таблицы бренда не дублировать внутри каждой модели — показать связь/доступ к существующим данным, редактор общих таблиц отдельный будущий шаг.
- R3: фото загружаются локально через Django storage, без S3/внешних URL fetch. Порядок, общий fallback и привязка к реальному цвету вариантов; размеры одного цвета используют одну галерею. Превью/alt и изменение/удаление связи. Существующие URL-фотографии сохраняются. Без опасных форматов, неподтверждённых расширений/размеров или путей, перезаписи оригиналов; ограничения сервером и понятные ошибки. Публичные media только карточек, не персональных документов.
- R4: явный процесс draft→review→published, сохранение само по себе не публикует. Проверка актуальных данных перед публикацией, обязательность базовых полей, активного EUR SKU/положительной цены/описания и фото для представленных цветов (общий fallback допустим), понятный список недостающего. Проверенное состояние связывается с содержимым; изменение данных/варианта/фото не должно позволять опубликовать устаревшую проверку. Недостаток demo stock не превращать в заявление о реальном складе/оплате.
- R5: опубликованный товар изменяется через явный возврат в черновик со снятием с витрины, с понятным предупреждением. Не снимать существующие товары автоматически при миграции/открытии/обычном GET. Старые состояния сопоставить без изменения содержимого, published_at не заполнять выдуманной датой существующим товарам. Публикация в витрине не включает SEO-indexing стенда и не превращает demo offers в реальные. SEO demo markers сохраняются.
- R6: серверные staff/model permissions на каждый endpoint, отдельно право публикации; CSRF/POST-only и атомарность/parent locks, защита устаревшего редактирования/двойного submit/доступа к чужой сущности через подмену parent ID. Audit содержит actor/action/object, без содержимого файлов и форм. Данные/изображения экранируются, private preview закрыт staff permissions и noindex/no-store.
- R7: тесты до замены поведения: формы/модели, безопасная загрузка, сохранность старых фото, цвета/порядок, недостающие данные/проверка/публикация/возврат, stale/concurrent actions/права/CSRF/GET, API/gallery/SEO regression. Проверить desktop/mobile браузером и полным suite, Django checks/migration drift; новые локальные миграции только после просмотра. Независимый fresh reviewer, findings закрыть до итогового отчёта.
- R8: сохранить roadmap отдельных следующих задач кабинета с критериями приёмки и короткими формулировками для следующего поручения. Обновить docs/project references. Без настоящих оплат/DHL/eBay/S3/внешних SMTP, deployment/commit/push, изменений managed/global skills или существующих рабочих записей ради демонстрации.

## План и владение

Основной исполнитель: product/editor/workflow/характеристики/views/templates и tests (кроме выделенного media). Второй исполнитель: media model/form/service/view/template/module URLs+tests, согласованный callback publication lock/fingerprint; папки не пересекаются. Ведущий: требования/roadmap/доки, интеграционная приёмка и браузер, отдельный ревизор. Миграция media0006, workflow0007 последовательно, чтобы не создать ветвление. Django storage адаптер, движок commerce остаётся независимым.

Первая версия не хранит параллельно опубликованную и новую черновую редакцию: явное снятие в черновик делает состояние однозначным. Полноценные редакционные версии без снятия — возможная отдельная будущая задача, не скрытое обещание этого шага.

| ID | Реализация | Проверка |
|---|---|---|
| R1 | существующий staff shell, вкладки | browser desktop/mobile390px, reviewer pass |
| R2 | обычные DE-тексты, материалы/свойства, общие size guides | info/public/private PDP regressions; legacy P2 закрыт |
| R3 | безопасный storage upload, color gallery/order/alt | 13media tests; actual CSRF multipartHTTP; браузер photo edit; перенос108 случаев reviewer |
| R4 | draft/review/publish, fingerprint и readiness | publication tests; review reset/manualcycle; legacy translation freshness |
| R5 | explicit withdraw перед правкой; legacy visible preserved | public200→404; PG hashes/counts прежних полей совпали |
| R6 | права, CSRF, parentlock, stale, audit, readonly admin/privatepreview | permission/POST/stale/admin regressions; reviewer pass |
| R7 | целевые+полный suite, visual/reviewer/checks | 599passed; Ruffclean; Djangocheckclean; migrationdrift нет |
| R8 | roadmapK1–K8, docs и app-owned skillref | отдельные критерии/промпты; future steps не выполнялись |

## Результат и доказательства

Реализован K1. [Рабочий контракт](../../docs/project/staff-product-editor.md), [очередь следующих поручений](../../docs/project/staff-cabinet-roadmap.md), [browser/HTTP/migration артефакты](../../docs/project/visuals/staff-product-editor/). Локальный8030 запущен с окончательным кодом; staff закрыт единым login/MFA. QA данные создавались только в отдельной SQLite-базе8032; исходные рабочие карточки ради демонстрации не менялись.

Полный итоговый suite после всех исправлений: `.local/staff-editor-review/full-tests-complete.txt` —599passed30.16s. Ruffsrc/tests, Djangocheck и makemigrations--check чистые. Локальные PostgreSQL migrations0006/7 применены после просмотра; explicit oldfield snapshots before/after совпали.

Независимый ревизор нашёл P2: legacy-описание засчитывалось готовностью, но не отображалось на PDP. Общий безопасный helper исправил missing/blank fallback; неизвестные ключи скрыты, fingerprint включает DE-текст. Ревизор повторно запустил50regressiontests и закрыл finding.

Полный suite выявил зависевшую от порядка set коллизию уникальных позиций при переносе фото. Исправлено двумя фазами reserve→normalize, staleguard сохранён.29media/publicationtests прошли при hashseeds1/2/14, ревизор независимо проверил108перемещений; новых findings нет.

Ограничения: native browser filechooser automation не сработал; загрузка проверена реальным CSRF multipartHTTP, отображение/сохранение фото — браузером. Реальная PostgreSQL конкурентная нагрузка не тестировалась. В deployproxy лимит2m, в приложении8МБ; согласовать отдельно перед rollout/media delivery. S3/параллельные редакции/справочникиK2/импортK3 не реализовывались. Нет внешних операций, commit/push/deploy. Окончательная пользовательская приёмка ожидается.

## Итог независимой проверки

Ревизор подтвердил R1–R8 pass в согласованном локальном объёме, открытых замечаний нет. Независимо повторены Ruff, Django check(test settings), migration drift; проверен лог599passed и сохранённые visual/HTTP artifacts. Прямой8030 smoke проверен ведущим: sandbox ревизора блокировал localhost. Реальный PGstress и nativefilepicker не заявляются проверенными. Статус reviewed-awaiting-acceptance — пользовательская приёмка ещё не выполнена.

## Уточнение пользователя: RU/DE кабинет

Кабинет сразу на русском и немецком; пользователь проверяет русский. Продолжение K1 с прежним независимым ревизором, статус in-progress. План: перевод всех staff-ключей и нужных общих chrome ключей; переключатель языка с сохранением раздела и POST/CSRF; проверить формы/статусы/ошибки и переходы RU/DE, German product content не меняется. Существующий дизайн сохраняем, настройки языка магазина глобально не меняем; ссылки на публичный German PDP в preview остаются корректными. Доки и проектный reference фиксируют обязательные два языка для будущих staff-фич.

## RU/DE — результат продолжения

Реализовано170/170staff-переводов RU и6общих chromegettextстрок для RU/DE. Staff размещён в существующих i18n_patterns, DEпути сохранены, RU `/ru/staff/`. Переключатель Django set_language POST/CSRF сохраняет path/query. Сам endpoint тоже локализован для разрешения исходного пути: redtest показал, что unprefixed endpoint не переводил RU next; исправлено. Sidebarcollapse скрывает форму, подпись/кнопка контрастны на тёмной панели. Библиотека не редактировалась, scopedprojectinclude сохраняет её layout. Fingerprint и readiness DElegacy не зависят от UIlocale. Товарные тексты автоматически не переводятся.

Полный frozen suite `.local/staff-editor-review/full-tests-ru-final.txt`:603passed37.43s.4новых tests проверяют routes/login/CSRF/switchquery, полное покрытие и параметры/compiledgettext, вкладки+fingerprint и русский stale409. Ruff/check/driftclean. Browser RU→DE→RU на том же товаре; desktopcollapsed и mobile390scroll390. Артефакты publication-ru-desktop.png/publication-ru-collapsed.png/publication-ru-mobile-menu.png в docs/project/visuals/staff-product-editor/. QA8032 остановлен,8030 обновлён; RUstaff ведёт на RUlogin. Доки и projectreference содержат правило двух языков для следующих staff-фич.

Независимая проверка RU/DE:pass, открытых замечаний нет. Ревизор выполнил57связанных тестов,4localization и отдельные проверки RUсохранения/межъязыковой публикации/MFA; подтвердил полный журнал603passed. Продолжение завершено в статусе reviewed-awaiting-acceptance.

## Явное изменение политики MFA пользователем

Поручение: убрать обязательность2FA для всех ролей, сделать её добровольным выбором. Продолжение с независимым ревизором. План: defaultpolicy безstaffenrollment/recentMFAgate; разрешить staff штатное отключение собственного фактора; убрать misleading staff-required UI; не удалять существующие устройства/пароли/сессии, при добровольном включении сохранить штатный allauthchallenge. Проверить парольный вход без enrollment в staff/admin и возможность отключения с обычной аутентификацией/CSRF. Это явное разрешение владельца изменить политику во всех окружениях, не только local.

## Добровольная MFA — результат

Default SHOP_STAFF_MFA_REQUIRED=False для всех окружений/ролей. Удалён запрет staff отключать собственное устройство: штатный allauthadapter/Form/POST/CSRF, роль больше не блокирует кнопку и deactivation. Добавлен RU/DEтекст о добровольности. Существующие устройства/секреты/пароли не изменялись; при добровольно включённой MFA loginchallenge остаётся.8030 перезапущен. Документы и app-owned accessreference обновлены по решению владельца.

Redtest подтвердил прежний запрет отключения;25целевых тестов затемpassed. Полный `.local/staff-editor-review/full-tests-optional-mfa.txt`:606passed35.44s; Ruff и Djangocheckclean. Ревизор независимо проверил реальный passwordlogin без фактора staff/admin200, включённыйTOTPchallenge без sessionдофактора, отключение ownGET/CSRF/POST и сохранность чужого устройства;38identity/account/emailtests passed.
