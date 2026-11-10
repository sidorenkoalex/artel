---
task: 01M70RYD6YXA6DFKCRECSHRKBM
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Команда suite-lock: внешний прогон под замком полных прогонов машины

## Подход
Новый модуль `orchestrator/suite_hold.py` — команда `suite-lock` поверх
готового замка `suite_lock`:

- `reason_text(raw)` — основание записи замка: каждый `\n`/`\r` → один
  пробел, затем первые 200 символов (AC-11; ANSWER-1 п. 5).
- `refusal(argv)` — единый разбор аргументов (`--reason`, `--limit`, `--`,
  команда); текст отказа или `None` (AC-5, AC-10). Основание, пустое после
  `strip()`, — отказ (ANSWER-1 п. 4). Граница предела —
  `config.FULL_SUITE_LOCK_WAIT_SEC − config.FULL_SUITE_TIMEOUT_SEC`,
  читается в момент вызова (`limit_bound`). `cmd_suite_lock` зовёт тот же
  разбор `_parse` до `acquire` и печатает его текст как есть (AC-12), код 2.
- `cmd_suite_lock(argv) -> int`: обработчики `SIGINT`/`SIGTERM` ставятся до
  взятия замка и превращают сигнал в исключение; `suite_lock.acquire(None,
  None, kind="внешний", reason=…)` без ожидания — занят: отказ с
  `suite_lock.describe`, код 1, чужой замок не трогается (`release` сверяет
  pid). Команда — `Popen(start_new_session=True, stdin=DEVNULL)`, вывод
  наследуется; `wait(timeout=limit)`. Предел — остановка группы
  `liveness.terminate_process_group` с паузой по умолчанию `liveness`
  (без своего `grace_sec`, ANSWER-1 п. 1), сообщение с пределом, код 124.
  Сигнал — та же остановка, код `128 + номер`. `OSError` запуска — отказ,
  код 127. Замок снимается в `finally` на любом исходе; на время снятия
  сигналы игнорируются, чтобы сигнал посреди `release` не оборвал его.
- На время остановки группы повторные `SIGINT`/`SIGTERM` игнорируются, а
  команда забирается отдельным потоком (`proc.wait`), чтобы её зомби не
  держал группу до `SIGKILL`.
- Отрицательный код (команда убита сигналом) переводится в `128 + номер`,
  как в оболочке.

`suite_lock`: вид `KIND_EXTERNAL = "внешний"`, параметр `reason` у
`acquire`/`_payload` (поле пишется только у внешнего вида), ветка `describe`
«внешней команды «<основание>» (pid N)». Прежние виды и их записи — без
изменений.

`artel.py`: строка в блоке «Команды:», описание модуля в списке модулей,
запись таблицы `main` (`sys.exit(код)`); в `_ROLE_ALLOWED_COMMANDS` не
добавляется.

## Шаги
1. `suite_lock.py`: вид `внешний`, `reason` в записи, `describe`.
2. `suite_hold.py`: `reason_text`, `refusal`, `cmd_suite_lock`.
3. `artel.py`: справка, таблица команд; регенерация карты
   `python3 scripts/codebase_map.py`.
4. Тесты по ANSWER-1 — новыми файлами задачи (залоченные не тронуты):
   `tests/test_01m70ryd6yxa6dfkcrecshrkbm_suite_lock_answer_process.py`
   (SIGINT, явный `--limit` на границе) и
   `tests/test_01m70ryd6yxa6dfkcrecshrkbm_suite_lock_answer_rules.py`
   (основание из пробельных символов). Прогон долгоживущих файлов задачи,
   `tests/test_suite_lock.py`, `tests/test_01m5m0kqpv0fj9nsmdcq3xb76w_help_registry.py`; guard.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 2, 3 |
| 2 | 2 |
| 3 | 1, 2 |
| 4 | 2 |
| 5 | 2 |
| 6 | 2, 4 |
| 7 | 2, 4 |
| 8 | 3 |
| 9 | 4 |

## REPORT по ANSWER-1

1. Пауза до `SIGKILL`: `suite_hold._stop` зовёт
   `liveness.terminate_process_group(proc.pid)` без `grace_sec` — пауза по
   умолчанию `liveness`. Закрыт долгоживущими AC-4/AC-6
   (`test_ac4_limit_stops_whole_group_releases_lock_code_124`,
   `test_ac6_sigterm_stops_group_releases_lock_code_143`) — зелёные, ~3 с.
2. SIGINT: `suite_hold._SIGNALS = (SIGINT, SIGTERM)`, обработчик
   `_raise_signalled`, код `128 + signum` в `cmd_suite_lock`. Тест
   `..._answer_process.py::test_sigint_stops_group_releases_lock_code_130` —
   зелёный; мутация «перехвачен только `SIGTERM`» — красный (проверено
   временной мутацией).
3. Явный `--limit` на границе: `cmd_suite_lock` разбирает тем же `_parse`,
   что `refusal`; граница — `limit_bound()` из констант в момент вызова.
   Тест `..._answer_process.py::test_explicit_limit_at_bound_runs_command`
   (константы подменены в дочернем процессе, разность ≠ 900) — зелёный;
   мутация «литерал 900 вместо констант» — красный.
4. Пустое основание: `suite_hold._parse` — `not reason.strip()` → отказ.
   Тест `..._answer_rules.py::test_blank_reason_refused_before_lock`
   (`"   "`, `"\n\r"`, смесь; « r » — не отказ) — зелёный; мутация
   «пустым считается только `""`» — красный (3 случая).

Итог прогона: `python3 -m pytest` по шести файлам (четыре файла задачи,
`test_suite_lock.py`, `test_01m5m0kqpv0fj9nsmdcq3xb76w_help_registry.py`) —
59 passed, 11 subtests passed.

## Влияние на систему
Замок машины получает четвёртый вид держателя; читатели замка (гейты через
`wait_acquire`, `suite-run`, `mutation-run`) видят его как любой живой
держатель — ожидают или отказывают, `acceptance.py` не меняется (AC-8).
Запись прежних видов побайтно прежняя (`reason` пишется только у
`внешний`). Команда вне белого списка ролей — отказ роли сохраняется.
Гейты, лимиты и тесты не ослабляются; существующие тесты не правлены.
Откат — revert merge-коммита.

## Риски
- `SIGKILL` процесса `suite-lock` оставляет замок за мёртвым pid и группу
  команды живой — вне задачи (SPEC «Не входит»); следующий `acquire`
  снимает замок.

## Предложения системе
- Причина возврата «API ENOTFOUND» (сеть) засчитывается как сбой шага с
  требованием «правки, закрывающей причину» — у сетевого сбоя такой правки
  в коде задачи нет; `orchestrator/runner.py`/классификация сбоя попытки.
