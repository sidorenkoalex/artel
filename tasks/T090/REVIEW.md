---
task: T090
type: review
author_role: reviewer
status: approved        # draft | approved | changes_requested | escalate
iteration: 1
schema_version: 2
---

# REVIEW: store.db: закрытие соединений (ResourceWarning)

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (систематическое закрытие во всех точках использования) | OK | `_AutoClosingConnection.__del__` (orchestrator/store.py:74-90) закрывает соединение при потере последней ссылки в ЛЮБОЙ точке вызова `db()` — без правки самих точек вызова. Эмпирически: полный прогон `tests/` под `-W always` — 0 `ResourceWarning: unclosed database` (было ~3663/3756). |
| 2 (приём выбирает разработчик) | OK | Приём («иной») обоснован в PLAN сопоставлением с альтернативами (контекст-менеджер, connection-per-command) и объёмом правки (~552 вызова `store.db()`, из них большинство инлайн без переменной — grep подтверждает порядок величины из PLAN). |
| 3 (поведение CLI/CAS/WAL не меняется) | OK | `factory=` не меняет публичный интерфейс `sqlite3.Connection`; `row_factory`/WAL проверены юнит-тестом (`tests/test_store_db_connection_close.py::test_row_factory_and_wal_unchanged`) и полным прогоном (`test_cas_set_state.py` и WAL-тесты — в зелёном наборе 1103). `set_state` коммитит сразу после `UPDATE` (orchestrator/store.py:536, 19 мест `conn.commit()` в файле — подтверждено grep) — закрытие никогда не откатывает незакоммиченное. |
| 4 (auto не держит соединение дольше шага, если дёшево) | OK (условно, не AC) | Требование условное и не выделено в AC (SPEC явно). PLAN честно фиксирует, что `cmd_auto` по-прежнему держит одно соединение на весь цикл, и обосновывает, почему сужение — отдельная задача вне рамок (SPEC «Не входит»). Не блокер. |
| AC-1 | OK | Приёмочный тест `tasks/T090/acceptance_tests/test_no_unclosed_connections.py` зелёный (прогнан локально, 117 с). Независимо перепроверено: `python3 -W always -m unittest discover -s tests` — 0 вхождений `ResourceWarning: unclosed database` в объединённом stdout+stderr. |
| AC-2 | OK | Полный прогон 1103 тестов зелёный (`Ran 1103 tests ... OK`), включая `test_cas_set_state.py` и WAL-покрытие. AC-2 в приёмочном наборе — осознанный skip с обоснованием (штатный CI-гейт `python`/`merge_gate` уже проверяет то же самое) — тот же приём, что в T053/T067/T077 (проверено — файлы-прецеденты существуют и используют идентичную формулировку). |

## Замечания

_(пусто)_

## Вердикт

approved. Изменение минимально (один метод `orchestrator/store.py::db()`
+ один новый класс), решает ровно то, что просит SPEC, не расширяет
периметр (нет правок `ci/`, `.github/`, `gates.yaml`, `roles.yaml`,
`templates/`, `skills/`), не ослабляет существующие тесты/гейты
(diff — только новые файлы + точечная правка `store.py` +
регенерация `docs/codebase-map.md`). Откат описан и тривиален.

## Проверено исполнением

- `python3 -m unittest tests.test_store_db_connection_close -v` — 4/4 OK.
- `python3 -W always -m unittest discover -s tests` (полный набор,
  независимый прогон вне приёмочного теста) — `Ran 1103 tests ... OK`;
  `grep -c "ResourceWarning: unclosed database"` по объединённому выводу
  — 0.
- `python3 -m unittest discover -s tasks/T090/acceptance_tests -v` —
  AC-1 (`test_ac1_full_suite_run_has_no_unclosed_database_resourcewarning`)
  зелёный, 117 с; AC-2 — 0 исполняемых тестов (skip по дизайну, файл
  собирается без ошибок).
- `python3 scripts/guard.py --all` — `GUARD: ок (295 файлов)`.
- `python3 scripts/codebase_map.py` (локальная регенерация для сверки
  с закоммиченной картой) — отличие только в `built_at_sha` (более
  свежий коммит `a233ca1` после "подтяжки main"), содержимое совпадает;
  по контракту CI-джоба `codebase-map` (`.github/workflows/ci.yml:75-78`,
  сравнение с исключением строки `built_at_sha:`) карта считается
  свежей. Локальная регенерация отменена (`git checkout -- docs/codebase-map.md`),
  код не правился.
- Точечная проверка кода: `grep -rn "type(conn)\|isinstance(conn"
  orchestrator/ tests/ tasks/` — совпадений вида проверки точного типа
  соединения нет (PLAN-овская проверка подтверждена независимо);
  `grep -c "conn.commit()" orchestrator/store.py` — 19, совпадает с
  заявленным в PLAN; `grep -rln "threading\|Thread("
  orchestrator/` — только `agent_log.py`, к `store.db()` не относится
  (риск закрытия соединения из другого потока в данной кодовой базе не
  актуален).

## Предложения системе

_(пусто)_
