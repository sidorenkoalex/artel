---
task: 01M4S24EBVB72B8WYJ3JY96Y0E
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Справочник ядра в брифе и пересборка после мержа (К-3б)

## Фаза A — план

- Таблица покрытия PLAN полна: требования 1–12 привязаны к шагам 1–4; шаги — единицы размера MR (бриф+константа, шаг мержа, свой тест, карта+приложение).
- Подход совпадает с образцами SPEC (`map_note`, `_handle_map_size_alert`, `_manifest_component`), архитектуре не противоречит; защищённые пути не тронуты, `targets.yaml` — только приложением PLAN.
- «Влияние на систему» сверено с diff (`git diff --stat b49b1f56...HEAD`): ровно `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/fsm_merge_gate.py`, `tests/test_merge_reference_step.py` (+ карта, долгоживущие тесты задачи) — в зонах SPEC. Путь отката описан.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `brief.py::developer_brief` — `_core_reference_part` вставлен между проекцией карты и `CONVENTIONS_REL`; вызов `get_reference(conn, task_id, reason="brief")` без `sha` |
| 2 | OK | `test_author_answer_component`: куски (причина, ANSWER, справочник) через `"\n".join`, `None` только при всех пустых |
| 3 | OK | `_core_reference_part` зовут только две функции; AC-3 зелёный |
| 4 | OK | `off` → `""`, кусок не добавляется; склейка двух прежних кусков `"\n".join` == прежний `sep="\n"` — байт в байт. Нечитаемый `targets.yaml`: К-3а (`reference_cache.get_reference`, стр. 111–120) не бросает, отдаёт `absent` с пометкой и алертом; отказы `brief.py`/`fsm_merge_gate.py` не тронуты |
| 5 | OK | `_manifest_component` с меткой `.artel/projects/{target}/` + `reference_cache.CACHE_REL` — относительная; опись, журнал, граница |
| 6 | OK | `note` — префикс вне хэшируемого текста при любом `state`; `absent`/пустой текст — только пометка |
| 7 | OK | `config.CORE_REFERENCE_MAX_BYTES = 32_768`, размер — `len(text.encode("utf-8"))`, `>`; строка пропуска без пути кэша; `incident` по `target`, авто-снятие по источнику И проекту; текст алерта — константа без чисел |
| 8 | OK | `size*10 > limit*9` и не oversized; при oversized предупреждение снимается |
| 9 | OK | `_rebuild_core_reference(conn, task_id, final_sha)` после `_await_main_ci`, перед `return ("done",)`; на `moved` ветка возвращается раньше; `try/except Exception`, журнал и алерт обработчика — под `contextlib.suppress(Exception)`; `sys.exit`-помощников нет, коммитов нет |
| 10 | OK | Приложение PLAN: `guard.plan_appendices` → ровно одно, `('targets.yaml',)`; `git apply --check` на чистом дереве — rc 0; блок и отступы буквально по требованию |
| 11 | OK | Долгоживущие файлы задачи + `tests/test_merge_reference_step.py` (свойства, которых нет в долгоживущих: содержимое записи исхода и алерт сбоя по проекту); существующие тесты не менялись (в diff `tests/` только новый файл) |
| 12 | OK | `python3 scripts/codebase_map.py` на голове ветки — расхождение только в строке `built_at_sha` (не дефект) |

## Замечания

Замечаний уровня blocker/major/minor нет.

Проверенные и снятые сомнения:
- Дедуп алерта предела при каждом брифе: `alerts.raise_alert` дедуплицирует по (target, kind, source, message) открытых — тексты-константы не плодят копий (`orchestrator/alerts.py:93-108`, прочитан ради этой проверки).
- Двойной алерт сбоя шага мержа с тем же источником `fsm.core_reference_regen`: `get_reference` по контракту К-3а не бросает (`reference_cache.py:99-113`), так что обработчик шага срабатывает только на непредусмотренном сбое — дубля с алертом К-3а нет.
- Удержание мьютекса мержа до 60 с — принятая SPEC цена (требование 9).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт

approved — все требования SPEC реализованы, планка и тесты затронутых модулей зелёные, заявки мутаций нового теста подтверждены временной мутацией.

## Проверено исполнением

- `python3 -m pytest -q tests/test_01m4s24ebvb72b8wyj3jy96y0e_brief_reference.py tests/test_01m4s24ebvb72b8wyj3jy96y0e_merge_reference.py tests/test_merge_reference_step.py tests/test_brief.py tests/test_review_package.py tests/test_core_reference.py` — 191 passed, 53 subtests passed.
- `python3 -m pytest -q tests/test_fsm_merge_gate_done_snapshot.py tests/test_merge_gate_ci_wait.py tests/test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py tests/test_advance_refusal_history.py tests/test_role_prompt_test_author_mission.py` — 51 passed, 20 subtests passed.
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M4S24EBVB72B8WYJ3JY96Y0E` — 2 passed, код выхода 0.
- Временная мутация 1: алерт в обработчике сбоя `_rebuild_core_reference` заменён на no-op → `test_failure_is_journaled_and_alerted_by_project` красный; код возвращён (`git checkout`).
- Временная мутация 2: убрано `detail += f"; {reference.note}"` → `test_outcome_is_journaled_with_state_sha_and_note` красный; код возвращён.
- `guard.plan_appendices(PLAN)` → 1 приложение, пути `('targets.yaml',)`, нераспознанных нет; `git apply --check` диффа приложения на чистом дереве — rc 0.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` — меняется только `built_at_sha`; изменение откатено, дерево чистое.
- Сверка неослабления: `git diff --stat b49b1f56...HEAD -- tests/` — только новый `tests/test_merge_reference_step.py`, существующие методы не тронуты.

## Предложения системе

- Ревью-пакет / `scripts/guard.py::plan_appendices`: функция возвращает кортеж (приложения, нераспознанные), а SPEC формулирует «возвращает ровно одно приложение» — проверяющий легко прочтёт `len(...) == 2` как два приложения; стоит в шаблоне SPEC писать «первый элемент результата».
