---
task: T086
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 2
---

# REVIEW: verifying — auto-опрос CI и потолок по времени

## Фаза A: гейт плана

PLAN.md покрывает все 7 требований SPEC (таблица покрытия полна, раздел
«Покрытие требований»). Шаги — проверяемые единицы одного MR (константы →
`ci.verifying_is_red` → потолок в `fsm.py` → цикл в `auto.py` → тесты →
прогон), не микрооперации и не «сделать всё». Подход переиспользует
существующие точки входа (`fsm.cmd_advance`, журнал шагов) тем же приёмом,
что уже несёт `_advance_refusal` в этом же файле (`orchestrator/auto.py`) —
не конфликтует с конвенциями. Раздел «Влияние на систему» соответствует
фактическому diff (проверено ниже, построчно). Гейт плана пройден.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `auto._cmd_auto` — `while role is not None or state == "verifying"`, ветка опроса живёт ДО блока `steps`/`AUTO_MAX_STEPS` (orchestrator/auto.py:170-177). Пауза — `config.VERIFYING_POLL_INTERVAL_SEC = 90` (orchestrator/config.py), в диапазоне 60–120с. |
| 2 | OK | Трактовка исходов `ci.verifying_status` не тронута (orchestrator/fsm.py:884-926, только комментарий обновлён). Зелёный → `acceptance`, цикл продолжается тем же вызовом (AC-3 зелёный тест). Завершённый красный → стоп цикла с `AUTO_STOP_VERIFYING_RED` (называет `reject`), состояние остаётся `verifying` (AC-4). NONE/RUNNING — ждут тем же циклом (AC-1). |
| 3 | OK | `fsm._verifying_elapsed_seconds` считает от `t["updated_at"]` (микросекундный формат `store.set_state`, с фолбэком на секундный формат `store.now()` — оба реально используются тестовой песочницей, где `set_state` в обход FSM не трогает `updated_at`). `verifying_attempts` остаётся информационным (инкрементируется, но не участвует в условии эскалации — orchestrator/fsm.py:910-914). `LIMIT_VERIFYING_ATTEMPTS` удалён из кода (grep подтверждает: только докстринги/комментарии/тесты его упоминают). |
| 4 | OK | Эскалация несёт диагностику последнего статуса CI в `detail` (orchestrator/fsm.py:916-921: `f"... — последний статус: {note}"`). |
| 5 | OK | `fsm.cmd_advance`/`_cmd_advance` вне `auto` не изменены — ручной advance по-прежнему один опрос без паузы (AC-8 зелёный с рождения и проходит). |
| 6 | OK | Инвариант 18 не задет: approve/reject на гейтах auto не вызывает; поведение на прочих не-агентских состояниях (`spec_gate`, `acceptance`, `merge_gate`, `escalated`, `done`, `killed`) не меняется — ветка `verifying` в `_cmd_auto` — отдельный дизъюнкт условия цикла, не расширяющий его для прочих состояний (AC-9 проходит). |
| 7 | OK | Опрос читает только `ci.verifying_status` (тот же источник, что раньше) и не дёргает git/`gh` write-подкоманды — AC-10 отдельно проверяет отсутствие git-вызовов и `rerun`/`dispatch` среди argv `gh` за несколько итераций опроса. |

Все 10 AC (AC-1..AC-10) реализованы отдельными приёмочными тестами
(`tasks/T086/acceptance_tests/`) — все проходят (см. «Проверено
исполнением»).

## Замечания

- minor — `orchestrator/store.py:509-510` — докстринг `set_state` утверждает
  «`tasks.updated_at` обратно не парсится нигде в кодовой базе» — с этой
  задачей это стало неверным: `orchestrator/fsm.py::_verifying_elapsed_seconds`
  теперь парсит `updated_at` обратно (`datetime.strptime`) для потолка
  `verifying`. Файл не в зоне diff T086, но diff делает существующее
  утверждение в нём ложным. Предложение: разработчику следующей задачи,
  трогающей `store.py`, поправить формулировку (не блокирует эту задачу —
  сам факт разбора обоих форматов уже корректно задокументирован в
  `_verifying_elapsed_seconds`, риска для корректности это не несёт).

## Вердикт

approved

## Проверено исполнением

- `python3 -m unittest discover -s tests` — 1111 тестов, все зелёные
  (132.6s), включая обновлённые `tests/test_auto_cycle.py`,
  `tests/test_ci_status.py` и новый `tests/test_verifying_ceiling.py`.
- Все 10 приёмочных тестов `tasks/T086/acceptance_tests/test_ac1..ac10*.py`
  запущены по отдельности (`python3 <файл>`) — каждый `OK`.
- `python3 scripts/guard.py --all` — `GUARD: ок (295 файлов)`.
- `git rev-parse HEAD` (39d2e5b) не совпадает с `built_at_sha` в
  `docs/codebase-map.md` (1d11482) — перегенерировал карту
  (`python3 scripts/codebase_map.py`) и сравнил построчно без строки
  `built_at_sha`: содержимое идентично коммиченному (карта свежая по
  содержанию, разошёлся только штамп sha из-за коммита после последней
  регенерации, не влияющего на карту). Рабочее дерево возвращено в исходное
  состояние (`git checkout -- docs/codebase-map.md`), `git status` чист.
- `grep -rn "LIMIT_VERIFYING_ATTEMPTS" --include="*.py" .` — только
  докстринги/комментарии/тесты, ни одного исполняемого использования
  константы не осталось (требование 3, AC-7 подтверждены и статически, и
  прогоном).
- Построчно перечитаны `orchestrator/auto.py`, `orchestrator/fsm.py`
  (ветка `verifying`, `_verifying_elapsed_seconds`), `orchestrator/ci.py`
  (`verifying_is_red`, формат `note` от `verifying_status`),
  `orchestrator/config.py`, `orchestrator/store.py` (`set_state`,
  `insert_task`, форматы `updated_at`) — прослежены сценарии: эскалация
  потолка ВНУТРИ цикла `auto` (после `_advance_verifying_poll` возвращает
  `False` при `state == "escalated"`, цикл естественно завершается через
  `auto_stop_advice`/`config.AUTO_STOP["escalated"]`, без незамеченного
  зависания или пропущенного сообщения Оператору); двойной формат
  `updated_at` (микросекундный от `set_state`, секундный от `insert_task`/
  тестового `set_state` в обход FSM) — оба разбираются `_verifying_elapsed_
  seconds`; уникальность подстроки `"не зелёный:"` среди всех четырёх
  исходов `ci.verifying_status` (не пересекается с NONE/RUNNING текстами).

## Предложения системе

- Опрос `verifying` внутри `auto` теперь может держать лизу задачи и
  блокировать вызов `artel.py auto <id>` до ~90 минут (потолок
  `VERIFYING_CEILING_SEC`), в отличие от прежних быстрых шагов цикла —
  если `auto` где-то запускается обёрткой с более коротким внешним
  таймаутом (cron, CI-раннер), вызов прервётся раньше эскалации без
  диагностики. Не находка этой задачи (SPEC явно требует именно такое
  владение опросом), но стоит проверить перед раскаткой, нет ли такой
  внешней обёртки с коротким таймаутом.
