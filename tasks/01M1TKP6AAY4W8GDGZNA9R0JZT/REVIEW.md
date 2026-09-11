---
task: 01M1TKP6AAY4W8GDGZNA9R0JZT
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: P1a — раннер pytest в пульте: acceptance, dry_run, amend и их тесты

## Соответствие SPEC

Инкрементальный diff «от sha предыдущего вердикта до HEAD» в пакете
пуст (base sha 9397c376 совпадает с HEAD) — сверено вручную (правило
скила «пустой diff — не значит без изменений»): `git log a221645f..
HEAD` (a221645f — коммит, на котором фактически стояла итерация 1,
назван в её «Проверено исполнением») показывает содержательные
изменения только в `orchestrator/stack.py` и `tests/test_stack.py`
(коммиты `967d5189` R1-F1, `14bbdd53` ANSWER-6, `8c867434` ANSWER-7) —
остальные требования (1, 2, 3, 5, 6, 7, 8) с итерации 1 не менялись,
повторно не пересматривались по существу.

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (acceptance.py::run()/run_full_suite() на pytest) | OK | Не менялось с итерации 1; AC-1..AC-3 зелёные в прогоне этой итерации. |
| 2 (amend.py::_run_summary/_RUN_SUMMARY на сводку pytest) | OK | Не менялось; AC-4, AC-5, AC-11 зелёные. |
| 3 (разбор AC-n/redness-маркеров не меняется) | OK | `scripts/guard.py` вне диффа обеих итераций; AC-6 зелёный. |
| 4 (таймаут отдельного теста, `stack.PER_TEST_TIMEOUT_SEC=120`) | OK | AC-7 зелёный; R1-F1 (защита синхронизации с `pyproject.toml`) закрыто — см. реестр. |
| 5 (`.pytest_cache/` не артефакт) | OK | Не менялось; AC-8 зелёный. |
| 6 (`pyproject.toml` с testpaths/python_files/timeout) | OK | AC-9 зелёный; комментарии `stack.py:62-67`/`pyproject.toml` теперь ссылаются на реально существующий тест (R1-F1 закрыт). |
| 7 (существующие `tests/*.py` не переписаны под идиомы pytest) | OK | Не менялось; фикстуры `tests/test_amend.py` не тронуты этой итерацией. |
| 8 (doctor.py явно называет pytest в venv-packages) | OK | Не менялось; AC-12 зелёный. |

Дополнительно (возвраты ANSWER-6/ANSWER-7, не отдельные требования
SPEC, но условие реального прохождения AC-1/AC-3/AC-7/AC-12 пультом):
`stack.pytest_python_executable()`/`_main_copy_root()` теперь находят
venv главной копии из worktree (планка пульта гоняется именно так,
`acceptance.run(tdir, code_root=<worktree>)`), отправная точка поиска
— расположение самого модуля (`_MODULE_ROOT`), не подменяемый тестами
`config.ROOT` — проверено чтением `orchestrator/stack.py:191-263` и
реальным вызовом `stack._main_copy_root()` из текущего worktree
(вернул корень главной копии `/Users/al.sidorenko/projects/artel`,
где `.artel/venv/bin/python3` существует).

## Замечания

(пусто — оба замечания предыдущих итераций закрыты, новых не найдено)

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/stack.py:62-67, pyproject.toml:1-9 | Комментарии утверждали, что `tests/test_stack.py` ловит рассинхронизацию `PER_TEST_TIMEOUT_SEC`/`pyproject.toml[timeout]`, такого теста не было | Будущий дрейф значения тихо не ловился | Подтверждено: `tests/test_stack.py::ManifestConstantsTest::test_per_test_timeout_matches_pyproject_toml` (коммит 967d5189) реально читает `pyproject.toml` через `tomllib` и сравнивает с `stack.PER_TEST_TIMEOUT_SEC`; прогнан в этой итерации — зелёный, комментарии `stack.py:62-67` теперь ссылаются на существующую защиту |

