---
task: 01M6KB0FS809DG55K9A20CYKJE
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Предел числа процессов шага роли

## Подход
Предел считает пульт в своём процессе, ребёнку достаётся только
`setrlimit` с готовым числом:

- `runner.spawn_agent(cmd, *, nproc_limit=None, **kwargs)`: при заданном
  `nproc_limit` ставит `preexec_fn`, который выполняет только
  `resource.setrlimit(RLIMIT_NPROC, (N, N))` (функция и аргументы
  связаны заранее, импортов в ребёнке нет); без аргумента запуск прежний.
- `runner._read_maxprocperuid() -> (int | None, "ok"|"absent"|"failed")`:
  не macOS — `"absent"` без подпроцесса; на macOS `/usr/sbin/sysctl -n
  kern.maxprocperuid`, любой сбой (`OSError` в том числе
  `FileNotFoundError`, таймаут, код ≠ 0, пустой вывод, вывод без числа,
  не положительное число) — `"failed"`.
- `runner.role_nproc_limit() -> int`: min(V − `ROLE_NPROC_RESERVE`,
  конечные мягкий и жёсткий `resource.getrlimit(RLIMIT_NPROC)`); V не
  прочитан — `ROLE_NPROC_FALLBACK_MAXPROC`. `resource` вызывается через
  модуль (Н-4).
- `runner._user_process_count() -> int`: `ps -U <uid> -o pid=` по пути
  `liveness._ps_executable()`; код ≠ 0, пустой вывод или строка не-pid —
  исключение.
- `runner._step_nproc_limit(conn, task_id, role)`: один раз на шаг —
  предел, запись-предупреждение при `"failed"`, счёт процессов (сбой —
  одна запись «счёт процессов пользователя недоступен: <причина>», шаг
  идёт), при N ≥ M — запись отказа и текст «запас процессов пользователя
  исчерпан: N из M». Зовётся в `_run_developer_step` сразу после
  `_refuse_before_start` (пауза/стоп-кран/pre-flight сохраняют
  приоритет), до подтяжки main и `_run_attempts`, внутри `try/finally`
  снятия захвата зоны `_cmd_run`; отказ — `sys.exit`, `auto` уже
  превращает его в остановку «run отказался стартовать» с тревогой.
- Предел протянут именованным аргументом `_run_attempts` →
  `run_agent_once` → `_spawn_and_wait` → `spawn_agent` (в `spawn_agent`
  передаётся только когда он не `None` — прямые вызовы `run_agent_once`
  без него не меняют вызов `spawn_agent`).
- Снятие группы на обычном исходе: ветка `else` у `proc.wait` в
  `_spawn_and_wait`, при `isinstance(agent_pid, int)`,
  `liveness.terminate_process_group(agent_pid)` до `close_pump`; ненулевое
  число — запись `agent process group terminated` с текстом
  `liveness.group_kill_detail`.
- `doctor`: новый модуль `orchestrator/doctor/role_nproc.py`, строка
  `role-nproc` в `cli.all_checks` после `machine-load`; значения — только
  из `runner._read_maxprocperuid`, `runner.role_nproc_limit`,
  `runner._user_process_count`.

Бюджет SPEC ($45) не пересматривается.

## Шаги
1. `orchestrator/config.py`: `ROLE_NPROC_RESERVE = 1000`,
   `ROLE_NPROC_FALLBACK_MAXPROC = 4000`.
2. `orchestrator/runner.py`: `spawn_agent(nproc_limit=)`, функции чтения и
   формулы, проверка запаса в `_run_developer_step`, протяжка предела,
   снятие группы до `close_pump`.
3. `orchestrator/doctor/role_nproc.py` + регистрация (`__init__.py`,
   `cli.py`).
4. Тесты: `tests/test_role_nproc_limit.py` (формула при бесконечном/
   конечном пределе пульта, `"absent"` вне macOS, разбор вывода `sysctl`
   и `ps`, статусы строки `doctor`). Сторожа проверены мутацией: сравнение
   строки `doctor` с `kern.maxprocperuid` вместо предела шага и снятая
   проверка кода `ps` — каждый тест краснеет на своей.
   Итерация 2 (R1-F1): `tests/test_role_nproc_step.py` — сторожа поведения
   шага через `runner.cmd_run` с `FakeProc`: отказ при N = M (SystemExit,
   агент не порождён, захвата зоны нет), `nproc_limit` в каждой попытке,
   однократные предупреждения (`failed`, сбой счёта) и их отсутствие
   (`absent`), снятие группы на обычном исходе до `close_pump` и запись
   только при непустой группе. Проверены семью временными мутациями
   `runner.py` — каждая красит тест.
5. `docs/stack.md` (раздел «Провайдер исполнителя роли», абзац «Предел
   числа процессов шага»), `docs/codebase-map.md` регенерирован.
