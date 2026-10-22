---
task: 01M5HJ4ZWRTB9481JC7SVYQ07B
type: spec_audit
author_role: spec_auditor
status: ready
verdict: pass
signals: "в) пути-признаки (тесты): tests/, tests/sandbox.py, tests/test_canary_parallel.py, tests/test_canary_parallel_protection.py, tests/test_canary_run_task.py, tests/test_invariants.py; в) защищённые пути: tests/test_invariants.py"
spec_sha: abbbb6be6fa27b799de04ab767a2baa5a4773d04
schema_version: 5
---

# SPEC-AUDIT: Б-1б (--parallel): постоянные тесты защиты части А и итога прогона

## ТЗ и SPEC
Требования ТЗ 1–6, AC-1…AC-4, зоны, «Только чтение» и «Не входит» перенесены
в SPEC по смыслу полностью. ANSWER-n нет, решений Оператора на гейте SPEC нет.

Отличия SPEC от ТЗ (отклонениями не считаю):
- SPEC добавил номера строк якорей (`canary.py:3334/3349/3372/3406/3449/3450/3457/3594/3667`,
  `artel.py:1573`) — все сверены, см. «Факты против кода».
- M18: из ТЗ выпала оговорка «(как `signal_parent` песочницы)»; суть
  («проверив, что родитель поставил свой обработчик SIGINT») осталась.
- ТЗ п. 4 «`PARALLEL_STOP_GRACE_SEC` уменьшается только в тестах, где все
  дочерние игнорируют SIGTERM (в этой задаче таких нет)» в SPEC сведено к
  «не уменьшается». Смысл тот же.
- `budget_usd: 25` при ТЗ «$15–22»: обосновано нижней планкой
  `config.BUDGET_CALIBRATION_TABLE` (`orchestrator/config.py:646`) и
  `skills/spec-authoring.md:44` («Планка не ниже $25»).
- Лишних требований сверх ТЗ в SPEC нет.

