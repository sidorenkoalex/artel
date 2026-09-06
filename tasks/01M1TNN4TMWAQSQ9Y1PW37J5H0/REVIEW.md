---
task: 01M1TNN4TMWAQSQ9Y1PW37J5H0
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: рабочие файлы роли не доезжают до артефактной ветки и main — белый список каталога задачи, guard до снимка

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (белый список первого уровня `tasks/<id>/`, `scripts/guard.py`) | реализовано не так | `is_extraneous_task_root_file` проверяет только файлы, чей путь состоит РОВНО из одного сегмента (`len(parts) == 1`); файл в ЛЮБОЙ новой поддиректории первого уровня (кроме `acceptance_tests/`) проходит молча независимо от имени/расширения/глубины — см. «Замечания» R1-F1 |
| 2 (автокоммит фильтрует посторонние, один источник истины) | реализовано не так | Импорт из `scripts.guard` — корректно (AC-6), но наследует пробел требования 1: файл в новой поддиректории не отфильтровывается и уходит в артефактную ветку — R1-F1 |
| 3 (guard на снимке в merge_gate до push) | реализовано не так | Порядок вызова (`_overlay_artifact_snapshot` → `_guard_task_root_or_refuse` → карта/RETRO → push) верный, `sys.exit` без `store.set_state`, журнал тем же классом «merge FAILED» — всё по AC-7/AC-8; но критерий тот же дырявый — R1-F1 |
| 4 (тесты) | реализовано не так | 16 новых приёмочных тестов зелёные и добросовестно ловят заявленные мутации белого списка/фильтра/порядка guard'а (проверено прогоном), но ни один не покрывает класс «файл в новой поддиректории первого уровня» — R1-F1 |
| 5 (скилы приложением) | OK | `skills-note.patch` — валидный unified-диф по `skills/coding-standards.md` и `skills/review-checklist.md`; `git apply --check` на чистом дереве подтверждён самостоятельно (см. «Проверено исполнением») |

## Замечания

- blocker — `scripts/guard.py:540-557` (`is_extraneous_task_root_file`), `scripts/guard.py:560-575` (`extraneous_task_root_files_in`, используется `orchestrator/fsm_merge_gate.py:272-299` `_guard_task_root_or_refuse`), `orchestrator/checkpoint.py:591-600` (`_commit_external_step_artifacts`) — критерий постороннего файла проверяет ТОЛЬКО: (а) скрытый сегмент на любой глубине, (б) `__pycache__` первым сегментом, (в) `.md`-имя, если у пути РОВНО один сегмент (`len(parts) == 1`). Файл, лежащий в любой ДРУГОЙ, впервые заведённой поддиректории первого уровня `tasks/<id>/` (не `acceptance_tests/`, не `__pycache__/`, без `.`-префикса) — например `tasks/<id>/wip/_head_map.md` или `tasks/<id>/tmp/notes.md` — не отсекается НИ ОДНОЙ из трёх точек контроля: `guard --all` молчит, `checkpoint._commit_external_step_artifacts` переносит файл в артефактную ветку как обычный артефакт, `fsm_merge_gate._guard_task_root_or_refuse` не отказывает переходу, main получает файл. Это ровно класс инцидента 06.09 (рабочий файл роли/ревьювера в каталоге задачи), просто с одним уровнем вложенности — ничто в SPEC/ANSWER-1 не ограничивает белый список первого уровня только листовыми `.md`-файлами: «первого уровня» относится к любому имени, появившемуся непосредственно в `tasks/<id>/`, включая имя новой поддиректории, которого нет в перечне (только `acceptance_tests/` разрешена как каталог). Подтверждено запуском: `python3 -c "from scripts import guard; print(guard.is_extraneous_task_root_file('wip/_head_map.md'))"` → `False`. Ни один из 16 приёмочных тестов задачи (`tasks/01M1TNN4TMWAQSQ9Y1PW37J5H0/acceptance_tests/test_ac1_ac2_guard_task_root_whitelist.py`, `test_ac4_ac5_ac6_checkpoint_task_root_filter.py`, `test_ac7_ac8_merge_gate_guard_before_push.py`) не заводит файл глубже одного уровня — сценарий не покрыт ни реализацией, ни тестами.
  Предложение: в `is_extraneous_task_root_file` проверять допустимость ПЕРВОГО сегмента пути (`parts[0]`) независимо от глубины остального пути — любой файл, чей `parts[0]` не входит в множество {`acceptance_tests`, разрешённые `.md`-имена при `len(parts)==1`}, считать посторонним (кроме уже обрабатываемых скрытых/`__pycache__` случаев). Тем же критерием автоматически чинятся все три точки контроля (requirement 2 требует единого источника истины) — добавить тест по образцу существующих `test_ac1_hidden_file_at_task_root_is_flagged_as_stray`/`test_ac1_pycache_directory_contents_are_flagged_as_stray`, но для новой произвольной поддиректории с содержимым.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | scripts/guard.py:540-575 (+orchestrator/checkpoint.py:591-600, orchestrator/fsm_merge_gate.py:272-299) | критерий постороннего файла не проверяет первый сегмент пути для файлов глубже одного уровня — новая поддиректория первого уровня (не `acceptance_tests/`) с любым содержимым проходит все три точки контроля молча | инцидент 06.09 повторяется на один уровень вложенности глубже: рабочие файлы роли/ревьювера в `tasks/<id>/<любое_имя>/` доезжают до артефактной ветки и main без единой проверки — задача не закрывает заявленный класс инцидента целиком | починить `is_extraneous_task_root_file`, проверяя допустимость `parts[0]` независимо от глубины остального пути; добавить тест на файл в новой поддиректории для guard/checkpoint/merge_gate |

