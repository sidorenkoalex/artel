---
task: 01M5JGSAANR1NZYQD4FCSVE48Y
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: G3б-3: компонент задачи по зонам, компоненты гейтов по диффу и снятие отказа записи из нескольких компонентов

## Фаза A — план
- Таблица покрытия полна: требования 1–7 привязаны к шагам 1–6. Шаги размера MR, не микрооперации.
- Подход «`for_task_target` с тем же `target` и ветки под `is_multi`» с конвенциями и архитектурой не конфликтует. Он побайтно сохраняет поведение прочих записей: это держат AC-2/AC-10/AC-15/AC-26, планка зелёная.
- «Влияние на систему» сверено с diff. Затронуты ровно места таблицы SPEC, `outcome_integrity`, `mandate` (три места), `targets.MULTI_COMPONENT_PENDING`, `layers_declared` и один новый тест `tests/test_profile_layers_declared.py`. Существующие тесты не правились, путь отката описан. Расхождений нет.
- Замечание к плану одно, оно же R1-F1: шаг 6 закладывает только «тесты test_author: долгоживущие и планка». Сторожа после мержа для мест таблицы, которые покрыты одной планкой, план не предусматривает.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `task_components`/`decide_task`/`for_task`/`_by_zones` (`orchestrator/project_profile.py`). Зона-каталог читается через `ls-tree` базы `origin/<base>`, при сбое — `ZoneListingError` и отказ. Три текста с причиной `decide` через «; ». Проверка обязательных подполей продублирована (`repo_context` — модуль только для чтения). Новый текст `MULTI_COMPONENT_PENDING`. |
| 2 | OK по коду, R1-F1 по тестам | Места таблицы переведены на `for_task_target`/`for_row`. Вызовы `decide(...)`, которые остались (`grep`), — это только недостижимые `fsm_merge_gate.py:865`/`:919`, `_bounds` и `suite_run._profile_command` (обе ветки только для не-multi), а также `brief._knowledge_of` без `task_id`. Команда `knowledge` профиль не читает, правка не нужна. Отказ вместо пропуска сделан в `acceptance_suite`, `full_suite`, `_test_integrity_diff_gate`, `_external_helpers`, `matrix_refusals`, `pull`. Мандаты и матрица — по компонентам записи в границе. |
| 3 | OK | `_components_gate`: дифф → `select_components` с потребителями → `component_profiles`. На каждый компонент в границе — свой `_gate`, отказ с префиксом «компонент X: », строки «вне границы» идут в `extra`. Когда все компоненты вне границы, пишется `journal_skip` с «голова <sha>». `review_lines`/`_components_review_lines`; фильтр в `review._outcome_gate_lines` снят только у multi. |
| 4 | OK | `_tests_writing_foreign_plank_gate` стоит первым в списке гейтов и не зависит от границы Y (AC-19/AC-25/AC-27 зелёные). |
| 5 | OK | `brief._knowledge_of` (компонент профиля вместо `comps[0]`), `role_prompt`, `runner._reports_vitest`, `plank_run`. |
| 6 | OK | Учебный проект и тесты test_author на месте. |
| 7 | OK | `layers_declared` (`compare=False`) и `layers_of`; `profile.layers` остаётся `()`. |

## Замечания

