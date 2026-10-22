"""Родитель параллельного прогона канарейки: очередь, argv дочернего, общий итог, сигнал и реестр.

Группа: разовый
Красен до реализации: --parallel ещё не разбирается — прогон идёт последовательно в процессе родителя, подменённое ведение родителя роняет сценарий, дочерних процессов нет; констант PARALLEL_CHILD_LIMIT, PARALLEL_STOP_GRACE_SEC и функции _wait_child (имена — ANSWER-1) в canary ещё нет — AttributeError.

Сценарии идут через `artel._cmd_canary([... "--parallel"])` в главном потоке;
дочерний подменяется на создании процесса (`_harness.py`). Срок остановки и
функция ожидания дочернего подменяются по именам, назначенным ответом
Оператора (ANSWER-1): `canary.PARALLEL_STOP_GRACE_SEC`, `canary._wait_child`.
Файл держит приёмку задачи через закрытые швы `canary` (`_run_one_task`,
`_set_plan`, `_resolve_target_sha`, `_wait_child`) — правила долгоживущих файлов их запрещают, поэтому
группа разовая; долгоживущую проверку свойства несут тесты разработчика по
требованию 9 SPEC.
"""
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _harness import (CanaryParallelSandbox, FULL_SHA, PARALLEL_SUFFIX,  # noqa: E402
                      SAFETY_SEC, SET_NAME, SHORT_SHA, SUMMARY, flag_value)
from orchestrator import canary, config, liveness, store  # noqa: E402

# Подменённый срок остановки (SPEC, требование 9): целое, чтобы причина
# «снят SIGKILL после <N> с» читалась однозначно.
GRACE = 1
WAIT_ERROR = "подменённый сбой ожидания"

TEMPLATES3 = ["alfa", "beta", "gamma"]
HEADER = re.compile(r"^\[canary\] (\w+): процесс (\d+) завершён с кодом (-?\d+), "
                    r"журнал (.+)$", re.M)


def _reason_line(stdout: str, template: str, reason: str) -> bool:
    return any(template in line and reason in line for line in stdout.splitlines())


class QueueTest(CanaryParallelSandbox):
    def test_ac6_at_most_two_children_third_after_one_finished(self):
        """`--k 3`: первые два дочерних живы вместе, третий — после конца одного.

        Координатор отпускает `alfa` только после запуска двух; к запуску
        `gamma` завершённым обязан быть `alfa`, живым — только `beta`. Порядок
        запуска — порядок прогона.

        Ловит мутацию: родитель запускает все шаблоны сразу без предела — к
        запуску `gamma` не завершён ни один; либо предел 1 — второй дочерний
        не запускается, пока жив первый.
        """
        self.children = {n: {"mode": "exit", "code": 0} for n in TEMPLATES3}

        def script(c):
            c.wait_spawns(2)
            c.release("alfa")
            c.wait_spawns(3)
            c.release("beta")
            c.release("gamma")

        run = self.run_parallel(TEMPLATES3, script)
        self.assert_clean(run)
        self.assertEqual([s.template for s in run.attempts], TEMPLATES3)
        by = {s.template: s for s in run.spawns}
        self.assertEqual(by["alfa"].unfinished_before, [])
        self.assertEqual(by["beta"].unfinished_before, ["alfa"], run.describe())
        self.assertEqual(by["gamma"].unfinished_before, ["beta"], run.describe())
        # Имя константы предела назначено ответом Оператора (ANSWER-1).
        self.assertEqual(canary.PARALLEL_CHILD_LIMIT, 2)

    def test_ac7_nonzero_child_does_not_stop_queue(self):
        """Дочерний `alfa` выходит с кодом 3 — очередь запускает `gamma`.

        Ловит мутацию: ненулевой код дочернего обрывает очередь (как `break`
        после первого провала) — третий шаблон не запускается.
        """
        self.children = {"alfa": {"mode": "exit", "code": 3},
                         "beta": {"mode": "exit", "code": 0},
                         "gamma": {"mode": "exit", "code": 0}}

        def script(c):
            c.wait_spawns(2)
            c.release("alfa")
            c.wait_spawns(3)
            c.release("beta")
            c.release("gamma")

        run = self.run_parallel(TEMPLATES3, script)
        self.assert_clean(run)
        self.assertEqual([s.template for s in run.spawns], TEMPLATES3)

    def test_ac7_unstarted_child_gets_red_row_and_queue_continues(self):
        """Создание процесса `alfa` бросает исключение — красная строка, очередь дальше.

        Строка `alfa` — по образцу `_report_drive_failure`, вывод несёт причину
        «процесс задачи не запущен: <ошибка>»; `beta` и `gamma` запущены.

        Ловит мутацию: исключение запуска пробрасывается наружу и роняет
        прогон (дальше никого) либо глотается без строки — шаблон пропадает из
        итога.
        """
        self.children = {"alfa": {"spawn_error": "подменённый сбой запуска"},
                         "beta": {"mode": "exit", "hold": False},
                         "gamma": {"mode": "exit", "hold": False}}
        run = self.run_parallel(TEMPLATES3)
        self.assert_clean(run)
        self.assertEqual([s.template for s in run.attempts], TEMPLATES3)
        self.assertEqual([s.template for s in run.spawns], ["beta", "gamma"])
        rows = self.rows(run.stamp)
        alfa = [r for r in rows if r["title"] == "alfa"]
        self.assertEqual(len(alfa), 1, rows)
        self.assert_red_row(alfa[0], run.stamp, "alfa")
        self.assertTrue(_reason_line(run.stdout, "alfa", "процесс задачи не запущен: ")
                        and "подменённый сбой запуска" in run.stdout, run.describe())


