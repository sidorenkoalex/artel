---
task: 01M446X1B7FB8JDMYFP5APWTVE
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Дозор показывает ход шага роли

## Фаза A — план
- Таблица покрытия полна (треб. 1–9 → шаги 1–3), шаги размера MR.
- Итерация 2 в PLAN описана адресно (R1-F1, R1-F2, мутации и прогоны);
  «Влияние на систему» совпадает с инкрементальным диффом
  (`orchestrator/agent_log.py`, `orchestrator/watch.py`,
  `tests/test_pytest_summary_pump.py` + карта). Откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_PYTEST_COUNT` = «<число> [subtests ]<исход>» + «no tests ran»; формы с подтестами распознаются (проверено вызовом), Claude и Codex — долгоживущий `..._pytest_journal.py` зелёный |
| 2 | OK | без изменений с итерации 1 |
| 3 | OK | без изменений с итерации 1 |
| 4 | OK | без изменений с итерации 1 |
| 5 | OK | «стоимость шага» теперь разбирает лог провайдером шага (`watch._step_provider` → `runner._step_provider`, сбой → `None`, разбор по умолчанию); ограничение посылки SPEC (в живом логе рендер, не usage) зафиксировано в PLAN «Риски»/«Предложения системе» |
| 6 | OK | без изменений |
| 7 | OK | без изменений |
| 8 | OK | без изменений |
| 9 | OK | новые кейсы `test_subtests_and_empty_run_forms_are_recognised`, `StepCostProviderTest::test_step_cost_parses_log_with_step_provider` с заявками «Ловит мутацию», заявки подтверждены временной мутацией |

## Замечания

Новых замечаний blocker/major/minor нет. Наблюдение без статуса
замечания: `StepCostProviderTest` подменяет `runner._step_provider`,
поэтому стережёт передачу провайдера в `partial_tokens_from_log`, а не
выбор провайдера по набору задачи — последний держат тесты раннера; для
заявленной мутации этого достаточно.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/agent_log.py:227-235 | Итоговая строка pytest с подтестами не распознавалась | Прогон `tests/` с `subTest` не давал записи «прогон pytest» | Исправлено: квалификатор `subtests` и форма «no tests ran»; `pytest_summaries` на «182 passed, 99 subtests passed in 62.97s (0:01:02)», «== 2 failed, 180 passed, 3 subtests failed, 96 subtests passed in 60.1s ==», «no tests ran in 0.01s» даёт строки без рамки; кейс красный на мутации «без `subtests`» |
| R1-F2 | accepted | orchestrator/watch.py:400-421 | Разбор лога стоимости без провайдера шага; usage в живом логе нет | Codex-лог разбирался парсером Claude; предупреждение мёртвое на настоящих шагах | Провайдер шага передан (с деградацией к умолчанию); часть «usage в живом логе нет» — ограничение посылки SPEC, вынесено в «Предложения системе» PLAN — обоснование принимаю; кейс красный на мутации «вызов без провайдера» |

## Вердикт
approved — R1-F1 и R1-F2 закрыты, новых blocker/major нет.

## Проверено исполнением
- `python3 -c "from orchestrator import agent_log as a; ..."` — формы с
  подтестами, «no tests ran», ANSI, «1 subtests skipped, 2 deselected»
  распознаются; «10 subtests passed» (без «in X.XXs») и
  `print("no tests ran in 1s")` → `[]`.
- `python3 -m pytest -q -p timeout -o timeout=300
  tests/test_pytest_summary_pump.py
  tests/test_01m446x1b7fb8jdmyfp5apwtve_pytest_journal.py
  tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py
  tests/test_watch.py tests/test_agent_log.py` — `89 passed, 7 subtests
  passed in 55.53s`.
- Временная мутация: `_PYTEST_COUNT` без `(?:subtests )?` и
  `partial_tokens_from_log(step.log_path)` без провайдера —
  `tests/test_pytest_summary_pump.py`: `2 failed, 3 passed` (оба новых
  кейса красные); код возвращён `git checkout`, повтор — `5 passed`,
  `git status` чистый.
- `artel.py plank-run 01M446X1B7FB8JDMYFP5APWTVE` — `2 passed`, код 0.
- `python3 scripts/codebase_map.py` — расхождение карты только в строке
  `built_at_sha` (карта свежа), регенерация отменена.
- `git diff 598dcf52 --stat -- tests/test_watch.py tests/test_agent_log.py`
  — пусто (существующие тесты не тронуты).
- CI коммита ffc645da — зелёный (из пакета).

## Предложения системе
- Рабочий процесс «временная мутация» в шаге ревью упирается в запрет
  составных bash-команд с `cp`/`sed` (требуют подтверждения, которого в
  шаге никто не даст); рабочий путь — Edit + `git checkout -- <файл>`.
  Стоит упомянуть его в `skills/review-checklist.md` рядом с приёмом.
