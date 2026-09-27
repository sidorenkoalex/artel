---
task: 01M3FQ3JVC3DGGM33XCX8TC7ME
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Автогейт приёмки называет упавшие тесты; approve в acceptance проверяет то, что обещает

## Подход

Рамку $40 из SPEC не переоцениваю: число файлов и шагов плана совпало с
оценкой SPEC (8 файлов зоны, один узел разбора + три потребителя), поле
`budget_usd` остаётся закомментированным.

Ключевые решения.

1. **Один узел разбора в `orchestrator/acceptance.py`** (требования 1-2).
   Регулярка итоговой строки `amend._RUN_SUMMARY` переезжает в
   `acceptance` (`_RUN_SUMMARY`), рядом встают `run_summary_line`,
   `failed_test_lines` и сам узел `run_digest(output)`: имена упавших
   (`FAILED <nodeid>`/`ERROR <nodeid>` блока «short test summary info») +
   итоговая строка, а при отсутствии и того, и другого — хвост вывода.
   Объём — тем же потолком, что `agent_log.log_tail`
   (`config.LOG_TAIL_LINES` строк, затем `config.LOG_TAIL_CHARS`
   символов), общим помощником `_bounded`. `amend._run_summary` остаётся
   на месте с прежним поведением и зовёт `acceptance.run_summary_line`
   (падение обратно на весь хвост — там же, где было), поэтому
   tests/test_amend.py зелен без правки ожиданий (AC-3).

2. **`run_full_suite` остаётся единственным входом прогона** —
   `(зелено, текст)`, но текст больше не режется `[-2000:]`: полный вывод
   нужен файлу лога (требование 3), а в журнал попадает только выжимка
   узла разбора. Это сохраняет мокабельность: `tests/test_plan_appendix.py`
   и `tests/test_fsm_autogate.py` подменяют именно `run_full_suite`, и
   новый узел прогона зовёт её же изнутри — патчи продолжают долетать.
   Вырожденные исходы («tests/ нет», таймаут) остаются прежними
   сообщениями, вынесенными в константу/функцию
   (`FULL_SUITE_NO_TESTS_NOTE`, `_full_suite_timeout_note`), которыми
   классификатор исхода и пользуется — производитель и потребитель текста
   не могут разойтись молча.

3. **`acceptance.full_suite(root, task_id) -> FullSuiteRun`** — узел
   «прогон + файл лога + разбор + различимая причина» для всех трёх
   потребителей (автогейт, гейт мержа, `approve`). Поля: `green`,
   `outcome` (одна из четырёх констант: зелёный / красный / таймаут /
   нет tests/), `digest`, `log_path`, `detail`. Файл лога —
   `agent_log.new_agent_log(task_id, "fullsuite")`, то есть ровно
   `.artel/logs/<id>-fullsuite-<n>.log` с нумерацией от 1 без
   перезатирания (требование 3 прямо разрешает «имя по образцу
   `new_agent_log`»); отдельной функции в `agent_log.py` не завожу —
   нумерация там уже есть, дубль был бы вторым источником истины.
   Сбой записи лога (`OSError`) деградирует до `log_path=None`, гейт не
   роняет.

4. **Потребители** (требования 4-6): автогейт и гейт мержа заменяют
   `acceptance.run_full_suite(...)` на `acceptance.full_suite(...)` и
   кладут `run.detail` в свою запись; состав и порядок условий
   `_autogate_conditions` и гейтов мержа не меняются. `approve` в
   `acceptance` получает общий узел `fsm._acceptance_full_suite_ok`:
   worktree не на ветке задачи — именованная запись «полный набор не
   проверен — worktree не заведён» и проход (требование 7, он же держит
   зелёным `test_operator_approve_passes_each_gate`); не-зелёный набор —
   отказ `approve` с причиной/именами/итоговой строкой/логом; флаг
   `--accept-red "<основание>"` — проход с основанием и той же выжимкой в
   журнале.

5. **Флаг в диспетчере** (требование 8): `artel._accept_red_arg` (пустое
   или отсутствующее основание — `sys.exit` тем же стилем, что
   `_reason_arg`) и `artel._approve_sha_arg` (второй позиционный
   аргумент, не флаг и не его значение) — разбор позиционного `sha` не
   меняется. `accept_red` доходит до `_approve_acceptance` через
   `functools.partial` в таблице «состояние -> обработчик»: таблица
   остаётся таблицей (роадмап §3, R3), остальные обработчики сигнатуру не
   меняют.

6. **Текст «приёмка: что проверит approve»** (требование 9) собирается
   тремя группами: первая — что `approve` действительно делает (полный
   набор tests/ в worktree, свежесть кодовой ветки), вторая — что уже
   проверено до приёмки (прогон планки на переходе `review -> verifying`,
   потолок бюджета `budget.budget_block` на старте шага роли), третья —
   что остаётся человеку (или «автогейт пройдёт сам»). Группа `approve`
   стоит ПЕРВОЙ: планка задачи читает пункты автоматических проверок как
   часть записи до первого разделителя ` | `.