class ChildArgvTest(CanaryParallelSandbox):
    def test_ac8_child_argv_full_sha_stamp_set_summary_and_log_path(self):
        """Короткий `--sha` команды — argv дочернего несёт полный sha записи родителя.

        argv каждого дочернего: интерпретатор с `-u`, `run-task` и ровно пять
        флагов — `--stamp` = `run_stamp`, `--sha`/`--set` = поля `sha`/
        `set_name` записи родителя (полный sha, не значение флага), `--summary`
        = сводка плана, `--template` = путь шаблона пула. Вывод дочернего — в
        `<LOGS>/canary/<run_stamp>-<шаблон>.log`. К origin — одно обращение.

        Ловит мутацию: дочернему передаётся значение флага `--sha` команды
        (короткое) вместо проверяемого sha; либо журнал открыт под другим
        именем (без `run_stamp`); либо `-u` потерян.
        """
        self.children = {"alfa": {"mode": "exit", "hold": False},
                         "beta": {"mode": "exit", "hold": False}}
        run = self.run_parallel(["alfa", "beta"])
        self.assert_clean(run)
        self.assertEqual(self.resolve_calls, [SHORT_SHA])
        self.assertEqual(sorted(s.template for s in run.spawns), ["alfa", "beta"])
        for spawn in run.spawns:
            with self.subTest(spawn.template):
                argv = spawn.argv
                cut = argv.index("run-task")
                self.assertIn("-u", argv[:cut], argv)
                rest = argv[cut + 1:]
                self.assertEqual(sorted(rest[0::2]), sorted(
                    ["--stamp", "--template", "--sha", "--set", "--summary"]), argv)
                record = spawn.parent_record
                self.assertIsNotNone(record, "записи родителя нет при запуске")
                self.assertEqual(flag_value(rest, "--stamp"), run.stamp)
                self.assertEqual(record["run_stamp"], run.stamp)
                self.assertEqual(flag_value(rest, "--sha"), FULL_SHA)
                self.assertEqual(flag_value(rest, "--sha"), record["sha"])
                self.assertEqual(flag_value(rest, "--set"), record["set_name"])
                self.assertEqual(flag_value(rest, "--set"), SET_NAME)
                self.assertEqual(flag_value(rest, "--summary"), SUMMARY)
                self.assertEqual(Path(flag_value(rest, "--template")).resolve(),
                                 (self.pool / f"{spawn.template}.md").resolve())
                log = self.log_path(run.stamp, spawn.template)
                self.assertTrue(log.is_file(), f"нет журнала {log}")
                self.assertIn(f"дочерний {spawn.template}: начало",
                              log.read_text(encoding="utf-8"))


