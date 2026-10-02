---
task: 01M3SF7DPFGEZ7VYEGGXGTX49E
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Main не краснеет незаметно: guard после снимка, CI main после мержа и в pin-update

## Подход

Одно определение цвета CI main (требование 2) — функция `ci.main_line_status(sha)`
в `orchestrator/ci.py`; три потребителя (`pin-update`, строка `doctor`, гейт
мержа до и после push) зовут её, а не разбирают проверки сами.

**Цвет по проверкам первой родительской линии.** Набор имён проверок берётся с
опорного коммита (`<sha>` для `pin-update`, голова origin/main для `doctor` и
следующего мержа, новая голова main для ожидания после мержа). Обход
`git rev-list --first-parent` от опорного коммита назад; для каждой ещё не
разрешённой проверки первый коммит, где она не `skipped`, даёт её результат:
`status != completed` — идёт, `success`/`neutral` — зелёная, иное — упала (с
этим коммитом). Коммит без проверок вовсе (промежуточные коммиты мержа:
merge/снимок/приложения — CI их не гоняет) пропускается. Итог: есть упавшая —
красный (упавшие с коммитами); иначе есть идущая или у опорного коммита нет
проверок — «идёт»; иначе зелёный. Сбой `gh` на любом коммите — «неизвестен»
(422 на опорном коммите — GitHub его ещё не видит — «идёт»).
Job'ы, которые на push в main не исполняются никогда (`protected-paths`,
`id-format-greplint` в `.github/workflows/ci.yml` — только `pull_request`),
иначе гнали бы обход по всей истории: проверка, пропущенная на коммите, чей
дифф с первым родителем меняет код (тот же `scripts/ci_push_class.is_doc_path`,
что у job `changes`), с обхода снимается — на таком push пропуск не
документный. Документная цепочка поверх кода так не маскируется: на ней
`python` пропущен на документных коммитах, и обход идёт до первого коммита с
кодом. Остановка обхода: все имена разрешены; история кончилась (не
исполнявшаяся проверка в цвет не входит, как и сегодняшний `skipped`); потолок
`MAIN_LINE_MAX_COMMITS` (200) — не разрешённая к нему проверка даёт «неизвестен».

