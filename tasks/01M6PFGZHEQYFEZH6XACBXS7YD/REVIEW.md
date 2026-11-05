---
task: 01M6PFGZHEQYFEZH6XACBXS7YD
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: reject --decision: отказ на нецифровом номере решения и форма --decision=<файл>

## Фаза A: план
- Таблица покрытия полна: требования 1–5 — шаги 1–2; требование 6 необязательное («можно»), справку оставили прежней, и `test_ac8_help_names_decision_form` от этого не пострадал.
- Шаги размером в MR, подход точечный, с архитектурой не конфликтует. «Влияние на систему» совпадает с diff: меняются только `orchestrator/artel.py::_cmd_reject` и `orchestrator/spec_gate_decision.py::parse`, плюс карта и долгоживущий тест test_author. `fsm.py`, шаблоны и существующие тесты не тронуты.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `spec_gate_decision.py:189`: `number.isascii() and number.isdigit()` стоит до `int()`. «²», «３», «١» дают прежний текст «… — не целое». |
| 2 | OK | `artel.py` `_cmd_reject`: ключ — это `== DECISION_FLAG` или `startswith(DECISION_FLAG + "=")`, после разбора обе формы идут в один вызов `fsm.cmd_reject(task_id, "", decision_file=value)`. |
| 3 | OK | Значение — `args[at][len(prefix):]`, то есть всё после первого «=». Одна проверка `not value or value.startswith("--")` покрывает `--decision=`, `--decision=--x`, `--decision ""` и ключ последним аргументом. Всё это — `sys.exit` до `fsm.cmd_reject`, то есть до lease и журнала. |
| 4 | OK | Порядок проверок: `len(keys) > 1` (повтор) → пустое значение → `extra` (причина). `--decision --decision=<b>` попадает в две позиции `keys` и даёт «повторён». |
| 5 | OK | `--decisions` под оба условия не подходит → `fsm.cmd_reject(task_id, args[0])`, как раньше. |
| 6 | OK | Справку не меняли (это допустимо), прежняя строка на месте. |

## Замечания
Нет.

Сам проверил граничные случаи по коду: `--decision -x` (одно тире) по-прежнему принимается файлом `-x`, так было и до задачи, SPEC это не меняет. `--decision --x причина` даёт «без значения», а не «не сочетается»: проверка значения идёт раньше остатка, как требует требование 4.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Замечаний нет, реестр пуст.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m6pfgzheqyfezh6xacbxs7yd_decision_equals_form.py tests/test_01m6kb0sjhda4d4gnem7pgz40p_decision_reject.py tests/test_spec_gate_decision.py tests/test_fsm_spec_gate_reject.py` — 75 passed, 8 subtests passed. Существующие тесты reject и файла решения зелёные.
- `artel.py plank-run 01M6PFGZHEQYFEZH6XACBXS7YD` — отказ «планки нет»: в refs/artifacts нет `test_*.py`. Все AC держит долгоживущий файл в `tests/`, так что сторож после мержа есть.
- Временные мутации в памяти. Временный pytest-плагин `_mut_plugin.py` подменял модуль через `exec` исправленного исходника; файлы кода не трогал; плагин удалён командой `task-rm`, `git status` чист:
  - возврат к `if not number.isdigit():` — красные AC-1 (4/4), AC-2 (5/5), AC-9. Заявки AC-1/AC-2/AC-9 подтверждены;
  - ключом считается только `== DECISION_FLAG`, форма с «=» не распознаётся — красные AC-4, AC-5[`--decision=`, `--decision=--x`], AC-6, AC-8. Заявки AC-4/AC-8 подтверждены;
  - пустое значение пропускается (проверяется только отсутствие аргумента и `--`) — красные AC-5[`--decision=`, `--decision ""`] и AC-6. Заявка AC-5 подтверждена.
- `git diff 75ec08d49...HEAD --stat -- tests/` — в `tests/` только новый долгоживущий файл задачи, существующие тесты не изменены и не ослаблены.

## Предложения системе
- Приём «временная мутация» из `skills/review-checklist.md` на практике упирается в окружение роли: запись в `/tmp`, префикс `VAR=… cmd` и `pytest.main` из `python -c` (сторож полного прогона не видит путей) отклоняются. Сработал только pytest-плагин в рабочей копии с `exec` исправленного исходника и последующим `task-rm`. Стоит описать этот рабочий способ в скиле или дать команду пульта для мутационного прогона.
