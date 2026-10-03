---
task: 01M41M6KGWA9PJ6G1KPDC6XY70
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: CI быстрее — минимальная версия Python отдельным параллельным заданием; песочница FsmTest не сорит в tasks/ корня запуска

## Подход
Оба изменяемых файла — защищённые пути (`config.is_protected_path` →
True для `.github/workflows/ci.yml` и `tests/test_invariants.py`), поэтому
вся правка — одно приложение ниже; кодовая ветка задачи не меняется
(SPEC, требования 4, 6, 7; карта кодовой базы не регенерируется — `*.py`
в ветке не правятся).

1. **CI.** Три шага минимальной версии (`stack_ci.py --min` →
   `setup-python` → `pip install -r requirements.lock` → pytest
   `tests/test_invariants.py`) переезжают из задания `python` в новое
   задание `python-min` («Инварианты на минимальной версии Python»):
   `needs: changes`, `if:` дословно как у `python`
   (`!cancelled() && needs.changes.outputs.code != 'false'`), тот же
   `timeout-minutes: 40`, свой `actions/checkout@v4`. Команда pytest
   получает `-n auto -p xdist` при прежних `-p timeout -o timeout=120`.
   В задании `python` остаются версия из манифеста, установка
   `requirements.lock`, `py_compile`, снимок ссылок, полный `tests/`,
   сверка ссылок — без изменений. `continue-on-error` не появляется.
2. **Песочница FsmTest.** `FsmTest.setUp` добавляет `("TASKS", root /
   "tasks")` в тот же список подмен, что `DB`/`LOGS`/`WORKTREES`/
   `PROJECTS`. Довод старого комментария «`brief._developer_spec_text`
   читает SPEC через `config.ROOT/tasks`» к текущему коду неприменим:
   `artifact_source.resolve` всегда отдаёт `foreign=True` (A7), бриф читает
   SPEC через `gitcmd.show`, а его подмена `disk_backed_show` читает
   `config.TASKS` (`tests/sandbox.py::_tasks_relative_path`). Ветка
   `foreign=False` в `orchestrator/brief.py:481` здесь недостижима, правка
   `orchestrator/` не нужна. `addCleanup(shutil.rmtree, self.tdir)` убран:
   `self.tdir` теперь во временном каталоге, его чистит `tmp.cleanup`.
3. **Сторож** — новый класс `FsmSandboxKeepsRunRootTasksCleanTest(FsmTest)`
   с методом `test_sandbox_task_dir_is_outside_run_root_tasks` (заявка
   «Ловит мутацию»): внутри теста, до `doCleanups`, `self.tdir` лежит под
   подменённым `config.TASKS` и не лежит под `REPO_ROOT/tasks`, каталога
   `REPO_ROOT/tasks/<id>` нет.
4. **Читатели структуры `ci.yml`** (требование 4). Структуру заданий читает
   только `tests/test_invariants.py::CiJobsByPushClassInvariantTest`
   (инвариант 36: задание `python` не исключает `task/` и не построено как
   `== 'true'`). В объёме переноса правило распространено на вынесенное
   задание `python-min` — без этого перенос молча вывел бы прогон на
   минимальной версии из-под инварианта. Остальные упоминания `ci.yml` в
   `tests/` (`tests/test_protected_paths_gate.py`,
   `tests/test_plan_appendix.py`, `tests/test_protected_test_settings.py`,
   `tests/test_guard_path_mentions.py`) используют путь как строку для
   проверки защищённости/упоминаний, имена заданий и шаги не читают;
   `scripts/ci_push_class.py`, `scripts/ci_protected_paths.py`,
   `orchestrator/ci.py` имена заданий `python` или «Синтаксис и тесты
   оркестратора» не читают (grep `needs:`/имени задания по `orchestrator/`,
   `scripts/`, `tests/`). Утверждения существующих методов не меняются:
   изменён только кортеж обходимых заданий в `violations` и текст
   находки `job {job}: условие fail-open`; тест
   `test_planted_fail_open_condition_is_caught` ищет подстроку
   `fail-open` — она на месте.

**Оценка времени (требование 5, AC-6).** Замер Оператора 03.10.2026 по CI
`main` (пин a5df6f64): задание `python` («Синтаксис и тесты оркестратора») — 314 с, из
них полный `tests/` с `-n auto` 193 с и `tests/test_invariants.py` на
минимальной версии в один процесс 110 с; остальные задания 8–12 с.
Замер на CI ветки задачи для нового устройства невозможен: CI ветки идёт
без приложений (приложение ложится на мерже,
`orchestrator/fsm_merge_gate.py`), а ветка задачи кода не меняет — её CI
повторяет устройство `main`, то есть задание `python` на ветке ≈ 314 с
до приложения; `gh run list` по ветке в шаге роли недоступен (команда
требует подтверждения, которого в шаге нет). Оценка после приложения:
- задание `python`: до 314 с, после ≈ 190 с (314 − 110 с прогона − ≈ 14 с
  на второй `setup-python` и второй `pip install`);