## Факты против кода
Рабочий каталог совпадает с f55b3ce1 по `orchestrator/` и `tests/`
(`git diff --stat f55b3ce1 HEAD -- orchestrator tests` пуст). Подтверждено:
- `orchestrator/canary.py:3334` — `print(f"[canary] прогон {run_stamp} завершён")`
  с отступом 8 (последовательная ветка, перед `return run_stamp` и комментарием
  «# Параллельный» на :3338); второе вхождение — :3594 (отступ 4).
- `:3349` `_PARALLEL_SIGNALS = (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)`;
  используется только в `_cmd_canary_parallel` (:3581).
- `:3372` `"--set", plan.name, "--summary", plan.summary or ""]` в `_child_argv`.
- `:3406` `os.killpg(child.proc.pid, signum)` в `_signal_group`; та же строка
  шлёт и SIGKILL из `_stop_children` (:3425), так что под M20 внук переживает
  и SIGKILL — тест M20 краснеет и по «снят SIGKILL» (:3452), и по живому внуку.
- `:3449` `if _has_run_row(run_stamp, child.title):`, `:3450`
  `return code == 0 and reason is None and not child.killed`, `:3457`
  `_report_child_failure(...)` перед `return False` (:3458).
- `:3667` `if not _mark_owned_by_parent(mark):` в `cmd_canary_run_task`.
- `orchestrator/artel.py:1573` `_detach_canary([arg for arg in rest if arg != "--detach"])`;
  `_detach_canary` (:1677) добавляет `--result-file` (:1686) и печатает одну
  строку «результат:» (:1691).
- Имена: `live_run_note(default_set_only=False)` (:3068) — фильтр по
  `set_name` записи (:3078), метка без записи — с `LIVE_MARK_ABSENT_NOTE`
  (:3083, :2801); `cmd_canary_live(drop, reason)` (:3129) снимает метку,
  только когда живых записей не осталось (:3164) — сценарий AC-16 («удалить
  все записи, затем drop») с кодом согласован; `_DRIVE_FAILED_OUTCOME` (:293);
  `_report_child_failure` (:3386) — поля, названные в AC-16 SPEC, совпадают
  (`main_sha=None`, `task_id`/`expected_escalation` None, `verdict="red"`);
  `PARALLEL_CHILD_LIMIT` (:3343), `PARALLEL_STOP_GRACE_SEC` (:3348);
  `store.set_canary_baseline(conn, title, steps, cost_usd, review_iterations,
  set_name)` (`store.py:1737`) — вставка мутации AC-10/12 синтаксически верна;
  `gitcmd.fetch_ref_sha` (`gitcmd.py:690`); `_pool_dir` — импорт в
  `canary.py:171` из `pool_seal` (подменяется как `canary._pool_dir`, как в
  планке); `CANARY_DEFAULT_SET = "default"` (`config.py:428`).
- `tests/test_canary_parallel.py`: `_CHILD` (:37), `_ParallelSandbox` (:108);
  `tests/sandbox.py`: `ALL_CONFIG_ATTRS` (:90), `InitializedTmpRootTest` (:1765).
- Планки: `d4533906` — коммит, в нём `_harness.py`, `test_parallel.py`,
  `test_preserved.py`, `test_cli.py`; названные методы есть
  (`test_preserved.py:48` + `SEQUENTIAL_LITERAL` :28; `test_cli.py:75`;
  `test_parallel.py:167, 318, 440, 475`; сверка `canary_baseline` — :183/:223 и :330/:349);
  `Coordinator._rescue` и `signal_parent` — `_harness.py:222, 274`.

## Проверяемость критериев
Мутации требования 5 проверены рассуждением по коду: каждая меняет
наблюдаемое тестом поведение.

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да (дифф ветки) | новый/изменённый файл вне `tests/test_canary_parallel_protection.py` в `orchestrator/`, `scripts/`, существующих `tests/` |
| AC-2 | да (состав файла + мутации п. 5) | AC-1 Б-1б: «завершён»→«завершен» в :3334 ломает литерал; AC-3: снятие `--parallel` в :1573 — счёт `--parallel` 0; AC-10/12: вставка `set_canary_baseline` перед :3449 — таблица меняется (в т. ч. строка `beta`); AC-15: `.upper()` в :3372 — запись дочернего с `set_name` «DEFAULT» отсекается фильтром :3078, `live_run_note` → `None` (либо настоящий `_set_plan("DEFAULT")` откажет до записи — сценарий не дойдёт до ведения, тест красный); AC-16: `if False:` в :3667 — `gamma` доходит до ведения; удаление :3457 — у `gamma` ноль строк; M14: :3450 без `code == 0` — нет «красный»; M18: без SIGINT в :3349 — обработчик не поставлен/`KeyboardInterrupt`, код ≠ 130; M20: `os.kill` в :3406 — «снят SIGKILL» через 60 с и живой внук |
| AC-3 | да (докстринги + таблица PLAN) | тест без «Ловит мутацию:»; мутация, не краснящая свой тест; остаток правки в `orchestrator/` |
| AC-4 | да (прогон) | тест, красный на f55b3ce1; нарушение `DeterministicTestsLintTest` (`time.sleep`/цикл по часам) |

Замечание без отклонения: под мутацией AC-15 (и `if False:` AC-16) сценарий
может не дойти до точки синхронизации — требование 5 SPEC прямо относит
зависание к дефекту теста, планка решает это сигналом `_FINISHED` и
неблокирующим открытием FIFO в `run_cli` (`_harness.py:508–530`).

## Зоны
Зона `tests/test_canary_parallel_protection.py` покрывает всё, что требуют
требования 1–6. Защищённый `tests/test_invariants.py` не меняется (требование 4,
«Не входит»). Регенерация `docs/codebase-map.md` после нового `*.py` в `tests/`
(карта содержит секции `tests/*`, напр. `docs/codebase-map.md:6564`) SPEC не
упоминает, но путь входит в `config.COMMON_ZONES` (`orchestrator/config.py:814`),
а AC-1 его не запрещает — не отклонение. Песочница ролей не расширяется.

## Матрица неослабления
Задача только добавляет тесты; ни один тест, гейт, лимит или проверка не
меняется и не удаляется. Раздела «Меняемое поведение» нет — и не нужно.

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| Новый файл `tests/test_canary_parallel_protection.py` | AC-1/3/10/12/15/16 Б-1б — только одноразовые планки `d4533906` (long_lived пуст); M14/M18/M20 — ничем | да, усиливается | новый файл (тесты требований 2–3) | добавление |
| `DeterministicTestsLintTest` | `tests/test_invariants.py:1999` | да, без правок и новых `_EXCEPTIONS` | тот же тест | без изменений |
| `PARALLEL_STOP_GRACE_SEC` | `orchestrator/canary.py:3348` | да, тесты не уменьшают | — | без изменений |

## Пути обхода гейтов
Существенных путей не нашёл. Мелкие места, закрытые текстом SPEC:
- Таблица мутаций в PLAN — самоотчёт разработчика; ревью/приёмка может
  повторить любую строку (якоря однозначны, строки сверены).
- M18 «обработчики восстановлены» мог бы стать пустым, если обвязка теста
  восстановит их сама до утверждения; восстановление делает
  `_interrupt_on_signal` (:3234–3236), мутации на это SPEC не требует —
  требования ТЗ сверх нет, не отклонение.

## Вердикт
pass — отклонений нет. Факты SPEC о коде и планках подтверждены
(`orchestrator/canary.py:3334, 3349, 3372, 3406, 3449–3457, 3667`;
`orchestrator/artel.py:1573`; `d4533906`), каждая мутация требования 5 краснит
свой тест по коду. Замечания без отклонения: регенерация
`docs/codebase-map.md` (в `COMMON_ZONES`, `config.py:814`); зависание под
мутацией AC-15/AC-16 уже названо дефектом теста в требовании 5.
