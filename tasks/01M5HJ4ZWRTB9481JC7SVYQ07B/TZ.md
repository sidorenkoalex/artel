---
task: 01M5HJ4ZWRTB9481JC7SVYQ07B
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Б-1б (--parallel): постоянные тесты защиты части А и итога (перенос приёмки 01M5H24PZX)

# Б-1б (--parallel): постоянные тесты защиты части А и итога прогона

## Факты

Строка бэклога «Б-1б (--parallel): постоянные тесты защиты части А и итога в tests/ (перенос приёмки 01M5H24PZX)», приоритет 1. Задача 01M5H24PZXZTBM03SF6V576S5P (Б-1б, флаг `canary --parallel`) смержена (f55b3ce1). Независимая проверка 22.10 на f55b3ce1: из 31 мутации кода пульта 28 убиты, код верен. Часть критериев SPEC Б-1б держат только одноразовые планки задачи (`acceptance_tests/long_lived.sha256.txt` пуст), то есть после мержа их ничто не проверяет; три мутации выжили и в `tests/`, и в планках. Планки лежат в `refs/artifacts/01M5H24PZXZTBM03SF6V576S5P` (`tasks/01M5H24PZXZTBM03SF6V576S5P/acceptance_tests/`: `_harness.py`, `test_parallel.py`, `test_preserved.py`, `test_cli.py`) и SPEC там же; файлы `tests/` из `tasks/` не импортируют, поэтому сценарии переносятся текстом.

В `tests/test_canary_parallel.py` (733 строки) нет:
- AC-15 «гибель родителя — прогон живой по записи дочернего» (планка `RegistryTest::test_ac15_parent_killed_run_stays_live_by_child_record`);
- AC-16 «`canary live --drop`, затем отказ следующего дочернего» (планка `RegistryTest::test_ac16_dropped_mark_makes_next_child_refuse_with_red_row`);
- литерала вывода последовательного пути без флага (AC-1, планка `SequentialPathTest::test_ac1_sequential_run_output_rows_result_and_registry_as_before`, константа `SEQUENTIAL_LITERAL`);
- сверки таблицы `canary_baseline` после параллельного прогона (AC-10, планка `SummaryTest::test_ac10_…`) и после прогона с сигналом родителю (AC-12, планка `ParentSignalTest::test_ac12_…`);
- доезда `--parallel` с `--detach` до отвязанного процесса (AC-3, планка `ParallelFlagTest::test_ac3_parallel_with_detach_reaches_detached_process`).

Выжившие мутации проверки 22.10 (по одной строке `orchestrator/canary.py`, каждая строка-якорь в f55b3ce1 встречается ровно один раз):
- M14 — в `_finish_child` `return code == 0 and reason is None and not child.killed` → `return reason is None and not child.killed`: дочерний, записавший свою строку и вышедший с ненулевым кодом, считается прошедшим, код родителя 0;
- M18 — `_PARALLEL_SIGNALS = (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)` → без `signal.SIGINT`: SIGINT родителю приходит `KeyboardInterrupt`, код 130 теряется;
- M20 — в `_signal_group` `os.killpg(child.proc.pid, signum)` → `os.kill(child.proc.pid, signum)`: сигнал получает только сам дочерний, не его группа процессов (ведение в клоне остаётся живым).

Имена кода, через которые тесты подменяют поведение (все уже есть в `orchestrator/canary.py` f55b3ce1, код не меняется): `cmd_canary` (параметр `parallel`), `_cmd_canary_parallel`, `_run_children`, `_start_child`, `_child_argv` (сборка argv дочернего — точка подмены дочернего), `_wait_child` (ожидание дочернего), `_stop_children`, `_signal_group`, `_finish_child`, `_report_child_failure`, `_has_run_row`, `PARALLEL_CHILD_LIMIT` (= 2), `PARALLEL_STOP_GRACE_SEC` (= 60), `_PARALLEL_SIGNALS`, `_interrupt_on_signal`, `CanaryInterrupted`, `_live_dir`, `_live_run_record`, `live_run_note`, `live_runs`, `live_marks`, `cmd_canary_live`, `cmd_canary_run_task`, `_mark_owned_by_parent`, `_write_child_record`, `_run_one_task`, `_set_plan`, `CanarySetPlan`, `_pool_dir`, `_resolve_target_sha`, `_ephemeral_clone`, `_locked_canary_profile`, `_canary_profile_auth`, `LIVE_MARK_ABSENT_NOTE`; в `orchestrator/artel.py` — `_cmd_canary`, `_detach_canary`; в `orchestrator/store.py` — `insert_canary_run`, `all_canary_runs`, `set_canary_baseline`, `canary_baseline`; в `orchestrator/gitcmd.py` — `fetch_ref_sha`. Песочница — `tests/sandbox.py` (`InitializedTmpRootTest`, `ALL_CONFIG_ATTRS`). Образец подменённого дочернего — `_CHILD` и `_ParallelSandbox` в `tests/test_canary_parallel.py`, а также `_harness.py` планок (`CanaryParallelSandbox`, `Coordinator`).

