---
task: 01M3YS928033B1QF89VN2N5KC3
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Нестабильный тест test_missing_cli_is_not_retried в полном наборе

## Подход

### Причина (требование 1, AC-1)

Тест вызывает настоящий CLI `claude` машины прогона, и падает утверждение
`self.assertEqual(self.pauses, [])` (`tests/test_agent_failure.py`, третье
утверждение теста).

Как это происходит:
- `CmdRunFailureTest.setUp` подменяет `runner.time.sleep` на
  `self.pauses.append`. `runner.time` — это общий модуль `time`, поэтому
  подменяется `time.sleep` всего процесса, а не только пауза бэкоффа runner.
- По пути `cmd_run` до `spawn_agent` настоящий CLI вызывается в двух местах,
  и песочница их не подменяла:
  1. предполётная сверка модели:
     `runner._refuse_before_start` → `providers/claude.py::model_verdict` →
     `stack.installed_cli_version` → `stack._probe_tool` →
     `subprocess.run(["claude", "--version"], timeout=10)`. Вызов идёт на
     каждом `cmd_run`;
  2. fingerprint окружения в журнале «agent run started»:
     `runner._prepare_step` → `agent_log.environment_fingerprint` →
     `_tool_version_text(["git"|"claude", "--version"])`. Значение кэшируется
     на процесс, поэтому вызов делает только первый шаг процесса.
  Оба вызова идут сквозь `SpyRun(passthrough_unknown=True)` из
  `tests/sandbox.py` в настоящий `subprocess.run`.
- `subprocess.run(..., timeout=…)` сначала дочитывает вывод, а затем ждёт
  выхода процесса через `Popen._wait(timeout)`. На POSIX это цикл
  `time.sleep(delay)` с `delay` 0.001…0.05. Если CLI закрыл вывод, но ещё не
  вышел, цикл крутится, и каждая его «пауза» попадает в `self.pauses`. Живой
  `claude` (Node) на машине, нагруженной другими сессиями Claude Code, может
  выйти позже, чем закроет stdout. На CI CLI нет (`OSError`), и окна нет.
- Поэтому падает одиночный тест, и только на машине Оператора. Какой тест
  класса упадёт, решает момент гонки. Утверждение `self.pauses == []` есть
  у четырёх тестов класса (`test_missing_cli_is_not_retried`,
  `test_timeout_is_not_retried`, `test_backoff_pauses_grow_between_attempts`,
  `test_successful_run_behaves_as_before`). 02.10 под гонку попал первый.
- Гипотеза аналитика (отказ сверки, после которого шаг заканчивается до
  `spawn_agent`) проверена и тоже воспроизводится. Если `claude` в PATH
  отвечает версией ниже минимума модели (`0.9.0` против `1.0.0` у
  `claude-opus-5`), `cmd_run` бросает `SystemExit` раньше всех утверждений.
  Но тогда падают сразу 42 теста трёх модулей (`test_agent_failure`,
  `test_agent_log`, `test_step_cost`), а не один. Поэтому эта гипотеза
  одиночное падение 02.10 не объясняет. Ответы CLI «отказ (rc=1)»,
  «версия не распознана» и «CLI нет в PATH» дают вердикт `warn`, и тест
  проходит.
- Другие кандидаты из ТЗ проверены и не подтвердились:
  - `config.LOGS` у каждого теста свой (tmp из `TmpRootTest`), утечки
    `*.prompt.txt` нет;
  - имя лога пронумеровано, а не взято со временем
    (`agent_log.new_agent_log` → `<task>-<role>-<N>.log`);
  - `FileNotFoundError` уходит в исход `skipped` без классификации отказа
    (`runner._spawn_and_wait`, `_run_attempts:583`);
  - порядок модулей `test_agent_failure` + `test_agent_log` +
    `test_step_cost` зелёный при настоящем CLI.

### Команда воспроизведения (AC-1)

Подставной `claude` печатает нормальную версию, закрывает вывод и выходит
через секунду:

```sh
d=$(mktemp -d) && printf '#!/bin/sh\necho "2.1.283 (Claude Code)"\nexec >&- 2>&-\nsleep 1\n' > "$d/claude" && chmod +x "$d/claude" && PATH="$d:$PATH" python3 -m pytest "tests/test_agent_failure.py::CmdRunFailureTest::test_missing_cli_is_not_retried" -p no:cacheprovider -p timeout -o timeout=120 -q
```

На коде до исправления команда даёт падение 3 из 3 прогонов:
`AssertionError: Lists differ: [0.001, 0.002, 0.004, 0.008, 0.016, 0.032, …0.05] != []`
на `self.assertEqual(self.pauses, [])`. Ту же причину без ручной установки
воспроизводит регрессионный тест:
`python3 -m pytest tests/test_agent_failure_cli_isolation.py -p no:cacheprovider -p timeout -o timeout=120`.

### Исправление (требование 2)

Обе внешние зависимости подменены в `CmdRunFailureTest.setUp`. ANSWER-1 п.3
разрешает это без эскалации.
- `stack.installed_cli_version` возвращает максимум `min_cli_version` по
  каталогу `models.yaml`. Такая версия заведомо проходит сверку для любой
  модели, а исход больше не зависит от установленного CLI.
