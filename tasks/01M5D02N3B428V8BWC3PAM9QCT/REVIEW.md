---
task: 01M5D02N3B428V8BWC3PAM9QCT
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: G3а-1б — мандат на ослабление по идентификатору теста

## Фаза A: план
- Таблица покрытия PLAN полна (требования 1–6 → шаги 1–5); шаги — размера MR.
- Подход не конфликтует с архитектурой: новый разбор `id_elements` + диспетчер
  `line_elements`, прежние `elements`/`TEST_WEAKENING_MANDATE_MARKER`/`_names`
  не тронуты; `test_integrity.py`, `zones.py`, `project_profile.py` не менялись
  (сверено по `git diff --stat`).
- «Влияние на систему» соответствует diff: 4 модуля зоны + `tests/test_mandate_test_id.py`
  + карта; путь отката назван (revert merge-коммита).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `mandate.py` `TEST_ID_MANDATE_MARKER`, `id_elements` (остаток со `strip`, без деления по запятым); `refusals`, `_matrix_mandate_elements`, `_has_mandate_lines` идут через `line_elements`. `_zones_extend_matrix` (`answer.py:519-520`) не тронут, но ловит строку через `startswith(mandate.MANDATE_MARKERS)`, куда новый маркер добавлен, — для строки маркера это то же условие, что `id_elements(...) is not None`; AC-8 зелёный |
| 2 | OK | `_test_id_refusal`: сначала «`»/«\|» → `FILE_MANDATE_REASON`, затем `parse_test_id`, отказ решения, `_outcome_profile` (`in_outcome_bounds`), компонент = `profile.component`, `in_weakening_scope`. Без задачи/решения — отказ (fail-closed, юнит-тест) |
| 3 | OK | `_has_mandate_lines`, `_spec_gate_answer_text` принимают новый маркер; `test_ids` пишется в `INSTRUCTION_STATES` и на `spec_gate`, в `escalated` — нет (как прежний вид); вид отдельный, идентификаторы в «» |
| 4 | OK | Маркер в `MATRIX_MANDATE_MARKERS` и `spec_audit._MANDATE_MARKERS` (распознавание `line_elements`); независимая проверка обязательна при любом из двух маркеров тестов; «Что меняется» — побайтно по span'ам одинарных кавычек; «Чем покрыто после» — `_component_covered` только при `outcome_bounds`, у артели/`None`/вне границы прежний код. См. наблюдение ниже о нестрогости правила «путь» |
| 5 | OK | `outcome_integrity._answer_mandates` — тот же перебор, отбраковка `zones._answer_commit_is_role_step_autocommit` (импорт); `_covering` — точное равенство для набора нового маркера, прежний `covering` без изменений; своя `_mandate_hint` с обоими маркерами |
| 6 | OK | Долгоживущие тесты задачи (3 файла) и прежние тесты мандата/матрицы/`zones-extend`/гейта SPEC/аудита/гейта исходов зелёные; `git diff 2ab4bfa2...HEAD -- tests/` — только новый `tests/test_mandate_test_id.py`, прежние тесты не правились |

## Замечания
Blocker/major нет.

Наблюдение (minor, вкус; в реестр не заносится, вердикт не блокирует) —
`orchestrator/advance_gates/mandate.py` `_component_covered` (правило «путь» в
`candidates`): требование 4 говорит «путь — любой файл в `weakening_scope`», а
код признаёт покрытием любой токен, совпавший с маской. Проверено исполнением
на профиле `src/**`: ячейки «`src/`», «src/**» и «`src/a.test.ts::suite > case`»
(идентификатор без компонента — `parse_test_id` его не разбирает) признаны
покрытием (`_covered(..., outcome_bounds=True)` → `True`). Последствие —
матрица Оператора может пройти с маской каталога вместо ссылки на тест; ANSWER
пишет только Оператор, поэтому канала обхода для роли нет. Предложение на будущее:
отбрасывать в правиле «путь» токены с `::`, с `*`/`?` и оканчивающиеся на «/».

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved — все требования SPEC реализованы, blocker/major нет; прежние маркеры и
правила ячеек матрицы у артели и вне границы исполняются прежним кодом.

## Проверено исполнением
- `python3 artel.py plank-run 01M5D02N3B428V8BWC3PAM9QCT` — «планки нет: в
  источнике нет файлов test_*.py»: все тесты задачи — долгоживущие в `tests/`.
- `python3 -m pytest -q` по 15 файлам: три долгоживущих файла задачи,
  `tests/test_mandate_test_id.py`, `test_mandate_matrix_form.py`,
  `test_mandate_profile_scope.py`, `test_answer_mandate.py`,
  `test_outcome_integrity.py`, `test_spec_audit_gate.py`,
  `test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_units.py`,
  `test_01m4nz5qrb7mneycwgxewvwfp0_mandate_matrix.py`,
  `test_01m55vdvvdvww2mtj01f88n5fm_weakening_mandate_scope.py`,
  `test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py`,
  `test_01m4r4jqzex2mbdb195sbj8a7s_answer_spec_gate.py`, `test_answer.py` —
  142 passed, 239 subtests passed (338 с).
- Временные мутации в памяти процесса, файлы кода не трогал: (1) префиксное
  правило `covering` для набора идентификаторов → `ExactCoverageTest` красный;
  (2) `_BACKTICK_SPAN_RE` принимает любое число кавычек → `DoubleBacktickNotNamedTest`
  красный; (3) fail-open `_test_id_refusal` без решения → `RefusalWithoutBoundsTest`
  красный. Заявки «Ловит мутацию» юнит-тестов подтверждены.
- Зонд `_covered(cell, COMPONENT_PROFILE, True)` по ячейкам (см. наблюдение):
  чужой компонент, путь вне области, идентификатор без кавычек → `False`;
  «`src/`», «src/**», «`src/a.test.ts::…`» → `True`.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` — без
  изменений сверх `built_at_sha` (карта свежая); регенерацию откатил.
- CI коммита 2986e799 — зелёный (16 проверок, по пакету).

## Предложения системе
- Пустая планка (все тесты задачи — долгоживущие в `tests/`) даёт отказ
  `plank-run` «планки нет» — скилу review-checklist стоит сказать, что тогда
  прогоняются долгоживущие файлы `tests/test_<id>_*.py`.