`DeterministicTestsLintTest` (`tests/test_invariants.py`) запрещает ожидание по часам (`time.sleep` с ненулевой паузой, циклы по `time.monotonic()`/`time.time()`); исключения `_EXCEPTIONS` добавляются только правкой защищённого файла.

## Требуется

1. **Один новый файл** `tests/test_canary_parallel_protection.py`, код пульта не меняется, существующие файлы `tests/` (в том числе `tests/test_canary_parallel.py`) не меняются. Файл самодостаточен: свою песочницу и подменённого дочернего он строит сам по образцу `_ParallelSandbox`/`_CHILD` и `_harness.py` планок; из других файлов `tests/` он импортирует только `tests/sandbox.py`.

2. **Тесты переноса планок** (сценарии и утверждения планок, переписанные под песочницу файла). Планки читать так: `git show d4533906:tasks/01M5H24PZXZTBM03SF6V576S5P/acceptance_tests/<файл>`, где d4533906 — коммит артефактной ветки:
   - **AC-1, литерал последовательного пути.** Прогон `artel._cmd_canary` без `--parallel` (`--k 2 --sha <короткий> --set <набор> --template alfa,beta --result-file <путь>`) на подменах: `_run_one_task` — заглушка, печатающая строку «[ведение] …» и пишущая строку `canary_runs`, как в планке. Вывод после замены `run_stamp` и пути пула метками `<STAMP>`/`<POOL>` равен литералу `SEQUENTIAL_LITERAL` планки дословно (литерал снят на коде до Б-1б; на f55b3ce1 он верен — мутация M23 проверки 22.10 убила планку на этом коде). Строки `canary_runs`, файл результата и реестр (во время ведения — метка и запись с прежним набором полей, после прогона — пусто) сверяются, как в планке; дочерних процессов нет.
   - **AC-3, `--parallel --detach`.** `artel._cmd_canary(["--k", "2", "--parallel", "--detach"])` при подменённом `artel.subprocess.Popen`: argv отвязанного процесса несёт `--parallel` ровно один раз и `--result-file` ровно один раз, без `--detach`; строка «результат:» в выводе одна.
   - **AC-10, `canary_baseline` после параллельного прогона.** До прогона заведена базовая строка шаблона прогона того же набора (`store.set_canary_baseline`); два дочерних, исполняющих настоящий `canary.cmd_canary_run_task`, пишут свои строки; после прогона с кодом 0 содержимое таблицы `canary_baseline` равно прежнему.
   - **AC-12, `canary_baseline` после сигнала родителю.** Три шаблона, два дочерних в ведении, SIGTERM родителю: код 128 + SIGTERM, третий шаблон не запущен, строки «оборвана сигналом SIGTERM» у двух, строки «завершён» нет, реестр пуст, таблица `canary_baseline` (заведённая до прогона, как выше) равна прежней.
   - **AC-15, гибель родителя.** Набор прогона — набор по умолчанию (`config.CANARY_DEFAULT_SET`). Подменённый дочерний получает хвост настоящего argv после run-task и передаёт `--set` в `cmd_canary_run_task` из этого argv. Пока оба дочерних (настоящий `cmd_canary_run_task`) в ведении, согласующий поток удаляет запись родителя `<run_stamp>-<pid родителя>.json` и пишет в метку `<run_stamp>.lock` pid уже завершившегося и пожатого процесса (гибель родителя — файлами реестра, без настоящего SIGKILL). В этот момент `canary.live_run_note(default_set_only=True)` не `None`, называет `run_stamp` прогона и не содержит `LIVE_MARK_ABSENT_NOTE` (прогон держится записями дочерних, а не меткой).
   - **AC-16, `canary live --drop`, затем отказ следующего дочернего.** Три шаблона: `alfa` и `beta` (настоящий `cmd_canary_run_task`, пишут строки) в ведении; согласующий поток удаляет все записи `<run_stamp>-*.json` и снимает метку `canary.cmd_canary_live(drop=<run_stamp>, reason=…)`; после отпускания `alfa`/`beta` запущенный `gamma` отказывает по сверке метки Б-1а: ведения (`_run_one_task`) и клона нет, у `gamma` ровно одна строка — красная строка родителя (поля `_report_child_failure`: исход `_DRIVE_FAILED_OUTCOME`, `main_sha` пуст, `task_id` и `expected_escalation` — `None`, `verdict` красный).

