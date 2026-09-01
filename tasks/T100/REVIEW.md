---
task: T100
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 3
---

# REVIEW: Реестр замечаний ревью — жизненный цикл каждого замечания

## Фаза A — гейт плана

PLAN.md покрывает все 11 требований SPEC таблицей «Покрытие требований»;
пропуски (8, 9) обоснованы явно (не требуют кода / мандат подтверждён
самим PLAN). Шаги — проверяемые единицы (guard, шаблон, гейт FSM,
скилы, тесты), не микрооперации и не «сделать всё разом». Подход
(версия-гейтинг `SUPPORTED_SCHEMA_VERSION`, переиспользование
`registry_table_rows` и структурной проверкой, и гейтом FSM,
единственный статус-пропуск `accepted`) не конфликтует с конвенциями:
тот же приём, что `requires_ac_markup` уже применяет к SPEC. Риск,
явно поднятый в PLAN (правка `schema_version` в трёх шаблонах вне
буквальной «зоны задачи»), проверен — обоснован необходимостью не
сломать существующий `TemplatesCarryTheVersionTest` (перепроверено
чтением теста, см. «Проверено исполнением»), не расширяет
функциональный объём. Замечаний к плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Секция «Реестр замечаний» — в `templates/REVIEW.md` и обязательна при `schema_version >= 3`; формат таблицы, id `R<iteration>-F<n>`, обязательные поля — всё на месте. |
| 2 | OK | Пятёрка статусов `open/fixed/rejected/accepted/needs_work` — `guard.REGISTRY_STATUSES`, проверено `RegistryRecordErrorsMessageTest`/AC-4. |
| 3 | OK | Обязанность разработчика описана в `skills/coding-standards.md` (новая секция «Реестр замечаний»), с явным запретом самозакрытия. |
| 4 | OK | Симметрия `fixed`/`rejected` реализована буквально — единственный пропускающий статус `accepted`; гейт не различает исходы (AC-8, AC-9 зелёные и содержательны — проверил, что удаление ветки гейта ломает именно эти тесты). |
| 5 | OK | Машинный гейт — `orchestrator/fsm_advance.py::review()`, ветка `status == "approved"`, до `acceptance.run` и до `store.set_state(..., "verifying", ...)`; отказ называет все незакрытые id (проверено `AllUnresolvedIdsAreNamedTest` — несколько незакрытых записей разом). |
| 6 | OK | `requires_registry` — версия-гейтинг `>= 3`, легаси (без поля, версия 1, версия 2) не подвергается проверкам — AC-6, AC-12 зелёные. |
| 7 | OK | `registry_errors`/`registry_record_errors` — секция обязательна, id уникальны и в формате `R\d+-F\d+`, статус из пятёрки, все поля заполнены; содержательность не проверяется (докстринг модуля явно это фиксирует). |
| 8 | OK | Не требует кода; восстановимость из git-истории REVIEW.md — существующий механизм T021, не тронут. |
| 9 | OK | Мандат на правку `templates/REVIEW.md` и `scripts/guard.py` подтверждается `tasks/T100/TZ.md` (правки на месте, зоны заявлены и соблюдены). |
| 10 | OK | `skills/review-checklist.md` и `skills/coding-standards.md` дополнены протоколом реестра — присвоение id, кумулятивность, оценка `fixed/rejected` → `accepted/needs_work`, обязанность разработчика. |
| 11 | OK | Зона соблюдена: `orchestrator/brief.py`, `store.py`, `catalog.py`, `fixation.py`, `doctor.py`, `cleanup.py`, `prune.py`, `config.py` разработчиком не тронуты (правка `config.py` в diff — только от подтяжки main, не от разработчика этой задачи). |

AC-1..AC-13 перепроверены реальным прогоном (не по тексту докстрингов) —
все 15 тестов `tasks/T100/acceptance_tests/` зелёные, все 50 тестов
`tests/test_guard_schema.py` + `tests/test_review_registry_gate.py`
зелёные (см. «Проверено исполнением»). AC-13 (manual) — прочитал оба
скила целиком: протокол реестра описан по существу (присвоение id,
кумулятивность, критерий перевода `fixed`/`rejected` → `accepted`/
`needs_work`, симметрия ANSWER-1, обязанность разработчика перед
выходом в review) — принимаю manual-пометку.

## Замечания

Замечаний уровня blocker/major/minor нет.

## Реестр замечаний

Записей нет — 0 blocker/major/minor замечаний по итогам ревью.

## Вердикт

approved

