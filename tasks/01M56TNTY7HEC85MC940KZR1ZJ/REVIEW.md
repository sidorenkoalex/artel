---
task: 01M56TNTY7HEC85MC940KZR1ZJ
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Гейт неослабления: помощники по области ослабления проекта

## Фаза A — план
- Таблица покрытия PLAN.md охватывает требования 1–8; шаги 1–3 — проверяемые
  единицы размера MR (guard / узел test_integrity / юнит-тесты + карта).
- Подход (режим в `guard.TestModules`, чтение режима и профиля на `_evaluate`)
  не конфликтует с архитектурой: `review.py`, `fsm_merge_gate.py`, `fsm.py`
  не тронуты.
- «Влияние на систему» соответствует diff (три файла в зонах SPEC). Раздел
  «Возврат с приёмки (ANSWER-1)» согласован с ANSWER-1: код и тесты после
  итерации 1 не менялись — последний кодовый коммит задачи 5bce46be, после
  него только подтяжки main, и ни одна не трогала `scripts/guard.py`,
  `orchestrator/advance_gates/`, `project_profile.py`, `repo_context.py`,
  `tests/sandbox.py` (`git log 5bce46be..HEAD -- <эти пути>` пуст).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_external_helpers` (test_integrity.py) по `repo_context.is_artel(store.task_target)`; внешний режим: `TestModules.module_path` → `<workdir>/a/b.py` со сверкой с областью, `_HelperScope.function` снимает ограничение `tests/sandbox.py` при `external`; `_helper_callers(everywhere=True)` + отсев по области в `_compare`. Артель — прежний `_tests_module_path` и pathspec `tests/`. |
| 2 | OK | `external` — отдельный аргумент; без него `_workdir = ""` при любом `workdir` (юнит-тест `test_workdir_without_external_keeps_artel_rule`, AC-2). |
| 3 | OK | Чтение на `_evaluate` → все три входа; временная мутация (поиск вызывающих только в `tests/` у внешнего) красит AC-1 на всех трёх входах. Вызовы в review.py/fsm_merge_gate.py не менялись. |
| 4 | OK | `TestModules.import_path` снимает префикс `workdir` перед `_tests_import_bindings`; AC-3 и юнит-тест `..h` с `workdir: backend/` зелёные. |
| 5 | OK | Сверка с областью в `module_path` до чтения модуля; AC-4 и `test_external_module_outside_scope_is_not_read`. |
| 6 | OK | Новые аргументы `TestModules` необязательные, `method_literal_keys` не менялся, `fsm.py` не тронут. |
| 7 | OK | AC-5 долгоживущего файла (пять исходов) зелёный; артельные ветки кода эквивалентны прежним. |
| 8 | OK | Тесты на локальном git песочницы, без сети; оба учебных проекта в долгоживущем файле. |

## Замечания
Блокеров и major нет.

- minor (наблюдение итерации 1, без требования правки) — orchestrator/advance_gates/test_integrity.py `_external_helpers` — внешний проект без читаемого профиля идёт во внешний режим с `workdir=""` и областью артели: функции любого модуля `tests/` становятся помощниками. Это строже, а не слабее, и PLAN это объявляет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

(Записей нет ни в итерации 1, ни в этой; minor выше — наблюдение без требования правки.)

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q tests/test_guard_helper_scope_modes.py tests/test_01m56tnty7hec85mc940kzr1zj_helper_scope.py tests/test_guard_helper_scope.py tests/test_guard_assertion_changes.py tests/test_test_integrity_helper_heirs.py tests/test_test_integrity_gate.py tests/test_01m4g8n9kbtvnnt7ygz59q5wbf_helper_assertions.py tests/test_guard_test_ast.py` на HEAD 295f4dee — 115 passed, 11 subtests passed.
- Временная мутация (test_integrity.py: `everywhere=helpers is not None` → `everywhere=False`, то есть поиск вызывающих только в `tests/` у внешнего проекта) — красные AC-1 (все три входа: рубеж, review_lines, merge_gate_escalates), AC-3, AC-4; AC-2 и AC-5 зелёные, как и ожидалось. Код возвращён `git checkout`, `git status` чист.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` без строки `built_at_sha` — расхождений нет; файл возвращён.
- `git log 5bce46be..HEAD` по файлам механики — пусто: подтяжки main после итерации 1 механику гейта не задели.
- `artel.py plank-run` не запускал: в итерации 1 команда ответила «планки нет», приёмка задачи — долгоживущий файл в `tests/`, он прогнан выше.

## Предложения системе
- Ревью-пакет итерации 2 не смог определить базу инкрементального diff («журнал фиксации не несёт её») при повторном ревью после ошибочного возврата с приёмки — для такого пути стоит фиксировать sha кодовой ветки прошлого вердикта.
