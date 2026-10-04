---
task: 01M42NBCADGSGTCBZB8NKBVDVH
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Мелкие дефекты пульта: amend-tests, гонка fetch, observe add, сверка путей SPEC в guard

## Фаза A: план
- Таблица покрытия полна: требования 1–5 сопоставлены шагу и тестам.
- Один шаг на четыре точечные правки (~120 строк, 6 файлов) — размер одного MR, допустимо.
- Подход не конфликтует с архитектурой: переиспользованы `acceptance.drop_from_code_copy`, `guard.spec_unclassified_paths`/`unclassified_paths_refusal`; у общего примитива `gitcmd.fetch_ref_sha` по умолчанию прежняя argv (как требует «Не входит» SPEC).
- «Влияние на систему» соответствует diff: затронуты ровно `amend.py`, `artel.py`, `gitcmd.py`, `workspace.py`, `scripts/guard.py`, `tests/test_gitcmd_fetch_ref_sha.py` (только добавлен класс) и карта кодовой базы. Откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `amend.py:645,737` — `_drop_fixed_task_dir` стоит последней строкой обоих успешных путей, после `update_task`/`_record_amend`; все `sys.exit` срабатывают раньше (`amend.py:560-635`), так что на отказе каталог не трогается. Исход «правки нет» (выход по `plank_same`) не изменён — как в «Не входит». Удаляется только `<wt>/tasks/<id>/`, главная копия пульта под защитой (`acceptance.py:404`). |
| 2 | OK | `gitcmd.py:564-565` `--refmap=` при `tracking_refs=False`; `workspace.py:77` использует его; отказ сохраняет прежний именованный префикс, отката на локальную `MAIN_BRANCH` нет. Прочие вызовы идут с дефолтом (сторож `TrackingRefsDefaultTest`). |
| 3 | OK | `artel.py:861-862` — проверка до `_observation_or_exit` и до любой записи в БД; текст называет лишний аргумент и форму `--tasks A,B`. Других флагов со значением, кроме `--tasks`, у add/remove нет (`artel.py:878`), так что пропуск флагов корректен. |
| 4 | OK | `guard.py:3131-3132` — `spec_path_errors` только при вызове по файлам; используются тот же узел и тот же текст, что у approve; находка ложится в `all_errors` (ненулевой код). `--all`/`check_content` и `fsm._approve_spec_gate` не тронуты. |
| 5 | OK с оговоркой | Долгоживущие тесты задачи + `TrackingRefsDefaultTest` с заявками «Ловит мутацию». Пробел в покрытии второго пути амендмента — см. R1-F1 (minor). |

## Замечания

- minor — `orchestrator/amend.py:737` (`_amend_with_long_lived`) — уборку каталога в режиме с перечнем долгоживущих файлов не держит ни один тест: временная мутация (вызов `_drop_fixed_task_dir` в `_amend_with_long_lived` заменён на `pass`) оставила зелёными `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py`, `tests/test_amend_long_lived.py`, `tests/test_amend.py` (50 passed). Долгоживущий AC-1 идёт только по пути без перечня. Сценарий: при рефакторинге `amend.py` вызов в ветке long-lived пропадает, и ложная находка гейта зон возвращается ровно у задач с долгоживущей планкой (а сейчас таких большинство) — CI этого не заметит. Сейчас код правильный, поэтому замечание не блокирует. Предложение: добавить в `tests/test_amend_long_lived.py` метод, проверяющий отсутствие `<wt>/tasks/<id>/` после успешного amend в режиме с перечнем (с заявкой «Ловит мутацию: уборка не вызвана в `_amend_with_long_lived`»). Можно отдельной задачей.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/amend.py:737 | уборка `tasks/<id>/` в `_amend_with_long_lived` не покрыта тестом (мутация не краснеет) | будущая регрессия по пути long-lived пройдёт CI незамеченной | minor, мерж не блокирует; тест-сторож — в копилку/отдельной задачей |

## Вердикт
approved — blocker/major нет. Требования 1–4 реализованы в общем виде, без веток под фикстуры. Сторожа на каждый пункт проверены временными мутациями. Единственное замечание — minor R1-F1 (пробел в покрытии второго пути amend) — мерж не блокирует.

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m42nbcadgsgtcbzb8nkbvdvh_{amend_cleanup,guard_spec_paths,observe_extra_args,workspace_fetch}.py tests/test_gitcmd_fetch_ref_sha.py tests/test_workspace.py tests/test_amend.py tests/test_amend_long_lived.py tests/test_guard_path_mentions.py tests/test_fsm_spec_gate_path_check.py tests/test_observation_edges.py` — 116 passed, 20 subtests passed.
- Временные мутации (после каждой код возвращён `git checkout --`, `git status` чистый):
  - `workspace.ensure` с `tracking_refs=True` → красные AC-3 и AC-4 (`..._workspace_fetch.py`);
  - вызов `spec_path_errors` из `guard.main` снят → красный AC-8;
  - вызов `_refuse_extra_observe_args` снят → красные AC-6 и AC-7;
  - `drop_from_code_copy` в `_drop_fixed_task_dir` снят → красный AC-1;
  - снят только вызов в `_amend_with_long_lived` → всё зелёное (50 passed): отсюда R1-F1.
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M42NBCADGSGTCBZB8NKBVDVH` — «планки нет»: разовых файлов в зафиксированной планке нет, вся планка долгоживущая и прогнана выше.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` — меняется только строка `built_at_sha`, карта свежая (изменение отменено).
- `grep` вызовов guard CLI в `orchestrator/`/`.github/` — оркестратор гоняет только `guard.py --all` (`fsm_merge_gate.py:444`, `ci.yml:44`), новая проверка их не задевает.
- Сверка утверждений существующих тестов с базой: в `tests/` изменён только `test_gitcmd_fetch_ref_sha.py`, и там лишь добавлен класс — удалённых или изменённых assert нет.

## Предложения системе
- Классу «правка вставлена в несколько равноправных веток кода (здесь два успешных пути `amend-tests`), а тест-сторож покрывает одну» стоит отвести пункт в `skills/review-checklist.md` (Фаза B, «Тесты»): проверять временной мутацией каждое место вставки, а не одно.