- major — свойство требования 2 и AC-9/AC-22/AC-24 после мержа без сторожа в `tests/`. По одной планке закрыты места `orchestrator/acceptance.py:3504–3512` (`acceptance_suite`: отказ вместо молчаливого пропуска `checks_local`), `orchestrator/fsm_merge_gate.py:143–149` (`_test_integrity_diff_gate`: отказ вместо пропуска гейта текста на мерже), `orchestrator/advance_gates/test_integrity.py:1304–1307` (`_external_helpers` без отката на область по умолчанию), `orchestrator/advance_gates/mandate.py:652–657` (`matrix_refusals`: отказ вместо отката на правило `tests/…`), `orchestrator/acceptance.py:3359–3369` (предел `full_suite` компонента задачи), `orchestrator/suite_run.py:625–647/:654–660/:874–877` (`suite-run <id>`), `orchestrator/pull.py:665–676`, `orchestrator/preflight.py:241`, `orchestrator/amend.py:184/:202`, `orchestrator/checkpoint.py:593/:626/:1858–1870` (`_multi_refusal_note`), `orchestrator/advance_gates/zones.py:287`, `orchestrator/advance_gates/review.py:209`, `orchestrator/runner.py:1325`, `orchestrator/fsm_autogate.py:252–264`, `orchestrator/review.py:638/:758`.
  - Их проверяют только `tasks/<id>/acceptance_tests/test_places_{gates,transitions,roles}.py`, и все три помечены «Группа: разовый». Долгоживущие файлы задачи (`tests/test_01m5jgsaanr1nzyqd4fcsve48y_*.py`) покрывают выход из `tests_writing`, гейт исходов на `in_dev` и мерже, бриф, задание, сводки Vitest, `plank-run` и мандат, но не места выше. `grep` по `tests/` текстов новых отказов («checks_local компонента задачи не определены», «матрица неослабления не сверена», «предел полного набора не определён», «планка после подтяжки … не прогнана») и имён `_component_command`/`_multi_refusal_note`/`for_task_target`/`is_multi` пуст.
  - Доказано временной мутацией. Возврат `acceptance_suite` к `profile = None` (молчаливый пропуск `checks_local`) вместе с отключением ветки отказа `_test_integrity_diff_gate` оставил зелёными четыре долгоживущих файла задачи, `tests/test_component_checks.py` и `tests/test_test_integrity_gate.py`: 108 passed. После этого код возвращён (`git checkout`), дерево чистое.
  - Сценарий последствий: любая будущая правка, которая вернёт одно из этих мест на `decide(target)` или на пропуск при отказе, у записи из нескольких компонентов молча снимет гейт неослабления (именно это ослабление SPEC в «Оценке объёма» называет запрещённым без ADR). Планку смерженной задачи CI не гоняет (ADR-0018 п. 3), и ни один тест не покраснеет.
  - Предложение: добавить в `tests/` (разработчик вправе, это не правка планки) долгоживущие тесты мест на учебной записи из двух компонентов. По каждому месту — два исхода: (а) у задачи с одним компонентом место берёт профиль этого компонента; (б) при отказе `for_task` — отказ с текстом AC-3, без пропуска. Обязательный минимум — fail-closed места, где раньше был пропуск: `acceptance_suite`, `_test_integrity_diff_gate`, `_external_helpers`, `matrix_refusals`, а также `full_suite`/`suite-run` (предел компонента). Остальные места списка — по возможности общим параметризованным тестом. Каждый тест должен нести «Ловит мутацию: место на `decide(target)`/пропуск при отказе — …». Повторять уже долгоживущее не нужно.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/acceptance.py:3504; orchestrator/fsm_merge_gate.py:143; orchestrator/advance_gates/test_integrity.py:1304; orchestrator/advance_gates/mandate.py:652; orchestrator/acceptance.py:3359; orchestrator/suite_run.py:625; orchestrator/pull.py:665; orchestrator/preflight.py:241; orchestrator/amend.py:184; orchestrator/checkpoint.py:593,1858; orchestrator/advance_gates/zones.py:287; orchestrator/advance_gates/review.py:209; orchestrator/runner.py:1325; orchestrator/fsm_autogate.py:252; orchestrator/review.py:638,758 | Места таблицы SPEC (профиль компонента задачи и отказ вместо пропуска при отказе `for_task`) закрыты только разовой планкой `test_places_*.py`. Сторожа в `tests/` нет, временная мутация `acceptance_suite` + `_test_integrity_diff_gate` прошла 108 тестов зелёной. | После мержа возврат места на `decide`/пропуск у записи из нескольких компонентов молча ослабит гейт неослабления, CI не заметит. | Долгоживущие тесты мест в `tests/` на учебной записи из двух компонентов: профиль компонента задачи и отказ с текстом AC-3. Минимум — fail-closed места (`acceptance_suite`, `_test_integrity_diff_gate`, `_external_helpers`, `matrix_refusals`, предел `full_suite`/`suite-run`), с заявками «Ловит мутацию». |

## Вердикт
changes_requested. Нужно исправить R1-F1: добавить в `tests/` сторожей мест таблицы SPEC, минимум для fail-closed мест, где раньше был молчаливый пропуск. Код задачи по SPEC замечаний не получил.

## Проверено исполнением
- `artel.py plank-run 01M5JGSAANR1NZYQD4FCSVE48Y` — 69 passed in 67.51s, код выхода 0. Повторно `… plank-run … test_places_gates.py` после возврата мутации — 31 passed, код выхода 0.
- Временная мутация: `acceptance_suite` при `ComponentsPending` → `profile = None` и `elif False and is_multi` в `_test_integrity_diff_gate`. Затем `python3 -m pytest` по четырём `tests/test_01m5jgsaanr1nzyqd4fcsve48y_*.py`, `tests/test_component_checks.py`, `tests/test_test_integrity_gate.py` — 108 passed, 41 subtests passed (3:42): мутацию не поймал ни один тест. Код возвращён `git checkout`, `git status` чистый.
- `python3 -m pytest` по `tests/test_profile_layers_declared.py`, `test_mandate_test_id.py`, `test_mandate_profile_scope.py`, `test_fsm_autogate_plank_rule.py`, `test_01m58fnwbv25ff26e7az9q9912_components.py`, `test_01m5j0jyw3gzsshhk3tycytq3j_profile_layers.py`, `test_suite_run.py`, `test_multitarget.py` — 96 passed, 159 subtests passed.
- `grep -n "decide(\|profile_of("` по `orchestrator/` — оставшиеся вызовы сверены с таблицей SPEC (см. «Соответствие SPEC», требование 2).

## Предложения системе
- Разовая группа планки для «мест таблицы» обоснована тем, что «прямой вызов места после мержа теряет смысл». Из-за этого fail-closed свойство остаётся без сторожа. Стоит прямо сказать в skills/test-authoring.md, что свойство «место не пропускает проверку при отказе» долгоживущее, даже когда тест зовёт закрытую функцию.
- `tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py` идёт 87.7 с при пороге 60 с (предупреждение пакета). Песочница G3а-1а с настоящим git на каждый метод дорога, этот класс будет повторяться в задачах гейта исходов.
