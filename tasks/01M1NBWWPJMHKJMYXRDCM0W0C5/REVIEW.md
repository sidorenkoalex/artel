---
task: 01M1NBWWPJMHKJMYXRDCM0W0C5
type: review
author_role: reviewer
status: approved
iteration: 2
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

Итерация 2: `git diff ed10a64...HEAD -- tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/PLAN.md
tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/SPEC.md` — пусто, план и спека не
менялись со времени итерации 1; оценка Фазы A выше остаётся в силе без
повторной проверки.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/fsm_autogate.py:45-60` — условие «а» читает `acceptance_tests/*.py` и AC-пометки через `artifact_source.resolve`+`gitcmd.ls_tree_files`/`gitcmd.show`, диск (`acc_tdir`) в этой ветке кода не используется (подтверждено юнит-тестом `DiskAccTdirIgnoredForConditionATest`, `tests/test_fsm_autogate.py:144-176`, который роняет тест, если `guard.scan_acceptance_tests` всё же вызван). |
| 2 | OK | Условия б/в/г/д (`orchestrator/fsm_autogate.py:75-92`) не изменены диффом; источник (ветка+sha) добавляется только к записям условия «а» (`ok`/`reason`), не к б/в/г/д — соответствует формулировке требования 2. |
| 3 | OK | AC-2..AC-5 подтверждены прогоном приёмочных тестов задачи (см. «Проверено исполнением»); формулировки причин «критерии manual — AC-…»/«критерии skip — AC-…» сохранены байт-в-байт (источник дописывается в скобках следом, не меняя ведущую подстроку). |

## Замечания

(нет новых на итерации 2 — см. «Реестр замечаний» по R1-F1.)

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_fsm_autogate.py:108, tests/test_fsm_autogate.py:123, tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/acceptance_tests/test_ac8_existing_suite_stays_green.py:48 | три новых теста без заявки «Ловит мутацию: …» в докстринге | тест-ревьюверу следующей итерации/следующей задачи, трогающей эти тесты, нечем свериться при мутационной проверке (skills/test-authoring.md) | Проверил дифф `git diff ed10a64...HEAD -- tests/test_fsm_autogate.py`: обе заявленные докстринг-заявки на месте и сверены с реальным кодом условия «а» (`orchestrator/fsm_autogate.py:14-59`) — `NonPyFilesIgnoredTest` (tests/test_fsm_autogate.py:108-119) корректно называет мутацию «убрать фильтр `p.endswith(\".py\")`» (строка `py_paths = [p for p in paths if p.endswith(\".py\")]`, fsm_autogate.py:46 — фильтр на месте, тест его действительно ловит); `SourceNoteOnPassTest` (tests/test_fsm_autogate.py:128-140) корректно называет мутацию «пропуск `ok.append(source_note)` на пути успеха» (строка есть, fsm_autogate.py:59) — обе заявки не пересказ имени теста, а конкретный сценарий поломки, обе правдоподобны и подтверждены прогоном (`python3 -m unittest tests.test_fsm_autogate -v` — 5 тестов, ok). Третий файл (`tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/acceptance_tests/test_ac8_existing_suite_stays_green.py:48`) действительно остался без докстринг-заявки — подтверждено (`git diff ed10a64...HEAD -- tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/acceptance_tests/` пуст), но обоснование developer'а выдерживает критику: файл лежит в залоченном `acceptance_tests/` (tasks/T023/SPEC.md требование 5), правка любого байта там — вне полномочий роли `developer` без ссылки на ADR-0012/событие `amend-tests` (review-checklist, раздел «Приёмочные тесты: manual/skip» и «Системная целостность» — правка зафиксированных тестов легальна только с таким основанием, здесь оно отсутствует и developer правильно НЕ стал править без него). Блокировать эту MR дальше по остаточной части находки было бы дедлоком: развернуть fixed/rejected symmetry на неисполнимое для роли требование бессмысленно — severity находки minor, риск (нечем свериться при будущей мутационной проверке именно этого файла) невелик и уже зафиксирован для системного решения в «Предложения системе» (адресовать test_author/Оператору через `amend-tests`, не developer'у). Закрываю запись целиком. |

## Вердикт
approved — итерация 2 закрывает единственную открытую запись реестра
(R1-F1 → `accepted`). Функциональных дефектов не найдено ни в итерации
1, ни в итерации 2: условие «а» корректно переведено на чтение через
артефактную ветку, условия б/в/г/д не тронуты, AC-1..AC-8 зелёные,
полный набор `tests/` зелёный, codebase-map свежая (расхождение только
в `built_at_sha`), протечек за периметр зоны задачи (`ci/`, `.github/`,
`gates.yaml` и т.п.) нет. Инкрементальный diff итерации 2 (сверен
вручную от коммита ed10a64, где REVIEW.md итерации 1 получил
`changes_requested` — исходный sha `00e32aaf2c15059ffb72260275b29b9d2b53e8fe`
в пакете отсутствует в истории репозитория) — только два докстринга в
`tests/test_fsm_autogate.py` плюс автоматическая подтяжка main
(`.gitignore`, `docs/codebase-map.md`), PLAN.md/SPEC.md не менялись.
Рабочее дерево на входе в ревью несло незакоммиченные удаления всего
`tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/` (артефакт автокоммита шага по
флоу A7, SPEC-контекст задачи) — восстановлено `git checkout --
tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/` перед проверкой, содержимого не
переписывал.

## Проверено исполнением
- `git checkout -- tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/` — восстановил незакоммиченно удалённые PLAN.md/SPEC.md/REVIEW.md/TZ.md/acceptance_tests/*.py перед ревью; `git status --short` после — чисто.
- `python3 -m unittest tests.test_fsm_autogate -v` — 5 тестов, все `ok` (включая оба исправленных докстринга).
- `python3 scripts/guard.py tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/PLAN.md tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/SPEC.md` — `GUARD: ок (2 файлов)`.
- `python3 tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/acceptance_tests/test_ac1_reads_via_artifact_source.py` — 2 теста, OK.
- `python3 tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/acceptance_tests/test_ac2_branch_only_planka_passes_autogate.py` — 1 тест, OK.
- `python3 tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/acceptance_tests/test_ac3_manual_criteria_blocks_autogate.py` — 1 тест, OK.
- `python3 tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/acceptance_tests/test_ac4_skip_criteria_blocks_autogate.py` — 1 тест, OK.
- `python3 tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/acceptance_tests/test_ac5_empty_or_missing_planka_blocks_autogate.py` — 2 теста, OK.
- `python3 tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/acceptance_tests/test_ac6_journal_names_artifact_source.py` — 3 теста, OK.
- `python3 tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/acceptance_tests/test_ac7_adr0007_conditions_bvgd_unchanged.py` — 4 теста, OK.
- `python3 tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/acceptance_tests/test_ac8_existing_suite_stays_green.py` — 1 тест (подпроцессом гоняет `tests.test_git_fixation`/`test_gitcmd_branch_reads`/`test_fsm_branch_correct_status_reads`/`test_guard_schema`), OK.
- `python3 -m unittest tests.test_git_fixation.AutogateMergeGateHintIncludesShaTest -v` — 1 тест, `ok` (не задет диффом итерации 2).
- `python3 -m unittest discover -s tests` — `Ran 1357 tests in 155.642s`, `OK`, 0 FAIL/ERROR.
- Сверка `docs/codebase-map.md`: перегенерировал `python3 scripts/codebase_map.py` (запись поверх файла, не в stdout — скрипт пишет напрямую в `docs/codebase-map.md`) и сравнил `git diff` — разошёлся только `built_at_sha`, вернул `git checkout -- docs/codebase-map.md`.
- `git diff ed10a64...HEAD -- tests/test_fsm_autogate.py` и `-- tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/acceptance_tests/` — подтвердили состав правки итерации 2 (см. «Вердикт»).
- Чтением кода подтверждены заявленные мутации в докстрингах: `orchestrator/fsm_autogate.py:46` (`py_paths = [p for p in paths if p.endswith(".py")]`) и `:59` (`ok.append(source_note)`) — обе строки на месте, соответствуют описанным в докстрингах сценариям.

## Предложения системе
- Класс: ревью адресовало minor-находку (докстринг без заявки «Ловит
  мутацию») файлу внутри залоченного `acceptance_tests/` (tasks/T023,
  требование 5) роли `developer`, у которой нет права его редактировать
  (любой байт-диф ловит фиксация T021 и блокирует `in_dev -> review`).
  Итерация 2 закрыла R1-F1 через `accepted` с обоснованием (developer
  корректно не тронул файл, остаточный докстринг-гэп малозначим и вне
  его полномочий), но сам класс — «ревьюверская находка адресована не
  той роли» — стоит закрыть системно, не разово: либо не заводить
  находки на файлы `acceptance_tests/` в адрес `developer` (адресовать
  test_author/Оператору напрямую, через `amend-tests`), либо явно
  проговорить в skills/coding-standards.md или review-checklist, что
  такие находки закрываются `accepted`-с-обоснованием на стороне
  ревьювера, а не ждут физической правки от роли без полномочий.
- Инкрементальный diff ревью-пакета снова оказался несобираемым: sha
  предыдущего вердикта в пакете (`00e32aaf2c15059ffb72260275b29b9d2b53e8fe`)
  отсутствует в истории репозитория вовсе (`git cat-file -t` — «could
  not get object info»), не просто «указывает не туда» (T082/T087 —
  прецеденты того же класса, но там объект хотя бы существовал).
  Пришлось искать вручную коммит, где REVIEW.md итерации 1 получил
  `changes_requested` (`git log --oneline -- .../REVIEW.md`) и
  диффать от него. Третий случай подряд одного и того же класса —
  возможно, стоит чинить сборку пакета так, чтобы sha всегда
  указывал на существующий в репозитории объект, а не только
  документировать обходной путь в review-checklist.
