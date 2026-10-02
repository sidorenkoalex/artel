---
task: 01M3Y75C9TY76083CG1PK00EM4
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Проверка CI, зависшая в состоянии «идёт» при известном исходе, не останавливает задачу

## Фаза A — план
- Таблица покрытия полна: требования 1–4 разложены на шаги 1–4. Шаги размером с MR (константа; правило и состояние в `ci.py`; развилка в `ci_rerun.py`; тесты и карта).
- Подход не спорит с архитектурой. Адрес перезапуска берётся из `note` (`stuck_check_ids`) — тот же приём, что `red_status_sha`. Узел перезапуска остаётся общим (`trigger_rerun`). Путь `trigger_rerun` без `run_id` не изменился. Секция «Влияние на систему» совпадает с diff: правки только в `ci.py`, `ci_rerun.py`, `config.py`, новом `tests/test_ci_stuck_check_run.py`, долгоживущем файле задачи и карте. Путь отката — revert.
- Риск «`gh run rerun` по ещё идущему прогону» в PLAN назван и закрыт именованным отказом. Отдельного замечания он не требует: инцидент 02.10 (прогон уже `completed`) покрыт.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `ci.check_finished` (`orchestrator/ci.py`, новая функция) — единственное правило: `status == "completed"` либо заданы оба поля `conclusion` и `completed_at`. Оба читателя зовут его через `_unfinished_checks`, литерала `"completed"` в их телах нет (AC-3, планка зелёная). Строка «<имя>: GitHub отдаёт status=… при conclusion=…, completed_at=… — считаю завершённой» идёт своей строкой после итога (`_with_reread`). Первая строка `note` остаётся итогом, поэтому `verifying_is_red`/`status_kind`/`red_status_sha` не задеты. |
| 2 | OK | `config.CI_STUCK_CHECK_MINUTES = 45`. Возраст берётся от `started_at`, без него — от `created_at` (`_check_age_minutes`); проверяется статус `in_progress`/`queued` и пустой `conclusion`. `note` называет имя, `check-run id` и возраст в минутах. В нём нет «не зелёный:», поэтому `verifying_is_red` ложно и `auto` не останавливается. `fsm_advance.verifying` (строки 308–339) двигает задачу только при `VERIFYING_GREEN`; исход `stuck` ждёт, как прочие, потолок прежний. Других потребителей `verifying_status` проверил grep'ом — `acceptance.py:605` и `fsm_autogate.py:255` сравнивают только с `GREEN`. Исход `stuck` ничего не ломает. |
| 3 | OK | `_cmd_ci_rerun`: при `VERIFYING_STUCK` вызывается `_stuck_rerun`. Id check-run берутся из `note`, затем `actions/jobs/<id>` → `run_id`, затем `trigger_rerun(branch, run_id=…)` (без `--failed`, с тем же `gh run watch`). Отказы по основанию, состоянию и lease стоят до развилки и не тронуты. Красный путь перенесён в `_red_rerun` без изменения проверок; `tests/test_ci_rerun_command.py` зелёный. `from . import fsm` переехал в `_red_rerun`; других обращений к `fsm` в `_cmd_ci_rerun` нет. |
| 4 | OK | Тесты лежат в `tests/test_ci_stuck_check_run.py`, все 10 несут «Ловит мутацию: …» (AC-9 планки зелёный). Заявки наблюдаемы, две проверены временной мутацией (ниже). Долгоживущий файл задачи эти тесты не повторяют: они закрывают другие границы (`conclusion` без `completed_at` и наоборот, статус `waiting`, неразобранные отметки, несколько зависших id, `run_id` задания, отказ при ненайденном прогоне). |

## Замечания
Замечаний уровня blocker/major/minor нет.

Сверка «набор не ослаблен»: в `git diff a43f3de4...HEAD -- tests/` нет ни одной удалённой строки. Изменены только новые файлы (`tests/test_ci_stuck_check_run.py` и долгоживущий файл задачи из перечня лока).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved.

Косметика, не замечание: `orchestrator/ci_rerun.py:130` — `t =store.get_task(...)` без пробела после `=`. На поведение не влияет; можно поправить попутно в следующей правке модуля.

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_ci_stuck_check_run.py tests/test_01m3y75c9ty76083cg1pk00em4_stuck_check.py tasks/01M3Y75C9TY76083CG1PK00EM4/acceptance_tests tests/test_ci_rerun_command.py tests/test_ci_status.py tests/test_ci_status_kind_gate.py tests/test_merge_gate_ci_wait.py tests/test_verifying_ceiling.py tests/test_auto_cycle.py tests/test_watch.py` — 210 passed, 71 subtests passed.
- Временные мутации `orchestrator/ci.py` (с `PYTHONDONTWRITEBYTECODE=1` и `-B`, код возвращён, `git status` чист, повторный прогон — 10 passed):
  - `gh("run", "rerun", run_id)` → с `--failed`: `tests/test_ci_stuck_check_run.py` — 1 failed (`test_given_run_is_rerun_whole_without_sha_lookup`);
  - `if conclusion and completed_at:` → `if conclusion:`: 1 failed (`test_conclusion_without_completed_at_is_still_running`).
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md`: расходится только строка `built_at_sha`, содержимое карты свежее. Изменение откачено `git checkout`.
- `git diff a43f3de4...HEAD -- tests/ | grep '^-'` — удалённых строк нет.
- grep потребителей `verifying_status`/`VERIFYING_*` в `orchestrator/` (`fsm_advance.py:308`, `fsm_autogate.py:255`, `acceptance.py:605`, `ci_rerun.py:121,156`): новый исход `stuck` обрабатывается как «не зелёный», ветвлений, ломающихся на неизвестном исходе, нет.

## Предложения системе
- Песочница ревьювера отклоняет запись в `/tmp` и `find … -exec`. Приём «временная мутация» из review-checklist удобно выполнять одним python-скриптом через heredoc: он сохраняет исходник в памяти, мутирует файл и в `finally` возвращает исходник. Стоит записать этот приём в skills/review-checklist.md рядом с советом про `__pycache__` из PLAN этой задачи.
- Ограничение, на будущее (вне SPEC): «зависшая» проверка в ещё идущем прогоне (`gh run rerun` по прогону in_progress GitHub отклоняет) даст только именованный отказ `ci-rerun`. Если такой случай повторится, нужен путь «cancel + rerun» отдельной задачей.
