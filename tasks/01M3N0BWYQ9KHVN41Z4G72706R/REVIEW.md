---
task: 01M3N0BWYQ9KHVN41Z4G72706R
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Приёмочные тесты двух групп — строка группы и проверки долгоживущих файлов (ADR-0020, задача 1)

## Фаза A — план

- Таблица покрытия по-прежнему полна: требования 1–9 разнесены по трём шагам.
- В PLAN добавлен абзац «Итерация 2 (REVIEW R1-F1)». Он совпадает с
  инкрементальным diff `7cc1f8a6..c2b2a328`: добавлен
  `tests/test_amend.py::AmendGroupLineRefusalTest` (+89 строк), переписана
  заявка `AmendGroupLineTest.test_post_rule_plank_is_checked`. В
  `docs/codebase-map.md` изменилась одна строка (регенерация). Код
  `orchestrator/` и `scripts/` не менялся — так и заявлено.
- «Влияние на систему» не поменялось, новых побочных эффектов нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Без изменений с итерации 1. |
| 2 | OK | Отказ `amend-tests` по строке группы теперь сторожит `tests/`: сквозные тесты через `amend.cmd_amend_tests` покрывают оба пути (worktree и `--from-branch`). Каждый путь проверен временной мутацией (см. «Проверено исполнением»). |
| 3 | OK | Без изменений с итерации 1. |
| 4 | OK | Без изменений с итерации 1. |
| 5 | OK | Без изменений с итерации 1. |
| 6 | OK | Без изменений с итерации 1. |
| 7 | OK | Без изменений с итерации 1. |
| 8 | OK | Приложения не менялись; AC-13 планки зелёный. |
| 9 | OK | Оба новых метода несут исполнимые заявки «Ловит мутацию». Переписанная заявка `test_post_rule_plank_is_checked` исполнима. Ассерты существующих тестов не тронуты: diff `tests/` в этой итерации — только добавленный класс и текст одного докстринга. |

## Замечания

Нет. Заявки мутаций я сверил так:
- `AmendGroupLineRefusalTest.test_worktree_edit_without_group_line_is_refused`:
  заявка «`if group_errors:` снят в worktree-пути» проверена мутацией
  `amend.py:349` → `if False:`. Покраснел только этот метод.
- `AmendGroupLineRefusalTest.test_from_branch_edit_without_group_line_is_refused`:
  заявка про путь `--from-branch` проверена мутацией `amend.py:485` →
  `if False:`. Покраснел только этот метод.
- `AmendGroupLineTest.test_post_rule_plank_is_checked`: заявка «лок со
  строкой группы считается планкой до правила» проверена мутацией
  `amend.py:182` → `if locked is None or True:`. Метод покраснел, вместе с
  ним — оба сквозных теста.

Тест ловит только отказ по отсутствующей строке группы. Отказ по
неизвестному значению в сквозных тестах не проверяется, но он идёт тем же
узлом `guard.group_line_errors_from_files`, а этот узел покрыт
`tests/test_guard_test_groups.py`. Это не дефект.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_fsm_advance_tests_writing_test_groups.py:212; orchestrator/amend.py:347, orchestrator/amend.py:483 | Подключение проверки строки группы к обоим путям `amend-tests` не было покрыто тестом в `tests/`; заявка мутации `test_post_rule_plank_is_checked` не исполнялась | После мержа регрессию AC-4 в `amend.py` не поймал бы ни один тест | **Ревьювер, итерация 2:** исправление принято. `tests/test_amend.py::AmendGroupLineRefusalTest` проверяет оба пути сквозь `amend.cmd_amend_tests`: `SystemExit` с «строка группы» и `test_ac.py`, запись журнала «amend-tests отклонён», `tests_locked_sha` не сдвинут. Временные мутации обоих путей и различения лока ловятся заявленными методами, код возвращён. |

## Вердикт

approved. R1-F1 закрыт, новых замечаний нет.

## Проверено исполнением

- `python3 -m pytest -q -p no:cacheprovider tests/test_amend.py tests/test_fsm_advance_tests_writing_test_groups.py`
  на HEAD `c2b2a328`: 44 passed, 2 subtests passed.
- Мутация 1: `orchestrator/amend.py:349` `if group_errors:` → `if False:`
  (worktree-путь). Тот же прогон: 1 failed —
  `AmendGroupLineRefusalTest::test_worktree_edit_without_group_line_is_refused`.
  Код возвращён через `git checkout -- orchestrator/amend.py`.
- Мутация 2: `orchestrator/amend.py:485` `if group_errors:` → `if False:`
  (путь `--from-branch`). 1 failed —
  `AmendGroupLineRefusalTest::test_from_branch_edit_without_group_line_is_refused`.
  Код возвращён.
- Мутация 3: `orchestrator/amend.py:182` различение лока снято
  (`if locked is None or True:`). 3 failed — оба сквозных метода и
  `AmendGroupLineTest::test_post_rule_plank_is_checked`. Код возвращён;
  `git status` показывает только `tasks/01M3N0BWYQ9KHVN41Z4G72706R/`.
- `python3 -m pytest -q -p no:cacheprovider -p timeout -o timeout=120 tasks/01M3N0BWYQ9KHVN41Z4G72706R/acceptance_tests tests/test_guard_test_groups.py tests/test_acceptance_tests_flow.py tests/test_codebase_map.py`:
  164 passed, 80 subtests passed. Сюда входят планка задачи и AC-13
  (`git apply --check` приложений).
- CI коммита `c2b2a328` зелёный (14 проверок, по пакету).

## Предложения системе

- В оболочке шага ревьювера `sed -i` требует подтверждения, которое в шаге
  никто не даст. Временные мутации пришлось вносить через Edit и
  откатывать `git checkout`. Скилу review-checklist (приём «временная
  мутация») стоит назвать этот рецепт явно.
- С итерации 1 остаётся открытым вопрос: признак 9 (закрытый атрибут)
  ложно срабатывает на публичный API namedtuple (`_replace`, `_asdict`,
  `_fields`). Его стоит решить в задаче 2 или 3 внедрения ADR-0020.
