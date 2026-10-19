---
task: 01M59Z0FW1699SJQ2FA5Y76CZ3
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: G2а-2 — выкладка планки компонента по `plank_layout` и `plank-run` по правилу планки

## Фаза A: план
- Таблица покрытия PLAN.md охватывает требования 1–10; шаги — три проверяемые единицы (acceptance.py, plank_run.py, тесты + карта), не микрооперации.
- Подход не конфликтует с архитектурой: правило планки только вызывается (`project_profile.plank_rule`), `targets.py`/`project_profile.py`/`guard.py` не тронуты — diff --stat: только `orchestrator/acceptance.py`, `orchestrator/plank_run.py` (+ сгенерированная карта). «Влияние на систему» совпадает с diff; откат — revert merge-коммита.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_plank_plan` (acceptance.py) проверяет `rule.refusal` только при `plank_present` — путь только `extra` идёт прежним кодом; `plank_run.cmd_plank_run` проверяет `refusal` только в ветке не долгоживущего файла. |
| 2 | OK | `_component_layout`: копия файлов компонента прямо в `<parent>/<task_id>`; выбор `rule.owns` у правила по умолчанию, иначе `component_of == component`; `_pult.py` — только при `is_pytest_command`. AC-2 зелёный. |
| 3 | OK | `_layout_check`: пять проверок в порядке SPEC, тексты дословны (константы `LAYOUT_*`), `workdir` по `realpath` (`_inside_real`), `git ls-files -- <родитель>`. Дополнительный отказ при сбое `git ls-files` — не зелёный, безопаснее молчаливого прохода. |
| 4 | OK | `_exclude_pattern(code_root, "/<parent>/", "выкладки планки")` до записи файлов (тот же `flock`); уборка в `finally`; `drop_from_code_copy` убирает `<id>` и `rmdir` только пустого родителя, лишь при годной форме. |
| 5 | OK | Порядок: refusal правила → не `components:`+`report` → прежний путь → `plank_layout` → pytest без него — прежняя выкладка → иначе «нет plank_layout» при файлах компонента. Решение по команде, не по `runner`. |
| 6 | OK | `run`/`collect`: цели — `laid.targets` + `extra`; `run_plank`: `_component_target` переводит каталог/файл планки в выкладку; нет файлов компонента → `absent` (та же «не заведена»). |
| 7 | OK | `_layout_ignore`: у `_uses_plank_layout` — родитель `<id>` через `_own_target`; иначе прежний `.artel-plank`. В `_report_argv` флаг только при `own` с pytest (прежний фильтр). Рефактор в `run_full_suite` эквивалентен: прежде `_own_target` на строке `--ignore=…` возвращал её как есть (флаг). |
| 8 | OK | У правила по умолчанию — прежние `_has_tests` и тексты; иначе маска компонента (`_component_masks`); узел `::` у команды не pytest — отказ дословно. |
| 9 | OK | Прежние ветви не тронуты; AC-9 и существующие тесты затронутых модулей зелёные. |
| 10 | OK | Долгоживущий файл задачи покрывает AC-1…AC-11, по одному тесту на `run`/`collect`/`run_plank`; `test_ac11`/`test_ac16` в report_outcome не менялись (файл вне diff). |

Тесты: в diff `tests/` нет изменений существующих файлов (diff --stat — только два модуля), утверждения базы не тронуты. Долгоживущий файл задачи несёт `Группа: долгоживущий`, у каждого метода — сценарий и «Ловит мутацию» с наблюдаемым расхождением; три заявки проверены временной мутацией (ниже).

## Замечания

Нет blocker/major/minor.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q tests/test_01m59z0fw1699sjq2fa5y76cz3_component_plank_layout.py` — 23 passed, 89 subtests passed.
- `artel.py plank-run 01M59Z0FW1699SJQ2FA5Y76CZ3` — отказ «нет файлов test_*.py» в зафиксированной планке: разовых файлов у задачи нет, все свойства — в долгоживущем файле `tests/`.
- Тесты затронутых модулей (16 файлов: test_01m41r4…_plank_run, …_plank_run_role, …_plank_run_drift, …_plank_run_long_lived, test_01m57jyjq…_artel_plank_unchanged и _plank_layout, test_01m590gj…_report_outcome, test_01m59kmpg…_plank_rule, test_acceptance, _collect, _own_launch, _plank_exclude_lock, _plank_layout_refusal, _suite_profile, test_plank_run_edges, test_docs_dir_layout) — 135 passed, 260 subtests passed.
- Временные мутации (код возвращён `git checkout`, дерево чистое): убран `_exclude_pattern` в `_component_layout` → AC-1 красный (9 failed); убрана уборка `plank_layout` в `drop_from_code_copy` → AC-10 красный (4 failed); снят отказ узлу `::` в plank_run.py → AC-8 красный.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` без строки `built_at_sha` — расхождений нет, карта свежая.

## Предложения системе
- `_component_layout` копирует только файлы верхнего уровня каталога планки (`tests_dir.iterdir()` с `is_file`), прежняя выкладка `_plank_layout` копировала дерево. SPEC говорит о «файлах», так что это не дефект задачи; если планки компонентов когда-нибудь получат подкаталоги (фикстуры), стоит решить это явно в G2б.
