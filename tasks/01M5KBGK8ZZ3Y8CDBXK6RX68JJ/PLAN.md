---
task: 01M5KBGK8ZZ3Y8CDBXK6RX68JJ
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Тест argv гейта полного набора не зависит от имени интерпретатора

## Подход
Правится только `tests/test_suite_run.py` (+ регенерация `docs/codebase-map.md`).
Метод `GateArgvTest::test_gate_call_argv_unchanged` получает одну подмену
`mock.patch.object(acceptance.stack, "pytest_python_executable",
return_value="/fake/venv/bin/python3")` на весь блок: внутри неё и вызов
`acceptance.run_full_suite(self.root)`, и список-литерал ожидания из SPEC;
сравнение — `assertEqual` всего argv. Зависимость от `stack._main_copy_root`
(чей `subprocess.run` перехватывает подмена `acceptance.subprocess.run`)
исчезает: выбор интерпретатора больше не вызывается.

Новый класс `GateArgvInterpreterIndependenceTest` строит во временном каталоге
главный репозиторий с `.artel/venv/bin/python3` и его `git worktree add`
без venv, подменяет `stack._MODULE_ROOT`, `config.VENV_DIR`,
`stack.sys.executable` и прогоняет метод гейта через `unittest.TestResult`.
На прежнем теле метода ожидание получает venv временного главного
репозитория, фактический argv — `/fake/bin/python` (красный), на новом —
зелёный. Git — настоящий, локальный, без сети.

Новый класс `GateArgvInterpreterSourceTest` (требование 3): подмена
`pytest_python_executable` значением-маркером, первый элемент argv
`run_full_suite` равен ему.

Мандат на смену утверждения метода — ANSWER-1 (строка «Ослабление тестов
разрешено: tests/test_suite_run.py::GateArgvTest::test_gate_call_argv_unchanged»).
Бюджет SPEC ($40) не переоценивается.

## Шаги
1. Правка `GateArgvTest::test_gate_call_argv_unchanged`, импорт `stack`,
   два новых класса тестов, регенерация карты; прогон
   `tests/test_suite_run.py`, планки, временные мутации.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 |

## Влияние на систему
Код пульта не меняется (AC-8); прочие методы `tests/test_suite_run.py` не
трогаются. Утверждение метода гейта усиливается: литерал называет каждый
элемент общей части команды, так что правка `_pytest_command` теперь краснит
тест (раньше обе стороны собирала одна функция). Гейт неослабления увидит
изменённое утверждение — покрыто мандатом ANSWER-1. Откат — revert коммита
ветки.

## Риски
- Тест требования 2 подменяет глобальный `sys.executable` (через
  `stack.sys`) на время одного вложенного прогона — значение возвращается
  `mock.patch` по выходе.
- Тест требования 2 зовёт настоящий git (`init`, `commit`, `worktree add`) —
  локально, идентичность передаётся `-c user.name/-c user.email`.

## Предложения системе
