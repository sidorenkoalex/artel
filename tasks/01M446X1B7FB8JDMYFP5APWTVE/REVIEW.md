---
task: 01M446X1B7FB8JDMYFP5APWTVE
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Дозор показывает ход шага роли

## Фаза A — план
- Таблица покрытия полна (треб. 1–9 → шаги 1–3); шаги размера MR.
- Подход (одно распознавание в `OutputPump.catch_event` по общему
  `StreamEvent.tool_results`, запись своим соединением из потока насоса,
  дозор — `_emit_progress` после `_emit_steps`) не конфликтует с
  архитектурой; «Влияние на систему» совпадает с диффом (7 файлов + карта,
  существующие тесты не тронуты — `git diff 598dcf52 -- tests/test_watch.py
  tests/test_agent_log.py` пуст). Откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | реализовано не так | Запись «прогон pytest» есть для Claude и Codex, но итоговая строка с подтестами (`… passed, N subtests passed in …`) не распознаётся — см. R1-F1 |
| 2 | OK | `pytest` в `_EVENT_CLASSES`/`_DEFAULT_EVENTS`, `_matches_class` по `PYTEST_RUN_ACTION`, печать `_print_line` |
| 3 | OK | Отметка k = ⌊прошло/N⌋, `last_mark`, «M/45 мин», 3 вызова ≤ 40, `git status --porcelain`, обрезка до 240 |
| 4 | OK | `_live_step_row`: последняя started vs последняя из finished/TIMEOUT/FAILED по id |
| 5 | OK по букве | «нет коммитов» — `git log --since=@…` по ветке; «стоимость шага» — по названным функциям SPEC, но в живом логе usage нет — см. R1-F2 |
| 6 | OK | actor `watch`, «ход шага»/«предупреждение», не классы `--events`/`--exit-on` |
| 7 | OK | `_LineBudget` — общий deque на задачу, окно 3600 с; невыданное считается выданным |
| 8 | OK | Раздел «Ход шага роли в дозоре» в `docs/operator-session.md` |
| 9 | OK | Долгоживущие файлы задачи + `tests/test_pytest_summary_pump.py` с заявками «Ловит мутацию» |

## Замечания

- major — orchestrator/agent_log.py:227-231 (`_PYTEST_OUTCOMES`/
  `_PYTEST_SUMMARY_RE`) — шаблон итоговой строки не знает счётчиков
  подтестов: `182 passed, 99 subtests passed in 62.97s (0:01:02)` и
  `2 failed, 180 passed, 3 subtests failed, 96 subtests passed in 60.1s`
  дают `[]` (проверено вызовом `agent_log.pytest_summaries`). Именно такую
  строку печатает pytest этого репозитория на прогоне `tests/` с
  `subTest` — мой прогон затронутых модулей закончился ровно ею. Сценарий:
  developer гоняет набор `tests/` (прецедент 04.10 из Контекста SPEC) —
  записи «прогон pytest» нет, дозор молчит, треб. 1 («итоговую строку
  каждого прогона pytest») не выполнено в главном случае. Предложение:
  допустить перед исходом необязательный квалификатор `subtests ` (общее
  правило «<число> [<слово> ]<исход>»), заодно `no tests ran in X.XXs`;
  юнит-кейс с формой подтестов в `tests/test_pytest_summary_pump.py`
  с заявкой «Ловит мутацию: шаблон без `subtests` — строка не
  распознается».
- minor — orchestrator/watch.py:399-407 (`_step_cost_usd`) — живой лог шага
  несёт только рендер (`agent_log.tee_lines` пишет `event.log_text`),
  usage-событий в нём нет, поэтому `partial_tokens_from_log` на настоящем
  шаге даёт `saw=False` и предупреждение «стоимость шага» в работе не
  сработает никогда (тест AC-7 зелен, потому что кладёт в лог сырую строку
  usage). Реализовано буквально по треб. 5, разработчик это честно отметил
  в PLAN «Риски»; дефект — в посылке SPEC, а не в коде. Кроме того, вызов
  без `provider=` разбирает лог Codex-шага парсером Claude. Предложение:
  код не трогать в этой задаче сверх передачи провайдера роли (по
  желанию); отдельное ТЗ на запись usage по ходу шага (см. «Предложения
  системе» PLAN).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/agent_log.py:227-231 | Итоговая строка pytest с подтестами («N passed, M subtests passed in …») не распознаётся | Прогон набора `tests/` с `subTest` не даёт записи «прогон pytest» — треб. 1 не выполнено в основном сценарии | Расширить шаблон квалификатором `subtests` (общим правилом), добавить юнит-кейс с заявкой «Ловит мутацию» |
| R1-F2 | open | orchestrator/watch.py:399-407 | Предупреждение «стоимость шага» читает usage из лога, где его нет (лог — рендер); провайдер для разбора не передан | Предупреждение мертво на настоящих шагах; на Codex разбор чужим парсером | Принять как ограничение SPEC (rejected с обоснованием допустимо) либо передать провайдер роли; отдельное ТЗ на usage по ходу шага |

## Вердикт
changes_requested — исправить R1-F1 (распознавание итоговой строки с
подтестами + юнит-тест). R1-F2 — minor, достаточно разметки
`fixed`/`rejected` с обоснованием.

## Проверено исполнением
- `python3 -m pytest -q -p timeout -o timeout=120
  tests/test_01m446x1b7fb8jdmyfp5apwtve_pytest_journal.py
  tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py
  tests/test_pytest_summary_pump.py tests/test_watch.py
  tests/test_agent_log.py tests/test_store_journal.py tests/test_providers.py
  tests/test_providers_codex.py` — `182 passed, 99 subtests passed in
  62.97s (0:01:02)`.
- `artel.py plank-run 01M446X1B7FB8JDMYFP5APWTVE` — 2 passed, код 0.
- `python3 -c "from orchestrator import agent_log as a; a.pytest_summaries(...)"`
  на формах: «182 passed, 99 subtests passed in 62.97s (0:01:02)» → `[]`;
  «== 2 failed, 180 passed, 3 subtests failed, 96 subtests passed in 60.1s
  ==» → `[]`; «1 failed, 2 passed in 3.00s», «5 passed, 1 warning in
  2.0s», «1 passed, 2 errors in 1.0s» → распознаны; «no tests ran in
  0.01s» → `[]`.
- `git diff 598dcf52 -- tests/test_watch.py tests/test_agent_log.py` —
  пусто (существующие тесты не тронуты).
- Чтение `orchestrator/agent_log.py::tee_lines` и
  `spend.partial_tokens_from_log` — для R1-F2 (в лог пишется только
  `log_text`).

## Предложения системе
- Планка/приёмочные тесты на распознавание вывода внешнего инструмента
  (здесь pytest) стоит строить на выводе, снятом с настоящего прогона
  этого же репозитория, а не на синтетике: синтетические формы AC-1/AC-2
  пропустили строку с подтестами, которую печатает каждый прогон `tests/`.
