---
task: 01M1TNN4TMWAQSQ9Y1PW37J5H0
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: рабочие файлы роли не доезжают до артефактной ветки и main — белый список каталога задачи, guard до снимка

## Примечание к пакету ревью (важно для чтения этого REVIEW.md)

Инкрементальный diff пакета (baseline `0b63591441d3...`, «sha предыдущего
вердикта») в этой итерации вводит в заблуждение — см. «Предложения
системе». `0b635914` сам оказался коммитом ФИКСА R1-F1 (сделан
разработчиком ПОСЛЕ вердикта iteration 1, а не ДО него), поэтому
инкрементальный diff «от 0b635914 до HEAD» этот фикс не показывает
вовсе — вместо него показывает только содержимое коммита «подтяжка
main» (`8604644a`), приносящее смерженные R2/R3 (`fsm_advance.py`,
`tasks/01M1TKNXX5YN5KT4WHG4T44JWV/*`) — ни строки из зоны этой задачи.
Сам фикс R1-F1 я нашёл и прочитал отдельно (`git show 0b635914`), а
также прочитал SPEC.md/PLAN.md с артефактной ветки `artifact/
01m1tnn4tmwaqsq9y1pw37j5h0` (в пакете они значились «не найдены» — они
живут не в кодовой ветке, см. «Предложения системе»).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (белый список первого уровня `tasks/<id>/`, `scripts/guard.py`) | OK | R1-F1 исправлен: `is_extraneous_task_root_file` (`scripts/guard.py:539-566`) теперь проверяет допустимость ПЕРВОГО сегмента пути независимо от глубины — файл в любой поддиректории первого уровня, кроме `acceptance_tests/`, безусловно посторонний. Прочитано целиком, прогнано. |
| 2 (автокоммит фильтрует посторонние, один источник истины) | OK | `orchestrator/checkpoint.py` вызывает `guard.is_extraneous_task_root_file` напрямую (`grep` подтверждает — не независимая копия); наследует починенный критерий автоматически. |
| 3 (guard на снимке в merge_gate до push) | OK | `orchestrator/fsm_merge_gate.py::_guard_task_root_or_refuse` — тот же `guard.extraneous_task_root_files_in`, вызывается после `_overlay_artifact_snapshot`, до `_push_merged_main`; наследует починенный критерий. |
| 4 (тесты) | OK | Новый `tests/test_guard_task_root_subdirectory.py` (6 тестов) закрывает ровно класс R1-F1 на всех трёх точках контроля (предикат, `guard --all`, `checkpoint.commit_step_artifacts`, `fsm_merge_gate._guard_task_root_or_refuse`); прогнан — зелёный. Залоченная планка приёмки (16 тестов) и все регрессионные наборы, названные PLAN.md (313 тестов суммарно, см. «Проверено исполнением»), зелёные. |
| 5 (скилы приложением) | OK | Уже было OK в итерации 1, не менялось — `git apply --check` на чистом дереве подтверждён повторно. |

## Замечания

(пусто — blocker/major/minor не найдено; итерация 1 несла одно
замечание R1-F1, оно закрыто фиксом, см. «Реестр замечаний»)

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | scripts/guard.py:539-566 (+orchestrator/checkpoint.py, orchestrator/fsm_merge_gate.py) | критерий постороннего файла не проверял первый сегмент пути для файлов глубже одного уровня | инцидент 06.09 повторялся на один уровень вложенности глубже | Фикс подтверждён: `is_extraneous_task_root_file` теперь безусловно относит к посторонним любой файл вне `acceptance_tests/`, чей путь глубже одного сегмента (для `len(parts)==1` поведение прежнее — `.md` по белому списку, прочее легально). Прочитан весь диф коммита `0b635914` (единственные тронутые файлы — `scripts/guard.py`, новый `tests/test_guard_task_root_subdirectory.py`, `docs/codebase-map.md`), прогнан новый тестовый файл (6/6 OK) и полный список регрессионных наборов из PLAN (313/313 OK), плюс залоченная планка задачи (16/16 OK). `checkpoint.py`/`fsm_merge_gate.py` подтверждены точечным чтением — оба зовут ровно тот же предикат/обёртку `scripts.guard`, независимой копии критерия нет. Заявка разработчика «чинятся автоматически (импортируют тот же предикат)» подтверждена, не просто принята на слово. Перевожу в `accepted`. |

## Вердикт

approved

## Проверено исполнением

