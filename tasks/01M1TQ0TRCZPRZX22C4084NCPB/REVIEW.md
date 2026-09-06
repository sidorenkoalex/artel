---
task: 01M1TQ0TRCZPRZX22C4084NCPB
type: review
author_role: reviewer
status: approved
iteration: 3
schema_version: 5
---

# REVIEW: CI кодовой ветки до ревью: порядок in_dev -> verifying -> review (ADR-0015)

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (порядок состояний; семь рубежей переезжают на `in_dev -> verifying` целиком, без дублирования) | OK | Подтверждено итерацией 2, без изменений в этой итерации. `grep -n "_origin_push_gate\|ensure_head_in_origin" orchestrator/fsm_advance.py orchestrator/fsm_merge_gate.py` — одна точка вызова гейта (`fsm_advance.py:1123`, внутри `in_dev`), второй вызов (`fsm_merge_gate.py:319`) — отдельный легитимный рубеж approve `merge_gate`. |
| 2 (`verifying -> review` только по зелёному CI) | OK | Без изменений с итерации 2. `orchestrator/fsm_advance.py:334-336`; `test_ac01_ac09_state_order.py`, `test_verifying_ceiling.py` — зелёные (прогнано этой итерацией). |
| 3 (`changes_requested` -> `in_dev`; повторный вход в review снова через `verifying`; счётчики без изменений) | OK | Без изменений с итерации 2. `test_ac10_ac12_review_return_cycle.py`, `test_invariants.CountersNeverResetTest` — зелёные. |
| 4 (ревью-пакет несёт строку статуса CI из журнала `verifying`, без нового опроса) | OK | Без изменений с итерации 2. `orchestrator/review.py:289-296`, `test_ac13_review_package_ci_status_line.py` — зелёный. |
| 5 (`auto`: `verifying` остаётся опрашивающим состоянием; подсказка после красного CI называет `reject` в `in_dev`) | OK | Без изменений с итерации 2. `test_ac14_ac16_auto_verifying_loop.py` — зелёный. |
| 6 (`docs/invariants.md`, `docs/roadmap.md`, `artel.py --help`) | OK | Проверено чтением этой итерацией: `docs/invariants.md:54,61,63` (инварианты 27/34/36) и `docs/roadmap.md:60` называют новый порядок; `orchestrator/artel.py:8,13,17,19,28` — докстринг схемы состояний и лока планки под новый порядок, `cmd_help` печатает именно его. `test_ac17_ac19_docs_state_order.py` — зелёный. |
| 7 (планки закрытых задач не гоняются/не правятся; R2/R3 дождались мержа) | OK | Без изменений с итерации 2. |

## Замечания

Итерация 3: новых замечаний класса «дефект в коде задачи» не найдено.
Единственное открытое замечание прошлой итерации (R2-F1, стухшая карта
кодовой базы) исправлено и подтверждено этой итерацией — см. «Реестр
замечаний».

Проверено отдельно (не было предметом R2-F1, но тот же класс риска):
после коммита `bc331947` (фикс R2-F1) в ветку задачи ещё раз подтянут
main (`b5aef0c9`, merge `fc8769a3`+`4ce54dbf` в `bc331947`) — это ТРЕТЬЯ
подтяжка main в истории этой ветки, а класс «подтяжка main меняет
`*.py`, но не регенерирует карту» уже сработал в этой же задаче один
раз (R2-F1) и является подтверждённым повторяющимся классом (T079,
T087). Проверено запуском `python3 scripts/codebase_map.py` и
построчным сравнением с закоммиченным (`git diff -- docs/codebase-map.md`
после регенерации, отброшено `git checkout --` после проверки): разница
— ТОЛЬКО строка `built_at_sha`, содержимое совпадает. Не дефект: сам
`b5aef0c9` принёс только `docs/backlog.md`/`docs/roadmap.md` (оба
проверено `git show --stat b5aef0c9`), `*.py` не тронуты — регенерация
карты не требовалась и после этой подтяжки.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/fsm_advance.py:301-303 (дубль, удалён), 1123 (единственное место) | Рубеж «сверка головы на origin» не был убран со старого места в `review()` после переноса в `in_dev()` | Лишний `git push` на каждый approved-вердикт | Закрыто итерацией 2, подтверждено повторно (см. «Соответствие SPEC», требование 1). |
| R2-F1 | accepted | docs/codebase-map.md (весь файл) | Карта стухла после коммита `d9893cd3` («подтяжка main») — содержимое расходилось с перегенерированным | CI-джоб `codebase-map` красил бы main тем же классом, что T079/T087 | Проверено этой итерацией: `git show --stat bc331947` — правка ровно `docs/codebase-map.md`; `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` после регенерации — разница только `built_at_sha`, содержимое совпадает с закоммиченным на HEAD (`b5aef0c9`). Регенерация отброшена `git checkout --` после проверки, рабочее дерево чистое. Фикс подтверждён, дополнительная подтяжка main после фикса (`b5aef0c9`) codebase-map не затронула (не трогает `*.py`, см. «Замечания»). Закрыто. |