- задание `python-min`: ≈ 90 с (checkout + `setup-python` + `pip install`
  ≈ 25 с; `tests/test_invariants.py` с `-n auto` на 4 vCPU раннера
  ≈ 60 с — локально 48 с по SPEC, в один процесс в этом шаге 117 с);
- стена CI: max(190 с, 90 с) ≈ 190 с вместо 314 с — около 2 мин на прогон.
Фактические длительности обоих заданий снимет первый CI `main` после
мержа (имена заданий в чеке: «Синтаксис и тесты оркестратора»,
«Инварианты на минимальной версии Python»).

## Шаги
1. Приложение ниже к `.github/workflows/ci.yml` и
   `tests/test_invariants.py` (один многофайловый дифф). Проверено:
   `git apply --check` на чистом дереве ветки (после отката рабочей копии)
   — без ошибок; в рабочей копии с наложенной правкой
   `python3 -m pytest tests/test_invariants.py -p no:cacheprovider -p timeout -o timeout=120`
   — 67 passed за 117 с, `git status` после прогона — только
   `tests/test_invariants.py` (никаких `tasks/<id>/`); мутация
   `("TASKS", config.TASKS)` (подмена фактически снята) — сторож
   `FsmSandboxKeepsRunRootTasksCleanTest` красный, возврат — зелёный.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 (задание `python-min`, `needs: changes`, `if:` как у `python`) |
| 2 | 1 (`-n auto -p xdist -p timeout -o timeout=120`) |
| 3 | 1 (шаги не удалены, `continue-on-error` нет, `requirements.lock` в новом задании, сверка ссылок остаётся в `python`) |
| 4 | 1 (приложение, `git apply --check`; читатели `ci.yml` — «Подход», п.4) |
| 5 | «Подход», оценка времени |
| 6 | 1 (подмена `config.TASKS` в `FsmTest.setUp`) |
| 7 | 1 (`FsmSandboxKeepsRunRootTasksCleanTest`) |

## Влияние на систему
- Покрытие CI не меняется: тот же набор на тех же версиях Python, те же
  зависимости; задание `python-min` красит прогон так же, как красил шаг.
  Гейты `ci.branch_status`/`verifying_status` читают все check-runs
  головы — новое задание попадает в них автоматически, его `skipped` на
  документном пуше — зелёный для `ci.GREEN`, как и у `python`.
- Инвариант 36 (`CiJobsByPushClassInvariantTest`) усилен — покрывает и
  `python-min`; ни одно утверждение не удалено.
- `FsmTest`: изоляция строже (ещё один путь в песочнице), все 67 тестов
  файла зелёные. Наследники, подменяющие `config.ROOT` своим деревом,
  `config.TASKS` не трогают — подмена в `setUp` им не мешает.
- Откат — revert коммита мержа с приложением.

## Риски
- `-n auto` на 3.11: известной нестабильности нет (SPEC, требование 2);
  если проявится — эскалация с прогоном-доказательством, не тихий откат.
- Локальный прогон с `-n auto` в шаге роли заблокирован сторожем роли
  (`conftest.py` воспринимает воркеры xdist как полный прогон), поэтому
  параллельность проверена только косвенно: полный `tests/` уже идёт с
  `-n auto` на CI, а файл не делит общего состояния вне временных
  каталогов.

## Предложения системе
- Сторож роли в `conftest.py` отказывает `pytest tests/test_x.py -n N`
  внутри шага (каждый воркер видит «полный прогон»): адресный параллельный
  прогон одного модуля невозможен, хотя его прямо заказывает SPEC.
- Требование SPEC «оценка по замерам CI ветки задачи» несовместимо с
  правкой только через приложение: CI ветки идёт без приложений, а
  `gh run list` в шаге роли требует подтверждения — замер «после» роль
  снять не может (аналитику: заказывать оценку, не замер ветки).

## Приложение: .github/workflows/ci.yml, tests/test_invariants.py

