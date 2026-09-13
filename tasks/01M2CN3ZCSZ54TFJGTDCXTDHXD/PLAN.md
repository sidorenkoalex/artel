---
task: 01M2CN3ZCSZ54TFJGTDCXTDHXD
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Рефакторинг R4: runner.py — фазы шага роли внутри модуля

## Подход

Перенос, не улучшение (SPEC «Не входит»; skills/coding-standards.md,
класс «рефакторинг»): тела `run_agent_once` и `_run_developer_step`
переезжают дословно, включая все комментарии, в новые приватные функции
того же модуля `orchestrator/runner.py` — без единого нового модуля
(AC-7), без изменения текста/порядка журнальных записей и печати
(AC-9), без правки логики отказов/ретраев/учёта стоимости.

**`run_agent_once` -> `_prepare_step`/`_spawn_and_wait`/`_account_step`/
`_finish_*`** (AC-1/AC-2/AC-3). Пять исходов SKIPPED физически
распределены по двум подготовительным фазам: `_prepare_step` ловит три
(промпт не записан; окружение роли не создано; рабочий каталог роли не
создан) — всё до открытия файла промпта; `_spawn_and_wait` — оставшиеся
два (промпт не прочитан; claude CLI не найден), поскольку по AC-3
именно `_spawn_and_wait` «открывает файл промпта, вызывает spawn_agent».
Обе фазы возвращают `(skip, ctx)`: `skip` — трёхэлементный кортеж,
который `run_agent_once` обязан вернуть немедленно (`None` при успехе);
`ctx` — данные для следующей фазы. Это не меняет НИ текст, НИ условие
ни одного из пяти исходов — все пять по-прежнему воспроизводятся
дословно теми же строками журнала/консоли, что и до разбора, просто
распределены по двум функциям вместо одной (SPEC допускает читать
формулировку AC-2 как описание итога декомпозиции в целом: AC-3 явно и
детально называет обе фазы, где физически стоят открытие файла и вызов
`spawn_agent`, поэтому именно ей отдан приоритет при разночтении —
неоднозначность не блокирующая, поведение одинаково проверяется тестами
и смоуком). `_account_step` — трение/стоимость/потолок программы, без
изменения вызовов. `_finish_timeout`/`_finish_failed`/
`_finish_missing_artifact`/`_finish_ok` — дословные ветки исходов;
`run_agent_once` их вызывает и возвращает результат без изменений.

**`_run_developer_step` -> `_refuse_before_start`/`_build_prompt`/
`_run_attempts`/`_escalate_after_attempts`** (AC-4/AC-5/AC-6).
`_refuse_before_start` несёт все шесть отказов до старта (пауза,
стоп-кран волны, чужая ветка worktree, pre-flight, инцидент
целостности, скилы роли) с прежними журналами/печатью и возвращает
признак `("exit", message)` | `("return", None)` |
`("continue", (target, skills))` — САМ `sys.exit`/`return` остаётся
текстом в `_run_developer_step` (AC-5, буквально). `_build_prompt`
собирает промпт (бриф/миссия/ревью-пакет/история отказов advance) без
изменений. `_run_attempts` — цикл попыток с бэкоффом; возвращает
`(attempt, reason, failure_class)` — `attempt is None` сигналит
вызывающему коду, что нужен ранний `return` без эскалации (потолок
бюджета либо исход не "failed"), иначе `attempt` — номер последней
попытки в точности как в прежнем теле цикла (AC-6, буквально).
`_escalate_after_attempts` — хвостовое тело эскалации, без изменений.

Никаких переименований/лишних проверок/новых модулей. Имена из AC-7
(`run_agent_once`, `spawn_agent`, `role_env`, `role_cwd`, `role_cmd`,
`cmd_run`, `_cmd_run`, `step_role`, `wave_breaker_alerts_open`) не
тронуты — сигнатуры и место (глобалы `orchestrator/runner.py`) те же.

## Шаги

1. Разбор `run_agent_once` на `_prepare_step`/`_spawn_and_wait`/
   `_account_step`/`_finish_timeout`/`_finish_failed`/
   `_finish_missing_artifact`/`_finish_ok` — один коммит.
2. Разбор `_run_developer_step` на `_refuse_before_start`/
   `_build_prompt`/`_run_attempts`/`_escalate_after_attempts` — один
   коммит.
3. Регенерация `docs/codebase-map.md` (правка `.py` в `orchestrator/`).
4. Прогон тестов, затронутых модулем (полный список — «Влияние на
   систему»), смоук `status`/`log`/`doctor` до/после, `scripts/guard.py`
   на PLAN.md.

Один MR — обе декомпозиции внутри одного файла образуют одно связное
изменение; `git revert -m 1 <merge>` откатывает его целиком.

## Покрытие требований

| Требование SPEC | Шаг |
|---|---|
| 1 (`run_agent_once` -> `_prepare_step`/`_spawn_and_wait`/`_account_step`/`_finish_*`) | 1 |
| 2 (`_run_developer_step` -> `_refuse_before_start`/`_build_prompt`/`_run_attempts`/`_escalate_after_attempts`) | 2 |
| 3 (имена-глобалы AC-7 не сдвинуты) | 1, 2 |
| 4 (поверхности неизменности: вывод, журнал, алерты, схема БД, файлы) | 4 (смоук) |
| 5 (правки tests/ — только импорты/пути патчей) | не потребовались: ни один тест не патчит `run_agent_once`/`_run_developer_step` по внутренней структуре (см. «Влияние на систему») |
| 6 (без попутных улучшений, без новых модулей, циклы импортов не тронуты) | 1, 2 |

