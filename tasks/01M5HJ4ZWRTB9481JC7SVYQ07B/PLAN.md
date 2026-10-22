---
task: 01M5HJ4ZWRTB9481JC7SVYQ07B
type: plan
author_role: developer
status: draft
schema_version: 5
---

# PLAN: Б-1б (--parallel): постоянные тесты защиты части А и итога прогона

## Подход
Один новый файл `tests/test_canary_parallel_protection.py`, код пульта и
существующие тесты не меняются. Песочница файла `_ProtectionSandbox` —
по образцу `_ParallelSandbox`/`_CHILD` (`tests/test_canary_parallel.py`) и
`CanaryParallelSandbox`/`Coordinator` планок Б-1б (d4533906), из `tests/`
импортируется только `tests/sandbox.py` (`InitializedTmpRootTest`,
`ALL_CONFIG_ATTRS`):
- дочерний подменяется через `canary._child_argv` (хвост настоящего argv
  после `run-task`, `--set` из него уходит в `cmd_canary_run_task`);
- запущенные дочерние учитываются обёрткой `canary._start_child` — при
  любой ошибке сценария согласующий поток снимает их группы SIGKILL и
  ещё не запущенных пускает без ожидания (приём `Coordinator._rescue`);
- в процессе родителя `_ephemeral_clone`, `_locked_canary_profile`,
  `_canary_profile_auth`, `_run_one_task`, `gitcmd.fetch_ref_sha` —
  запрещающие заглушки (AC-1 Б-1б подменяет `_run_one_task` своей
  заглушкой ведения поверх запрета);
- ожидание — только FIFO и `wait()` без срока; `PARALLEL_STOP_GRACE_SEC`
  не трогается; для M20 — режим дочернего `grandchild` (пустой обработчик
  SIGTERM до внука, внук пишет pid в FIFO и ждёт `signal.pause()`).

Бюджет не пересматривается: один файл, оценка SPEC верна.

## Шаги
1. Файл `tests/test_canary_parallel_protection.py`: песочница и 9 тестов
   (AC-1, AC-3, AC-10, AC-12, AC-15, AC-16 Б-1б; M14, M18, M20);
   регенерация `docs/codebase-map.md` (`python3 scripts/codebase_map.py`).
2. Таблица мутаций: каждая мутация требования 5 наложена на worktree,
   тест покраснел, правка откачена (`git checkout -- <файл>`).

## Тесты и мутации

| Тест | Сценарий SPEC |
|---|---|
| `SequentialPathTest::test_sequential_run_output_rows_result_and_registry_as_before` | AC-1 Б-1б |
| `DetachTest::test_parallel_with_detach_reaches_detached_process` | AC-3 Б-1б |
| `BaselineTest::test_parallel_run_leaves_canary_baseline_unchanged` | AC-10 Б-1б |
| `BaselineTest::test_parent_sigterm_leaves_canary_baseline_unchanged` | AC-12 Б-1б |
| `RegistryTest::test_parent_death_run_stays_live_by_child_records` | AC-15 Б-1б |
| `RegistryTest::test_dropped_mark_makes_next_child_refuse_with_red_row` | AC-16 Б-1б |
| `OutcomeTest::test_child_with_own_row_and_nonzero_code_makes_run_red` | M14 |
| `SigintTest::test_parent_sigint_stops_children_with_exit_130` | M18 |
| `GroupSignalTest::test_parent_sigterm_reaches_grandchild_in_child_group` | M20 |

Таблица мутаций (каждая наложена на код worktree заменой ровно одного
вхождения якоря, тест прогнан `python3 -m pytest
tests/test_canary_parallel_protection.py::<тест> -p no:cacheprovider -p
timeout -o timeout=120 -q`, правка откачена `git checkout -- <файл>`):

