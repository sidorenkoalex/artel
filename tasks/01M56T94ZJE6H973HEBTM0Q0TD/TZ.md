---
task: 01M56T94ZJE6H973HEBTM0Q0TD
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Неустойчивый тест предела полного прогона: две найденные причины, детерминированно

# Неустойчивый тест предела полного прогона: две найденные причины, детерминированно

## Факты

`tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py::SuiteRunProfileLimitTest::test_ac5_suite_run_cuts_at_profile_limit_and_reports_it` краснел на CI пять раз при зелёном коде (07.10, 11.10, 13.10, 17.10 — CI main 6fbeaa8d, 18.10 — CI main 96972e61, «N=12»); каждый раз — ручной повтор CI. Задача 01M55VG9Q5A5341ZED8NRJKVTC нашла обе причины и ликвидирована решением Оператора 18.10: её критерий «50 прогонов под нагрузкой» оказался слишком тяжёлым для шага роли (серии с 14–17 процессами нагрузки держали машину и роняли полные наборы других задач).

Установленные причины (SPEC и записка developer задачи 01M55VG9Q5):
1. Строка отчёта «не уложился» начинается со случайного id задачи фикстуры (`orchestrator/suite_run.py:439`, `render`); утверждение «в строке нет отдельно стоящего значения config» (`:621-622`, `COPY_LIMIT = 60`, `standalone` — `:119-120`) ложно срабатывает, когда в id между буквами оказывается «60» (`standalone` не считает буквы границей). Это причина падения 17.10.
2. Гонка часов в подмене времени: пробник ветки стартовал раньше первого чтения часов в `Popen._wait`, предел вычислялся от более раннего момента, и обрыв не наступал (сигнатура 07.10 «пробник не стартовал до обрыва»).

Тест сегодня держит исход на реальных часах: обрыв через N = 11–13 с реального времени, пробник на 100 с, `--wait 1` с таймаутом вызова 100 с (`:606-614`).

## Требуется

1. Данные фикстуры (id задачи, имя проекта, номер прогона), попадающие в строку «не уложился», не могут дать в ней отдельно стоящее значение config ни при каком зерне — правкой фикстуры, не правкой утверждения.
2. Свойство теста (фоновый `suite-run` обрывает прогон по пределу профиля N и называет N, а не значение config) доказывается без зависимости от реального времени: подменяется только источник времени или таймаута; обрыв выполняет настоящий код копии пульта (`orchestrator/acceptance.py:1598`, `proc.wait(timeout=limit[0])` в `_run_full_suite_to_log`; путь `suite_run.py:579-581` → `acceptance.py:1538-1540`), функция и `proc.wait` исполняются настоящими. Гонка часов закрыта.
3. Ни одно ожидание по реальным часам, от которого зависит исход, не длиннее 5 с; пределы `cli(timeout=…)` и `--wait` — страховочные потолки.
4. Утверждения метода не удаляются и не ослабляются; мутации из докстринга (`:601-604`) тест ловит. Правка смерженного долгоживущего файла — по общим правилам `tests/` и гейта неослабления.
5. Нагрузочных серий в шаге роли нет: устойчивость доказывается детерминированно (подмена часов, замороженный пробник, фиксированное зерно по нескольким значениям).

Критерии приёмки:
- при любом зерне фикстуры строка отчёта не содержит отдельно стоящего значения config;
- исход теста не зависит от реального времени и нагрузки (детерминированная проверка, не серия прогонов);
- мутации из докстринга тест по-прежнему ловит.

Материалы: исходная точка — правка задачи 01M55VG9Q5 (ветка ликвидирована; файл теста 7/7 и планка 10/11 зелёные, красна была только серия 50/50). Диф от `main` 0180d1df:

