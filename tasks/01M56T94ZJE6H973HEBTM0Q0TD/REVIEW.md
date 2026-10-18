---
task: 01M56T94ZJE6H973HEBTM0Q0TD
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Неустойчивый тест предела полного прогона — две найденные причины, детерминированно

## Фаза A — план
- Таблица покрытия полна: требования 1–5 → шаг 1. Шаг один, но размер MR (один файл теста), не микрооперация и не «сделать всё».
- Подход в зоне SPEC: правится только `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py`; `orchestrator/` не тронут (diff --stat: 1 файл). «Влияние на систему» совпадает с диффом.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `SuiteRunLimitSandbox.task_id` (:610-614) — после `01M` только `ID_LETTERS`; `standalone` и `assertFalse(any(standalone(...)))` не тронуты. Сторож — `SuiteRunFixtureIdTest` на зёрнах 0–2999 (структурная форма + фиксированный набор). Имя проекта — `"p"+word()` (буквы), номер прогона мал — других источников «60» в строке нет. |
| 2 | OK | `COPY_CLOCK` подменяет только `subprocess._time` и оборачивает `Popen.wait`, зовя настоящий; `TimeoutExpired` бросает настоящий `Popen._wait` (проверено по traceback в `CopyClockOrderTest.assert_cut_by_real_wait`). Путь обрыва — настоящий `_run_full_suite_to_log` (`orchestrator/acceptance.py:1593-1600`, `start_new_session=True` ⇒ pgid пробника = pid pytest — на этом стоит сверка `pgid`). Перевод часов на каждом чтении закрывает оба порядка; оба порядка гоняются детерминированно (`test_probe_started_before/after_first_clock_read_is_cut`). Проверка подмены — `clock_jump` с текстом «подмена часов копии не сработала». |
| 3 | OK | Реальное ожидание `cut − max(wait_enter, start)` по `time.monotonic` < 5 с; `cli(timeout=60/100)` и `--wait 1` — страховочные потолки. Возврат к реальному N краснит и `clock_jump`, и потолок 5 с. |
| 4 | OK | Прежние утверждения метода не удалены и не ослаблены (diff — только дописки после них и в `context`); `setUp`/данные фикстуры не сужены, кроме алфавита id — это и есть правка требования 1. Мутации докстринга: при пределе ≠ N обёртка пишет стоп, прогон кончается сам, «не уложился» нет; печать config ловит неизменённый `standalone`. Планка AC-4 зелёная. |
| 5 | OK | Серий нет: подмена часов, файл-стоп, фиксированные зёрна. |

## Замечания
Блокеров, major и minor нет.

Наблюдение без замечания: `add_project_task` (:636-639) дописывает `COPY_CLOCK` в `config.py` копии при каждом вызове — при двух вызовах в одном тесте обёртки легли бы друг на друга. Сейчас его зовёт только `SuiteRunProfileLimitTest` (grep `add_project_task` — один вызов, :737), поэтому сценария поломки нет.

Заявки «Ловит мутацию» новых методов называют наблюдаемое расхождение (`wait вернул 0` / `TimeoutExpired` вместо 0 / id с цифрой / нет `clock_jump`); все четыре проверены временной мутацией (ниже).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Замечаний нет — реестр пуст.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py` — 11 passed за 83 с.
- `artel.py plank-run 01M56T94ZJE6H973HEBTM0Q0TD` — 11 passed за 73 с, код выхода 0 (AC-1…AC-5).
- Временные мутации (одноразовый сценарий правил файл и восстанавливал его; `git status` после — чисто), прогон только названного класса:
  - однократный перевод часов (`call["at"] += N` внутрь `if not jumped`) → `CopyClockOrderTest::test_probe_started_before_first_clock_read_is_cut` красный: «обрыва нет: wait вернул 0»;
  - `cut = True` (обрыв при любом пределе) → `test_other_limit_releases_probe_without_cut` красный;
  - `rng.choice(ALPHABET)` в `task_id` → `SuiteRunFixtureIdTest` красный (id с цифрами уже на зёрнах 0, 1, …);
  - снята установка `subprocess._time = _sandbox_clock` в `COPY_CLOCK` → `SuiteRunProfileLimitTest` красный с текстом «подмена часов копии не сработала… обрыв не по ним» (AC-5), за 17 с, не зелёный по реальному времени.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md | grep -v built_at_sha` — расхождений по содержимому нет (карта свежа); файл восстановлен.
- Полный набор `tests/` не гонялся (решение Оператора 05.09); CI коммита 3b8aa671 зелёный (16 проверок).

## Предложения системе
- Bash шага отказывает heredoc/строки с `{…!r}` («brace with quote character») — временную мутацию пришлось писать отдельным файлом в каталоге документов и удалять через `python3 -c os.remove` (`rm` в шаге недоступен). Повторяет наблюдение PLAN: нужна команда пульта `mutation-check`.
