---
task: 01M56TNTY7HEC85MC940KZR1ZJ
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Гейт неослабления: помощники по области ослабления проекта

## Фаза A — план
- Таблица покрытия PLAN.md охватывает требования 1–8, шаги 1–3 — проверяемые
  единицы размера MR (guard / узел test_integrity / юнит-тесты + карта).
- Подход (режим в `guard.TestModules`, чтение режима и профиля на `_evaluate`)
  не противоречит архитектуре: `review.py`, `fsm_merge_gate.py`, `fsm.py` не
  тронуты (diff --stat — только три файла в зонах SPEC).
- «Влияние на систему» соответствует diff: у артели `_external_helpers`
  возвращает `None` → `_compare` и `TestModules` идут по прежним веткам. Откат
  описан.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_external_helpers` (test_integrity.py) по `repo_context.is_artel(store.task_target)`; внешний режим: `TestModules.module_path` → `<workdir>/a/b.py` со сверкой с областью, `_HelperScope.function` снимает ограничение `tests/sandbox.py` при `external`; `_helper_callers(everywhere=True)` + отсев `in_scope(path)` в цикле `_compare` (~:784). Артель — прежний `_tests_module_path` и pathspec `tests/`. |
| 2 | OK | `external` — отдельный аргумент; `_workdir = workdir.strip("/") if external else ""` — без режима `workdir` игнорируется (юнит-тест `test_workdir_without_external_keeps_artel_rule`, AC-2). |
| 3 | OK | Чтение на `_evaluate` → получают все три входа; временная мутация «`_external_helpers` всегда `None`» красит AC-1 на всех трёх subTest-входах. Вызовы в review.py/fsm_merge_gate.py не менялись. |
| 4 | OK | `TestModules.import_path` снимает префикс `workdir` перед `_tests_import_bindings`; AC-3 и юнит-тест `..h` с `workdir: backend/` зелёные. |
| 5 | OK | Сверка с областью в `module_path` до чтения модуля; временная мутация (снять сверку) красит AC-4 и `test_external_module_outside_scope_is_not_read`. |
| 6 | OK | Новые аргументы `TestModules` необязательные, `method_literal_keys` не менялся, `fsm.py` не тронут. |
| 7 | OK | AC-5 долгоживущего файла (пять исходов) зелёный; артельные пути кода побайтно эквивалентны прежним (`_tests_module_path` = прежнее тело `_module`, `import_path` при пустом `_workdir` — тождество). |
| 8 | OK | Тесты на локальном git песочницы, без сети; оба учебных проекта (backend и плоский) в долгоживущем файле. |

## Замечания
Блокеров и major нет.

- minor — orchestrator/advance_gates/test_integrity.py `_external_helpers` — внешний проект без читаемого профиля переводится во внешний режим с `workdir=""` и областью артели (`_in_scope`): функции любого модуля `tests/` такого проекта становятся помощниками (раньше — только `tests/sandbox.py`). Это строже, не слабее, и PLAN это объявляет («остаётся на переданной области»); фиксирую как наблюдение, не требую правки.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

(Замечаний уровня, требующего записи в реестр, нет; minor выше — наблюдение без требования правки.)

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q tests/test_guard_helper_scope_modes.py tests/test_01m56tnty7hec85mc940kzr1zj_helper_scope.py tests/test_guard_helper_scope.py tests/test_guard_assertion_changes.py tests/test_test_integrity_helper_heirs.py` — 45 passed, 8 subtests passed.
- `python3 -m pytest -q -x tests/test_test_integrity_gate.py tests/test_01m4g8n9kbtvnnt7ygz59q5wbf_helper_assertions.py tests/test_guard_test_ast.py` — 70 passed, 3 subtests passed.
- `artel.py plank-run 01M56TNTY7HEC85MC940KZR1ZJ` — отказ «планки нет» (в refs/artifacts нет test_*.py; приёмка задачи — долгоживущий файл в `tests/`, прогнан выше).
- Временная мутация 1 (guard.py: убрана сверка `_in_scope` в `module_path`) — красные `test_ac4_…` и `test_external_module_outside_scope_is_not_read`; код возвращён `git checkout`.
- Временная мутация 2 (test_integrity.py: `_external_helpers` всегда `None`) — красные AC-1 (все три входа), AC-2, AC-3, AC-4; AC-5 зелёный; код возвращён `git checkout`, `git status` чист.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` без строки `built_at_sha` — расхождений нет (карта свежая); файл возвращён.

## Предложения системе
- В шелле шага роли нет `cat`/`ls` (`command not found`) — записку пришлось писать инструментом Write; стоит отразить в conventions-core или проверить PATH курируемого HOME.
