---
task: 01M1TKP08PKB87K8772H69GCXJ
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 4
---

# REVIEW: R3 — fsm.py: подтяжка в модуль pull.py с явными исходами, approve как таблица переходов

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (pull.py: типы Fresh/Pulled/Conflict/Refused + декомпозиция) | OK | `orchestrator/pull.py` заводит все четыре типа с нужными полями (`Pulled.sha`, `Conflict.files/note`, `Refused.reason`); логика разложена на `_conflicting_files`, `_auto_resolve_map_conflict`, `_merge_conflict_note`, `_clean_worktree_before_merge`, `_run_merge`, `_handle_merge_failure`, `_materialize_and_run_plank`, `evaluate` — самая длинная (`evaluate`, ~40 строк) далеко от прежних 218. |
| 2 (`_pull_main_or_escalate`: сигнатура/контракт неизменны) | OK | `orchestrator/fsm.py:145-176` — сигнатура `(conn, task_id, t, state) -> str` сохранена, возврат транслирует `Fresh/Pulled/Refused` → `"fresh"/"pulled"/"refused"`, всё остальное → `"escalated"`. Три вызывающие точки (`in_dev->review`/`acceptance->merge_gate`/`merge_gate->done`) не тронуты. |
| 3 (`_cmd_approve`: таблица «состояние → обработчик») | OK | `orchestrator/fsm.py:706-720` — словарь `{"spec_gate": ..., "acceptance": ..., "merge_gate": ..., "escalated": ...}.get(state)`, ветка `handler is None` несёт прежний текст отказа. |
| 4 (поведение байт-в-байт) | OK | Тексты `store.journal`/`store.set_state`/print совпадают с исходником построчно (сверено диффом и AC-3/AC-9 фикстурами — прогнаны, зелёные). |
| 5 (юнит-тесты pull.py + таблица approve) | OK, см. замечание R1-F1 | `tests/test_pull.py` (9 тестов, все 4 исхода) и `tests/test_cmd_approve_dispatch.py` (5 тестов) написаны и зелёные, но большинство тестовых методов не несёт докстринг с заявкой «Ловит мутацию: …» (skills/test-authoring.md, review-checklist п.3) — см. реестр. |
| 6 (смоук трёх сценариев байт-в-байт) | OK | `tasks/.../acceptance_tests/test_ac3_ac9_pull_message_fixtures.py` фиксирует ровно три сценария (свежая/авторазрешённый конфликт карты/неразрешённый конфликт по двум файлам) и сверяет журнал+stdout байт-в-байт — зелёные. |

AC-1..AC-9 (критерии приёмки) прогнаны все — зелёные (см. «Проверено исполнением»); AC-1/AC-7/AC-8 структурные проверки (ast) подтверждают форму кода, не только поведение.

## Замечания

- major — `tests/test_pull.py` (все 9 методов: `test_fresh_when_origin_sha_missing:136`, `test_fresh_when_branch_not_behind:146`, `test_pulled_on_clean_merge_and_green_acceptance:153`, `test_pulled_when_plank_missing_but_skip_tests_legitimate:164`, `test_conflict_on_two_file_unresolved_merge_conflict:179`, `test_conflict_when_worktree_not_available:190`, `test_conflict_on_red_acceptance_after_clean_merge:200`, `test_refused_when_plank_missing_and_ac_required:214`, `test_refused_none_when_branch_text_read_already_refused:228`) и `tests/test_cmd_approve_dispatch.py` (все 5 методов: `test_spec_gate_routes_to_its_own_handler:76`, `test_acceptance_routes_to_its_own_handler:79`, `test_merge_gate_routes_to_its_own_handler:82`, `test_escalated_routes_to_its_own_handler:85`, `test_state_outside_table_calls_no_handler_and_keeps_previous_text:88`) — ни один тестовый метод не несёт докстринг с заявкой «Ловит мутацию: …» (skills/test-authoring.md, обязательна для каждого нового/изменённого теста, review-checklist п.3); часть методов вовсе без докстринга (все 5 в `test_cmd_approve_dispatch.py`, 6 из 9 в `test_pull.py`), у остальных докстринг описывает сценарий, но не называет мутацию, которую тест обязан ловить. Контраст с этой же задачей: `tasks/01M1TKP08PKB87K8772H69GCXJ/acceptance_tests/*.py` (написаны той же задачей, той же логике) — образцовые, каждый метод несёт полную заявку «Ловит мутацию: …» с конкретным сценарием поломки. Последствие: ревьювер не может сверить тест с заявленной мутацией (п.3 review-checklist) — приходится восстанавливать её самостоятельно по коду теста, а будущий автор правки не знает, какую регрессию тест обязан ловить. Предложение: добавить в оба файла докстринги по образцу `acceptance_tests/test_ac2_ac7_pull_outcomes.py`/`test_ac4_ac8_cmd_approve_table.py` — по одной заявке «Ловит мутацию: …» на метод, описывающей конкретный сломанный сценарий и как assert его ловит.

