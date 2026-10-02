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
иначе гнали бы обход по всей истории: проверка, пропущенная на голове push'а
класса «код», с обхода снимается — на таком push пропуск не документный. Класс
push'а считается как у job `changes` (`scripts/ci_push_class.is_doc_path`) по
диапазону `before..after`: от следующей глубже по линии головы с проверками до
этой головы (`ci._push_touches_code(base, head)`), а не по диффу головы с
первым родителем — голова push'а гейта мержа (RETRO) документная, код лежит в
merge-коммите под ней без проверок (R1-F1). Документная цепочка поверх кода так
не маскируется: на ней `python` пропущен, и обход идёт до головы push'а с
кодом. Остановка обхода: все имена разрешены; история кончилась (не
исполнявшаяся проверка в цвет не входит, как и сегодняшний `skipped`); потолок
`MAIN_LINE_MAX_COMMITS` (200) — не разрешённая к нему проверка даёт «неизвестен».

**AC-1, guard после снимка.** `fsm_merge_gate._guard_all_or_refuse` в
`_publish_merge_artifacts`, по дереву scratch после снимка и карты, но ДО
генерации RETRO задачи (guard не сканирует планку задачи с
`docs/retro/<id>.md` на посторонние файлы — собственный RETRO скрыл бы
нарушение её снимка; см. «Возврат по приёмке» ниже), до push:
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

### Подтяжка main (возврат по конфликту, ANSWER-1)

- `git merge main` → коммит `fb5b572e`. `orchestrator/artel.py`: справка
  «Команды:» взята из main целиком, в строку `approve` добавлен
  `[--fixes-main "<основание>"]` после `[--accept-red "<основание>"]`;
  остальной код обеих сторон без изменений (auto-merge `fsm.py` чистый).
  `docs/codebase-map.md` взят из main и перегенерирован
  `python3 scripts/codebase_map.py`. Других правок нет.
- Прогон после подтяжки: `test_pin`, `test_artel_role_restricted_commands`,
  `test_new_argv_parsing`, `test_cmd_approve_dispatch`,
  `test_merge_gate_ci_wait`, `test_codebase_map`, `test_ci_status`,
  `test_doctor`, `test_invariants`, `test_fsm_merge_gate_done_snapshot` —
  363 passed.
- Планка задачи (`tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`,
  `acceptance_tests/`) и `tests/test_main_ci_line.py::FixesMainArgTest` в
  шаге роли — 19 failed, все одной причиной: пришедший из main отказ
  команд процессу роли (`artel.py`, SPEC 01M3XTF5506GF43HD51ECE230T) —
  «artel.py approve|pin-update: команда недоступна процессу роли
  developer», потому что окружение шага несёт `ARTEL_ROLE`. До подтяжки
  те же тесты были зелёными (итоги выше); у CI и прогона планки пультом
  `ARTEL_ROLE` нет. Снять маркер в шаге роли нельзя (команда требует
  подтверждения), правка тестов вне ANSWER-1 — поэтому не правились.

### Возврат по приёмке (отказ advance: AC-1, зёрна 808019665/2803227082)

- Причина: оба зерна выбирают вариант «посторонний файл планки»
  (`acceptance_tests/fixture.json`). `guard.scan_extraneous_acceptance_files`
  пропускает задачи, у которых есть `docs/retro/<id>.md`, а guard по дереву
  мержа звался ПОСЛЕ `_generate_and_commit_retro` — RETRO самой задачи
  маскировал нарушение, мерж проходил. Варианты README/QUESTIONS.md
  (`check_content`) от RETRO не зависят — поэтому тест краснел лишь на
  трети зёрен и в прошлом шаге проходил.
- Правка: `orchestrator/fsm_merge_gate.py::_publish_merge_artifacts` —
  `_guard_all_or_refuse` перенесён между картой и RETRO; докстринги
  обновлены. Правило guard не менялось.
- Сторож: `tests/test_main_ci_line.py::GuardAllLaunchTest::
  test_task_retro_does_not_hide_snapshot_violation` — покраснел на
  временной мутации (guard обратно после RETRO), код возвращён.
- Прогоны: зерно 808019665 воспроизведено красным до правки и зелёное после
  (2803227082 — зелёное); долгоживущий файл задачи + `acceptance_tests/` +
  `test_main_ci_line`, `test_fsm_map_regen`, `test_fsm_retro`,
  `test_fsm_merge_gate_scratch_worktree_cleanup`,
  `test_fsm_merge_gate_done_snapshot`, `test_guard_task_root_subdirectory`,
  `test_invariants` — 135 passed. CLI-сценарии в шаге роли гонялись с
  подменой `runner.in_role_environment` в процессе pytest (маркер роли
  иначе отказывает `approve`/`pin-update`, см. «Предложения системе»);
  окружение и тесты не правились. Карта перегенерирована.

### Возврат по ревью, итерация 1 (R1-F1, R1-F2)