- `agent_log.environment_fingerprint` возвращает фиксированную строку.

Ни одно утверждение теста не меняется (требование 3). Код пульта не
затронут (требование 4). Место правки — `setUp` класса, а не
`tests/sandbox.py::TmpRootTest`. Утверждение о паузах есть только у этого
класса: проверено прогоном трёх модулей с «медленным» CLI, после правки
142 passed. Подмена `installed_cli_version` в общей песочнице сломала бы
тесты, которые кормят сверку версией через `subprocess.run`
(`tests/test_runner_model_preflight.py` и др.).

## Шаги

1. `tests/test_agent_failure.py`: в `CmdRunFailureTest.setUp` подменить
   `stack.installed_cli_version` и `agent_log.environment_fingerprint`, с
   комментарием о причине. Добавлен импорт `models`, `stack`.
2. `tests/test_agent_failure_cli_isolation.py` (новый): прогоняет
   `CmdRunFailureTest("test_missing_cli_is_not_retried")` с подставным
   `claude` первым в PATH и со сброшенным кэшем fingerprint.
   - `test_cli_exit_lag_does_not_leak_into_backoff_pauses`: CLI выходит
     позже, чем закрывает вывод. Это и есть причина.
   - `test_outcome_does_not_depend_on_cli_in_path`: подтесты «нет в PATH»,
     «отказ», «версия не распознана», «версия ниже минимума» (AC-2).
3. Регенерирована `docs/codebase-map.md`.

Проверки:
- Временная мутация «убрать подмену `installed_cli_version`»: красные оба
  теста нового файла (паузы и `SystemExit` подтеста «версия ниже минимума»).
- Мутация «убрать подмену `environment_fingerprint`»: красный
  `test_cli_exit_lag_does_not_leak_into_backoff_pauses`.
- Код возвращён. `tests/test_agent_failure.py tests/test_agent_failure_cli_isolation.py tests/test_agent_log.py tests/test_step_cost.py tests/test_sandbox.py`:
  155 passed, 34 subtests passed.
- Целевой тест прошёл с настоящим `claude`, с подставными «старая версия»,
  «отказ», «мусор», «медленный выход» (×3) и без `claude` в PATH.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (причина, утверждение, команда — AC-1) | «Подход»: причина и команда воспроизведения |
| 2 (детерминизм на macOS/Linux, изоляция в setUp — AC-2) | 1 |
| 3 (утверждения не ослаблены — AC-3) | 1: тестовые методы и их утверждения не тронуты, правка только в `setUp` |
| 4 (код пульта не правится) | 1–2: правки только в `tests/` |
| 5 (регрессионный тест с «Ловит мутацию» — AC-4) | 2 |
| AC-5 (`conftest.py`, `tests/test_invariants.py` не тронуты) | 1–2 |

## Влияние на систему

- Затронут только `tests/`. Изменён `setUp` неослабляемого модуля
  `tests/test_agent_failure.py` (ADR-0002, docs/invariants.md). Все пять
  проверок `test_missing_cli_is_not_retried` и утверждения остальных
  методов класса сохранены. Подмена убирает внешний шум и ничего не
  разрешает: отказ CLI в самом тесте по-прежнему приходит из
  `spawn_agent` (`FileNotFoundError`).
- Предполётная сверка модели в этом классе теперь всегда даёт `ok`. Её
  отказы проверяют свои тесты (`tests/test_runner_model_preflight.py`,
  `tests/test_stack.py`), этот класс их никогда не проверял.
- Новый тест создаёт shell-скрипт во временном каталоге и подменяет PATH
  через `mock.patch.dict(os.environ)`. Подмена снимается после прогона.
  Тест рассчитан на POSIX (macOS, Linux), как и пульт.
- Откат — revert коммита задачи.

## Риски

- `test_cli_exit_lag_…` держит подставной CLI живым 1 с после закрытия
  вывода. Тест длится ~0.1 с, потому что `time.sleep` подменён и ожидание
  выхода не спит. Висящий `sleep 1` уходит сам.
- Каталог `models.yaml` с моделью без `min_cli_version` сломал бы `max()` в
  подмене. Сегодня поле есть у всех записей, и каталог его требует
  (`models.py::_catalog_model`).

## Предложения системе

- `tests/test_agent_log.py::CmdRunLoggingTest` и
  `tests/test_step_cost.py::CmdRunCostTest`/`CmdRunPartialCostTest` тоже
  вызывают настоящий `claude --version` в предполётной сверке модели: CLI с
  версией ниже минимума красит 27 их тестов. Подмену CLI в сверке и в
  `environment_fingerprint` стоит вынести в общий помощник песочницы
  (`tests/sandbox.py`), а не повторять её по классам. Отдельная задача.
- Класс «`mock.patch.object(<модуль>.time, "sleep", …)` подменяет
  `time.sleep` всего процесса» ловит чужие ожидания (`Popen._wait`, потоки).
  Для сбора пауз бэкоффа надёжнее отдельная точка в runner
  (`runner._sleep`), но это правка кода пульта, вне зоны этой задачи.