```diff
diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml
index 55d542cb..6c434c39 100644
--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -229,6 +229,19 @@ jobs:
             echo "::error::прогон tests/ изменил набор ссылок репозитория — см. diff выше"
             exit 1
           fi
+
+  python-min:
+    name: Инварианты на минимальной версии Python
+    # Отдельно от `python` и параллельно ему (SPEC 01M41M6KGWA9PJ6G1KPDC6XY70):
+    # прежде этот прогон шёл в `python` после полного tests/ и удлинял его
+    # на ~110 с. Условие запуска — то же, что у `python` (ADR-0016,
+    # fail-closed на пустом output `changes`).
+    needs: changes
+    if: ${{ !cancelled() && needs.changes.outputs.code != 'false' }}
+    runs-on: ubuntu-latest
+    timeout-minutes: 40
+    steps:
+      - uses: actions/checkout@v4
       - name: минимальная версия Python из манифеста (01M1RDCCKBQMJ5G2K9ANJP059H, требование 2)
         id: stack-python-min
         run: echo "version=$(python3 scripts/stack_ci.py --min)" >> "$GITHUB_OUTPUT"
@@ -241,8 +254,8 @@ jobs:
         run: |
           # Литерал timeout=120 дублирует stack.PER_TEST_TIMEOUT_SEC —
           # известное ограничение (YAML не читает Python-константу), тот
-          # же класс, что и в шаге unit-тестов выше.
-          python3 -m pytest tests/test_invariants.py -p no:cacheprovider -p timeout -o timeout=120
+          # же класс, что и в шаге unit-тестов задания `python`.
+          python3 -m pytest tests/test_invariants.py -n auto -p no:cacheprovider -p timeout -p xdist -o timeout=120
 
   protected-paths:
     name: Enforcement, конфиги системы меняет только Оператор
diff --git a/tests/test_invariants.py b/tests/test_invariants.py
index 46434fe8..096685bc 100644
--- a/tests/test_invariants.py
+++ b/tests/test_invariants.py
@@ -166,7 +166,12 @@ class FsmTest(unittest.TestCase):
                             ("WORKTREES", root / ".artel" / "worktrees"),
                             # Каталог документов задачи (ADR-0021, этап 1)
                             # выкладывает шаг роли — тоже в песочницу.
-                            ("PROJECTS", root / ".artel" / "projects")):
+                            ("PROJECTS", root / ".artel" / "projects"),
+                            # Каталог задач — тоже в песочницу (SPEC
+                            # 01M41M6KGWA9PJ6G1KPDC6XY70, требование 6):
+                            # прерванный прогон не оставляет `tasks/<id>/`
+                            # в рабочей копии, `addCleanup` до него не доходит.
+                            ("TASKS", root / "tasks")):
             patcher = mock.patch.object(config, attr, value)
             patcher.start()
             self.addCleanup(patcher.stop)
@@ -182,19 +187,12 @@ class FsmTest(unittest.TestCase):
         stack_patcher.start()
         self.addCleanup(stack_patcher.stop)
 
-        # `TASKS` НЕ патчится отдельно (в отличие от прежней версии этого
-        # файла): `brief._developer_spec_text` на «чужая ветка не найдена»
-        # (`on_foreign_branch` здесь всегда False — SpyRun ниже отвечает
-        # отказом на ЛЮБОЙ `rev-parse --verify refs/heads/*`) читает
-        # SPEC.md с диска через `config.ROOT / "tasks/<id>/..."`, НЕ через
-        # `config.TASKS` — до SPEC T094 (id — предсказуемый "T001") это
-        # расхождение маскировалось совпадением: `config.ROOT` этого
-        # класса намеренно настоящий (см. ниже), и в реальном дереве
-        # пульта существует настоящий `tasks/T001/` (давно закрытая
-        # задача) — сверка читала ЕГО, не то, что писал `write_spec` этого
-        # файла. С ULID id каждый прогон уникален, совпадения больше нет.
-        # `config.TASKS` остаётся дефолтным `ROOT/tasks` (как и в проде) —
-        # `self.tdir` ниже пишет туда же, откуда бриф реально читает.
+        # `TASKS` подменён выше, хотя `brief._developer_spec_text` при
+        # `foreign=False` читает SPEC.md через `config.ROOT / "tasks/<id>/..."`,
+        # а не через `config.TASKS`: эта ветка здесь недостижима —
+        # `artifact_source.resolve` всегда отдаёт `foreign=True` (A7), и
+        # бриф читает SPEC через `gitcmd.show`, подменённый ниже чтением
+        # диска `config.TASKS` (`tests/sandbox.py::_tasks_relative_path`).
 
         self.git_spy = SpyRun()
         spy_patcher = mock.patch.object(gitcmd.subprocess, "run", self.git_spy)
@@ -296,11 +294,6 @@ class FsmTest(unittest.TestCase):
         # диск (симуляция ветко-корректного fallback), каталог заводит
         # сам файл.
         self.tdir.mkdir(parents=True, exist_ok=True)
-        # `config.TASKS` теперь = реальный `ROOT/tasks` (см. комментарий
-        # выше) — `self.tdir` физически лежит в РЕАЛЬНОМ дереве пульта;
-        # ULID гарантирует уникальное неколлизирующее имя, но каталог
-        # обязан быть убран, а не оставлен в рабочей копии после теста.
-        self.addCleanup(shutil.rmtree, self.tdir, ignore_errors=True)
         self.branch = self.task_row()["branch"]
 
     # ------------------------------------------------------------ утилиты
@@ -413,6 +406,33 @@ class FsmStatesCoverTheCodeTest(unittest.TestCase):
         self.assertLessEqual(set(config.STATE_ROLE), set(FSM_STATES))
 
 
+class FsmSandboxKeepsRunRootTasksCleanTest(FsmTest):
+    """Песочница `FsmTest` не заводит каталог задачи в настоящем `tasks/`
+    корня запуска (SPEC 01M41M6KGWA9PJ6G1KPDC6XY70, требования 6-7).
+
+    Случай 03.10: таймаут шага прервал прогон до `addCleanup`, каталог
+    задачи песочницы остался в рабочей копии кода, и гейт зон отказал
+    переходу задачи-владельца рабочей копии.
+    """
+
+    def test_sandbox_task_dir_is_outside_run_root_tasks(self):
+        """`self.tdir` лежит под подменённым `config.TASKS`, а в настоящем
+        `<корень>/tasks/` каталога задачи песочницы нет — проверка внутри
+        теста, до `doCleanups`.
+
+        Ловит мутацию: подмена `config.TASKS` убрана из `FsmTest.setUp`
+        (`self.tdir` снова строится в настоящем `<корень>/tasks/`) — тест
+        красный, хотя `addCleanup` убрал бы каталог после него.
+        """
+        real_tasks = (REPO_ROOT / "tasks").resolve()
+        tdir = self.tdir.resolve()
+        self.assertTrue(tdir.is_dir())
+        self.assertTrue(tdir.is_relative_to(Path(config.TASKS).resolve()))
+        self.assertFalse(tdir.is_relative_to(real_tasks),
+                         f"каталог задачи песочницы {tdir} — в {real_tasks}")
+        self.assertFalse((real_tasks / self.TASK).exists())
+
+
 class MergeOnlyFromMergeGateTest(FsmTest):
     """Инвариант 12 (ред. ADR-0006): в main мержит только `approve` из
     merge_gate.
@@ -2022,9 +2042,11 @@ class CiJobsByPushClassInvariantTest(unittest.TestCase):
     потолка ожидания. Три проверяемых свойства файла:
 
     1. под `on:` нет ключей `paths` / `paths-ignore`;
-    2. job `python` не несёт условия, исключающего `refs/heads/task/`,
-       и не построен как `== 'true'` по output соседнего job (упавший
-       `changes` дал бы пустой output и молча снял тесты — fail-open);
+    2. job `python` и вынесенный из него `python-min` (SPEC
+       01M41M6KGWA9PJ6G1KPDC6XY70) не несут условия, исключающего
+       `refs/heads/task/`, и не построены как `== 'true'` по output
+       соседнего job (упавший `changes` дал бы пустой output и молча снял
+       тесты — fail-open);
     3. job `guard` не несёт условия, исключающего `refs/heads/artifact/`
        (ради этой ветки триггер и заводился, SPEC T094, требование 7).
 
@@ -2068,7 +2090,8 @@ class CiJobsByPushClassInvariantTest(unittest.TestCase):
         for ln in on:
             if re.match(r"\s+paths(-ignore)?:", ln):
                 found.append(f"фильтр путей под on: — {ln.strip()}")
-        for job, forbidden in (("python", "task/"), ("guard", "artifact/")):
+        for job, forbidden in (("python", "task/"), ("python-min", "task/"),
+                               ("guard", "artifact/")):
             block = cls._job_block(text, job)
             if not block:
                 found.append(f"job {job} не найден")
@@ -2077,8 +2100,8 @@ class CiJobsByPushClassInvariantTest(unittest.TestCase):
             for ln in own_if:
                 if forbidden in ln:
                     found.append(f"job {job}: условие исключает {forbidden!r} — {ln.strip()}")
-                if job == "python" and "== 'true'" in ln:
-                    found.append(f"job python: условие fail-open (== 'true') — {ln.strip()}")
+                if job != "guard" and "== 'true'" in ln:
+                    found.append(f"job {job}: условие fail-open (== 'true') — {ln.strip()}")
         return found
 
     def test_repo_ci_workflow_keeps_a_run_for_every_push(self):
```