```diff
diff --git a/tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py b/tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py
index 047cf6f1..5d22dae9 100644
--- a/tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py
+++ b/tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py
@@ -15,7 +15,8 @@
 в корне песочницы; `config.ROOT` копии считается от её `config.py`, и её
 пути — те же, что подменены песочницей) для задачи внешнего проекта с
 клоном и bare `origin` (`tests/sandbox.py::make_project_repo`); в конец
-`config.py` копии дописаны параллель 1 и предел прогона сценария.
+`config.py` копии дописаны параллель 1, предел прогона сценария и часы
+`proc.wait` прогона pytest (`COPY_CLOCK`).
 
 Пределы, имена и времена держания — от зерна; зерно печатается и входит
 в текст провала.
@@ -44,6 +45,7 @@ from tests.sandbox import (RealGitSandbox, capture, make_project_repo,
 CODE_ROOT = Path(acceptance.__file__).resolve().parent.parent
 ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
 LETTERS = "abcdefghijkmnpqrstuvwxyz"
+ID_LETTERS = "".join(ch for ch in ALPHABET if not ch.isdigit())
 PROFILE_HEAD = "    test_profile:\n"
 
 PROBE_TEST = '''import json, os, time
@@ -53,7 +55,8 @@ def note(event):
     with open({records!r}, "a", encoding="utf-8") as fh:
         fh.write(json.dumps({{"event": event, "at": time.time(),
                               "pid": os.getpid(),
-                              "ppid": os.getppid()}}) + "\\n")
+                              "ppid": os.getppid(),
+                              "pgid": os.getpgid(0)}}) + "\\n")
 
 
 def test_{name}():
@@ -115,6 +118,75 @@ PROJECT_ENTRY = """  {name}:
       mutation_claim_scope: [tests/test_*.py]
 """
 
+# Часы `proc.wait` прогона pytest в копии пульта (SPEC
+# 01M55VG9Q5A5341ZED8NRJKVTC, требование 1): настоящий `Popen.wait` с
+# переданным ему пределом считает время по `subprocess._time`; на время
+# такого вызова часы стоят, а когда пробник прогона (его группа процессов)
+# записал «start», показывают ровно на предел профиля N больше — обрыв
+# делает сам `Popen.wait` копии, без N секунд реального времени и без
+# зависимости от того, сколько пробник ждал процессора. Предел, отличный от
+# N, часы не переводят и отпускают пробник: прогон кончается сам, отчёта
+# «не уложился» нет.
+COPY_CLOCK = '''
+
+# Песочница теста предела полного прогона: часы proc.wait прогона pytest.
+import json as _sandbox_json
+import subprocess as _sandbox_subprocess
+import threading as _sandbox_threading
+
+_sandbox_call = _sandbox_threading.local()
+_sandbox_real_clock = _sandbox_subprocess._time
+_sandbox_real_wait = _sandbox_subprocess.Popen.wait
+
+
+def _sandbox_probe_started(pgid):
+    try:
+        with open({records!r}, encoding="utf-8") as fh:
+            lines = fh.read().splitlines()
+    except FileNotFoundError:
+        return False
+    for line in lines:
+        try:
+            rec = _sandbox_json.loads(line)
+        except ValueError:
+            continue
+        if rec.get("event") == "start" and rec.get("pgid") == pgid:
+            return True
+    return False
+
+
+def _sandbox_clock():
+    call = getattr(_sandbox_call, "state", None)
+    if call is None:
+        return _sandbox_real_clock()
+    # После старта пробника каждое чтение часов — ещё N секунд: срок
+    # `endtime` вызова, прочитанный и до, и после старта (пробник успел
+    # раньше, чем `Popen.wait` впервые спросил часы), истекает на следующем
+    # же чтении.
+    if call["cut"] and _sandbox_probe_started(call["pgid"]):
+        call["at"] += {limit!r}
+    return call["at"]
+
+
+def _sandbox_wait(self, timeout=None):
+    if timeout is None or "pytest" not in list(self.args):
+        return _sandbox_real_wait(self, timeout)
+    cut = timeout == {limit!r}
+    if not cut:
+        with open({stop!r}, "w", encoding="utf-8") as fh:
+            fh.write("stop")
+    _sandbox_call.state = {{"at": _sandbox_real_clock(), "pgid": self.pid,
+                           "cut": cut}}
+    try:
+        return _sandbox_real_wait(self, timeout)
+    finally:
+        _sandbox_call.state = None
+
+
+_sandbox_subprocess._time = _sandbox_clock
+_sandbox_subprocess.Popen.wait = _sandbox_wait
+'''
+
 
 def standalone(number: int, text: str) -> bool:
     return re.search(rf"(?<![\d.:]){number}(?![\d.:])", text) is not None
@@ -514,6 +586,13 @@ class SuiteRunLimitSandbox(ProbeSandbox):
 
     COPY_LIMIT = 60
 
+    def task_id(self) -> str:
+        # Id стоит в начале строки отчёта «не уложился», а `standalone`
+        # считает число отдельно стоящим и между буквами: цифры id давали
+        # там `COPY_LIMIT` (…K60X…) — около 1% зёрен (SPEC
+        # 01M55VG9Q5A5341ZED8NRJKVTC, требование 3).
+        return "01M" + "".join(self.rng.choice(ID_LETTERS) for _ in range(23))
+
     def setUp(self):
         super().setUp()
         for name in ("orchestrator", "scripts"):
@@ -531,7 +610,13 @@ class SuiteRunLimitSandbox(ProbeSandbox):
 
     def add_project_task(self, limit: int) -> tuple:
         """(id, рабочая копия) задачи проекта с `full_suite_timeout_sec:
-        limit`; база — один быстрый тест, ветка добавляет пробник."""
+        limit`; база — один быстрый тест, ветка добавляет пробник. Часы
+        `proc.wait` прогона pytest копии пульта переводятся на `limit`
+        (`COPY_CLOCK`)."""
+        with open(self.root / "orchestrator" / "config.py", "a",
+                  encoding="utf-8") as fh:
+            fh.write(COPY_CLOCK.format(records=str(self.records),
+                                       stop=str(self.stop_file), limit=limit))
         target = "p" + self.word()
         origin = config.PROJECTS / target / "origin.git"
         entry = PROJECT_ENTRY.format(name=target, origin=origin,
@@ -586,6 +671,21 @@ class SuiteRunLimitSandbox(ProbeSandbox):
             kill_group(proc.pid)
         return proc.returncode, raw.decode("utf-8", errors="replace")
 
+    def run_traces(self, task_id: str) -> str:
+        """Записи пробника и файлы `suite-run` задачи — для текста провала:
+        по одному коду выхода `--wait` исход не восстановить (копилка
+        07.10)."""
+        try:
+            records = self.records.read_text(encoding="utf-8")
+        except OSError:
+            records = "(нет)\n"
+        parts = [f"записи пробника:\n{records}"]
+        logs = self.root / ".artel" / "logs" / "suite-run" / task_id
+        for path in sorted(logs.glob("*")) if logs.is_dir() else ():
+            text = path.read_bytes().decode("utf-8", errors="replace")
+            parts.append(f"{path.name}:\n{text[-4000:]}")
+        return "\n".join(parts)
+
 
 class SuiteRunProfileLimitTest(SuiteRunLimitSandbox):
 
@@ -594,14 +694,19 @@ class SuiteRunProfileLimitTest(SuiteRunLimitSandbox):
 
         Сценарий: в `config.py` копии пульта предел — 60 с; в профиле
         проекта задачи `full_suite_timeout_sec: N` (11–13 с, от зерна);
-        пробник ветки держится дольше 60 с. Запуск `suite-run`, затем
+        пробник ветки держится дольше 60 с. Часы `proc.wait` прогона pytest
+        копии (`COPY_CLOCK`) стоят, пока пробник не стартовал, и тогда
+        переходят ровно на N: обрыв делает настоящий `Popen.wait` копии без
+        N секунд реального времени. Запуск `suite-run`, затем
         `suite-run --wait 1`: отчёт несёт «не уложился» и N в той же
         строке, без 60.
 
         Ловит мутацию: фоновый прогон `suite-run` берёт
         `config.FULL_SUITE_TIMEOUT_SEC` (подполе профиля читает только
-        гейт) — прогон за минуту ожидания не оборван, отчёта нет; либо
-        отчёт о таймауте печатает значение config, а не N.
+        гейт) либо `proc.wait` получает предел, отличный от N (config,
+        N ± k) — часы его не переводят, пробник отпущен, прогон кончается
+        сам, строки «не уложился» нет; либо отчёт о таймауте печатает
+        значение config, а не N.
         """
         limit = self.rng.randint(11, 13)
         task_id, wt = self.add_project_task(limit)
@@ -613,7 +718,8 @@ class SuiteRunProfileLimitTest(SuiteRunLimitSandbox):
         code, report = self.cli("suite-run", task_id, "--wait", "1", cwd=wt,
                                 timeout=100)
         context = self.note(f"N={limit}; отчёт (код {code}):\n{report}\n"
-                            f"targets.yaml:\n{self.targets_text}")
+                            f"targets.yaml:\n{self.targets_text}\n"
+                            f"{self.run_traces(task_id)}")
         self.assertTrue(self.events("start"), context)
         lines = [line for line in report.splitlines() if "не уложился" in line]
         self.assertTrue(lines, context)
```

Зоны: `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py`, `tests/`.

Только чтение: `orchestrator/suite_run.py`, `orchestrator/acceptance.py`, `orchestrator/config.py`, `docs/backlog.md`. Правка вне зон — эскалация до SPEC.

Не входит: команда пульта для повтора CI main (отдельная строка бэклога); другие неустойчивые тесты; нагрузочные серии.

Рамка: $25. Набор моделей — по умолчанию.