class SummaryTest(CanaryParallelSandbox):
    def test_ac10_one_first_line_whole_blocks_and_finish_line_after_all(self):
        """Две настоящие подкоманды `run-task` пишут строки; итог родителя.

        Первая строка вывода — одна, дополнена « параллельно: не более 2
        процессов»; блок каждой задачи — заголовок «[canary] <шаблон>: процесс
        <pid> завершён с кодом 0, журнал <путь>» и сразу целиком содержимое
        журнала; строка «прогон <run_stamp> завершён» — одна и после всех
        блоков. Строки задач несут один `run_stamp`, набор, сводку и sha;
        `canary_baseline` не изменилась.

        Ловит мутацию: родитель пересылает вывод дочерних построчно по мере
        поступления — блок журнала разорван; либо строка «завершён» печатается
        до блоков; либо первая строка печатается каждым дочерним.
        """
        self.children = {"alfa": {"mode": "real", "row": True},
                         "beta": {"mode": "real", "row": True}}
        store.set_canary_baseline(store.db(), "alfa", 3, 1.0, 0, SET_NAME)
        baseline = self.baseline_rows()

        def script(c):
            c.wait_spawns(2)
            c.reach("alfa")
            c.reach("beta")
            c.release("beta")
            c.release("alfa")

        run = self.run_parallel(["alfa", "beta"], script)
        self.assert_clean(run)
        self.assertEqual(run.code, 0, run.describe())
        lines = run.stdout.splitlines()
        firsts = [line for line in lines
                  if line.startswith(f"[canary] прогон {run.stamp}:")]
        self.assertEqual(len(firsts), 1, run.describe())
        self.assertEqual(lines[0], firsts[0])
        self.assertTrue(lines[0].endswith(PARALLEL_SUFFIX), lines[0])
        self.assertIn("alfa, beta", lines[0])
        finish = f"[canary] прогон {run.stamp} завершён"
        self.assertEqual(lines.count(finish), 1, run.describe())
        finish_at = run.stdout.index(finish)
        pids = {s.template: s.pid for s in run.spawns}
        for template in ("alfa", "beta"):
            with self.subTest(template):
                log = self.log_path(run.stamp, template)
                text = log.read_text(encoding="utf-8")
                self.assertIn(f"дочерний {template}: ведение завершено", text)
                header = (f"[canary] {template}: процесс {pids[template]} "
                          f"завершён с кодом 0, журнал {log}")
                block = header + "\n" + text.rstrip("\n")
                self.assertIn(block, run.stdout, run.describe())
                self.assertLess(run.stdout.index(block) + len(block), finish_at)
        rows = self.rows(run.stamp)
        self.assertEqual(sorted(r["title"] for r in rows), ["alfa", "beta"])
        for row in rows:
            self.assertEqual((row["run_stamp"], row["set_name"], row["models_summary"],
                              row["main_sha"], row["verdict"]),
                             (run.stamp, SET_NAME, SUMMARY, FULL_SHA, "green"))
        self.assertEqual(self.baseline_rows(), baseline)