- `git show 0b635914` (коммит фикса R1-F1, найден вручную вне пакета — см. «Примечание к пакету ревью») — прочитан целиком; правка ограничена `scripts/guard.py` (10 строк логики) + новый `tests/test_guard_task_root_subdirectory.py` (193 строки) + `docs/codebase-map.md`.
- `python3 -m unittest tests.test_guard_task_root_subdirectory -v` — 6/6 OK (новый регрессионный тест R1-F1).
- `python3 -m unittest tests.test_guard_task_root_subdirectory tests.test_guard_extraneous_acceptance_files tests.test_guard_artifact_branch_mode tests.test_guard_schema tests.test_guard_split_signals tests.test_guard_zones tests.test_advance_guard tests.test_step_autocommit tests.test_timeout_checkpoint tests.test_checkpoint_stray_acceptance_files tests.test_checkpoint_external_step_artifacts tests.test_fsm_merge_gate_done_snapshot tests.test_merge_gate_ci_wait tests.test_split_assessment_merge_gate tests.test_ci_status_kind_gate tests.test_fsm_map_regen tests.test_fsm_retro tests.test_fsm_map_conflict_autoresolve tests.test_fsm_merge_conflict_note tests.test_capacity_gate tests.test_acceptance_tests_flow` — 313/313 OK (полный список регрессионных наборов PLAN итерации 1+2, все зелёные без правки ассертов).
- `python3 -m unittest tasks.01M1TNN4TMWAQSQ9Y1PW37J5H0.acceptance_tests.test_ac1_ac2_guard_task_root_whitelist tasks.01M1TNN4TMWAQSQ9Y1PW37J5H0.acceptance_tests.test_ac3_mockup_html_exception tasks.01M1TNN4TMWAQSQ9Y1PW37J5H0.acceptance_tests.test_ac4_ac5_ac6_checkpoint_task_root_filter tasks.01M1TNN4TMWAQSQ9Y1PW37J5H0.acceptance_tests.test_ac7_ac8_merge_gate_guard_before_push -v` — 16/16 OK (залоченная планка приёмки, без правки).
- `git apply --check tasks/01M1TNN4TMWAQSQ9Y1PW37J5H0/skills-note.patch` на чистом дереве worktree — применяется без ошибок.
- `python3 scripts/guard.py --all` на реальном дереве `tasks/` этого репозитория — «GUARD: ок (613 файлов)», новый критерий не красит штатное дерево.
- `python3 scripts/codebase_map.py` в рабочей копии — diff с закоммиченной версией только в строке `built_at_sha` (`git diff -- docs/codebase-map.md | grep -v built_at_sha` пуст); откатил `git checkout -- docs/codebase-map.md`. Карта в HEAD актуальна.
- `grep -rn "<<<<<<<\|=======\|>>>>>>>"` по `orchestrator/`, `scripts/`, `tests/`, `docs/` — конфликтных маркеров от коммита «подтяжка main» (`8604644a`) не найдено; сам коммит не трогает файлы зоны задачи (`scripts/guard.py`, `orchestrator/checkpoint.py`, `orchestrator/fsm_merge_gate.py`) — принесённые им `orchestrator/fsm_advance.py` и артефакты `01M1TKNXX5YN5KT4WHG4T44JWV` не пересекаются с этой задачей.
- Точечное чтение `orchestrator/checkpoint.py` и `orchestrator/fsm_merge_gate.py` (grep по `guard\.`) — оба зовут `guard.is_extraneous_task_root_file`/`guard.extraneous_task_root_files_in` напрямую, независимой копии критерия нет (требование 2/AC-6).
- Полный набор `tests/` не гонял (решение Оператора 05.09, гоняет CI на каждый пуш) — сверка «набор не ослаблен» по diff `tests/`: только новый файл `tests/test_guard_task_root_subdirectory.py` добавлен, ни один существующий тест не тронут.

## Предложения системе

- Пакет ревью для этой задачи не показал SPEC.md/PLAN.md («не найдены» — искал их в кодовой ветке `task/...`, а не в артефактной `artifact/...`, где они реально живут для задач без self-worktree артефактов). Пришлось читать их вручную (`git show artifact/01m1tnn4tmwaqsq9y1pw37j5h0:tasks/.../SPEC.md`). Стоит проверить генератор пакета на этот случай.
- Класс «инкрементальный diff вводит в заблуждение» (skills/review-checklist.md, T082/T087) подтверждён третий раз на этой задаче: baseline `0b63591441d3...` оказался коммитом ФИКСА разработчика, сделанным ПОСЛЕ вердикта iteration 1 (а не сохранённым состоянием НА момент вердикта) — инкрементальный diff исключил сам фикс R1-F1 (самое важное для ревью iteration 2!) и показал вместо него только шум от последующей подтяжки main. Похоже, генератор пакета берёт «последний коммит кодовой ветки на момент завершения шага reviewer», а не «коммит кодовой ветки, который РЕАЛЬНО стоял в момент чтения ревьювером» — эти две вещи расходятся, когда разработчик коммитит фикс до следующего advance. Симптом стоит завести отдельным тикетом, не только копилкой.