**AC-1, guard после снимка.** `fsm_merge_gate._guard_all_or_refuse` в конце
`_publish_merge_artifacts`, по финальному дереву scratch (после снимка, карты,
RETRO — ровно то, что уходит push'ем и что увидит CI main), до push:
`<python> scripts/guard.py --all` дерева мержа с `cwd=scratch`. Код возврата
≠ 0 — запись «merge FAILED», снятие scratch-дерева тем же
`_drop_scratch_worktree`, `sys.exit` со строками нарушений guard (файлы и
тексты); предупреждения guard (код 0) не останавливают. Только self target и
только если в дереве мержа есть `scripts/guard.py` и `tasks/` (у внешнего
target'а guard пульта к его дереву неприменим; сбой/таймаут запуска guard —
отказ, fail-closed).

**AC-5, красный main отказывает следующему мержу.** `_main_red_or_proceed` в теле
`_cmd_approve_merge_gate` после подтверждения зелёного CI ветки и до
плотницкого merge (под мьютексом, по свежему origin/main): красный —
`sys.exit` «merge отклонён: main красный с <коммит> — сначала починить main»
с упавшими проверками и подсказкой `--fixes-main`; «идёт»/«неизвестен» — запись
журнала и проход (AC-5 требует отказа только на красном). Флаг
`approve <id> [sha] --fixes-main "<основание>"` разбирает `artel.py`
(основание обязательно, тем же приёмом, что `--accept-red`), доводит до
обработчика `merge_gate` через `fsm.cmd_approve(..., fixes_main=)`; при нём
сверка не отказывает, а основание пишется в журнал задачи. Флаг живёт только в
этом вызове — глобального состояния нет.

**AC-4, ожидание CI новой головы main.** `_await_main_ci` в конце тела, после
push/`done`/уборки (задача уже `done` — исход CI не откатывает мерж), под тем же
мьютексом (heartbeat продлевается — следующий мерж не начнётся, пока цвет
неизвестен): опрос `main_line_status(final_sha)` с паузой
`config.VERIFYING_POLL_INTERVAL_SEC` (тот же интервал, что у ожидания
`verifying`) до предела `MAIN_CI_WAIT_LIMIT_SEC = 18 * 60` — новой константы
модуля `orchestrator/fsm_merge_gate.py`, не `MERGE_GATE_CI_WAIT_CEILING_SEC`.
Исход — запись журнала задачи «CI main после мержа» и строка вывода: зелёный;
красный с упавшими проверками; «не дождался» (предел истёк либо `gh` не
ответил — опросить нечем, ждать нечего).

**AC-2/AC-3.** `pin.cmd_pin_update` после проверки канарейки и до `merge
--ff-only`: красный — отказ с упавшими проверками и коммитами; «идёт»/
«неизвестен» — отказ «CI не подтверждён». `cmd_pin_to` не меняется. `doctor` —
новая строка `main-ci` (`orchestrator/doctor/main_ci.py`, после
`pin-unpushed`): fetch origin/main тем же `fetch_origin_main_sha`, затем
`main_line_status`: `ok`/`fail` (коммит падения и имена)/`warn`.

## Шаги

1. `orchestrator/ci.py`: `first_parent_line`, `main_line_status` + текст исхода
   (`MainLineStatus`).
2. `orchestrator/fsm_merge_gate.py`: `_guard_all_or_refuse`, `_main_red_or_proceed`,
   `_await_main_ci`, `MAIN_CI_WAIT_LIMIT_SEC`; проводка `fixes_main` через цикл и
   тело гейта.
3. `orchestrator/fsm.py`, `orchestrator/artel.py`: флаг `--fixes-main`
   (разбор, справка, проводка до обработчика `merge_gate`).
4. `orchestrator/pin.py`: сверка CI в `cmd_pin_update`.
5. `orchestrator/doctor/main_ci.py` + фасад + `all_checks`.
6. Юнит-тесты `tests/test_main_ci_line.py` (свойства, не покрытые
   долгоживущим файлом задачи: остановка обхода на коммите с кодом,
   потолок обхода, красный сильнее идущего, 422 и сбой `gh`, разбор флага,
   сбой запуска guard и отсутствие guard в дереве, ожидание без пауз при
   неизвестном статусе); `tests/test_pin.py::PinUpdateGateAfterFetchTest::
   test_pin_update_succeeds_on_a_sha_not_yet_fetched_locally` — добавлен
   зелёный CI подменой `ci.main_line_status` (новое условие `pin-update`,
   AC-2; ассерты и предмет теста — порядок гейта и `fetch` — не тронуты);
   прогон планки задачи и затронутых модулей; `scripts/codebase_map.py`.

### Итоги прогонов (шаг in_dev, `-p timeout -o timeout=120`)

- `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py` — 20 passed;
  `tasks/01M3SF7DPFGEZ7VYEGGXGTX49E/acceptance_tests/` — в общем прогоне ниже.
- acceptance_tests задачи + `test_pin`, `test_ci_status`,
  `test_ci_status_kind_gate`, `test_cmd_approve_dispatch`,
  `test_approve_acceptance_full_suite`, `test_merge_gate_ci_wait`,
  `test_fsm_merge_gate_done_snapshot` — 123 passed.
- `test_invariants`, `test_plan_appendix`, `test_long_lived_transitions`,
  `test_fsm_map_regen`, `test_fsm_retro`, `test_done_branch_cleanup` —
  134 passed.
- `test_doctor*` (8 файлов), `test_models_doctor`, `test_model_tariffs`,
  `test_01m3pymq6n4scaj9wwttkh6xng_role_models`, `test_git_hooks` — 259 passed.
- `test_multitarget`, `test_git_fixation`, `test_test_integrity_gate`,
  `test_protected_paths_gate`, `test_guard_task_root_subdirectory`,
  `test_fsm_merge_gate_scratch_worktree_cleanup`,
  `test_split_assessment_merge_gate`, `test_snapshot_closing_outcome`,
  `test_merge_lock`, `test_merge_queue`, `test_repo_context`,
  `test_branch_freshness_gate` — 234 passed.
- `test_canary_drive`, `test_auto_cycle`, `test_protected_test_settings`,
  `test_retro_artifact_branch_reads`, `test_pull_conflict_marker_states`,
  `test_task_id_prefix_regression`, `test_fsm_draft_mr_reentry`,
  `test_draft_mr_commits`, `test_long_lived_manifest`,
  `test_artel_role_restricted_commands`, `test_new_argv_parsing`,
  `test_codebase_map` — 195 passed.
- `tests/test_main_ci_line.py` — 10 passed; каждый сторож покраснел на
  своей временной мутации (11 мутаций в `ci.py`/`artel.py`/
  `fsm_merge_gate.py`, код возвращён).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (guard после снимка до push) | 2 |
| 2 (цвет CI main по проверкам первой родительской линии) | 1 |
| 3 (`pin-update` сверяет CI, `pin --to` нет; строка doctor) | 1, 4, 5 |
| 4 (ожидание CI новой головы main, отказ следующего мержа, `--fixes-main`) | 2, 3 |
| 5 (тесты, существующие не ослаблены) | 6 |

## Влияние на систему

- Гейт мержа получает три новые точки: отказ по guard (только ужесточение,
  до push — main не тронут), отказ по красному main (только ужесточение,
  снимается явным флагом Оператора с основанием в журнале), ожидание после
  push (задача уже `done`; мьютекс держится дольше — до 18 минут на мерж,
  heartbeat продлевается). Прежние отказы и порядок шагов не меняются.
- Неизвестный/идущий CI main не блокирует мерж (только журнал) — сознательно:
  AC-5 требует отказа только на красном, а `gh` недоступный — не повод
  останавливать пульт; `pin-update` при этом отказывает (AC-2).
- Существующие тесты гейта мержа с подменой `gh` (`tests/test_invariants.py`
  — один ответ на любой коммит) проходят: сверка main стоит после ожидания CI
  ветки, отказ несёт «merge отклонён» и `name=conclusion`; песочницы без
  `gh`/GitHub-remote получают «gh не ответил» — ожидание после мержа
  заканчивается сразу «не дождался», без реальных пауз. Дерево scratch без
  `scripts/guard.py` (песочницы без копии кода) guard не гоняет.
- `pin-update` теперь требует зелёный CI коммита: единственный существующий
  тест успешного `pin-update` (`tests/test_pin.py::PinUpdateGateAfterFetchTest::
  test_pin_update_succeeds_on_a_sha_not_yet_fetched_locally`) получил
  подмену `ci.main_line_status` зелёным исходом — без неё он отказал бы по
  новому требованию AC-2 (песочница без `gh`). Метод, имя и ассерты прежние;
  это адаптация к новому условию, не ослабление.
- Откат — revert merge-коммита задачи.

## Риски

- Число вызовов `gh` на сверку — по одному на коммит линии до первого
  коммита с кодом; на сегодняшнем main (~25 документных коммитов поверх
  последнего кода) — ~25–30 вызовов (десятки секунд в `doctor`,
  `pin-update`, сверке перед мержем). Ускорение (GraphQL одним запросом) —
  вне задачи.
- Правило «пропуск на коммите с кодом — проверка не исполняется на push»
  опирается на ADR-0016: единственная причина пропуска job на push в main —
  документный класс. Если job начнут пропускать по иному условию на коммитах
  с кодом, он выпадет из цвета (как и сегодня выпадает из цвета головы).
- Сверка перед мержем стоит после ожидания CI ветки: при красном main
  Оператор узнаёт об отказе после зелёного CI ветки (обычно мгновенно — CI
  ветки подтверждён ещё в `verifying`).

## Предложения системе

- Окружение шага роли: `ls` и `rm` из Bash не находятся (`command not
  found`), `ls` в другой форме требует подтверждения — временные файлы
  приходится убирать через `python3 -c "os.remove(...)"`. Класс «инструмент
  шага без базовых утилит PATH» (`.artel/home`, `runner.role_env`).
- `ci.main_line_status` опрашивает `gh` по коммиту за раз; строка `doctor`
  и сверка перед мержем на длинной документной цепочке — десятки вызовов.
  Кандидат в задачу: один GraphQL-запрос на окно линии.