6. Приложение `skills/test-authoring.md` — ниже.

Прогоны шага: `plank-run` — 27 passed; долгоживущий
`tests/test_01m6kb0fs809dg55k9a20cykje_role_nproc.py` — 3 passed;
затронутые модули (`test_agent_log`, `test_doctor`, `test_git_fixation`,
`test_step_project`, `test_auto_cycle`, `test_liveness`,
`test_invariants`, `test_agent_failure`, `test_step_cost`,
`test_providers*`, `test_runner_*`, прочие тесты запуска шага) — 624
passed. Итерация 2: `test_role_nproc_step`, `test_role_nproc_limit`,
долгоживущий, `test_agent_log`, `test_codebase_map` — 104 passed.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 |
| 2 | 1, 2 |
| 3 | 2 |
| 4 | 2 (fork-отказ внутри шага — ошибка роли; пульт без предела) |
| 5 | 2 |
| 6 | 3 |
| 7 | 5 |
| 8 | 6 |
| 9 | 4 (тесты задачи без порождения процессов; долгоживущий и планка — test_author) |

## Влияние на систему
- Процесс агента обоих провайдеров теперь несёт `RLIMIT_NPROC`; пульт —
  нет (проверено AC-1). Предел наследуют `suite-run`/`plank-run`,
  запущенные ролью: на машине с V = 4000 предел 3000 процессов
  пользователя — штатному прогону хватает (`-n auto` — десятки процессов).
- Новый отказ старта шага (`SystemExit`) — тем же путём, что пауза и
  бюджет; захват зоны снимает существующий `finally` `_cmd_run`
  (проверено AC-5). Прочие записи журнала шага не меняются: на CI
  (Linux) предупреждения о `kern.maxprocperuid` нет, счёт процессов там
  работает.
- Снятие группы на обычном исходе добавляет один вызов `ps -g` на
  попытку с настоящим процессом; подменные процессы тестов
  (`FakeProc`) не затронуты условием `isinstance(agent_pid, int)`.
- Гейты, лимиты и тесты не ослабляются; существующие тестовые методы не
  менялись. Откат — revert merge-коммита задачи.

## Риски
- Шаг стартует до 2 с дольше (`sysctl` + `ps`), при зависании `ps` — до
  таймаута 10 с, затем шаг идёт с предупреждением.
- На Linux `RLIMIT_NPROC` считает потоки — расхождение с счётом
  процессов принято SPEC и описано в `docs/stack.md`.

## Приложение: skills/test-authoring.md — урок 04.11
Дифф дословно из ТЗ, база `origin/main` bccaa499. Проверено `git apply
--check` на чистом дереве ветки задачи: `Checking patch
skills/test-authoring.md...` — применяется.

```diff
diff --git a/skills/test-authoring.md b/skills/test-authoring.md
index 5757841ad..c602f87c3 100644
--- a/skills/test-authoring.md
+++ b/skills/test-authoring.md
@@ -364,6 +364,25 @@ ls_tree_files` на дисковые реализации, помощники `w
 считала от локальной ветки и эскалировала исправную задачу на мерже;
 соседняя 01M3H3JRBD544GQ10SS3DBGEVP считала от `origin` и не пострадала.
 
+## Красная фаза — безопасна для машины и репозитория
+Тесты исполняются до кода задачи: механизма, от которого тест ждёт
+отказа или защиты, в красной фазе нет. Пиши тест так, чтобы и без него
+прогон не вредил:
+- хук, pager, fsmonitor или псевдоним в тесте — заглушка, которая
+  пишет файл-метку и завершается; заглушка не вызывает git и сам тест
+  (иначе без механизма — бесконечная рекурсия);
+- каждый дочерний процесс теста — с пределом времени и в своей группе
+  процессов (`start_new_session=True`); по пределу снимай всю группу
+  (`os.killpg`), а не только верхний процесс;
+- меняющие команды (`git clean`, `reset --hard`, удаление файлов) — только
+  против временного репозитория или дублёра вне репозитория пульта.
+
+Прецедент 04.11 (01M6JJ4J4NBV): тест формы `core.fsmonitor` в красной
+фазе запустил хук, вызывавший `git clean`, тот снова хук — 3645
+процессов git, таблица процессов машины исчерпана, команды пульта и
+сессии Оператора не запускались; предел времени теста снял только
+верхний процесс.
+
 ## Краснота — объяснённая, не по умолчанию
 Красный тест до реализации — норма, но только по ПРАВИЛЬНОЙ причине.
 Прогони тесты и для КАЖДОГО файла напиши в докстринге модуля маркер:
```

## Предложения системе
- Строка `doctor` в SPEC не имела имени — test_author искал её по
  содержимому (записка test_author); SPEC с новой строкой `doctor` мог бы
  называть её имя.