## Шаги

1. `orchestrator/acceptance.py`: узел разбора (`_RUN_SUMMARY`,
   `run_summary_line`, `failed_test_lines`, `_bounded`, `run_digest`),
   рефакторинг `run_full_suite` (полный вывод, вынесенные сообщения
   вырожденных исходов), узел `full_suite` + `FullSuiteRun` + запись файла
   лога; `orchestrator/amend.py`: `_run_summary` через общий узел.
2. `orchestrator/fsm_autogate.py`: `full_suite` вместо `run_full_suite` в
   условии полного набора, `run.detail` в причине отказа, путь к логу в
   перечне выполненных условий; текст `_acceptance_checklist_detail` в
   соответствии с фактом.
3. `orchestrator/fsm_merge_gate.py`: `_full_suite_or_refuse` на том же
   узле — detail отказа несёт итоговую строку, имена упавших и путь к
   логу.
4. `orchestrator/fsm.py`: `_acceptance_full_suite_ok`, `_approve_acceptance`
   с параметром `accept_red`, `cmd_approve`/`_cmd_approve` + таблица;
   `orchestrator/artel.py`: `_accept_red_arg`/`_approve_sha_arg`, строка
   usage.
5. `docs/operator-session.md`, раздел «Запуски и рабочие копии»: что
   проверяет автогейт приёмки, что гоняет `approve`, флаг осознанного
   принятия красного набора, каталог лога полного набора.
6. Юнит-тесты `tests/` (см. «Покрытие требований», требование 11) +
   регенерация `docs/codebase-map.md`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 2 |
| 5 | 3 |
| 6 | 4 |
| 7 | 4 |
| 8 | 4 |
| 9 | 2 |
| 10 | 5 |
| 11 | 6 |

Тесты по требованию 11 (файл -> что ловит):

- `tests/test_acceptance.py` — узел разбора (итоговая строка + имена
  упавших, падение на хвост, потолки `config.LOG_TAIL_*`), файл лога
  полного набора и его нумерация, различимость исходов
  `full_suite`;
- `tests/test_fsm_autogate.py` — detail отказа автогейта (имена упавших,
  итоговая строка, путь к логу), различимость трёх исходов, соответствие
  текста «что проверит approve» тому, что `approve` делает;
- `tests/test_approve_acceptance_full_suite.py` (новый) — отказ `approve`
  при красном наборе, проход с `--accept-red` и основанием в журнале,
  пропуск прогона без worktree, разбор аргументов команды `approve`.

## Влияние на систему

- **Контракт `run_full_suite` (bool, str) сохранён**, изменилось только
  содержимое второго элемента (полный вывод вместо среза 2000 символов).
  Существующие ожидания (`MARKER-RED`, «превысил», «tests/») остаются
  выполненными; в журнал сырой вывод больше не попадает нигде — его
  заменяет выжимка, ограниченная `config.LOG_TAIL_*` (объём записей
  журнала только уменьшается).
- **Гейты и лимиты не ослабляются**: состав и порядок условий
  `_autogate_conditions` (6 условий) и гейтов мержа не меняются — это
  зафиксировано приёмочным тестом состава; `approve` в `acceptance`
  приобретает ОДНУ новую проверку (полный набор tests/), прямо
  предписанную требованием 6, и единственный легальный выход из неё —
  осознанный флаг Оператора с основанием в журнале. Остальные проверки
  `approve` (фиксация, свежесть ветки) не тронуты.
- **`test_operator_approve_passes_each_gate`** (защищённый
  `tests/test_invariants.py`) остаётся зелёным без правок: в его
  песочнице worktree задачи не зарегистрирован
  (`workspace.registered_paths()` пуст на поддельном git), прогон
  пропускается требованием 7. Тот же механизм защищает все лёгкие
  FSM-песочницы (`LightTransitionSandbox`), проводящие `approve` из
  `acceptance`.
- **Каталог логов**: файлы `<id>-fullsuite-<n>.log` совпадают по форме с
  логами шагов ролей, поэтому попадают под `prune` (штатная ротация),
  под проверку утечки пула (`doctor.check_role_log_pool_leak` — полезно)
  и под сбор диагностики канарейки. Дисковый fallback метрики трения
  (`report._task_step_logs`) увидит и их — трение такого файла 0.0;
  приоритетный источник метрики — журнал, поэтому на живых задачах
  значение не меняется. Отмечено в «Предложениях системе».
- **Откат** — revert одного merge-коммита задачи: новых миграций схемы,
  новых состояний FSM и новых файлов конфигурации нет.

## Риски

- Существующие тесты, проводящие `approve` из `acceptance` в песочнице с
  РЕАЛЬНЫМ git и зарегистрированным worktree, получили бы новый прогон
  набора. Проверяется прогоном затронутых модулей (`test_invariants`,
  `test_branch_freshness_gate`, `test_pull_conflict_marker_states`,
  `test_git_fixation`, `test_acceptance_tests_flow`, `test_plan_appendix`,
  `test_cmd_approve_dispatch`) — результат каждого прогона записан в
  «Проверки» ниже.