3. **Тесты выживших мутаций.**
   - **M14.** Два шаблона: `alfa` пишет свою строку прогона и выходит с ненулевым кодом (например, заглушка ведения в настоящем `cmd_canary_run_task` пишет строку и вызывает `sys.exit(3)`), `beta` пишет строку и выходит с кодом 0. Родитель завершается с ненулевым кодом (`SystemExit` с текстом «прогон <run_stamp> красный»), у `alfa` ровно одна строка с `run_stamp` прогона — своя, красной строки родителя для неё нет; строка «прогон <run_stamp> завершён» есть; заголовок блока `alfa` называет код 3.
   - **M18.** Два шаблона в ведении (настоящий `cmd_canary_run_task`), согласующий поток после проверки, что родитель поставил свой обработчик SIGINT (как `signal_parent` песочницы), шлёт `os.kill(os.getpid(), signal.SIGINT)`. Итог: код выхода 130 (`SystemExit(128 + SIGINT)`, не `KeyboardInterrupt`), у обоих дочерних строки «оборвана сигналом SIGTERM» (остановка по требованию 5 SPEC Б-1б), строки «завершён» нет, реестр пуст, обработчики сигналов процесса теста восстановлены. При любой ошибке сценария согласующий поток снимает группы всех запущенных дочерних SIGKILL (по образцу `Coordinator._rescue` из `_harness.py`), чтобы родитель не завис; исход `cmd_canary` ловится как `BaseException` — `KeyboardInterrupt` не должен выйти из теста и оборвать сеанс pytest.
   - **M20.** Дочерний — простой процесс, не `cmd_canary_run_task`; обработчик SIGTERM — пустая функция Python, которая не выходит и не бросает исключение (не `SIG_IGN`, который внук унаследовал бы), ставится ДО создания внука; затем `Popen` внука без новой сессии (в группе процессов дочернего) и `wait()` внука; внук открывает свой FIFO на запись (событие для согласующего потока, который читает из FIFO pid внука) и затем ждёт `signal.pause()`. Согласующий поток, дождавшись внука, шлёт SIGTERM родителю. Срок `PARALLEL_STOP_GRACE_SEC` не уменьшается. Итог: дочерний завершился сам после гибели внука (в выводе нет причины «снят SIGKILL»), внук завершён (`os.kill(<pid внука>, 0)` даёт `ProcessLookupError`: дочерний пожал внука до своего выхода, проверка без ожидания). Уборка теста снимает внука, если тот жив (при мутации он остаётся), с подавлением `ProcessLookupError`.

4. **Детерминированность.** Ожидание — только событиями: FIFO или канал от подменённого дочернего, `Popen.wait()`/`os.waitpid` без срока; без `time.sleep` с паузой и без циклов по часам; `select.select` на дескрипторах не использовать; правила детерминизма действуют и для кода дочернего и внука в строковых литералах — проверка тестов их не видит; `cmd_canary` идёт в главном потоке, сигнал родителю — `os.kill(os.getpid(), …)` из согласующего потока. Тесты не читают и не пишут настоящий реестр и каталог журналов пульта (песочница `ALL_CONFIG_ATTRS`), без сети, клона, профиля Codex и настоящих ролей (`_ephemeral_clone`, `_locked_canary_profile`, `_canary_profile_auth`, `gitcmd.fetch_ref_sha` в процессе родителя подменены запрещающими заглушками). `PARALLEL_STOP_GRACE_SEC` уменьшается только в тестах, где все дочерние игнорируют SIGTERM (в этой задаче таких нет). Правка `tests/test_invariants.py` и новая запись `_EXCEPTIONS` не нужны; если без неё не обойтись — эскалация.