## Вердикт

approved — R1-F1 закрыт настоящим тестом (не косметической правкой
комментария), проверено прогоном в этой итерации. Новых blocker/major
не найдено: правки ANSWER-6/ANSWER-7 (интерпретатор pytest для
worktree) корректны, покрыты `MainCopyRootTest`/
`PytestPythonExecutableWorktreeTest`, воспроизведены реальным вызовом
из текущего окружения. Зона диффа (по коммитам с префиксом
`01M1TKP6AAY4W8GDGZNA9R0JZT:`) — ровно заявленные файлы
(`orchestrator/acceptance.py`, `orchestrator/amend.py`,
`orchestrator/stack.py`, `pyproject.toml`, `tests/test_amend.py`,
`tests/test_stack.py`, `docs/codebase-map.md`), `orchestrator/doctor.py`
не тронут (ожидаемо — требование 8 закрыто через `check_stack()` без
правки самого `doctor.py`, докстринг AC-12 подтверждает это же).

## Проверено исполнением

- `python3 -m unittest tests.test_stack -v` — 14 passed (класс
  `ManifestConstantsTest::test_per_test_timeout_matches_pyproject_toml`
  — R1-F1; `MainCopyRootTest`, `PytestPythonExecutableWorktreeTest` —
  ANSWER-6/ANSWER-7).
- `python3 -m unittest tests.test_stack tests.test_amend
  tests.test_acceptance -v` — 45 passed (регресс затронутых модулей).
- `python3 -m unittest discover -s tasks/01M1TKP6AAY4W8GDGZNA9R0JZT/
  acceptance_tests -v` — 28 passed за 125.8с (вся приёмочная планка
  задачи, AC-1..AC-9, ровно тем способом, каким её гоняет пульт — голым
  `python3` из PATH против worktree).
- `python3 scripts/codebase_map.py --check` — без вывода/без ошибки,
  карта актуальна.
- `python3 scripts/guard.py tasks/01M1TKP6AAY4W8GDGZNA9R0JZT/SPEC.md
  tasks/01M1TKP6AAY4W8GDGZNA9R0JZT/PLAN.md` — «ок (2 файлов)».
- `git log --oneline main..HEAD --grep="^01M1TKP6AAY4W8GDGZNA9R0JZT:"
  --name-only` — сверка зоны диффа по собственным коммитам задачи (не
  подтяжкам main): файлы вне заявленной зоны SPEC не найдены.
- `python3 -c "from orchestrator import stack; print(stack.
  _main_copy_root())"` из текущего worktree — вернул корень главной
  копии репозитория, где реально лежит `.artel/venv/bin/python3`
  (прямая проверка логики ANSWER-6/ANSWER-7 в реальном окружении, не
  только юнит-тестами).
- Полный `tests/` в шаге ревью не прогонялся (решение Оператора 05.09)
  — CI коммита 9397c376 зелёный (14 проверок, дано в пакете), условие
  гейтов verifying/merge выполнено независимо.

## Предложения системе

- Пакет ревью посчитал инкрементальный diff по sha 9397c376, который
  оказался равен HEAD (пустой diff), хотя между вердиктом итерации 1
  (фактически коммит a221645f) и HEAD легло три содержательных коммита
  правки (R1-F1, ANSWER-6, ANSWER-7). Класс уже описан в skills
  review-checklist (T082/T087) — этот случай его подтверждает третий
  раз: механизм выбора «sha предыдущего вердикта» для инкрементального
  diff не находит фактический коммит вердикта, если после него было
  несколько подтяжек main вперемешку с правками. Стоит либо искать sha
  по `git log -- tasks/<id>/REVIEW.md` на стороне сборщика пакета, либо
  явно подсвечивать в пакете расхождение «diff пуст, но HEAD ветки
  продвинулся с N коммитами с последнего вердикта».
