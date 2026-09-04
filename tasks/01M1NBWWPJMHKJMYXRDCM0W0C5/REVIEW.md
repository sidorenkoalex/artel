---
task: 01M1NBWWPJMHKJMYXRDCM0W0C5
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 3
---

# REVIEW: Автогейт приёмки читает планку через источник артефактов

## Фаза A: гейт плана
PLAN.md покрывает все три требования SPEC таблицей «Покрытие требований»
(1→шаг1, 2→шаг1, 3→шаги1,2). Шаги — размера MR (правка одной функции +
юнит-тесты + прогон), не микрооперации и не «сделать всё». Подход
(перенос условия «а» на `artifact_source.resolve` + `gitcmd.ls_tree_files`/
`gitcmd.show` + `guard.scan_ac_content`) сверен построчно с реальным
кодом прецедента `orchestrator/fsm.py::_tests_writing_ac_state`
(`orchestrator/fsm.py:338-401`) — сигнатуры `artifact_source.resolve`
(`orchestrator/artifact_source.py:24-26`, действительно всегда
`foreign=True`) и `gitcmd.ls_tree_files`/`gitcmd.show`/`branch_head_sha`
(`orchestrator/gitcmd.py:173-246`) совпадают с описанием в PLAN.
Конфликта с конвенциями и архитектурой не найдено — план проверяем,
замечаний к плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/fsm_autogate.py:45-60` — условие «а» читает `acceptance_tests/*.py` и AC-пометки через `artifact_source.resolve`+`gitcmd.ls_tree_files`/`gitcmd.show`, диск (`acc_tdir`) в этой ветке кода не используется (подтверждено юнит-тестом `DiskAccTdirIgnoredForConditionATest`, `tests/test_fsm_autogate.py:144-176`, который роняет тест, если `guard.scan_acceptance_tests` всё же вызван). |
| 2 | OK | Условия б/в/г/д (`orchestrator/fsm_autogate.py:75-92`) не изменены диффом; источник (ветка+sha) добавляется только к записям условия «а» (`ok`/`reason`), не к б/в/г/д — соответствует формулировке требования 2. |
| 3 | OK | AC-2..AC-5 подтверждены прогоном приёмочных тестов задачи (см. «Проверено исполнением»); формулировки причин «критерии manual — AC-…»/«критерии skip — AC-…» сохранены байт-в-байт (источник дописывается в скобках следом, не меняя ведущую подстроку). |

## Замечания

- minor — `tests/test_fsm_autogate.py:108` (`NonPyFilesIgnoredTest.test_directory_with_only_non_py_files_is_treated_as_empty`), `tests/test_fsm_autogate.py:123` (`SourceNoteOnPassTest.test_ok_list_names_branch_and_sha_on_clean_planka`), `tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/acceptance_tests/test_ac8_existing_suite_stays_green.py:48` (`test_ac8_fsm_autogate_and_branch_reading_precedent_tests_pass`) — докстринги этих трёх новых тестов не несут заявки «Ловит мутацию: …» (skills/test-authoring.md, review-checklist п.3): первые два ограничиваются описанием сценария без явной мутации, которую тест обязан ловить (остальные тесты того же файла — `AllPyFilesScannedTest`, `MissingLsTreeAnswerTest`, `DiskAccTdirIgnoredForConditionATest` — заявку несут, расхождение выборочное); третий тест вовсе без докстринга на уровне метода (только модульный докстринг с обоснованием состава `MODULES`, не заявка по конкретному тесту). Сами тесты содержательны и проверяемы (прогнаны, зелёные, сценарии правдоподобны) — предложение: дописать в каждый из трёх докстринг вида «Ловит мутацию: <какая правка кода тест уронит>», не меняя сам тест.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | fixed | tests/test_fsm_autogate.py:108, tests/test_fsm_autogate.py:123, tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/acceptance_tests/test_ac8_existing_suite_stays_green.py:48 | три новых теста без заявки «Ловит мутацию: …» в докстринге | тест-ревьюверу следующей итерации/следующей задачи, трогающей эти тесты, нечем свериться при мутационной проверке (skills/test-authoring.md) | дописал заявку «Ловит мутацию: …» в докстринги `NonPyFilesIgnoredTest.test_directory_with_only_non_py_files_is_treated_as_empty` (tests/test_fsm_autogate.py:108) и `SourceNoteOnPassTest.test_ok_list_names_branch_and_sha_on_clean_planka` (tests/test_fsm_autogate.py:123) — оба зелёные. Третий файл (`tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/acceptance_tests/test_ac8_existing_suite_stays_green.py`) не тронул: он в залоченном `acceptance_tests/` (tasks/T023/SPEC.md, требование 5 — «правка залоченного теста = правка SPEC = только Оператор», фиксация T021 детектирует любой байт-диф и блокирует переход `in_dev -> review` причиной «спор с тестом = эскалация»); правка docstring в нём — вне полномочий роли `developer`, не только логики теста. Оставил файл без изменений — решение по этой части finding'а за ревьювером/Оператором (см. «Предложения системе»). |

## Вердикт
changes_requested — единственное замечание R1-F1 (minor, три докстринга
без заявки «Ловит мутацию»). Функциональных дефектов не найдено:
условие «а» корректно переведено на чтение через артефактную ветку,
условия б/в/г/д не тронуты, AC-1..AC-8 зелёные, полный набор `tests/`
зелёный, codebase-map свежая, протечек за периметр зоны задачи
(`ci/`, `.github/`, `gates.yaml` и т.п.) нет. После дописывания трёх
докстринг-заявок — готово к approve.

## Проверено исполнением
- `python3 scripts/guard.py tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/PLAN.md tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/SPEC.md` — `GUARD: ок (2 файлов)`.
- `python3 -m unittest tests.test_fsm_autogate -v` — 5 тестов, все `ok`.
- `python3 tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/acceptance_tests/test_ac1_reads_via_artifact_source.py` — 2 теста, OK.
- `python3 tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/acceptance_tests/test_ac2_branch_only_planka_passes_autogate.py` — 1 тест, OK.
- `python3 tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/acceptance_tests/test_ac3_manual_criteria_blocks_autogate.py` — 1 тест, OK.
- `python3 tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/acceptance_tests/test_ac4_skip_criteria_blocks_autogate.py` — 1 тест, OK.
- `python3 tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/acceptance_tests/test_ac5_empty_or_missing_planka_blocks_autogate.py` — 2 теста, OK.
- `python3 tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/acceptance_tests/test_ac6_journal_names_artifact_source.py` — 3 теста, OK.
- `python3 tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/acceptance_tests/test_ac7_adr0007_conditions_bvgd_unchanged.py` — 4 теста, OK.
- `python3 tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/acceptance_tests/test_ac8_existing_suite_stays_green.py` — 1 тест (запускает `tests.test_git_fixation`/`test_gitcmd_branch_reads`/`test_fsm_branch_correct_status_reads`/`test_guard_schema` подпроцессом), OK.
- `python3 -m unittest tests.test_git_fixation.AutogateMergeGateHintIncludesShaTest -v` — 1 тест, `ok` (единственный тест `fsm_autogate.py` до этой задачи, мокает `_autogate_conditions` целиком — подтверждено чтением `tests/test_git_fixation.py:1038-1067`, не задет диффом).
- `python3 -m unittest discover -s tests` — `Ran 1357 tests in 202.204s`, `OK`, 0 FAIL/ERROR во всём логе прогона.
- Сверка `docs/codebase-map.md`: перегенерировал `python3 scripts/codebase_map.py` и сравнил с закоммиченной картой через `grep -v '^built_at_sha:'` — содержимое совпадает, разошёлся только `built_at_sha` (не дефект).
- Чтением кода подтверждены сигнатуры и поведение зависимостей: `orchestrator/gitcmd.py::ls_tree_files/show/branch_head_sha` (строки 173-246), `orchestrator/artifact_source.py::resolve` (строки 24-26), `scripts/guard.py::scan_ac_content/scan_acceptance_tests` (строки 191-224), `orchestrator/fsm.py::_tests_writing_ac_state` (строки 338-401) — все совпадают с описанием в PLAN.md.
- Прочитан `docs/adr/0007-gate-policy-autogate.md` (условия а-д, строки 30-36) — состав и порядок условий совпадают с `orchestrator/fsm_autogate.py:45-92`, дифф не меняет б/в/г/д.

## Предложения системе
- Класс: ревью адресует minor-находку (докстринг без заявки «Ловит
  мутацию») файлу внутри залоченного `acceptance_tests/` (tasks/T023,
  требование 5) — роль `developer` не имеет права его редактировать
  (любой байт-диф ловит фиксация T021 и блокирует `in_dev -> review`).
  Итерация 2 не смогла закрыть R1-F1 полностью по этой причине
  (`tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/acceptance_tests/test_ac8_
  existing_suite_stays_green.py:48` остался без докстринг-заявки).
  Стоит либо не адресовывать developer'у находки на файлы
  `acceptance_tests/` (адресовать test_author/Оператору напрямую,
  или через `amend-tests`), либо явно проговорить в
  skills/coding-standards.md, что такие находки — материал для
  `rejected` с пояснением, а не для правки.