## Влияние на систему

Затронут только `orchestrator/runner.py` (плюс регенерация
`docs/codebase-map.md` — только `built_at_sha`, публичный список
функций модуля не изменился: все новые имена приватные, `_`-префикс).
Публичные имена модуля (AC-7) не переименованы и не потеряли
сигнатуру — 101 патч этих имён в 38 тестовых файлах (SPEC «Контекст»)
продолжает резолвиться на те же атрибуты модуля. Ни `_run_developer_step`,
ни `run_agent_once` не патчатся тестами по внутренней структуре (только
как единая точка входа через `cmd_run`/прямой вызов с моками
`spawn_agent`/`role_env`/`role_cwd`/`roles.skills` и т.п.) — поэтому
правки `tests/` не потребовались вовсе (требование 5 выполнено
пустым множеством правок).

Инварианты/гейты/лимиты не тронуты: `zone_lock`/`budget`/
`parallel_limit`/`fixation`/`checkpoint`/`failure_classification`
вызываются в прежнем порядке и с прежними аргументами — просто из
других физических функций одного модуля. Схема БД не тронута (задача
не пишет миграций). Циклы импортов вокруг `runner.py` не изменены (SPEC
«Не входит»).

**Тесты, затронутые модулем** (запущены в шаге; полный набор `tests/`
гоняет CI на пуш ветки): test_agent_log.py, test_agent_prompt.py,
test_agent_failure.py, test_multitarget.py, test_step_cost.py,
test_runner_wave_breaker.py, test_timeout_checkpoint.py,
test_step_refixation.py, test_review_package.py, test_zone_lock.py,
test_step_autocommit.py, test_failure_classification.py,
test_liveness.py, test_lease.py, test_alerts_wave_breaker.py,
test_catalog_wave_breaker_status.py, test_diff_not_collected_alerts.py,
test_advance_refusal_history.py, test_brief.py,
test_checkpoint_external_step_artifacts.py,
test_artifact_materialization.py, test_multitarget_invariants.py,
test_git_fixation.py, test_review_freshness.py, test_doctor.py,
test_doctor_canary_pool.py, test_watch.py, test_report.py, test_retro.py,
test_kill_live_cycle_refusal.py, test_invariants.py,
test_fsm_draft_mr_reentry.py, test_canary.py, test_answer.py,
test_analyst_role.py, test_auto_cycle.py, test_acceptance_tests_flow.py,
sandbox.py — все зелёные, кроме одного пункта ниже.

Один сбой воспроизведён и на `HEAD` ДО правки (`git stash` +
единичный прогон того же теста) — не связан с этой задачей:
`tests/test_liveness.py::TerminateProcessGroupTest::
test_kills_the_leader_and_returns_a_positive_count` падает средой
(сигнал группе процессов песочницы сессии), не логикой
`orchestrator/liveness.py`, который эта задача не трогает.

**Откат.** Оба шага (1, 2) — один семантически связный MR; `git revert
-m 1 <merge>` возвращает `orchestrator/runner.py` к монолитным
`run_agent_once`/`_run_developer_step` одним коммитом.

**Смоук до/после.** Метод T091 (тот же приём, тот же инвариант T056
не даёт прогнать `artel.py status/log/doctor` через `main()` из
worktree): два временных git-worktree внутри рабочего каталога задачи
(`smoke_before` — detached на HEAD до правки, `smoke_after` — HEAD +
скопированный поверх изменённый `orchestrator/runner.py`), в каждом
собрана одинаковая синтетическая `state.db` (`schema.create_schema` +
5 задач в состояниях in_dev/review/escalated/done/killed с записями
журнала), вызваны напрямую `catalog.cmd_status`, `catalog.cmd_log`
(две задачи), `doctor.cli.cmd_doctor()` (без `--fix`/`--restore`).
Результат: вывод идентичен посимвольно, кроме: временных меток и pid
процесса-держателя журнала (реальное время/pid каждого прогона); sha
материализации `tasks/<id>/` (генерируется заново из HEAD каждого
worktree — не зависит от кода); `disk-space` (78500 vs 78498 МБ —
реальное изменение свободного места между прогонами); путей, несущих
имя каталога сравнения `smoke_before`/`smoke_after` (артефакт метода
сверки: `orphans-dirs`, `venv`, `git-identity`). Ни одно расхождение
не связано с содержимым декомпозиции; вспомогательные worktree убраны
(`git worktree remove --force`) до коммита кода.

`scripts/guard.py` прогнан на этом PLAN.md — без нарушений (см. журнал
шага).

## Риски

Разночтение AC-2/AC-3 по тому, какая именно фаза (`_prepare_step` или
`_spawn_and_wait`) физически ловит какие из пяти исходов SKIPPED —
разрешено в пользу более детального AC-3 (см. «Подход»); поведение
(тексты, журнал, тип/значение возврата `run_agent_once`) от выбора
физического распределения между фазами не зависит и подтверждено
тестами AC-8 — риск не эскалационный.

## Предложения системе