class MissingRowTest(CanaryParallelSandbox):
    def test_ac11_child_without_row_gets_red_row_and_nonzero_exit(self):
        """Дочерние вышли с кодами 0 и 5 без строки прогона — красные строки родителя.

        По одной строке на шаблон с полями `_report_drive_failure` (`task_id`
        и `expected_escalation` — None, коммит пуст), в выводе — причина
        «процесс задачи завершился с кодом <n> без строки прогона»; код
        выхода родителя ненулевой.

        Ловит мутацию: родитель смотрит только на код выхода — дочерний с кодом
        0 без строки считается зелёным, ни строки, ни ненулевого кода.
        """
        self.children = {"alfa": {"mode": "exit", "code": 0, "hold": False},
                         "beta": {"mode": "exit", "code": 5, "hold": False}}
        run = self.run_parallel(["alfa", "beta"])
        self.assert_clean(run)
        self.assertNotIn(run.code, (0, None), run.describe())
        rows = self.rows(run.stamp)
        for template, code in (("alfa", 0), ("beta", 5)):
            with self.subTest(template):
                mine = [r for r in rows if r["title"] == template]
                self.assertEqual(len(mine), 1, rows)
                self.assert_red_row(mine[0], run.stamp, template)
                self.assertTrue(_reason_line(
                    run.stdout, template,
                    f"процесс задачи завершился с кодом {code} без строки прогона"),
                    run.describe())

    def test_ac11_all_children_zero_with_rows_exit_zero(self):
        """Все шаблоны запущены, все дочерние с кодом 0 и строкой — код 0, красных нет.

        Ловит мутацию: родитель пишет красную строку и после дочернего,
        записавшего свою (проверка «нет строки» по другому `run_stamp`), — дубль
        и ненулевой код.
        """
        self.children = {"alfa": {"mode": "real", "row": True, "hold": False},
                         "beta": {"mode": "real", "row": True, "hold": False}}
        run = self.run_parallel(["alfa", "beta"])
        self.assert_clean(run)
        self.assertEqual(run.code, 0, run.describe())
        rows = self.rows(run.stamp)
        self.assertEqual(sorted(r["title"] for r in rows), ["alfa", "beta"])
        self.assertTrue(all(r["verdict"] == "green" for r in rows), rows)

    def test_ac11_unstarted_child_makes_exit_nonzero(self):
        """Один шаблон не запустился, остальные с кодом 0 и строкой — код ненулевой.

        Ловит мутацию: код выхода считается только по завершившимся дочерним —
        не запущенный шаблон его не портит, прогон выходит с 0.
        """
        self.children = {"alfa": {"spawn_error": "подменённый сбой запуска"},
                         "beta": {"mode": "real", "row": True, "hold": False}}
        run = self.run_parallel(["alfa", "beta"])
        self.assert_clean(run)
        self.assertEqual([s.template for s in run.spawns], ["beta"])
        self.assertNotIn(run.code, (0, None), run.describe())

    def test_ac11_red_row_for_child_without_row_on_parent_signal(self):
        """SIGTERM родителю: дочерний без строки получает красную строку, с строкой — нет.

        `alfa` — настоящая подкоманда (пишет «оборвана сигналом»), `beta` —
        простой процесс, умирающий от SIGTERM без строки: родитель пишет `beta`
        красную строку с причиной «процесс задачи завершился с кодом … без
        строки прогона», `alfa` второй строки не получает.

        Ловит мутацию: на пути сигнала родитель пропускает сверку строк —
        `beta` пропадает из итога; либо пишет красную строку всем, давая `alfa`
        дубль.
        """
        self.children = {"alfa": {"mode": "real"}, "beta": {"mode": "exit"}}

        def script(c):
            c.wait_spawns(2)
            c.reach("alfa")
            c.reach("beta")
            c.signal_parent(signal.SIGTERM)

        run = self.run_parallel(["alfa", "beta"], script)
        self.assert_clean(run)
        self.assertEqual(run.code, 128 + signal.SIGTERM, run.describe())
        rows = self.rows(run.stamp)
        alfa = [r for r in rows if r["title"] == "alfa"]
        beta = [r for r in rows if r["title"] == "beta"]
        self.assertEqual([r["outcome"] for r in alfa], ["оборвана сигналом SIGTERM"])
        self.assertEqual(len(beta), 1, rows)
        self.assert_red_row(beta[0], run.stamp, "beta")
        self.assertTrue(any("beta" in line and "процесс задачи завершился с кодом" in line
                            and "без строки прогона" in line
                            for line in run.stdout.splitlines()), run.describe())


class ParentSignalTest(CanaryParallelSandbox):
    def test_ac12_sigterm_stops_children_skips_queue_and_exits_143(self):
        """SIGTERM родителю при двух ведущих задачах и третьей в очереди.

        Дочерним идёт SIGTERM (их строки «оборвана сигналом SIGTERM»), `gamma`
        не запускается и строки не получает, строки «завершён» нет, код —
        128 + SIGTERM, реестр после прогона пуст, `canary_baseline` прежняя.

        Ловит мутацию: обработчик сигнала родителя только выходит, не снимая
        дочерних, — их строк «оборвана» нет; либо очередь продолжает запуск
        `gamma` после сигнала.
        """
        self.children = {n: {"mode": "real"} for n in TEMPLATES3}
        store.set_canary_baseline(store.db(), "alfa", 3, 1.0, 0, SET_NAME)
        baseline = self.baseline_rows()

        def script(c):
            c.wait_spawns(2)
            c.reach("alfa")
            c.reach("beta")
            c.signal_parent(signal.SIGTERM)

        run = self.run_parallel(TEMPLATES3, script)
        self.assert_clean(run)
        self.assertEqual(run.code, 128 + signal.SIGTERM, run.describe())
        self.assertEqual([s.template for s in run.attempts], ["alfa", "beta"])
        rows = self.rows(run.stamp)
        self.assertEqual(sorted((r["title"], r["outcome"]) for r in rows),
                         [("alfa", "оборвана сигналом SIGTERM"),
                          ("beta", "оборвана сигналом SIGTERM")])
        self.assertNotIn(f"[canary] прогон {run.stamp} завершён", run.stdout)
        self.assertEqual(self.listing(), [])
        self.assertEqual(self.baseline_rows(), baseline)

    def test_ac14_sighup_during_stop_does_not_interrupt_it(self):
        """SIGHUP приходит, пока дочерние обрабатывают SIGTERM родителя.

        Оба дочерних держат свой обработчик SIGTERM до команды координатора;
        в это время родителю идёт SIGHUP. Остановка доходит до конца: оба
        дочерних пожаты, у обоих красные строки, реестр пуст, код —
        128 + SIGTERM (первый сигнал), а не 128 + SIGHUP.

        Ловит мутацию: остановка не под откладыванием сигналов — SIGHUP рвёт
        ожидание, дочерние остаются без красных строк, код 129.
        """
        self.children = {n: {"mode": "exit", "term_hold": True} for n in ("alfa", "beta")}

        def script(c):
            c.wait_spawns(2)
            c.reach("alfa")
            c.reach("beta")
            c.signal_parent(signal.SIGTERM)
            c.reach("alfa", term=True)
            c.reach("beta", term=True)
            c.signal_parent(signal.SIGHUP)
            c.release("alfa", term=True)
            c.release("beta", term=True)

        run = self.run_parallel(["alfa", "beta"], script)
        self.assert_clean(run)
        self.assertEqual(run.code, 128 + signal.SIGTERM, run.describe())
        self.assertEqual(sorted(c["template"] for c in run.calls_of("term")),
                         ["alfa", "beta"])
        for spawn in run.spawns:
            self.assertIsNotNone(spawn.proc.returncode,
                                 f"{spawn.template} не пожат родителем")
        rows = self.rows(run.stamp)
        for template in ("alfa", "beta"):
            mine = [r for r in rows if r["title"] == template]
            self.assertEqual(len(mine), 1, rows)
            self.assert_red_row(mine[0], run.stamp, template)
        self.assertEqual(self.listing(), [])