- minor — `orchestrator/pull.py:15` — опечатка в докстринге модуля: «не бере\`т их отсюда бare-именем» (лишний backtick внутри слова, смешение кириллицы/латиницы «бare» вместо «bare»/«голым»). На поведение не влияет, но искажает чтение docstring, на который явно ссылается PLAN как объяснение архитектурного решения (инъекция параметром vs импорт).

- minor — `orchestrator/fsm.py:12` — `import subprocess` в fsm.py становится фактически неиспользуемым самим модулем (единственный вызов `subprocess.run` теперь в `orchestrator/pull.py`); импорт держится только ради того, что `tests/test_ac3_ac9_pull_message_fixtures.py:72` патчит `fsm.subprocess.run` — работает (общий объект модуля в `sys.modules`), но по факту это неиспользуемое имя в самом fsm.py. Не блокирует — правка стилевая, можно оставить как тестовый шов явно, а не молчаливым мёртвым импортом.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | tests/test_pull.py (9 методов), tests/test_cmd_approve_dispatch.py (5 методов) | ни один тестовый метод не несёт докстринг «Ловит мутацию: …» (skills/test-authoring.md) | ревьювер и будущий разработчик не могут сверить тест с заявленной регрессией | добавить докстринг с заявкой «Ловит мутацию: …» каждому методу, по образцу acceptance_tests этой же задачи |
| R1-F2 | open | orchestrator/pull.py:15 | опечатка в докстрине модуля («бере\`т», «бare-именем») | искажает чтение обоснования архитектурного решения (инъекция параметром) | поправить опечатку |
| R1-F3 | open | orchestrator/fsm.py:12 | `import subprocess` в fsm.py не используется самим модулем, держится только как тестовый шов для `mock.patch.object(fsm.subprocess, ...)` | не блокирует, но неочевидно откуда и зачем импорт | оставить как есть, либо явно прокомментировать, что импорт — шов для теста |

## Вердикт
changes_requested — исправить R1-F1 (докстринги «Ловит мутацию» в двух новых тестовых файлах); R1-F2/R1-F3 minor, на усмотрение разработчика, но лучше закрыть тем же заходом.

## Проверено исполнением
- `python3 -m unittest tests.test_pull tests.test_cmd_approve_dispatch tests.test_branch_freshness_gate tests.test_fsm_map_conflict_autoresolve tests.test_fsm_merge_conflict_note -v` — 38 тестов, все зелёные.
- `cd tasks/01M1TKP08PKB87K8772H69GCXJ/acceptance_tests && python3 -m unittest test_ac1_pull_module_structure test_ac2_ac7_pull_outcomes test_ac3_ac9_pull_message_fixtures test_ac4_ac8_cmd_approve_table test_ac5_fsm_reexport test_ac6_existing_suite_still_green -v` — 22 теста (все AC-1..AC-9), все зелёные.
- `python3 -m unittest tests.test_fsm_draft_mr_reentry tests.test_zones_approve tests.test_review_registry_gate tests.test_fsm_retro tests.test_multitarget_invariants tests.test_answer_gate tests.test_answer_branch_reads -v` — 41 тест (модули, соседствующие с `_cmd_approve`/FSM), все зелёные.
- `python3 scripts/guard.py --all` — «GUARD: ок (577 файлов)».
- `python3 scripts/codebase_map.py` (перегенерация на месте) — diff с закоммиченной картой пуст, кроме строки `built_at_sha` (карта актуальна коммиту).
- Сверка diff'а `tests/test_branch_freshness_gate.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_merge_conflict_note.py` против main — файлы не тронуты (AC-6 подтверждён и статически: assert'ы не правились).
- Ручное построчное сравнение `orchestrator/fsm.py`/`orchestrator/pull.py` diff'а с прежним телом `_pull_main_or_escalate`/`_cmd_approve` (пакет ревью, часть 2-3) — логика ветвления `_handle_merge_failure` (инцидент overwrite / авторазрешение карты / неразрешённый конфликт) соответствует прежнему порядку и текстам.

## Предложения системе
