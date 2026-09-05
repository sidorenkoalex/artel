---
task: 01M1P9QCHPHSCEA6TK13PV85SP
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 4
---

# REVIEW: Механика зон, часть 3: сверка диффа с зонами при переходе в ревью

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 / AC-1 | OK* | `_zones_gate_refuses` (orchestrator/fsm_advance.py:525-593) реализует отказ; unit- и приёмочные тесты зелёные. *Одна из подтверждённых ANSWER-1 (п.4) сцен AC-1 (`zones_extension` из прошлого раунда засчитывается зоной) не попала в код-ветку — см. R1-F1. |
| 2 / AC-3 | OK* | Исключение по разделу «## Расширение зон» + маркеру `Расширение зон разрешено:` реализовано (fsm_advance.py:471-593), логика корректна (проверено юнит- и приёмочными тестами на диске). *Единственный исполняемый тест этого требования (`test_ac3_zones_extension_with_operator_mandate.py`) в код-ветку не попал — см. R1-F1 (blocker). |
| 3 / AC-4 | OK | Новый гейт — просто `return False`/`True` из функции, вызываемой перед `store.set_state(..., "review", ...)`; нового состояния FSM нет, `state()` остаётся `in_dev` (проверено `test_ac4_...`). |
| 4 / AC-7 | OK | Полный `tests/` прогнан — 1527/1527, зелёный (см. «Проверено исполнением»). Ослабления существующих тестов/гейтов не найдено. |
| AC-2 | OK | `detail` перечисляет конкретные файлы (`', '.join(out_of_zone)`), не общую фразу; `test_ac2_refusal_names_the_exact_out_of_zone_files` подтверждает. |
| AC-5 | OK | Отказ журналируется действием `"переход отклонён: гейт зон"` — тот же префикс, что и остальные отказы `advance`; `brief.advance_refusal_history` подхватывает (`test_ac5_...` зелёный). |
| AC-6 | OK | `zones = declared + list(config.COMMON_ZONES)` — пересечение с общим списком зон не считается нарушением (`test_ac6_common_zones_pass.py` зелёный). |

Код (`orchestrator/fsm_advance.py`, `orchestrator/store.py`) реализует все семь критериев корректно и по образцу существующих гейтов того же перехода (`_capacity_gate_refuses`), что подтверждается юнит-тестами (`tests/test_zones_gate.py`) и приёмочными тестами задачи — но см. R1-F1: приёмочный набор, который это подтверждает, целиком лежит в артефактной ветке и НЕ смержен в код-ветку, которую фактически ревьюю.

## Замечания

- **blocker** — `tasks/01M1P9QCHPHSCEA6TK13PV85SP/acceptance_tests/` (весь каталог, код-ветка `task/01m1p9qchphscea6tk13pv85sp-mekhanika-zon-chast-3-sverka-d`, HEAD 45ebfd4b) — код-ветка, которую ревьюю (и которая пойдёт на merge), несёт УСТАРЕВШИЙ снимок приёмочных тестов задачи, а не финальный, разрешивший обе эскалации test_author. Конкретно:
  - `test_ac3_zones_extension_with_operator_mandate.py` — единственный исполняемый тест AC-3 (мандат Оператора на расширение зон) — в код-ветке ОТСУТСТВУЕТ ВООБЩЕ. Файл существует в артефактной ветке `artifact/01m1p9qchphscea6tk13pv85sp` с коммита `4bcfa0c6` (шаг test_author, ДО коммита разработчика `45ebfd4b`) — разработчик имел к нему доступ на момент своего коммита, но не перенёс.
  - `test_ac7_existing_suite_marker.py` — файл с оставшейся пометкой AC-7 (после того как AC-3 выделили в исполняемый тест) — тоже отсутствует в код-ветке.
  - `test_ac3_ac7_markers.py` в код-ветке несёт СТАРЫЙ полный текст эскалации `# AC-3: escalate` (полсотни строк вопроса Оператору), хотя эскалация снята ANSWER-1/ANSWER-2 ещё 05.09 — актуальная версия (на диске, из артефактной ветки) короче и просто ссылается на исполняемый тест.
  - `test_ac1_ac2_out_of_zone_diff_refuses.py` в код-ветке не несёт класс `Ac1PreviouslyRecordedExtensionCountsAsZoneTest` — тест сценария ANSWER-1 п.4 (уже одобренный `zones_extension` прошлого раунда засчитывается зоной без повторного мандата) отсутствует.
  - `_sandbox.py` в код-ветке короче актуальной версии на 103 строки — не несёт вспомогательные методы (`write_plan_with_zones_extension`, `write_answer_mandate`, `zones_extension()`, параметр `write_plan` у `advance_with_diff_files`), нужные тесту AC-3.

  Последствие: код, который фактически смержится в main, не имеет НИ ОДНОГО исполняемого теста на исключение AC-3 (самое сложное и дважды эскалированное требование этой задачи) и теряет покрытие одного сценария AC-1. Формально «зелёный набор тестов» на этой ветке проверяется НЕ по тому, что реально в ней лежит: и я, и CI видели зелёный только потому, что рабочее дерево материализовано из артефактной ветки (голова которой ушла дальше кода) поверх код-ветки — при реальном merge в main этих файлов не будет.

  Предложение: разработчику до следующей итерации скопировать актуальное состояние `tasks/01M1P9QCHPHSCEA6TK13PV85SP/acceptance_tests/` из артефактной ветки (`artifact/01m1p9qchphscea6tk13pv85sp`, коммит `05e866b4` или свежее) в код-ветку и закоммитить (`git checkout artifact/01m1p9qchphscea6tk13pv85sp -- tasks/01M1P9QCHPHSCEA6TK13PV85SP/acceptance_tests/` из код-ветки, дальше обычный коммит), затем перепрогнать приёмочный набор УЖЕ из код-ветки (не полагаясь на материализацию поверх).