| Метка | Мутация | Тест | Результат | Строка pytest |
|---|---|---|---|---|
| AC-1 | `canary.py:3334` «прогон {run_stamp} завершён» → «завершен» (вхождение с отступом 8) | `SequentialPathTest` | красный | `1 failed in 0.33s` |
| AC-3 | `artel.py:1573` фильтр `arg not in ("--detach", "--parallel")` | `DetachTest` | красный | `1 failed in 0.25s` |
| AC-10 | `canary.py:3449` вставка `store.set_canary_baseline(store.db(), child.title, 0, 0.0, 0, plan.name)` | `BaselineTest::test_parallel_run_leaves_canary_baseline_unchanged` | красный | `1 failed in 0.47s` |
| AC-12 | та же вставка | `BaselineTest::test_parent_sigterm_leaves_canary_baseline_unchanged` | красный | `1 failed in 0.46s` |
| AC-15 | `canary.py:3372` `"--set", plan.name.upper()` | `RegistryTest::test_parent_death_run_stays_live_by_child_records` | красный | `1 failed in 0.46s` (`live_run_note` → `None`) |
| AC-16 (сверка метки) | `canary.py:3667` `if not _mark_owned_by_parent(mark):` → `if False:` | `RegistryTest::test_dropped_mark_makes_next_child_refuse_with_red_row` | красный | `1 failed in 0.57s` |
| AC-16 (красная строка) | `canary.py:3457` удалён `_report_child_failure(...)` перед `return False` | `RegistryTest::test_dropped_mark_makes_next_child_refuse_with_red_row` | красный | `1 failed in 0.58s` |
| M14 | `canary.py:3450` `return reason is None and not child.killed` | `OutcomeTest` | красный | `1 failed in 0.43s` |
| M18 | `canary.py:3349` `_PARALLEL_SIGNALS` без `signal.SIGINT` | `SigintTest` | красный | `1 failed in 0.42s` (согласующий поток: «родитель не поставил обработчик SIGINT», дочерние сняты, без зависания) |
| M20 | `canary.py:3406` `os.kill(child.proc.pid, signum)` | `GroupSignalTest` | красный | `1 failed in 60.32s (0:01:00)` (ожидаемо: срок `PARALLEL_STOP_GRACE_SEC` не уменьшается) |

Каждый прогон под мутацией завершился кодом pytest 1 (красное
утверждение), ни одного «Timeout». После всех мутаций
`git status --porcelain orchestrator/` — пусто.

Без мутаций: `python3 -m pytest tests/test_canary_parallel_protection.py
--durations=10` — `9 passed in 2.38s`, самый длинный тест —
`RegistryTest::test_dropped_mark_makes_next_child_refuse_with_red_row`,
0.43 с. Вместе с соседями (`tests/test_canary_parallel.py`,
`tests/test_canary_run_task.py`,
`tests/test_invariants.py::DeterministicTestsLintTest`) — `45 passed, 140
subtests passed in 11.72s`.

Число тестов набора: SUITE_COUNTS.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 |
| 5 | 2 |
| 6 | 1, 2 |

## Влияние на систему
Добавляется только тестовый файл (+ регенерированная карта
`docs/codebase-map.md` — правило conventions-core). Код пульта,
`tests/test_invariants.py`, `_EXCEPTIONS`, `conftest.py`,
`pyproject.toml`, существующие тесты не тронуты — ни один гейт, лимит или
тест не ослабляется. Тесты не трогают настоящий реестр и каталог журналов
(песочница `ALL_CONFIG_ATTRS`), не ходят в сеть и не клонируют. Дочерние
процессы, внук M20 снимаются уборкой теста. Откат — удаление файла
(revert коммита).

## Риски
- Под M20 тест краснеет через ~60 с (срок не уменьшается по SPEC); при
  таймауте pytest 120 с запас двукратный.
- Гонка установки обработчика SIGINT родителем с `_SignalDeferral` при
  старте дочернего: при любом исходе отложенный сигнал поднимается тем же
  обработчиком, утверждения теста не зависят от момента.

## Предложения системе
- Bash-обёртка шага отклоняет однострочные циклы мутаций с `$'…{…}'`
  («brace with quote character») — таблицу мутаций пришлось гонять
  Python-heredoc'ом; штатной команды «наложить мутацию, прогнать тест,
  откатить» у пульта нет (planka test_author делает это сама на копии).