## Вердикт

changes_requested — починить R1-F1 (критерий постороннего файла должен ловить файлы в ЛЮБОЙ новой поддиректории первого уровня `tasks/<id>/`, не только листовые `.md`-имена ровно одного уровня) и добавить тест, ловящий эту мутацию, во всех трёх точках контроля (guard, checkpoint, merge_gate — единый источник истины, требование 2).

## Проверено исполнением

- `git apply --check tasks/01M1TNN4TMWAQSQ9Y1PW37J5H0/skills-note.patch` на чистом дереве — применяется без ошибок (AC для требования 5).
- `python3 -m unittest tasks.01M1TNN4TMWAQSQ9Y1PW37J5H0.acceptance_tests.test_ac1_ac2_guard_task_root_whitelist tasks.01M1TNN4TMWAQSQ9Y1PW37J5H0.acceptance_tests.test_ac3_mockup_html_exception tasks.01M1TNN4TMWAQSQ9Y1PW37J5H0.acceptance_tests.test_ac4_ac5_ac6_checkpoint_task_root_filter tasks.01M1TNN4TMWAQSQ9Y1PW37J5H0.acceptance_tests.test_ac7_ac8_merge_gate_guard_before_push` — 16 ok.
- `python3 -m unittest tests.test_guard_extraneous_acceptance_files tests.test_guard_artifact_branch_mode tests.test_guard_schema tests.test_guard_split_signals tests.test_guard_zones tests.test_advance_guard` — 121 ok.
- `python3 -m unittest tests.test_step_autocommit tests.test_timeout_checkpoint tests.test_checkpoint_stray_acceptance_files tests.test_checkpoint_external_step_artifacts` — 57 ok.
- `python3 -m unittest tests.test_fsm_merge_gate_done_snapshot tests.test_merge_gate_ci_wait tests.test_split_assessment_merge_gate tests.test_ci_status_kind_gate tests.test_fsm_map_regen tests.test_fsm_retro tests.test_fsm_map_conflict_autoresolve tests.test_fsm_merge_conflict_note tests.test_capacity_gate` — 60 ok.
- `python3 -m unittest tests.test_acceptance_tests_flow` — 69 ok.
- `python3 scripts/codebase_map.py` на чистом дереве после — diff содержательно пуст (только `built_at_sha`, что не дефект); откатил (`git checkout -- docs/codebase-map.md`).
- Ручная проверка находки R1-F1: `python3 -c "from scripts import guard; print(guard.is_extraneous_task_root_file('wip/_head_map.md'))"` → `False` (ожидалось `True`).
- Полный набор `tests/` не гонял (решение Оператора 05.09) — зелёность на push проверяет CI.

## Предложения системе