- **minor** — `tests/test_zones_gate.py` — часть новых unit-тестов не несёт заявку `Ловит мутацию:` в докстринге (skills/test-authoring.md, review-checklist.md п.3) — либо докстринга нет вовсе, либо он описывает семантику без явной мутации-под-удар:
  - `SplitZonePathsTest.test_comma_separated_paths_are_trimmed` — докстринга нет.
  - `SplitZonePathsTest.test_empty_string_gives_empty_list` — докстринга нет.
  - `SplitZonePathsTest.test_blank_entries_are_dropped` — докстринга нет.
  - `TouchesZoneTest.test_exact_file_match` — докстринга нет.
  - `TouchesZoneTest.test_directory_zone_matches_file_under_it` — докстринг есть, но описывает формат зоны (trailing `/`), не формулирует «Ловит мутацию».
  - `TouchesZoneTest.test_file_zone_does_not_match_as_prefix_of_unrelated_file` — докстринга нет (пояснение только в сообщении `assertTrue`, тест к тому же с обманчивым именем: называется «...does_not_match...», а проверяет ИМЕННО совпадение по префиксу, `assertTrue`).
  - `PlanZonesExtensionPathsTest.test_no_section_gives_none` — докстринга нет.
  - `PlanZonesExtensionPathsTest.test_section_with_paths_line_is_parsed` — докстринга нет.
  - `ZonesGateGitFailureTest.test_git_not_answering_diff_names_refuses` — докстринга у метода нет (у класса есть пояснение принципа, но не «Ловит мутацию» дословно).

  Тот же класс замечания уже отмечен в прошлых задачах ([[feedback_test_authoring_mutation_claim_gap]] по памяти ревьювера) — конвенция соблюдается в `acceptance_tests/`, но проседает в `tests/*.py`. Предложение: дописать по каждому тесту одну строку, что именно за регрессия/упрощение кода тест ловит (по примеру уже написанных `test_none_gives_empty_list`, `test_unrelated_path_does_not_match`, `test_section_without_paths_line_gives_none` в том же файле).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | fixed | tasks/01M1P9QCHPHSCEA6TK13PV85SP/acceptance_tests/ (код-ветка, HEAD 45ebfd4b) | код-ветка несёт устаревший снимок приёмочных тестов задачи — отсутствует единственный исполняемый тест AC-3, отсутствует файл `test_ac7_existing_suite_marker.py`, устарели `_sandbox.py`/`test_ac1_ac2_...`/`test_ac3_ac7_markers.py` | AC-3 не имеет исполняемого теста в мержимом коде; AC-1 теряет покрытие сценария ANSWER-1 п.4 | сверил все 5 файлов побайтово с `artifact/01m1p9qchphscea6tk13pv85sp` (совпадают дословно — рабочее дерево уже материализовано из головы артефактной ветки) и закоммитил `acceptance_tests/` целиком в код-ветку; приёмочный набор перепрогнан ИЗ код-ветки (не поверх материализации) — 11/11 зелёных |