## Вердикт
approved — реализация соответствует всем 22 AC SPEC, оба замечания
прошлых итераций (R1-F1, R2-F1) проверены и закрыты (`accepted`),
новых дефектов не найдено.

## Проверено исполнением
- `python3 -m unittest tests.test_acceptance_tests_flow tests.test_advance_guard tests.test_amend tests.test_auto_cycle tests.test_branch_freshness_gate tests.test_fsm_map_conflict_autoresolve tests.test_git_fixation tests.test_invariants tests.test_review_freshness tests.test_review_registry_gate tests.test_verifying_ceiling tests.test_github_adapter tests.test_merge_gate_ci_wait tests.test_codebase_map` — 316 тестов, все зелёные (~188с).
- `python3 -m unittest test_ac01_ac09_state_order test_ac02_ac08_gates_moved_to_verifying test_ac10_ac12_review_return_cycle test_ac13_review_package_ci_status_line test_ac14_ac16_auto_verifying_loop test_ac17_ac19_docs_state_order test_ac20_ac22_process_markers` (каталог `acceptance_tests/` задачи) — 20 тестов, все зелёные.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` (регенерация против закоммиченного на HEAD `b5aef0c9`) — разница только строка `built_at_sha`, содержимое идентично; изменение отброшено `git checkout -- docs/codebase-map.md` после проверки (R2-F1 закрыто, новой стухлости после третьей подтяжки main нет).
- `grep -n "_origin_push_gate\|ensure_head_in_origin" orchestrator/fsm_advance.py orchestrator/fsm_merge_gate.py` — ровно одна точка вызова гейта в `in_dev` (R1-F1 подтверждено повторно).
- `python3 scripts/guard.py tasks/01M1TQ0TRCZPRZX22C4084NCPB/SPEC.md tasks/01M1TQ0TRCZPRZX22C4084NCPB/PLAN.md` — «GUARD: ок (2 файлов)».
- `git diff --stat main..HEAD` (полный дифф ветки от текущего main, merge-base совпадает с main — main целиком влит) — 19 файлов: `docs/backlog.md`, `docs/codebase-map.md`, `docs/invariants.md`, `docs/roadmap.md`, `orchestrator/artel.py`, `orchestrator/fsm_advance.py`, `orchestrator/github_adapter.py`, `orchestrator/review.py`, 11 файлов `tests/*`; сверено с `zones:` SPEC (`fsm.py, fsm_advance.py, auto.py, review.py, config.py, docs/invariants.md, docs/roadmap.md, tests/`) + мандатами ANSWER-2.md (`orchestrator/artel.py`) и ANSWER-3.md (`orchestrator/github_adapter.py`) — расхождений нет; `docs/backlog.md` вне зон и вне мандатов, но пришёл ЧЕРЕЗ подтяжку main (коммит `fc8769a3`, уже на main), не авторской правкой этой задачи — не нарушение гейта зон (зона проверяет дифф авторских коммитов задачи, не содержимое смерженного main).
- `git show --stat b5aef0c9` (последняя подтяжка main в истории ветки) — только `docs/backlog.md`, `docs/roadmap.md`; `*.py` не затронуты, регенерация карты после неё не требовалась.
- Чтением кода: `docs/invariants.md:54,61,63`, `docs/roadmap.md:60`, `orchestrator/artel.py:8,13,17,19,28` — новый порядок состояний отражён (AC-17..19); `docs/adr/0015-ci-before-review.md` существует (ссылка инварианта 36 не висит в пустоте).

## Предложения системе
- Подтверждён третий случай класса «инкрементальный sha ревью-пакета ненадёжен после подтяжки main» на ОДНОЙ и той же задаче (после T087): sha предыдущего вердикта (`bc331947`) в этот раз оказался коммитом РАЗРАБОТЧИКА (фикс R2-F1), а не коммитом ревьювера — пакет построил инкрементальный diff от него до HEAD корректно (показал только последующую подтяжку main), но само по себе совпадение «база сравнения = коммит фикса, а не коммит вердикта» стоит матчить по содержимому REVIEW.md в истории, а не только по факту непустого diff — в этот раз повезло, что diff был непуст и мал; при более длинной цепочке коммитов между фиксом и HEAD подмена базы могла бы скрыть часть изменений так же, как в T087.