class RegistryTest(CanaryParallelSandbox):
    def test_ac15_parent_record_and_mark_live_until_children_done(self):
        """Запись и метка родителя есть у каждого дочернего до его выхода — штатно и по сигналу.

        Штатный прогон: каждый дочерний перед выходом видит запись
        `<run_stamp>-<pid родителя>.json` и метку. Прогон с SIGTERM: каждый
        дочерний в своём обработчике SIGTERM видит их же. После прогона реестр
        пуст.

        Ловит мутацию: родитель снимает свою запись сразу после запуска всех
        дочерних (или до остановки дочерних на сигнале) — дочерний видит
        реестр без записи родителя.
        """
        for case in ("штатно", "сигнал"):
            with self.subTest(case):
                if case == "штатно":
                    self.children = {"alfa": {"mode": "exit"}, "beta": {"mode": "exit"}}
                    kind = "exit"

                    def script(c):
                        c.wait_spawns(2)
                        c.release("alfa")
                        c.release("beta")
                else:
                    self.children = {"gamma": {"mode": "exit", "term_hold": True},
                                     "delta": {"mode": "exit", "term_hold": True}}
                    kind = "term"

                    def script(c):
                        c.wait_spawns(2)
                        c.reach("gamma")
                        c.reach("delta")
                        c.signal_parent(signal.SIGTERM)
                        c.release("gamma", term=True)
                        c.release("delta", term=True)

                names = list(self.children)
                self.spawns.clear()
                self.attempts.clear()
                if getattr(self, "calls_path", None) and self.calls_path.exists():
                    self.calls_path.unlink()
                run = self.run_parallel(names, script)
                self.assert_clean(run)
                seen = {c["template"]: (c["record"], c["mark"])
                        for c in run.calls_of(kind)}
                self.assertEqual(seen, {n: (True, True) for n in names},
                                 run.describe())
                self.assertEqual(self.listing(), [])

    def test_ac15_parent_killed_run_stays_live_by_child_record(self):
        """Гибель родителя смоделирована: запись родителя убрана, в метке мёртвый pid.

        Пока дочерние ведут задачи, координатор убирает запись родителя и
        пишет в метку pid завершившегося процесса: `live_run_note(
        default_set_only=True)` при наборе по умолчанию не `None` и называет
        `run_stamp` — прогон держится записями дочерних.

        Ловит мутацию: дочерний пишет в запись не набор родителя (`--set`
        берётся не из `plan.name`) — запись дочернего не набора по умолчанию,
        окно мержа открыто.
        """
        self.set_name = config.CANARY_DEFAULT_SET
        dead = subprocess.Popen([sys.executable, "-c", ""])
        dead.wait()
        self.children = {"alfa": {"mode": "real"}, "beta": {"mode": "real"}}
        seen = {}

        def script(c):
            c.wait_spawns(2)
            c.reach("alfa")
            c.reach("beta")
            stamp = flag_value(c.h.spawns[0].argv, "--stamp")
            (self.registry / f"{stamp}-{os.getpid()}.json").unlink(missing_ok=True)
            (self.registry / f"{stamp}.lock").write_text(f"{dead.pid}\n",
                                                        encoding="utf-8")
            seen["note"] = canary.live_run_note(default_set_only=True)
            c.release("alfa")
            c.release("beta")

        run = self.run_parallel(["alfa", "beta"], script)
        self.assert_clean(run)
        self.assertIsNotNone(seen.get("note"), run.describe())
        self.assertIn(run.stamp, seen["note"])

    def test_ac16_dropped_mark_makes_next_child_refuse_with_red_row(self):
        """`canary live --drop` снимает метку без записей — следующий дочерний отказывает.

        Пока `alfa` и `beta` ведут задачи, записи реестра убраны и метка снята
        `cmd_canary_live(drop=…)`; запущенный затем `gamma` отказывает по
        сверке метки Б-1а: ни ведения, ни клона, родитель пишет ему красную
        строку.

        Ловит мутацию: родитель после завершения `gamma` с ненулевым кодом без
        строки не пишет красную строку — шаблон пропадает из итога.
        """
        self.children = {"alfa": {"mode": "real", "row": True},
                         "beta": {"mode": "real", "row": True},
                         "gamma": {"mode": "real", "hold": False}}
        seen = {}

        def script(c):
            c.wait_spawns(2)
            c.reach("alfa")
            c.reach("beta")
            stamp = flag_value(c.h.spawns[0].argv, "--stamp")
            for record in self.registry.glob(f"{stamp}-*.json"):
                record.unlink()
            canary.cmd_canary_live(drop=stamp, reason="планка: метка без записей")
            seen["mark"] = (self.registry / f"{stamp}.lock").exists()
            c.release("alfa")
            c.release("beta")
            c.wait_spawns(3)

        run = self.run_parallel(TEMPLATES3, script)
        self.assert_clean(run)
        self.assertIs(seen.get("mark"), False, run.describe())
        self.assertIn("gamma", [s.template for s in run.spawns])
        self.assertEqual(run.calls_of("drive", "gamma"), [])
        self.assertEqual(run.calls_of("clone"), [])
        gamma = [r for r in self.rows(run.stamp) if r["title"] == "gamma"]
        self.assertEqual(len(gamma), 1, run.describe())
        self.assert_red_row(gamma[0], run.stamp, "gamma")


