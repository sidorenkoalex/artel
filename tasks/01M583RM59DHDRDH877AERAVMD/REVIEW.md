---
task: 01M583RM59DHDRDH877AERAVMD
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Канарейка: сигнал остановки в момент запуска процесса ведения задачи не оставляет его живым

## Фаза A — план
- Таблица покрытия PLAN закрывает требования 1–9 одним шагом. Это законно: SPEC сам обосновывает монолит (одно место `_drive_in_clone` + тесты, прогноз 16 КиБ, фактически +61/−1 строк кода и тестов).
- Подход — откладывающий обработчик-функция без `pthread_sigmask` и без `SIG_IGN` — это ровно способ, принятый в SPEC («Способ», ANSWER-1, ответ 1). С архитектурой не конфликтует: `_interrupt_on_signal`, `liveness.terminate_process_group` и уборка клона не тронуты.
- «Влияние на систему» совпадает с diff: `orchestrator/canary.py` (+52), общие помощники `CanaryLifecycleTest` (+9/−1) и регенерированная карта. Путь отката — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `canary.py` `_drive_in_clone`: `deferral.release()` — первая строка защищённого `try`, поэтому `CanaryInterrupted` отложенного SIGTERM/SIGHUP уходит в `except BaseException` → `terminate_process_group` + `proc.wait()`. `signal.raise_signal` вызывает `PyErr_CheckSignals`, поэтому исключение возникает синхронно. Подтверждено тестом раннего окна AC-1 (оба сигнала) |
| 2 | OK | SIGINT входит в `SIGNALS`; прежний `default_int_handler` даёт `KeyboardInterrupt` в той же ветке. Тест AC-2 зелёный |
| 3 | OK | `release()` стоит в ветке `except OSError` до `return 127` и в новой ветке `except BaseException: release(); raise` — сигнал заменяет исключение. Тест AC-4 (OSError и RuntimeError) зелёный, мутация подтверждена (см. ниже) |
| 4 | OK | Участок ставит только `self._defer` (функцию Python), `SIG_IGN` не вводит. Тест AC-3: ведение сообщает `{"SIGTERM": false, "SIGHUP": false}`. Мутация с `SIG_IGN` даёт красный тест |
| 5 | OK | Без сигнала `release()` только восстанавливает обработчики: прежние 127/текст, `RuntimeError` уходит наверх. Вне главного потока обработчики не ставятся. С `Popen` без `pid` код работает (`CanaryCloneMarkerTest` зелёный) |
| 6 | OK | Методы `test_ac1`–`test_ac5` не правлены. Точка сигнала (`os.kill(child.pid, …)` после файла наблюдения), предел 20 с и четыре `assertFalse` прежние |
| 7 | OK | Тесты test_author: сигнал посылает `os.kill` из подменённого `Popen`, группы процессов настоящие, `default_int_handler` в дочернем процессе, уборка `reap_observed` через `addCleanup` (ANSWER-3) |
| 8 | OK | `if handler in (signal.SIG_IGN, None): continue`. Тест AC-11 зелёный |
| 9 | OK | `time.sleep(90)` в `_CHILD` (:36, :44) не тронут. Короткое ведение (`drive="short"`) есть только в `_EARLY_CHILD` нового файла |

Сверка утверждений `tests/` с базой (`git diff 86b63fb5...HEAD -- tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py`): правка только добавляет поле `alive_before_signal` в наблюдение `_CHILD` и два утверждения в `launch_signalled` перед `os.kill` (AC-12). Ни одно утверждение не удалено и не ослаблено. Данные не сужены, утверждения под условие не перенесены. Правка покрыта мандатом ANSWER-2. `tests/test_canary_drive.py` и `tests/test_01m4beg0003ch0qa1gy0pxat03_clone_marker.py` не правились (AC-7). Долгоживущий тест задачи лежит в `tests/` (ADR-0018); разработчик его не повторяет. Файлов вне зоны задачи (ci/, .github/, gates.yaml, skills/, templates/) diff не трогает.

## Замечания
Блокирующих и серьёзных (major) нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved.

Наблюдение на заметку, в реестр не внесено: исход не меняет ни одно требование SPEC. `_SignalDeferral.release()` восстанавливает обработчики циклом SIGTERM → SIGHUP → SIGINT. Живой (не отложенный) SIGTERM может прийти сразу после восстановления обработчика SIGTERM, но до конца цикла. Тогда `CanaryInterrupted` прервёт цикл, и обработчики SIGHUP/SIGINT останутся на `_defer`. `_interrupt_on_signal` потом вернёт только SIGTERM/SIGHUP, и Ctrl-C будет молча проглочен до выхода процесса. Процесс в этот момент уже убирается и выходит с `128+n`, группа ведения снимается (ветка `except BaseException` тот же), поэтому окно гонки — микросекунды, а последствие — только неработающий Ctrl-C во время уборки. Обезвредить можно восстановлением в `try/finally` либо снятием `self.previous` до вызова `signal.signal`. Это вкус, мержу не мешает.

## Проверено исполнением
- `python3 -m pytest -q tests/test_01m583rm59dhdrdh877aeravmd_early_signal.py tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py tests/test_canary_drive.py tests/test_01m4beg0003ch0qa1gy0pxat03_clone_marker.py` — 34 passed, 15 subtests passed (63,7 с).
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M583RM59DHDRDH877AERAVMD` — 5 passed, код выхода pytest 0.
- Временная мутация 1 (заявка AC-3): после установки `_defer` в `_SignalDeferral.__init__` добавлен `signal.signal(SIGTERM, SIG_IGN)`. `pytest … early_signal.py -k ac3` — 1 failed. Код возвращён `git checkout`.
- Временная мутация 2 (заявка AC-4): из ветки `except BaseException` участка `Popen` убран `deferral.release()`. `pytest … early_signal.py -k ac4` — SUBFAILED `mode='raise_runtime'`, вариант OSError прошёл, как и должен (его держит своя ветка). Код возвращён, `git status` чист.
- Свежесть карты: `python3 scripts/codebase_map.py` перегенерировал `docs/codebase-map.md`; вне строки `built_at_sha` diff пуст, карта свежая. Файл возвращён `git checkout`.
- Полный набор `tests/` не гонял (решение Оператора 05.09). CI на ffe7c593 зелёный, 16 проверок.

## Предложения системе
- `scripts/codebase_map.py --help` не печатает справку, а молча перегенерирует карту в рабочей копии. Ревьювер, который хотел узнать флаги, получил грязное дерево. Нужен `argparse` с `--check`/`--help`.
