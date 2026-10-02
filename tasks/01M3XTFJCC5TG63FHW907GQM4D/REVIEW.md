---
task: 01M3XTFJCC5TG63FHW907GQM4D
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Подсказки пульта называют полный порядок запуска цикла после наблюдения фоновых задач

## Фаза A — план
- Таблица покрытия PLAN полна: требования 1–8 SPEC сведены к шагу 1.
- Один шаг на всю задачу — это нормально, так как SPEC обосновывает монолит
  (AC-7/AC-9 проверяют все 13 мест вызова сразу). Объём MR — 10 файлов,
  +174/−31.
- Подход не расходится с архитектурой: SQL лежит в `store.py` рядом с
  `matching_observation`, модуль подсказки только читает БД. Раздел «Влияние
  на систему» совпадает с diff: правки только в зонах SPEC, гейты, схема и
  поведение команд не тронуты, откат — revert коммита.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/cycle_hint.py::launch_hint(conn, task_id, cmd, note="") -> list[str]`. `launch_text` — тонкая склейка над ним для однострочных `print`/`Stop.hint`, сама строку не собирает |
| 2 | OK | Все 13 мест из SPEC переведены: fsm.py ×4, auto.py ×4 (`_stop_command_stop`, `_wait_for_zone` ×2 через `_stop_command_stop` + потолок + потеря lease, `_step_limit_stop`), answer, catalog, budget, ci_rerun, advance_gates/tests_writing. Префиксы «дальше:»/«затем:» и текст до «затем» сохранены, пояснения переданы через `note`. `git grep -nE "artel.py (run\|auto)" -- orchestrator` вне `cycle_hint.py` ничего не находит |
| 3 | OK | `[строка запуска --client … --chat …  note, "сначала:", "1. …", …]` |
| 4 | OK | Случай «а» — один шаг `watch` с «если ещё не идёт». «б» — `observe add` перед `watch`. «в» — `observe register` → `watch` с заполнителями `codex\|claude` и `<ID чата>` |
| 5 | OK | `store.session_observations`: фильтр `target`/`session_id`/`state='active'`, сортировка `task_enabled DESC, last_seen_at DESC, rowid DESC`, поэтому «а» выигрывает у «б», а внутри побеждает самая свежая связь, как в `matching_observation` |
| 6 | OK | Только `SELECT` в `store.py`. В `cycle_hint.py` нет SQL, записи в БД нет (AC-8) |
| 7 | OK | AC-6: строка случая «а» проходит `artel.main` с подменённым `Popen`, запуск записывается в `observed_runs` того же наблюдения. Команды не менялись |
| 8 | OK | `tests/test_cycle_hint.py` на временной БД (`TaskSeededTmpRootTest`) |

Сессия в отсоединённом `auto` — это сценарий риска, поэтому проверил отдельно.
`resolve_session_id(None)` берёт `ARTEL_SESSION_ID` или файл `.artel/session-id`
(`orchestrator/session.py:92-107`). Дочерний процесс наследует и то и другое,
поэтому подсказка в стопе `auto` видит ту же сессию, что и `artel.py`
`_launch_detached` (`artel.py:678`). Ложного случая «в» нет.

Тесты:
- В `tests/test_cycle_hint.py` нет повторов свойств долгоживущего файла
  задачи. Он добавляет приоритет «а» над более свежим «б», случай «удалена
  через `observe remove`» и склейку с префиксом.
- У каждого метода есть докстринг со сценарием и заявкой «Ловит мутацию»,
  причём заявки называют наблюдаемое расхождение в подсказке.
- Существующие тесты в `tests/` не изменены — diff `tests/` состоит только из
  нового файла.

## Замечания
Блокеров и major нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py tests/test_cycle_hint.py`
  — 13 passed, 24 subtests passed.
- Временная мутация `LEFT JOIN` → `JOIN` в `store.session_observations`
  покрасила `test_task_removed_from_observation_suggests_observe_add`.
  Код восстановлен (`git checkout`).
- Временная мутация `ORDER BY task_enabled DESC, o.last_seen_at…` →
  `ORDER BY o.last_seen_at…` покрасила
  `test_enabled_observation_wins_over_fresher_one_without_task`. Код
  восстановлен.
- `python3 -m pytest -q tests/test_answer.py tests/test_step_cost.py tests/test_ci_rerun_command.py tests/test_fsm_spec_gate_reject.py tests/test_auto_cycle.py tests/test_catalog_new_race.py tests/test_detached_cycle.py tests/test_observation_edges.py`
  — 205 passed, 65 subtests passed. Это модули мест вызова и наблюдения.
- `git grep -nE "artel.py (run|auto)" -- 'orchestrator/*.py' 'orchestrator/**/*.py'`
  вне `cycle_hint.py` — пусто. `git grep -nE "(run|auto) \{(id|task_id|tid)\}" -- orchestrator`
  — пусто, в шаблонах `config` голых подсказок тоже нет.
- `python3 scripts/codebase_map.py` + `git diff -U0 -- docs/codebase-map.md`
  — расходится только строка `built_at_sha`, карта свежа. Изменение отменено.
- CI коммита 6cb9b55e зелёный по пакету (14 проверок).

## Предложения системе
- Шаблон REVIEW (реестр при schema_version ≥ 3) и гейт «approved только при
  всех accepted» не оставляют места для minor-заметок при аппруве: любая
  записанная minor открывает запись и блокирует `approved`. Стоит либо
  явно разрешить строки вне реестра для minor, либо ввести статус
  `info` (templates/REVIEW.md, skills/review-checklist.md).
