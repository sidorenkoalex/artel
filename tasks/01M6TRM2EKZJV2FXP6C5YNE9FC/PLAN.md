---
task: 01M6TRM2EKZJV2FXP6C5YNE9FC
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Мерж не ждёт CI main под замком: цвет main сверяет следующий мерж, идущий CI main он дожидается

## Подход
Ожидание CI `main` переезжает из `_await_main_ci` (после мержа) в сверку
следующего мержа `_refuse_if_main_red` (`orchestrator/fsm_merge_gate.py`).

- `_await_main_ci`: `send_pending()`, одно чтение `ci.main_line_status`
  новой головы, запись «CI main после мержа»: зелёный / красный / «идёт —
  цвет сверит следующий мерж» / неизвестно (текст «не дождался» сохранён —
  его ждёт `tests/test_main_ci_line.py:324,327`). Цикла и паузы нет.
- Новый помощник `_await_running_main_ci`: зовётся из `_refuse_if_main_red`
  только при `ci.MAIN_RUNNING` и после ветки `--fixes-main` (она снимает и
  ожидание). Перед ожиданием — `artifact_branch.send_pending()`, запись
  «ожидание CI main» с sha головы; `start = time.monotonic()` — от начала
  этого ожидания; цикл: предел исчерпан → запись исхода, «merge FAILED»,
  `sys.exit` «CI main <sha> не завершён за 18 мин — повтори approve»;
  иначе пауза `config.VERIFYING_POLL_INTERVAL_SEC`, heartbeat замка,
  чтение. Первый не «идёт» исход (зелёный/красный/неизвестный) — запись
  «ожидание CI main: исход» и возврат в `_refuse_if_main_red`, который
  дальше ведёт себя прежне: красный — прежний отказ, иное — проход с
  записью «сверка CI main».
- Внешние проекты: обе функции по-прежнему выходят по
  `repo_context.is_artel` до чтения цвета.
- Бюджет SPEC не пересматривается.

## Шаги
1. `orchestrator/fsm_merge_gate.py`: `_await_running_main_ci`, вызов из
   `_refuse_if_main_red`, однократное чтение в `_await_main_ci`, докстринги
   и комментарий `MAIN_CI_WAIT_LIMIT_SEC`.
2. `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py` — по мандату ANSWER-1
   переписаны только два метода «Меняемого поведения»:
   `test_ac4_green_after_running_is_reported_green` (два мержа; пп. 1–4
   SPEC + прежние утверждения о голове после второго мержа; состояние
   `gh` переключается в подставной паузе через `patch_sleep(fsm_merge_gate,
   …)`, импорт `patch_sleep` добавлен) и
   `test_ac4_unfinished_ci_is_reported_after_15_to_20_minutes` (второй мерж
   ждёт 15–20 подставных минут, отказ «не завершён», задача на
   `merge_gate`, origin/main не сдвинут).
3. `python3 scripts/codebase_map.py` — карта регенерирована.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 (AC-1, AC-7 — долгоживущий файл задачи) |
| 2 | 1 (AC-2, AC-3, AC-4, AC-6, AC-8, AC-9) |
| 3 | 1 (AC-2; шаг 2 — первый тест) |
| 4 | 1 (AC-5) |
| 5 | 1 (ранний выход по `is_artel` не тронут) |

## Влияние на систему
- Мьютекс мержа больше не держится 18 мин после каждого мержа; держится
  только пока следующий мерж ждёт идущий CI `main` (тот же предел). Сверка
  цвета усилена: идущий CI больше не пропускается без сверки, после
  предела — отказ, а не проход.
- Heartbeat замка в ожидании продлевается каждый опрос (как в прежнем цикле).
- Прочие тесты не менялись. Прогнаны: долгоживущий файл задачи (9/9),
  `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py` (20/20),
  `tests/test_main_ci_line.py`,
  `tests/test_01m5rwnjezt6ya2vp7jk6f3rxs_one_push_per_command.py`,
  `tests/test_01m4s24ebvb72b8wyj3jy96y0e_merge_reference.py`,
  `tests/test_full_suite_reuse.py` — зелёные (58 passed).
- Мутация «идущий CI — проход без ожидания» (`if False and …`) — оба
  переписанных теста красные; код возвращён.
- Откат — revert коммита задачи.

## Риски
- Сценарий «CI main шёл, следующий мерж не пришёл» больше не даёт записи о
  финальном цвете в журнале смерженной задачи — цвет видит `doctor` и
  следующий мерж (принято ADR-0031 п. 6).

## Предложения системе
- `tests/sandbox.MainCiSandbox.fake_sleep` (в `..._main_ci.py`) без хука на
  паузу: сценариям, меняющим состояние CI во время ожидания, приходится
  накладывать второй `patch_sleep` поверх — хук `on_sleep` упростил бы это.
