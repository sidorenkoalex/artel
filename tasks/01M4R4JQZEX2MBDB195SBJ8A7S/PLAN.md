---
task: 01M4R4JQZEX2MBDB195SBJ8A7S
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Мандат Оператора на правку существующего теста — на гейте SPEC

## Подход
Одна новая ветка `state == "spec_gate"` в `orchestrator/answer.py::_cmd_answer`.
`cmd_answer` для `spec_gate` уже идёт под `lease.run_locked` (`_instruction_text`
возвращает `None` вне `in_dev`/`review`), так что lease (AC-10) достаётся
без изменения входа. Внутри ветки:

1. рубеж окружения роли `runner.in_role_environment()` — до чтения файла,
   тем же текстом `_ROLE_ENV_REFUSAL` (AC-5);
2. новый помощник `_spec_gate_answer_text`: читает файл; строка зон или
   зависимостей, распознанная `mandate.elements` с маркерами
   `_ZONES_MANDATE_MARKER`/`MERGE_AFTER_MANDATE_MARKER` (а значит с любым
   отступом), — именованный отказ со словами reject/escalated раньше формы и
   матрицы (AC-3); нет ни одной строки «Ослабление тестов разрешено:» —
   отказ «решения по SPEC передаются reject» (AC-2); затем тот же
   `_read_checked_answer_file` (`mandate.refusals` + `_matrix_problems`), что
   в `in_dev`, — те же тексты отказов (AC-4);
3. коммит общим `_commit_answer` (ссылка документов + `store.record_fixation`
   — голый approve проходит сверку, AC-1), запись журнала прежним форматом
   «ANSWER создан (мандат на ослабление тестов: …)» без «ждёт approve»,
   подсказка «дальше: approve» о пересчёте sha.

Прочие состояния (`spec_writing`, `spec_audit`, `tests_writing`,
`acceptance`, `verifying`) по-прежнему падают в общий отказ (AC-9); разбор
аргументов `artel.py::_answer_args` не тронут (AC-5, CLI). Рубежи
неослабления читают все ANSWER ссылки документов — правка не нужна (AC-6, AC-7).

Справка `answer` в `orchestrator/artel.py` и пункт в
`docs/operator-session.md`: порядок «аудит → мандат → approve», sha после
мандата или голый approve, мандат на всю жизнь задачи — перечитать после
reject (AC-8).

## Шаги
1. Ветка `spec_gate` и `_spec_gate_answer_text` в `orchestrator/answer.py`,
   справка `orchestrator/artel.py`, `docs/operator-session.md`, регенерация
   `docs/codebase-map.md`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 (`_spec_gate_answer_text`: отказ зон/зависимостей через `mandate.elements`, отказ без мандата тестов) |
| 2 | 1 (`_read_checked_answer_file`, рубеж окружения роли, lease через `cmd_answer`, журнал) |
| 3 | 1 (ANSWER в ссылке документов через `_commit_answer`; рубежи не меняются) |
| 4 | 1 (справка `artel.py`, `docs/operator-session.md`) |
| 5 | покрыто долгоживущими `tests/test_01m4r4jqzex2mbdb195sbj8a7s_*.py` (SPEC требование 5: дублировать не нужно) |

Проверка: `tests/test_01m4r4jqzex2mbdb195sbj8a7s_answer_spec_gate.py` и
`..._spec_gate_mandate_flow.py` — 10 passed, 47 subtests; тесты модуля
`answer` (`tests/test_answer*.py`, `test_01m44ep0…_answer_merge_after.py`,
`test_01m4kaymw…_answer_in_dev_gate.py`, `test_01m44enw…_answer_args_no_answer.py`)
— 78 passed; `plank-run` — 2 passed.

## Влияние на систему
Расширяется канал записи ANSWER: ещё одно состояние (`spec_gate`), только для
мандата тестов, с теми же проверками формы/матрицы, рубежом окружения роли и
lease, что у существующих каналов. Гейты неослабления, `mandate.py`, FSM,
`merge_after` не меняются; `merge_after` на `spec_gate` не трогается (строка
зависимостей отказывается до коммита). Тесты не ослабляются, существующие
методы не правятся. Откат — revert merge-коммита задачи.

## Риски
- Мандат, данный на `spec_gate`, переживает reject и новую редакцию SPEC —
  это требование 3; Оператор предупреждён справкой (перечитать после reject).

## Предложения системе
- `orchestrator/merge_after.py::spec_gate_declared_refusal` по-прежнему
  советует `answer <id>` со строкой «Зависимости мержа:» на `spec_gate`, а
  `answer` теперь отказывает ей именованным отказом — подсказку стоит
  поправить отдельной строкой бэклога (SPEC «Не входит»).
- Полный `suite-run` в шаге отказал: на машине идёт прогон другой задачи
  (01M4R4JDG8RH53ZNWM0XF90CFJ); команда не умеет встать в очередь — шаг
  разработчика вынужден либо ждать вручную, либо сдаваться без полного прогона.
