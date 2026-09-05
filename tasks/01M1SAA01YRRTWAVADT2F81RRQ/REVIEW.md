---
task: 01M1SAA01YRRTWAVADT2F81RRQ
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 4
---

# REVIEW: посторонние файлы в каталоге планки не попадают в артефактную ветку

## Соответствие SPEC

| Требование/AC | Вердикт | Комментарий |
|---|---|---|
| Требование 1 (checkpoint фильтрует посторонние) | OK | `_is_stray_acceptance_test_file` + фильтр в `_commit_external_step_artifacts` (orchestrator/checkpoint.py:20-22, 555-569) |
| Требование 2 (guard именует нарушение) | OK | `is_extraneous_acceptance_test_file`/`scan_extraneous_acceptance_files` подключены в обоих режимах `main()` (scripts/guard.py:407-470, 1165-1199) |
| Требование 3 (codebase_map пишет в корень) | OK | `repo_root()` через `git rev-parse --show-toplevel`, используется в `main()` (scripts/codebase_map.py:215-223, 260) |
| AC-1 | OK | приёмочный `Ac1AllowedVsExtraneousTest` зелёный, юниты `test_checkpoint_stray_acceptance_files.py` покрывают границы регулярки |
| AC-2 | OK | `Ac2SingleJournalEntryTest` — одна запись на несколько посторонних файлов, симметричный тест «без посторонних — без записи» |
| AC-3 | OK | `Ac3ExtraneousFileNamedReasonTest` — именованная причина в обоих режимах (`--all`, `--all --artifact-branch`) |
| AC-4 | OK | `Ac4WritesToRootFromShallowSubdirTest` |
| AC-5 | OK | `Ac5IncidentReproductionTest` — буквальное воспроизведение инцидента 05.09 |
| AC-6 | OK | `Ac6IncidentBothModesTest` — проверяет отсутствие подсказок «нет frontmatter»/«неизвестный type» рядом с найденным файлом |
| AC-7 | OK | `Ac7WritesToRootFromDeepAcceptanceTestsSubdirTest` — глубина ровно как в инциденте (`tasks/<id>/acceptance_tests/`) |
| AC-8 | OK | `test_existing_zone_tests_not_weakened.py` зелёный; diff `tests/*` — только добавления, ни один существующий метод не удалён и не ослаблен (проверено вручную по diff и прогоном) |

## Замечания

- major — tests/test_checkpoint_stray_acceptance_files.py:24,30,41,49,55; tests/test_guard_extraneous_acceptance_files.py:26,32,36,43,49,69,76; tests/test_codebase_map.py:115,123 — ни один из 12 новых методов unit-тестов не несёт докстринга с заявкой `Ловит мутацию: …` (skill test-authoring.md, п. «Чувствительность»; review-checklist Фаза B п.3 — конвенция обязательна для каждого нового/изменённого теста, не только для залоченной планки приёмки). Классы `test_checkpoint_stray_acceptance_files.py`/`test_guard_extraneous_acceptance_files.py` целиком без единого докстринга на метод, `RepoRootTest` в `test_codebase_map.py` — тоже; при этом параллельные приёмочные тесты этой же задачи (`tasks/01M1SAA01YRRTWAVADT2F81RRQ/acceptance_tests/*.py`) конвенцию соблюдают образцово на каждом методе — тот же повторяющийся паттерн «test_author дисциплинирован, developer в своих tests/*.py — нет». Модульные докстроки файлов объясняют, что интеграционное поведение уже покрыто залоченной планкой приёмки, и это разумно избавляет от дублирования сценариев — но конкретную мутацию, которую ловит именно ЭТОТ юнит-метод (например, «отдельный символ вместо экранированной точки в regex», «цикл коммитит журнал внутри for вместо одного вызова»), докстринг метода не называет нигде. Предложение: добавить короткую строку `Ловит мутацию: …` в докстринг каждого метода — не требует новых тестовых сценариев, только документирования уже написанной проверки.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | tests/test_checkpoint_stray_acceptance_files.py:24-59; tests/test_guard_extraneous_acceptance_files.py:26-92; tests/test_codebase_map.py:115,123 | 12 новых unit-тестовых методов без докстринга `Ловит мутацию: …`, хотя параллельные приёмочные тесты той же задачи конвенцию соблюдают | конвенция test-authoring (обязательная и для новых tests/*.py, не только для планки приёмки) нарушена — при регрессии тестового намерения не восстановить его из докстринга, только из имени метода | добавить в докстринг каждого метода строку `Ловит мутацию: <конкретная мутация>` |

## Вердикт

changes_requested — единственное найденное замечание (R1-F1, major) не требует правки логики: добавить докстринги `Ловит мутацию: …` к 12 новым unit-тестовым методам (см. «Замечания»), сама реализация и её поведение под вопросом не стоят. Остальная реализация SPEC/PLAN покрыта полностью, приёмочные и юнит-тесты зелёные, регрессий не найдено.

## Проверено исполнением

- `python3 -m pytest tasks/01M1SAA01YRRTWAVADT2F81RRQ/acceptance_tests/ -q` — 11 тестов (41 subtests), все зелёные.
- `python3 -m pytest tests/test_checkpoint_stray_acceptance_files.py tests/test_guard_extraneous_acceptance_files.py tests/test_codebase_map.py tests/test_checkpoint_external_step_artifacts.py tests/test_guard_artifact_branch_mode.py tests/test_guard_schema.py tests/test_guard_split_signals.py tests/test_guard_zones.py tests/test_id_format_guard.py tests/test_step_autocommit.py tests/test_timeout_checkpoint.py -q` — 187 тестов (56 subtests), все зелёные.
- `python3 -m pytest tests/test_invariants.py -q` — 45 тестов (215 subtests), все зелёные.
- `python3 scripts/guard.py --all` и `python3 scripts/guard.py --all --artifact-branch` на реальном дереве пульта — «GUARD: ок (508 файлов)» / «сдано 398 / черновиков 110 / нарушений 0»: новое правило не красит ни одну существующую задачу (риск, названный в PLAN, не подтвердился).
- `python3 scripts/codebase_map.py` и сравнение с закоммиченным `docs/codebase-map.md` (`git diff` без строки `built_at_sha`) — карта в ветке актуальна, регенерирована тем же коммитом, что и код (конвенция соблюдена).
- Диф `tests/*` вручную сверен построчно на предмет удалённых/ослабленных ассертов — только добавления новых файлов/классов, ни один существующий тестовый метод не тронут.
- Эмпирическая проверка regex-границ (`_is_stray_acceptance_test_file`, `is_extraneous_acceptance_test_file`) интерпретатором Python — экранирование точек в обоих модулях корректно, ложных срабатываний на именах вида `_sandboxXpy` не найдено.

## Предложения системе

- Паттерн R1-F1 (докстринг «Ловит мутацию» отсутствует в новых `tests/*.py`, при этом образцово соблюдён в параллельных `acceptance_tests/` той же задачи) — уже отмечался ревью на других задачах: конвенция дисциплинированно соблюдается test_author, но регулярно проседает у developer в собственных юнит-тестах. Возможно, стоит вынести явное напоминание в PLAN-чеклист разработчика (skills/developer.md?), а не полагаться на то, что ревьювер поймает это постфактум каждый раз.