- R1-F1 (`orchestrator/ci.py`): `_commit_touches_code(sha)` (дифф с первым
  родителем) заменён на `_push_touches_code(base, head)` — дифф от следующей
  глубже по линии головы с проверками, как `before..after` у job `changes`.
  В `main_line_status` пропущенные на голове проверки откладываются
  (`skipped_at`) и снимаются с обхода, когда найдена следующая голова с
  проверками и диапазон до неё меняет код. Коммиты без проверок
  пропускаются до этой сверки.
- Тест на топологию гейта:
  `tests/test_main_ci_line.py::MainLineStatusTest::test_check_skipped_on_code_commit_stops_the_walk`
  (метод добавлен этой задачей, в main его нет) переписан под реальную
  линию. Это 70 мержей вида RETRO (`python`/`guard` исполнены,
  `protected-paths` пропущен) → снимок → merge с кодом без проверок, сверху
  документная заметка. Ожидается `green`, опрошено 5 коммитов. Добавлен
  `test_doc_push_keeps_check_pending_to_the_code_push`: документный push
  поверх красного мержа не снимает пропущенный `python`. `FakeLine` отвечает
  на `diff base head` по диапазону линии.
- Мутации (временные, код возвращён):
  - дифф с первым родителем вместо диапазона → тест топологии красный,
    исход `unknown` вместо `green` — воспроизводит R1-F1;
  - снятие пропущенных без сверки класса push'а → красные оба новых теста,
    `test_check_unresolved_within_the_cap_is_not_confirmed` и
    `test_failure_outranks_running_check`.
- R1-F2: `fixes_main` передаётся явно в `fsm._approve_merge_gate` →
  `_cmd_approve_merge_gate_cycle` → `_cmd_approve_merge_gate`. Две подмены
  тела `fake_body` в `tests/test_merge_gate_ci_wait.py` получили параметр
  `fixes_main=None`. Ассерты, имена и сценарии не тронуты.
- Прогоны: долгоживущий файл задачи + `acceptance_tests/` +
  `test_main_ci_line`, `test_merge_gate_ci_wait`, `test_cmd_approve_dispatch`,
  `test_pin`, `test_ci_status`, `test_invariants`, `test_doctor`,
  `test_fsm_merge_gate_done_snapshot` — 343 passed, 251 subtests (маркер
  `ARTEL_ROLE` снят внутри процесса pytest). `test_codebase_map` зелёный после
  регенерации карты.

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

- Число вызовов `gh` на сверку — по одному на коммит линии от опорного до
  головы, что лежит под ближайшим push'ем с кодом. Каждый мерж гейта — push
  с кодом (голова RETRO, под ней снимок и merge без проверок), так что поверх
  мержа без документных коммитов это ~4–5 вызовов, плюс по одному на каждый
  документный коммит сверху (`note`/`doc-commit`). На каждом опросе ожидания
  после мержа обход повторяется — та же цена. Ускорение (GraphQL одним
  запросом) — вне задачи. Прежняя оценка «~25–30 вызовов, до первого коммита
  с кодом» была неверна: на main коммиты с кодом проверок не имеют (R1-F1).
- Правило «пропуск на голове push'а с кодом — проверка не исполняется на push»
  опирается на ADR-0016: единственная причина пропуска job на push в main —
  документный класс. Если job начнут пропускать по иному условию на коммитах
  с кодом, он выпадет из цвета (как и сегодня выпадает из цвета головы).
- Сверка перед мержем стоит после ожидания CI ветки: при красном main
  Оператор узнаёт об отказе после зелёного CI ветки (обычно мгновенно — CI
  ветки подтверждён ещё в `verifying`).

## Предложения системе

- `scripts/guard.py::scan_extraneous_acceptance_files` считает «закрытой
  историей» любую задачу с `docs/retro/<id>.md`, и это неявно зависит от
  порядка служебных коммитов гейта мержа (RETRO задачи пишется в то же
  дерево). Порядок теперь закреплён сторожем, но признак «закрыта до
  правила» лучше брать явным перечнем/датой, а не наличием RETRO.
- Приёмочный тест с выбором варианта по случайному зерну краснел лишь на
  трети прогонов: в шаге разработчика прошёл, у пульта упал. Класс
  «рандомизированная планка без перебора всех вариантов» (skills/test-authoring.md).

- Окружение шага роли: `ls` и `rm` из Bash не находятся (`command not
  found`), `ls` в другой форме требует подтверждения — временные файлы
  приходится убирать через `python3 -c "os.remove(...)"`. Класс «инструмент
  шага без базовых утилит PATH» (`.artel/home`, `runner.role_env`).
- `ci.main_line_status` опрашивает `gh` по коммиту за раз; строка `doctor`
  и сверка перед мержем на длинной документной цепочке — десятки вызовов.
  Кандидат в задачу: один GraphQL-запрос на окно линии.
- Отказ команд процессу роли (01M3XTF5506GF43HD51ECE230T) делает
  CLI-тесты `artel.main(["approve"|"pin-update", …])` красными внутри шага
  роли, хотя в CI они зелёные: разработчик не может прогнать такую планку
  в своём шаге. Кандидат: песочница `tests/sandbox.py` снимает
  `ARTEL_ROLE` на время сценария (как вручную делают
  `test_approve_acceptance_full_suite.py:270`, `test_doctor.py:474`).
