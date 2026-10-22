---
task: 01M5HJ4ZWRTB9481JC7SVYQ07B
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: tests/test_canary_parallel_protection.py
budget_usd: 25
---

# SPEC: Б-1б (--parallel): постоянные тесты защиты части А и итога прогона (перенос приёмки 01M5H24PZX)

## Контекст
Задача 01M5H24PZXZTBM03SF6V576S5P (Б-1б, флаг `canary --parallel`) смержена (f55b3ce1). Часть её критериев держат только одноразовые планки (`acceptance_tests/long_lived.sha256.txt` пуст), после мержа их ничто не проверяет. Независимая проверка 22.10 на f55b3ce1: из 31 мутации кода пульта 28 убиты, код верен; три мутации (M14, M18, M20) выжили и в `tests/`, и в планках. В `tests/test_canary_parallel.py` нет сценариев AC-1 (литерал последовательного пути), AC-3 (`--parallel --detach`), AC-10/AC-12 (`canary_baseline` без изменений), AC-15 (гибель родителя), AC-16 (`canary live --drop`). Задача переносит эти сценарии текстом в один новый постоянный файл `tests/` и добавляет тесты на выжившие мутации; код пульта не меняется.

Планки — материал, не импортируются: `git show d4533906:tasks/01M5H24PZXZTBM03SF6V576S5P/acceptance_tests/<файл>` (`_harness.py`, `test_parallel.py`, `test_preserved.py`, `test_cli.py`; коммит d4533906 артефактной ветки проверен — файлы на месте); SPEC Б-1б — там же.

## Требования

1. **Один новый файл** `tests/test_canary_parallel_protection.py`; код пульта не меняется, существующие файлы `tests/` (в том числе `tests/test_canary_parallel.py`) не меняются. Файл самодостаточен: песочницу и подменённого дочернего строит сам по образцу `_ParallelSandbox`/`_CHILD` (`tests/test_canary_parallel.py`) и `_harness.py` планок (`CanaryParallelSandbox`, `Coordinator`); из других файлов `tests/` импортирует только `tests/sandbox.py` (`InitializedTmpRootTest`, `ALL_CONFIG_ATTRS`).

2. **Тесты переноса планок** — сценарии и утверждения планок, переписанные под песочницу файла:
   - **AC-1 Б-1б, литерал последовательного пути** (планка `SequentialPathTest::test_ac1_sequential_run_output_rows_result_and_registry_as_before`). Прогон `artel._cmd_canary` без `--parallel` (`--k 2 --sha <короткий> --set <набор> --template alfa,beta --result-file <путь>`) с заглушкой `_run_one_task`, печатающей строку «[ведение] …» и пишущей строку `canary_runs`, как в планке. Вывод после замены `run_stamp` и пути пула метками `<STAMP>`/`<POOL>` дословно равен литералу `SEQUENTIAL_LITERAL` планки. Строки `canary_runs`, файл результата и реестр (во время ведения — метка и запись с прежним набором полей, после прогона — пусто) сверяются, как в планке; дочерних процессов нет.
   - **AC-3 Б-1б, `--parallel --detach`** (планка `ParallelFlagTest::test_ac3_parallel_with_detach_reaches_detached_process`). `artel._cmd_canary(["--k", "2", "--parallel", "--detach"])` при подменённом `artel.subprocess.Popen`: argv отвязанного процесса несёт `--parallel` ровно один раз и `--result-file` ровно один раз, без `--detach`; строка «результат:» в выводе одна.
   - **AC-10 Б-1б, `canary_baseline` после параллельного прогона.** До прогона заведена базовая строка шаблона прогона того же набора (`store.set_canary_baseline`); два дочерних, исполняющих настоящий `canary.cmd_canary_run_task`, пишут свои строки; после прогона с кодом 0 содержимое таблицы `canary_baseline` равно прежнему.
   - **AC-12 Б-1б, `canary_baseline` после сигнала родителю.** Три шаблона, два дочерних в ведении, SIGTERM родителю: код 128 + SIGTERM, третий шаблон не запущен, строки «оборвана сигналом SIGTERM» у двух, строки «завершён» нет, реестр пуст, таблица `canary_baseline` (заведённая до прогона) равна прежней.
   - **AC-15 Б-1б, гибель родителя.** Набор прогона — `config.CANARY_DEFAULT_SET`. Подменённый дочерний получает хвост настоящего argv после run-task и передаёт `--set` в `cmd_canary_run_task` из этого argv. Пока оба дочерних (настоящий `cmd_canary_run_task`) в ведении, согласующий поток удаляет запись родителя `<run_stamp>-<pid родителя>.json` и пишет в метку `<run_stamp>.lock` pid уже завершившегося и пожатого процесса (без настоящего SIGKILL). В этот момент `canary.live_run_note(default_set_only=True)` не `None`, называет `run_stamp` прогона и не содержит `LIVE_MARK_ABSENT_NOTE`.
   - **AC-16 Б-1б, `canary live --drop`, затем отказ следующего дочернего.** Три шаблона: `alfa` и `beta` (настоящий `cmd_canary_run_task`, пишут строки) в ведении; согласующий поток удаляет все записи `<run_stamp>-*.json` и снимает метку `canary.cmd_canary_live(drop=<run_stamp>, reason=…)`; после отпускания `alfa`/`beta` запущенный `gamma` отказывает по сверке метки Б-1а: ведения (`_run_one_task`) и клона нет, у `gamma` ровно одна строка — красная строка родителя (поля `_report_child_failure`: исход `_DRIVE_FAILED_OUTCOME`, `main_sha` пуст, `task_id` и `expected_escalation` — `None`, `verdict` красный).

