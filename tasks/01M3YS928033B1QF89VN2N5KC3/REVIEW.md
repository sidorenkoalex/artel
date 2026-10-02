---
task: 01M3YS928033B1QF89VN2N5KC3
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Нестабильный тест test_missing_cli_is_not_retried в полном наборе

## Фаза A: план

- Таблица покрытия в PLAN полна: требования 1–5 и AC-5 привязаны к
  разделу «Подход» и шагам 1–2.
- Шаги проверяемые и по размеру подходят для MR: правка `setUp` и новый
  файл регрессии.
- Подход не расходится с ANSWER-1 п.3: изоляция сделана в `setUp` класса
  `CmdRunFailureTest`. Отказ от `TmpRootTest` обоснован: подмена в общей
  песочнице сломала бы тесты, которые подают версию CLI через
  `subprocess.run`.
- Гипотеза аналитика проверена первой, как требует ANSWER-1 п.1. PLAN
  объясняет, почему она не подходит к одиночному падению (при старой
  версии CLI падают сразу 42 теста), а установленная причина подходит.
  Кандидаты из ТЗ разобраны по отдельности.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 / AC-1 | OK | Причина: настоящий `claude --version` в сверке модели и в fingerprint; паузы `Popen._wait` попадают в подменённый глобально `time.sleep`. Падающее утверждение: `assertEqual(self.pauses, [])`. Команда воспроизведения есть. Падение на базовом коде воспроизвёл сам: в выводе `Lists differ: [0.001, 0.002, …] != []`, строка 309 `self.assertEqual(self.pauses, [])`. |
| 2 / AC-2 | OK | Обе внешние зависимости подменены в `setUp`. Подтесты «нет в PATH», «отказ», «не распознана», «ниже минимума» и «медленный выход» зелёные. Других реальных подпроцессов в классе нет, кроме `git check-ignore` (`gitcmd.py:253`). Он вызывается без `timeout`, поэтому `wait` блокирующий и цикла `time.sleep` нет. |
| 3 / AC-3 | OK | Тестовые методы и утверждения не тронуты, дифф `tests/test_agent_failure.py` касается только импорта и `setUp`. Сигнатура подмены совпадает с `stack.installed_cli_version(tool=None)` (`stack.py:405`). |
| 4 | OK | Код пульта не менялся: `git diff c1bae0f6 HEAD -- orchestrator/` пуст. |
| 5 / AC-4 | OK | Новый файл `tests/test_agent_failure_cli_isolation.py`, у обоих методов есть «Ловит мутацию: …». На базовой версии `test_agent_failure.py` он красный, на текущей зелёный. Заявки мутаций проверены временными мутациями (см. ниже). |
| AC-5 | OK | `**/conftest.py` и `tests/test_invariants.py` не изменены, дифф пуст. |

## Замечания

Blocker и major нет.

- minor — tests/test_agent_failure_cli_isolation.py:34 — подставной
  `SLOW_EXIT` оставляет после теста висящий `sleep 1`. Процесс короткий и
  уходит сам, на результат он не влияет. Вердикт не меняет, это вкус,
  поэтому в реестр не заносится.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: blocker и major не найдены.

## Вердикт

approved.

## Проверено исполнением

- `python3 -m pytest tests/test_agent_failure.py tests/test_agent_failure_cli_isolation.py -p no:cacheprovider -q`:
  24 passed, 4 subtests passed.
- Воспроизведение на коде до исправления
  (`git checkout c1bae0f6 -- tests/test_agent_failure.py`, затем прогон
  `tests/test_agent_failure_cli_isolation.py`, затем
  `git checkout HEAD -- tests/test_agent_failure.py`). Красные
  `test_cli_exit_lag_…`: `Lists differ: [0.001, 0.002, …0.05] != []` на
  `self.assertEqual(self.pauses, [])` (строка 309), 2688 лишних пауз.
  Красный и подтест «версия ниже минимума»: `SystemExit … claude-opus-5
  требует claude ≥ 1.0.0, установлен 0.9.0`. AC-1 и красное состояние
  до исправления (AC-4) подтверждены.
- Временная мутация «не стартовать `fp_patcher`»: красный
  `test_cli_exit_lag_does_not_leak_into_backoff_pauses`, заявка
  подтверждена. Код возвращён.
- Временная мутация «не стартовать `cli_patcher`»: красные
  `test_cli_exit_lag_…` и подтест «версия ниже минимума», обе заявки
  подтверждены. Код возвращён, `git status` чистый.
- Инструментированный прогон `CmdRunFailureTest` с подменой
  `subprocess.Popen.__init__`: 16 тестов OK. Единственный реальный
  подпроцесс — `git check-ignore` без `timeout`, второго источника пауз
  нет.
- `python3 scripts/codebase_map.py`: карта отличается только строкой
  `built_at_sha`, то есть свежая. Файл возвращён.

## Предложения системе

- Подмена `mock.patch.object(<модуль>.time, "sleep", …)` подменяет
  `time.sleep` всего процесса и ловит чужие ожидания (`Popen._wait`).
  Предложение разработчика (отдельная точка `runner._sleep` и общий
  помощник песочницы, который подменяет CLI в сверке модели) стоит
  завести задачей: `CmdRunLoggingTest` и `CmdRunCostTest` по-прежнему
  ходят в настоящий `claude --version`.
