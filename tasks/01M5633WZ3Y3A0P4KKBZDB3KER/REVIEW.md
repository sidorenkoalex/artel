---
task: 01M5633WZ3Y3A0P4KKBZDB3KER
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Долгоживущие тесты внешнего проекта: правило импортов по профилю

## Фаза A: план
- Таблица покрытия PLAN полна (требования 1–7 → шаг 1 / долгоживущие файлы test_author).
- Один шаг-монолит соответствует оценке объёма SPEC; размер MR — 6 файлов, +112/−24.
- Подход не конфликтует с архитектурой: признак артели берётся через `repo_context.is_artel`
  внутри зон, `orchestrator/fsm_advance.py` не тронут; сигнатуры guard расширены
  keyword-аргументами со значением по умолчанию — обёртка `(files, task_id, **kwargs)` из
  `tests/test_01m4kaj0bj9ec37rwxnfkqn7dw_amend_network_scope.py` продолжает работать (файл зелёный).
- «Влияние на систему» совпадает с diff: правки только в шести файлах зон, `tests/` — только
  два долгоживущих файла задачи, защищённые пути (`.github`, `gates.yaml`, `roles.yaml`,
  `skills`, `templates`) не тронуты.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `targets.py`: вид `identifiers` (`isinstance list` + `str.isidentifier` на каждый элемент; пустая строка, `"src.app"`, `"*"`, не-строки — отказ), подполе в `PROFILE_OPTIONAL`; `Profile.long_lived_imports: tuple = ()`, `from_values` переносит с сохранением порядка. |
| 2 | OK | `targets.check`: при `name == config.DEFAULT_TARGET` присутствие подполя — `TargetsError`; у артели `project_profile.long_lived_imports` → `None` → прежний набор и литерал `_SIGN_EXPLANATIONS`. |
| 3 | OK | `_allowed_import_tops(project_imports)` — объединение frozenset, членство = точное совпадение; текст для непустого перечня называет `test_profile.long_lived_imports: <имена>`. |
| 4 | OK | Пустой/отсутствующий перечень → `()` → прежний набор; текст называет подполе, которое надо заполнить. |
| 5 | OK | Все пять мест передают `project_imports`; grep подтверждает, что других вызовов `long_lived_errors_from_files` в `orchestrator/`, `scripts/` нет. |
| 6 | OK | `tests_writing._project_imports` и `amend` — через `workspace.task_target`; `preflight` — через `target` строки задачи; `fsm_advance.py` не в diff. |
| 7 | OK | Тесты на учебном внешнем проекте (`make_project_repo`), без сети, зерно печатается. |

## Замечания

Замечаний нет.

Не замечание, для сведения: базовая фраза «только стандартная библиотека, orchestrator,
scripts, tests» продублирована литералом в `scripts/guard.py::_foreign_import_explanation`
рядом с `_SIGN_EXPLANATIONS`. Для поведения это ничего не меняет, поэтому замечанием не
заведено.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: замечаний в итерации 1 не заведено.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q tests/test_01m5633wz3y3a0p4kkbzdb3ker_long_lived_imports.py tests/test_01m5633wz3y3a0p4kkbzdb3ker_profile_imports_field.py`: 12 passed, 92 subtests passed (62 с).
- `artel.py plank-run 01M5633WZ3Y3A0P4KKBZDB3KER`: отказ «планки нет: в источнике нет файлов test_*.py», pytest не запускался. Разовой планки у задачи нет, всё покрыто долгоживущими файлами `tests/`.
- Соседние модули: `test_01m4kaj0bj9ec37rwxnfkqn7dw_amend_network_scope`, `test_01m4p4zp37wv81410ytzhkqc8d_preflight`, `test_01m4s24963r9h18an2xdp6r15b_targets_field`, `test_01m4s0jvb85w9ty1esgnbh97fp_targets_knowledge`, `test_01m4jn2edqp8q3wvyk0ts95zvc_network_address`, `test_amend_long_lived`, `test_fsm_advance_tests_writing_test_groups`, `test_guard_test_groups`, `test_long_lived_transitions`, `test_preflight`, `test_project_profile`, `test_project_profile_gates`: 109 passed, 273 subtests passed.
- Временная мутация 1: в `preflight.cmd_preflight` в `_groups` передан `()` вместо `project_imports`. Покраснели `test_ac3_listed_imports_pass_preflight` (место «preflight: проверка групп планки») и `test_ac1_artel_foreign_import_refused_with_old_text` (тот же раздел), то есть заявки AC-1/AC-3 подтверждены. Код возвращён через `git checkout`.
- Временная мутация 2: условие отказа артели в `targets.check` заменено на `if False`. Покраснел `test_ac1_artel_record_with_long_lived_imports_refused` (оба подтеста). Код возвращён.
- `python3 scripts/codebase_map.py`: diff карты — только строка `built_at_sha`, по содержимому карта свежая. Регенерация отменена через `git checkout`.
- `git diff 9d04674d...HEAD --stat -- tests/ .github gates.yaml roles.yaml skills templates`: только два новых долгоживущих файла задачи. Существующие тесты не изменены и не удалены.
- `git status --short` после всех проверок пуст.

## Предложения системе
- `plank-run` на задаче, где все тесты долгоживущие и лежат в `tests/`, отвечает «отказ — планки нет». Ревьюверу стоит знать заранее, что это штатный исход, а не сбой, например по пометке в `skills/review-checklist.md`.