def _kill_after_grace(c):
    """Сценарий срока: `alfa` в ведении, SIGTERM родителю, ждать конца прогона."""
    c.wait_spawns(1)
    c.reach("alfa")
    c.signal_parent(signal.SIGTERM)
    c.wait_finished()


class StopGraceTest(CanaryParallelSandbox):
    def test_ac13_term_ignoring_child_killed_only_after_grace(self):
        """Дочерний игнорирует SIGTERM — SIGKILL только после подменённого срока.

        `alfa` — настоящая подкоманда `run-task` без строки прогона, в ведении
        учитывает и игнорирует SIGTERM; родителю идёт SIGTERM, срок подменён на
        `GRACE` с. От SIGTERM дочернему до возврата родителя прошло не меньше
        срока; дочерний снят SIGKILL; у `alfa` одна красная строка родителя, в
        выводе — причина «снят SIGKILL после <N> с; группа ведения в клоне могла
        остаться — проверь doctor». Запись дочернего (её не снять самому после
        SIGKILL) снята родителем, и в этот момент метка и запись родителя целы;
        метка снята не раньше записи родителя; реестр после прогона пуст.
        Константа срока равна 60 и больше двух `GROUP_TERMINATE_GRACE_SEC`.

        Ловит мутацию: родитель шлёт SIGKILL сразу вслед за SIGTERM (срок не
        выдержан — прогон кончается раньше `GRACE` с); либо запись снятого
        SIGKILL дочернего остаётся в реестре; либо её снимают уборкой
        `_drop_live_record`, уносящей метку прогона вместе с записью.
        """
        self.assertEqual(canary.PARALLEL_STOP_GRACE_SEC, 60)
        self.assertGreater(canary.PARALLEL_STOP_GRACE_SEC,
                           2 * liveness.GROUP_TERMINATE_GRACE_SEC)
        self.patch_grace(GRACE)
        self.children = {"alfa": {"mode": "real", "ignore_term": True}}
        unlinks = self.record_unlinks()
        run = self.run_parallel(["alfa"], _kill_after_grace)
        ended = time.monotonic()
        self.assert_clean(run)
        self.assertEqual(run.code, 128 + signal.SIGTERM, run.describe())
        terms = run.calls_of("term", "alfa")
        self.assertEqual(len(terms), 1, run.describe())
        self.assertGreaterEqual(ended - terms[0]["at"], GRACE, run.describe())
        (spawn,) = run.spawns
        self.assertEqual(spawn.proc.returncode, -signal.SIGKILL, run.describe())
        alfa = [r for r in self.rows(run.stamp) if r["title"] == "alfa"]
        self.assertEqual(len(alfa), 1, run.describe())
        self.assert_red_row(alfa[0], run.stamp, "alfa")
        self.assertTrue(_reason_line(
            run.stdout, "alfa",
            f"снят SIGKILL после {GRACE} с; группа ведения в клоне могла "
            f"остаться — проверь doctor"), run.describe())
        child = f"{run.stamp}-{spawn.pid}.json"
        parent = f"{run.stamp}-{os.getpid()}.json"
        mark = f"{run.stamp}.lock"
        names = [name for name, _ in unlinks]
        self.assertIn(child, names, unlinks)
        listing = dict(unlinks)[child]
        self.assertIn(mark, listing, unlinks)
        self.assertIn(parent, listing, unlinks)
        self.assertIn(parent, names, unlinks)
        if mark in names:
            self.assertLess(names.index(parent), names.index(mark), unlinks)
        self.assertEqual(self.listing(), [])

    def test_ac19_killed_child_with_row_gets_no_duplicate(self):
        """Дочерний записал строку и затем снят SIGKILL — дубля нет.

        `alfa` — настоящая подкоманда, записавшая зелёную строку прогона, в
        ведении игнорирует SIGTERM; сигнал родителю, срок подменён, дочерний
        снят SIGKILL. За `alfa` в `canary_runs` и в файле результата ровно одна
        строка с `run_stamp` прогона — его собственная (задача и вердикт
        дочернего).

        Ловит мутацию: родитель пишет красную строку «снят SIGKILL…» любому
        снятому SIGKILL дочернему, не сверяя `canary_runs`, — у `alfa` две
        строки.
        """
        self.patch_grace(GRACE)
        self.children = {"alfa": {"mode": "real", "row": True, "ignore_term": True}}
        result = self.root / "result.json"
        run = self.run_parallel(["alfa"], _kill_after_grace,
                                extra=["--result-file", str(result)])
        self.assert_clean(run)
        self.assertEqual(run.code, 128 + signal.SIGTERM, run.describe())
        (spawn,) = run.spawns
        self.assertEqual(spawn.proc.returncode, -signal.SIGKILL, run.describe())
        alfa = [r for r in self.rows(run.stamp) if r["title"] == "alfa"]
        self.assertEqual([(r["task_id"], r["verdict"], r["outcome"]) for r in alfa],
                         [("01FIXTUREALFA", "green", "merged")], run.describe())
        runs = json.loads(result.read_text(encoding="utf-8"))["runs"]
        self.assertEqual([(r["title"], r["task_id"], r["verdict"]) for r in runs
                          if r["title"] == "alfa"],
                         [("alfa", "01FIXTUREALFA", "green")], runs)