- Классификация исхода по префиксу собственного сообщения
  (`FULL_SUITE_NO_TESTS_NOTE`/`_full_suite_timeout_note`) — цена
  сохранения мокабельного единственного входа прогона; производитель и
  потребитель читают одну константу, расхождение возможно только правкой
  обоих мест сразу.

## Проверки

Раннер и таймаут — те же, которыми пульт принимает планку (`python3 -m
pytest <файлы> -p no:cacheprovider -p timeout -o timeout=…`), каждый
прогон в переднем плане. Полный набор `tests/` в шаге не гонялся (правило
скила; его гоняет CI на пуш ветки) — прогнаны планка задачи и модули,
затронутые диффом прямо или через `approve`/`acceptance`.

| Прогон | Итог |
|---|---|
| `tasks/01M3FQ3JVC3DGGM33XCX8TC7ME/acceptance_tests` (вся планка) | 34 passed, 3 subtests |
| `tests/test_acceptance.py tests/test_fsm_autogate.py tests/test_approve_acceptance_full_suite.py tests/test_amend.py tests/test_plan_appendix.py` | 118 passed, 2 subtests |
| `tests/test_invariants.py tests/test_cmd_approve_dispatch.py tests/test_branch_freshness_gate.py tests/test_pull_conflict_marker_states.py` | 88 passed, 215 subtests |
| `tests/test_git_fixation.py tests/test_acceptance_tests_flow.py tests/test_zones_approve.py tests/test_division_parent_cleanup.py tests/test_answer_gate.py` | 127 passed |
| `tests/test_canary.py tests/test_auto_cycle.py tests/test_merge_gate_ci_wait.py tests/test_done_branch_cleanup.py tests/test_ci_status_kind_gate.py tests/test_fsm_advance_gate_smoke.py` | 175 passed, 32 subtests |
| `tests/test_spec_budget.py tests/test_step_refixation.py tests/test_step_cost.py tests/test_agent_failure.py tests/test_analyst_role.py tests/test_acceptance_collect.py tests/test_dry_run.py` | 187 passed, 54 subtests |
| `tests/test_doctor.py tests/test_multitarget.py tests/test_fsm_advance_gate_framework.py tests/test_mutation_claim_gate.py tests/test_review_registry_gate.py tests/test_zones_gate.py tests/test_protected_paths_gate.py tests/test_codebase_map.py` | 274 passed, 17 subtests |
| `tests/test_new_argv_parsing.py tests/test_kill_live_cycle_refusal.py tests/test_artel_role_restricted_commands.py tests/test_artel_bootstrap.py tests/test_report.py tests/test_prune.py tests/test_doctor_canary_pool.py` | 123 passed, 12 subtests |
| `python3 scripts/guard.py --all` | ок (1032 файлов); два предупреждения — чужие артефакты (`_sandbox.py` задач 01M1RA0R9A/T067), не этой задачи |
| `guard.test_functions_without_mutation_claim` по трём изменённым файлам `tests/` | пусто (заявка мутации есть у каждого нового/изменённого теста) |
| линт формата id задачи (`scripts/id_format_patterns.txt` по новым строкам диффа `*.py`) | 0 совпадений |
| `python3 scripts/codebase_map.py` | карта перегенерирована тем же коммитом |

Риск из «Рисков» закрыт: ни один существующий тест, проводящий `approve`
из `acceptance`, нового прогона набора не получил — в лёгких
FSM-песочницах `workspace.registered_paths()` пуст (поддельный git), и
ветвь требования 7 пропускает прогон.

Найдено и исправлено по ходу: первая версия юнит-тестов автогейта писала
файл лога прогона в настоящий `config.LOGS` рабочей копии (4 файла
`T001-fullsuite-*.log`) — классы переведены на песочницу `TmpRootTest`,
файлы удалены.

## Предложения системе

- `orchestrator/report.py::_task_step_logs` считает логом шага роли любой
  файл `<id>-*-*.log` — после этой задачи под форму попадает и лог
  полного набора (`<id>-fullsuite-<n>.log`), не бывший шагом роли.
  Дисковый fallback метрики трения из-за этого чуть размывается (журнал
  как приоритетный источник это скрывает). Класс: «форма имени файла как
  единственный признак сущности».
- Точка подмены в существующем тесте становится де-факто контрактом
  модуля: `tests/test_plan_appendix.py` патчит `acceptance.run_full_suite`
  с сигнатурой `(root)`, и это (а не SPEC) определило, что новый узел
  прогона обязан звать её изнутри, а не наоборот. Класс: «мок как
  архитектурное ограничение» — стоит проговорить в skills/test-authoring.md,
  какой уровень подмены тест вправе фиксировать.