Обоснование: код реализует все 11 требований и все 13 AC SPEC без
отклонений; реализация симметрии `fixed`/`rejected` (ANSWER-1) буквально
исключает самозакрытие разработчиком — единственный переход в `accepted`
управляется ролью reviewer; парсер таблицы реестра переиспользован между
структурной проверкой guard и гейтом FSM (не два парсера одной сущности,
как и заявлял PLAN); легаси-артефакты (`schema_version < 3` или без
поля) не затронуты ни одной новой проверкой — подтверждено тестами
AC-6/AC-12 и повторной проверкой существующего `tests/test_review_freshness.py`/
`test_invariants.py` в полном прогоне. Системная целостность соблюдена:
ни один существующий тест/гейт/лимит не ослаблен и не удалён; единственное
расширение диффа за пределы буквальной «зоны задачи» (schema_version
в `templates/SPEC.md`/`PLAN.md`/`TEST_REPORT.md`) — механическая правка
без нового поведения, необходимая, чтобы не сломать
`TemplatesCarryTheVersionTest` (перепроверил его содержимое — он
действительно требует текущей версии от всех четырёх шаблонов); PLAN
прозрачно документирует это решение в «Риски» и «Влияние на систему».

## Проверено исполнением

- `python3 -m unittest discover -s tests` — 1192 теста, 2 упавших:
  `test_agent_log.CmdRunLoggingTest.test_timeout_kills_process_and_journals`
  и `test_step_cost.CmdRunPartialCostTest.test_timeout_with_usage_events_charges_a_partial_token_sum`.
  Оба не связаны с диффом T100 — причина: правка `orchestrator/config.py`
  (`AGENT_TIMEOUT_SEC` 1800 → 2700, коммит `20afc92` на main, «временно
  на стройку M1»), тесты жёстко ждут «30 мин». Воспроизвёл оба сбоя
  изолированным прогоном на HEAD main (`20afc92`) — тот же результат,
  дефект main, не этой ветки; ни один из двух файлов не входит в diff
  T100.
- `python3 -m unittest tests.test_guard_schema tests.test_review_registry_gate -v` —
  50 тестов, все зелёные (включая новые `RequiresRegistryTest`,
  `RegistryTableRowsTest`, `RegistryRecordsTest`,
  `RegistryRecordErrorsMessageTest`, `RegistryErrorsDuplicateIdMessageTest`,
  `AllUnresolvedIdsAreNamedTest`, `GateSilentWhenNoRecordsTest`).
- `python3 -m unittest discover -s tasks/T100/acceptance_tests -v` —
  15 тестов, все зелёные (AC-1..AC-12 исполняемые, AC-13 manual).
- `python3 scripts/codebase_map.py` — регенерация меняет только строку
  `built_at_sha` (сверил `git diff docs/codebase-map.md` до отката
  локальной регенерации) — содержимое карты уже актуально относительно
  фактических изменений `.py`-файлов этой ветки; локальную регенерацию
  откатил (`git checkout docs/codebase-map.md`), рабочее дерево чистое.
- Ручное чтение: `orchestrator/fsm_advance.py::review()` целиком (гейт
  требования 5), `scripts/guard.py` (секция «Реестр замечаний» —
  `requires_registry`, `registry_table_rows`, `registry_records`,
  `registry_record_errors`, `registry_errors`, встройка в
  `check_content`), `templates/REVIEW.md`, `skills/review-checklist.md`
  и `skills/coding-standards.md` (добавленные секции), `tests/
  test_guard_schema.py::TemplatesCarryTheVersionTest` (подтверждение
  риска из PLAN) — на предмет циклического импорта `scripts.guard` ↔
  `orchestrator.fsm_advance` (нет: `guard.py` импортирует только
  `orchestrator.yamlmini`, `python3 -c "import orchestrator.fsm_advance"`
  прошёл без ошибок).

## Предложения системе

- Ни один из ~15 предыдущих гейтов/инвариантов, добавленных задачами
  T017–T090 (см. `docs/invariants.md`, пункты 13, 17–32), не пропустил
  регистрацию в этом файле — но SPEC/PLAN/скилы ни разу явно не называют
  `docs/invariants.md` обязательным шагом для задачи, вводящей новый
  машинный гейт (T100 не исключение — новый гейт requirement 5 не
  зарегистрирован). Само правило соблюдалось по инерции прежних
  разработчиков, не по явному чек-пункту ни в одном скиле — стоит
  добавить пункт в `review-checklist.md`/`coding-standards.md`: задача,
  вводящая новый машинный гейт `orchestrator/fsm*.py`, обязана
  предложить строку `docs/invariants.md`. Не блокирует эту задачу (SPEC
  T100 такого требования не ставит), но со временем реестр инвариантов
  рискует стать неполным по этому классу пропуска.