class WaitFailureTest(CanaryParallelSandbox):
    def test_ac20_base_exception_in_wait_then_signal_during_stop(self):
        """`KeyboardInterrupt` из функции ожидания при живых дочерних, затем SIGHUP.

        `alfa` и `beta` в ведении (третий шаблон в очереди), первый вызов
        подменённой `_wait_child` бросает `KeyboardInterrupt`; дочерние держат
        свой обработчик SIGTERM, и в это время родителю идёт SIGHUP. Очередь не
        продолжена (`gamma` не запускался), остановка дошла до конца (оба
        дочерних получили SIGTERM и пожаты, реестр пуст), код выхода —
        128 + SIGHUP.

        Ловит мутацию: `KeyboardInterrupt` из ожидания выходит из родителя
        мимо остановки дочерних — дочерние живы, исход — сам `KeyboardInterrupt`;
        либо код выхода не учитывает сигнал, пришедший во время остановки.
        """
        self.children = {n: {"mode": "exit", "term_hold": True} for n in TEMPLATES3}
        fault = self.patch_wait(KeyboardInterrupt())

        def script(c):
            c.wait_spawns(2)
            c.reach("alfa")
            c.reach("beta")
            fault.ready.set()
            if not fault.raised.wait(SAFETY_SEC):
                raise AssertionError("функция ожидания дочернего не вызвана")
            c.reach("alfa", term=True)
            c.reach("beta", term=True)
            c.signal_parent(signal.SIGHUP)
            c.release("alfa", term=True)
            c.release("beta", term=True)

        run = self.run_parallel(TEMPLATES3, script)
        self.assert_clean(run)
        self.assertEqual(run.code, 128 + signal.SIGHUP, run.describe())
        self.assertEqual(sorted(fault.spawned_at_raise), ["alfa", "beta"])
        self.assertEqual([s.template for s in run.attempts], ["alfa", "beta"])
        self.assertEqual(sorted(c["template"] for c in run.calls_of("term")),
                         ["alfa", "beta"])
        for spawn in run.spawns:
            self.assertIsNotNone(spawn.proc.returncode,
                                 f"{spawn.template} не пожат родителем")
        self.assertEqual(self.listing(), [])

    def _wait_exception_run(self, children):
        """`alfa`/`beta` в ведении, первый вызов `_wait_child` бросает исключение."""
        self.children = children
        fault = self.patch_wait(RuntimeError(WAIT_ERROR))

        def script(c):
            c.wait_spawns(2)
            c.reach("alfa")
            c.reach("beta")
            fault.ready.set()
            c.wait_spawns(3)
            for template in TEMPLATES3:
                c.release(template)

        run = self.run_parallel(TEMPLATES3, script)
        self.assert_clean(run)
        terms = run.calls_of("term")
        self.assertEqual(len(terms), 1, run.describe())
        failed = terms[0]["template"]
        self.assertIn(failed, ("alfa", "beta"))
        self.assertEqual([s.template for s in run.spawns], TEMPLATES3)
        self.assertNotIn(run.code, (0, None), run.describe())
        by = {s.template: s for s in run.spawns}
        self.assertIsNotNone(by[failed].proc.returncode, run.describe())
        return run, failed

    def test_ac21_wait_exception_red_row_group_stopped_queue_goes_on(self):
        """`Exception` из функции ожидания: красная строка, SIGTERM группе, очередь дальше.

        Первый вызов подменённой `_wait_child` бросает `RuntimeError`; дочерний,
        чьё ожидание прервано, получает SIGTERM (порядок остановки требования 5)
        и пожат; у его шаблона одна красная строка по образцу
        `_report_drive_failure`, в выводе — причина «ожидание процесса задачи
        прервано: <ошибка>»; `gamma` запущен; код выхода ненулевой.

        Ловит мутацию: исключение ожидания пробрасывается и обрывает прогон —
        `gamma` не запущен; либо глотается без строки — шаблон пропадает из
        итога, код 0; либо группа дочернего не снимается — SIGTERM не приходит.
        """
        run, failed = self._wait_exception_run(
            {"alfa": {"mode": "exit", "term_exit": True},
             "beta": {"mode": "exit", "term_exit": True},
             "gamma": {"mode": "exit"}})
        mine = [r for r in self.rows(run.stamp) if r["title"] == failed]
        self.assertEqual(len(mine), 1, run.describe())
        self.assert_red_row(mine[0], run.stamp, failed)
        self.assertTrue(_reason_line(
            run.stdout, failed, f"ожидание процесса задачи прервано: {WAIT_ERROR}"),
            run.describe())

    def test_ac21_wait_exception_no_second_row_when_row_exists(self):
        """`Exception` из функции ожидания у дочернего со строкой — второй строки нет.

        Все дочерние — настоящие подкоманды, записавшие зелёную строку до точки
        ожидания; дочерний с прерванным ожиданием снят SIGTERM. За каждый шаблон
        ровно одна строка `run_stamp` прогона — собственная зелёная.

        Ловит мутацию: родитель пишет красную строку «ожидание процесса задачи
        прервано» без сверки `canary_runs` — у шаблона две строки.
        """
        run, failed = self._wait_exception_run(
            {"alfa": {"mode": "real", "row": True, "term_exit": True},
             "beta": {"mode": "real", "row": True, "term_exit": True},
             "gamma": {"mode": "real", "row": True}})
        rows = self.rows(run.stamp)
        for template in TEMPLATES3:
            with self.subTest(template):
                self.assertEqual(
                    [(r["task_id"], r["verdict"]) for r in rows if r["title"] == template],
                    [("01FIXTURE" + template.upper(), "green")], run.describe())