3. **Тесты выживших мутаций** (`orchestrator/canary.py` f55b3ce1):
   - **M14** (`_finish_child`, строка 3450: `return code == 0 and reason is None and not child.killed` → `return reason is None and not child.killed`). Два шаблона: `alfa` пишет свою строку прогона и выходит с ненулевым кодом (например, заглушка ведения в настоящем `cmd_canary_run_task` пишет строку и вызывает `sys.exit(3)`), `beta` пишет строку и выходит с кодом 0. Родитель завершается `SystemExit` с текстом «прогон <run_stamp> красный»; у `alfa` ровно одна строка с `run_stamp` прогона — своя, красной строки родителя для неё нет; строка «прогон <run_stamp> завершён» есть; заголовок блока `alfa` называет код 3.
   - **M18** (строка 3349: `_PARALLEL_SIGNALS` без `signal.SIGINT`). Два шаблона в ведении (настоящий `cmd_canary_run_task`); согласующий поток, проверив, что родитель поставил свой обработчик SIGINT, шлёт `os.kill(os.getpid(), signal.SIGINT)`. Итог: `SystemExit(128 + SIGINT)` (код 130, не `KeyboardInterrupt`), у обоих дочерних строки «оборвана сигналом SIGTERM», строки «завершён» нет, реестр пуст, обработчики сигналов процесса теста восстановлены. При любой ошибке сценария согласующий поток снимает группы всех запущенных дочерних SIGKILL (по образцу `Coordinator._rescue`); исход `cmd_canary` ловится как `BaseException` — `KeyboardInterrupt` не выходит из теста.
   - **M20** (`_signal_group`, строка 3406: `os.killpg(child.proc.pid, signum)` → `os.kill(child.proc.pid, signum)`). Дочерний — простой процесс, не `cmd_canary_run_task`; его обработчик SIGTERM — пустая функция Python (не выходит, не бросает, не `SIG_IGN`), ставится ДО создания внука; затем `Popen` внука без новой сессии и `wait()` внука; внук открывает свой FIFO на запись (событие согласующему потоку, который читает из FIFO pid внука) и ждёт `signal.pause()`. Согласующий поток, дождавшись внука, шлёт SIGTERM родителю. `PARALLEL_STOP_GRACE_SEC` не уменьшается. Итог: дочерний завершился сам после гибели внука (в выводе нет причины «снят SIGKILL»), внук завершён (`os.kill(<pid внука>, 0)` даёт `ProcessLookupError`, без ожидания). Уборка теста снимает внука, если тот жив, с подавлением `ProcessLookupError`.

4. **Детерминированность.** Ожидание — только событиями: FIFO или канал от подменённого дочернего, `Popen.wait()`/`os.waitpid` без срока; без `time.sleep` с паузой и без циклов по часам; `select.select` на дескрипторах не используется; те же правила — для кода дочернего и внука в строковых литералах. `cmd_canary` идёт в главном потоке, сигнал родителю — `os.kill(os.getpid(), …)` из согласующего потока. Тесты не читают и не пишут настоящий реестр и каталог журналов пульта (песочница `ALL_CONFIG_ATTRS`); без сети, клона, профиля Codex и настоящих ролей: `_ephemeral_clone`, `_locked_canary_profile`, `_canary_profile_auth`, `gitcmd.fetch_ref_sha` в процессе родителя подменены запрещающими заглушками. `PARALLEL_STOP_GRACE_SEC` в тестах этой задачи не уменьшается. Правка `tests/test_invariants.py` и новая запись `_EXCEPTIONS` не делаются; если без неё не обойтись — эскалация.

