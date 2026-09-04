---
task: 01M1HNNHDMP2C1AJTH5QF1BTN2
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

Вопрос 1 — вариант по умолчанию. Вопрос 2 — вариант по умолчанию.

Лок приёмочных тестов снимается Оператором на ОДИН файл
`tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/acceptance_tests/_sandbox.py` и
только на две правки (ADR-0012, канал ANSWER); правку делает
developer, не test_author (перезапуск test_author из in_dev в FSM
не предусмотрен, прецедент — задача 01M1K7KP0D8ZKRM9KTE75DCCYR,
ANSWER-2):

1. `AmendSandbox.setUp()`/`enter_in_dev()`: перед первой записью в
   `self.tdir` — `workspace.ensure(self.TASK, self.row()["branch"])`
   (или эквивалент, синхронный с
   `tests/test_acceptance_tests_flow.py::LockTest`) и
   `self.tdir.mkdir(parents=True, exist_ok=True)`; после A7 `cmd_new`
   worktree не заводит.
2. `BASELINE_COMMANDS` дополняется `"pin-update"` — снимок диспетчера
   приводится к состоянию main на момент прогона; правило «ровно одна
   новая команда» не меняется.

Ограничители (ADR-0012), все обязательны:

- содержание и утверждения всех AC-1..AC-13 не меняются и не
  ослабляются; другие файлы `acceptance_tests/` не трогать;
- обязательный прогон до итоговой строки: планка задачи (14 тестов
  `AmendSandbox` плюс остальные) и полный `tests/`; обе строки
  «Ran N … OK» — в PLAN, раздел «Влияние на систему», и в
  «Проверено исполнением» следующей итерации ревью по требованию
  ревьювера;
- правка фикстуры — отдельный коммит с сообщением, называющим этот
  ANSWER-2 основанием; ревьювер сверяет объём с этим ответом и
  признаёт канал (skills/review-checklist.md, ADR-0012);
- замечания ревью R1-F1/R1-F2 закрываются в реестре REVIEW.md
  штатно, по леджеру.

После правки PLAN.md переводится в `ready`, шаг сдаётся штатно.