| R1-F2 | fixed | tests/test_zones_gate.py (см. список в «Замечания») | ряд новых unit-тестов без заявки «Ловит мутацию:» в докстринге | ревью не может свериться с заявленным свойством теста при следующих правках | дописан докстринг «Ловит мутацию:» во всех перечисленных методах; `test_file_zone_does_not_match_as_prefix_of_unrelated_file` также переименован в `test_file_zone_matches_as_prefix_of_unrelated_file` (имя соответствует `assertTrue`) — 14/14 тестов файла зелёные |

## Вердикт

changes_requested — один blocker (R1-F1: код-ветка не несёт финальный приёмочный набор test_author, AC-3 фактически без теста в мержимом коде) и один minor (R1-F2: докстринги «Ловит мутацию» в части новых unit-тестов). Сама реализация гейта зон (`orchestrator/fsm_advance.py`, `orchestrator/store.py`) корректна и семантически покрывает все семь AC — проблема исключительно в том, что код-ветка разошлась с артефактной по составу `acceptance_tests/`.

## Проверено исполнением

- `python3 -m unittest discover -s tests` — 1527 тестов, все зелёные (полный набор, ~198 сек, включая новый `tests/test_zones_gate.py`, 14 тестов).
- `python3 -m unittest discover -s tasks/01M1P9QCHPHSCEA6TK13PV85SP/acceptance_tests -p "test_*.py" -v` — 11 тестов, все зелёные (запуск на РАБОЧЕМ ДЕРЕВЕ, материализованном из артефактной ветки — не то же самое, что код-ветка, см. R1-F1).
- `git diff --stat main...HEAD -- tasks/01M1P9QCHPHSCEA6TK13PV85SP/acceptance_tests/` — подтверждено: 5 файлов в код-ветке, `test_ac3_zones_extension_with_operator_mandate.py` и `test_ac7_existing_suite_marker.py` в код-ветке отсутствуют.
- `git log --oneline --all -- tasks/01M1P9QCHPHSCEA6TK13PV85SP/acceptance_tests/test_ac3_zones_extension_with_operator_mandate.py` + `git branch --all --contains 4bcfa0c6` — подтверждено: файл существует только в `artifact/01m1p9qchphscea6tk13pv85sp` (и origin), с коммита ДО коммита разработчика.
- `python3 scripts/codebase_map.py` (регенерация) сравнена с закоммиченной картой построчно без строки `built_at_sha` — расхождений нет, карта актуальна; файл возвращён в исходное состояние (`git checkout -- docs/codebase-map.md`) после сверки.
- Прочитан код `orchestrator/fsm_advance.py::_zones_gate_refuses` и вспомогательные функции (`_split_zone_paths`, `_touches_zone`, `_plan_zones_extension_paths`, `_answer_zones_mandate`) целиком; прослежены сценарии AC-1..AC-6, включая частичный мандат (`test_ac3_mismatched_mandate_path_is_not_silently_substituted`) — логика корректна, отказ называет верный файл даже когда мандат покрывает не все пути раздела «Расширение зон».
- Прочитан `orchestrator/artifact_source.resolve` — подтверждено, что `branch`, передаваемый в `_answer_zones_mandate`/`_plan_zones_extension_paths`, это АРТЕФАКТНАЯ ветка (не код-ветка) — ANSWER-n.md и PLAN.md там и читаются корректно.

## Предложения системе

- Лок `acceptance_tests/` (`in_dev`, orchestrator/fsm_advance.py:621-681) сверяет ТОЛЬКО артефактную ветку с зафиксированным `tests_locked_sha` — не существует проверки, что КОД-ветка (та, что реально мержится) несёт тот же состав `acceptance_tests/`, что и артефактная. Класс дефекта из R1-F1 (код-ветка отстала от финального test_author) в принципе не ловится ни одним существующим гейтом `advance` — стоит рассмотреть отдельную сверку diff_names код-ветки и артефактной ветки по `tasks/<id>/acceptance_tests/` на переходе `in_dev -> review`, тем же приёмом, что уже есть для лока.