5. **Докстринги и таблица мутаций.** Докстринг каждого теста несёт «Сценарий» и строку «Ловит мутацию:». Каждая названная мутация проверяется в PLAN.md: применяется к коду пульта в worktree задачи, новый тест краснеет, правка откатывается; в конце `git status --porcelain orchestrator/` пуст; итог — таблица «тест → мутация → результат (красный/зелёный) → строка pytest». Минимальный перечень (якоря сверены с f55b3ce1):
   - AC-1: `print(f"[canary] прогон {run_stamp} завершён")` последовательной ветки `cmd_canary` (вхождение с отступом 8 пробелов, `orchestrator/canary.py:3334`; второе вхождение — 3594 — не трогается) → «завершен»;
   - AC-3: в `artel._cmd_canary` (`orchestrator/artel.py:1573`) `_detach_canary([arg for arg in rest if arg != "--detach"])` → `_detach_canary([arg for arg in rest if arg not in ("--detach", "--parallel")])`;
   - AC-10 и AC-12: в `_finish_child` перед `if _has_run_row(run_stamp, child.title):` (`orchestrator/canary.py:3449`) вставка `store.set_canary_baseline(store.db(), child.title, 0, 0.0, 0, plan.name)`;
   - AC-15: в `_child_argv` (`orchestrator/canary.py:3372`) `"--set", plan.name, "--summary"` → `"--set", plan.name.upper(), "--summary"`;
   - AC-16: в `cmd_canary_run_task` (`orchestrator/canary.py:3667`) `if not _mark_owned_by_parent(mark):` → `if False:`; второй — в `_finish_child` удалена строка `_report_child_failure(run_stamp, child.title, plan, reason)` перед `return False` (`orchestrator/canary.py:3457`);
   - M14, M18, M20 — как в требовании 3.
   Под M20 тест краснеет примерно через `PARALLEL_STOP_GRACE_SEC` (60 с) — ожидаемо, срок не уменьшается. Мутация, при которой тест виснет до таймаута pytest вместо красного утверждения, — дефект теста.

6. **Зелёный на f55b3ce1.** Все новые тесты зелёные на коде без мутаций — при прогоне файла отдельно и вместе с `tests/test_canary_parallel.py`, `tests/test_canary_run_task.py`, `tests/test_invariants.py::DeterministicTestsLintTest`. В PLAN.md — число тестов набора до и после (плюс ровно число новых методов) и время самого длинного нового теста (`--durations`; ориентир — не более 10 с без мутаций).

## Критерии приёмки

AC-1. В репозитории появился ровно один новый файл `tests/test_canary_parallel_protection.py`; дифф задачи не затрагивает `orchestrator/`, `scripts/`, существующие файлы `tests/`, `conftest.py`, `pyproject.toml`.

AC-2. Файл содержит тесты на AC-1 Б-1б (литерал `SEQUENTIAL_LITERAL`), AC-3 Б-1б (`--parallel --detach`), AC-10 и AC-12 Б-1б (`canary_baseline` без изменений), AC-15 Б-1б (гибель родителя — `live_run_note(default_set_only=True)` не `None`), AC-16 Б-1б (`canary live --drop` — отказ `gamma` с красной строкой), M14, M18, M20 со свойствами требований 2–3.

AC-3. Каждый новый тест несёт в докстринге «Сценарий» и «Ловит мутацию:»; таблица мутаций требования 5 в PLAN.md — каждая мутация краснит свой тест, `git status --porcelain orchestrator/` в конце пуст.

AC-4. Новые тесты зелёные без мутаций; `DeterministicTestsLintTest` зелёный без правок `tests/test_invariants.py`; `tests/test_canary_parallel.py` и `tests/test_canary_run_task.py` зелёные без правок.

## Не входит

- Правка кода пульта (`orchestrator/`, `scripts/`): все три выжившие мутации — пробел тестов, не дефект кода.
- Правка существующих тестов, в том числе дописывание в `tests/test_canary_parallel.py`.
- Перевод одноразовых планок Б-1б в `long_lived`.
- Новые записи `_EXCEPTIONS` / правка `tests/test_invariants.py`.
- Настоящая канарейка и настоящий реестр.
- Консолидация тестов канарейки.
- Только чтение: `orchestrator/` (весь каталог), `scripts/`, `tasks/` (планки Б-1б — материал, не импортируются), `tests/sandbox.py`, `tests/test_canary_parallel.py`, `tests/test_canary_run_task.py`, `tests/test_invariants.py`, `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_registry.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_mark.py`, `tests/test_canary_live_registry_units.py`, `pyproject.toml`.

## Материалы

- ТЗ: `tasks/01M5HJ4ZWRTB9481JC7SVYQ07B/TZ.md`.
- Планки и SPEC Б-1б: `git show d4533906:tasks/01M5H24PZXZTBM03SF6V576S5P/…` (`acceptance_tests/_harness.py`, `test_parallel.py`, `test_preserved.py`, `test_cli.py`).
- Образец песочницы: `tests/test_canary_parallel.py` (`_CHILD`, `_ParallelSandbox`), `tests/sandbox.py`.
- Бюджет: ТЗ называет $15–22; поставлен $25 — нижняя планка калибровки (`config.BUDGET_CALIBRATION_TABLE`, skills/spec-authoring.md: «Планка не ниже $25 ни для одной задачи»).