5. **Строка «Ловит мутацию:»** в докстринге каждого теста; там же «Сценарий». Каждая названная мутация проверяется в PLAN.md: применяется к коду пульта в worktree задачи, новый тест краснеет, правка откатывается; в конце `git status --porcelain orchestrator/` пуст; итог — таблица «тест → мутация → результат (красный/зелёный) → строка pytest». Минимальный перечень мутаций (якоря сверены с f55b3ce1, каждый встречается в файле один раз):
   - AC-1: `print(f"[canary] прогон {run_stamp} завершён")` последовательной ветки `cmd_canary` (перед `return run_stamp` и комментарием «# Параллельный») → «завершен»; строка `print(f"[canary] прогон {run_stamp} завершён")` встречается дважды, мутируется вхождение с отступом 8 пробелов (строка 3334, последовательная ветка);
   - AC-3: в `artel._cmd_canary` `_detach_canary([arg for arg in rest if arg != "--detach"])` → `_detach_canary([arg for arg in rest if arg not in ("--detach", "--parallel")])`;
   - AC-10 и AC-12: в `_finish_child` перед строкой `if _has_run_row(run_stamp, child.title):` вставка `store.set_canary_baseline(store.db(), child.title, 0, 0.0, 0, plan.name)`;
   - AC-15: в `_child_argv` `"--set", plan.name, "--summary"` → `"--set", plan.name.upper(), "--summary"`;
   - AC-16: в `cmd_canary_run_task` `if not _mark_owned_by_parent(mark):` → `if False:`; второй — в `_finish_child` `_report_child_failure(run_stamp, child.title, plan, reason)` перед `return False` удалён;
   - M14, M18, M20 — как в «Фактах».
   Под M20 тест краснеет примерно через `PARALLEL_STOP_GRACE_SEC` (60 с) — ожидаемо, не зависание; срок не уменьшать.
   Мутация, при которой тест виснет до таймаута pytest вместо красного утверждения, — дефект теста.

6. **Зелёный на f55b3ce1.** Все новые тесты зелёные на коде без мутаций, при прогоне файла отдельно и вместе с `tests/test_canary_parallel.py`, `tests/test_canary_run_task.py`, `tests/test_invariants.py::DeterministicTestsLintTest`. В PLAN.md — число тестов набора до и после (плюс ровно число новых методов) и время самого длинного нового теста (`--durations`; ориентир — не более 10 с без мутаций).

## Критерии приёмки

AC-1. В репозитории появился ровно один новый файл `tests/test_canary_parallel_protection.py`; дифф задачи не затрагивает `orchestrator/`, `scripts/`, существующие файлы `tests/`, `conftest.py`, `pyproject.toml`.

AC-2. Файл содержит тесты на AC-1 (литерал `SEQUENTIAL_LITERAL`), AC-3 (`--parallel --detach`), AC-10 и AC-12 (`canary_baseline` без изменений), AC-15 (гибель родителя — `live_run_note(default_set_only=True)` не `None`), AC-16 (`canary live --drop` — отказ `gamma` с красной строкой), M14, M18, M20 со свойствами п. 2–3.

AC-3. Каждый тест несёт «Сценарий» и «Ловит мутацию:»; таблица мутаций п. 5 в PLAN.md — каждая мутация краснит свой тест, `git status --porcelain orchestrator/` в конце пуст.

AC-4. Новые тесты зелёные без мутаций; `DeterministicTestsLintTest` зелёный без правок `tests/test_invariants.py`; `tests/test_canary_parallel.py` и `tests/test_canary_run_task.py` зелёные без правок.

Зоны: tests/test_canary_parallel_protection.py

Только чтение: orchestrator/ (весь каталог: код пульта не меняется, в том числе прочие места, вызывающие `sleep`, `Popen`, `CANARY_DEFAULT_SET`, `fetch_ref_sha`), orchestrator/canary.py, orchestrator/artel.py, orchestrator/store.py, orchestrator/config.py, orchestrator/gitcmd.py, scripts/, tasks/ (планки Б-1б — материал, не импортируются), tests/sandbox.py, tests/test_canary_parallel.py, tests/test_canary_run_task.py, tests/test_invariants.py, tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_registry.py, tests/test_01m5fa4nr91pcf47szt6v0q9hs_mark.py, tests/test_canary_live_registry_units.py, pyproject.toml.

Не входит: правка кода пульта (все три выжившие мутации — пробел тестов, не дефект кода); правка существующих тестов, в том числе дописывание в `tests/test_canary_parallel.py`; перевод одноразовых планок Б-1б в `long_lived`; новые записи `_EXCEPTIONS`; настоящая канарейка и настоящий реестр; консолидация тестов канарейки.

Бюджет: $15–22.
