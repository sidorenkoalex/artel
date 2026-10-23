"""Планка задачи: имя файла времени и номера логов (AC-4); сбой и остановка
потока чтения прогона в файл лога (AC-7).

Группа: разовый
Красен до реализации: прогон `_run_full_suite_to_log` не оставляет файла `<лог>.durations.tsv` (AC-4 падает на предпосылке) и не заводит потока чтения, которого пульт ждёт после отметки конца прогона (AC-7: ожидания нет).

Оба свойства SPEC оставляет только планке задачи («Не входит»: долгоживущих
тестов на AC-4 и AC-7 в `tests/` нет), поэтому файл разовый и вправе
обращаться к закрытым именам: `acceptance._run_full_suite_to_log` (его
называет критерий), `suite_run._new_log`/`_log_path`/`_task_dir`,
`acceptance._last_run_completed_at`. Прогоны — настоящий pytest с xdist
интерпретатором пульта по маленькому проекту во временном каталоге
песочницы путей `tests.sandbox.TmpRootTest`.
"""
import random
import shutil
import string
import threading
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import acceptance, agent_log, config, suite_run
from tests.sandbox import TmpRootTest

LETTERS = string.ascii_lowercase
ID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
FAST = "def test_{name}():\n    assert True\n"
SLEEPING = "import time\n\n\ndef test_{name}():\n    time.sleep({seconds})\n"
WAIT_LIMIT_SEC = 2.0


def durations_path(log: Path) -> Path:
    log = Path(log)
    return log.with_name(log.name[:-len(".log")] + ".durations.tsv")


class PlankRunTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def word(self, k: int = 6) -> str:
        return "".join(self.rng.choices(LETTERS, k=k))

    def project(self, sources: list) -> Path:
        root = self.root / f"proj-{self.word()}"
        (root / "tests").mkdir(parents=True)
        (root / "tests" / f"test_{self.word()}.py").write_text(
            "\n\n".join(sources), encoding="utf-8")
        return root

    def argv(self, workers: int = 1) -> list:
        """argv `suite-run` для прогона в файл: команда пульта, параллель,
        `-vv` — как его собирает `run_full_suite`."""
        return acceptance._pytest_command("tests") + [
            "-n", str(workers), "-p", "xdist", "-vv"]

    def run_to_log(self, root: Path, log: Path, limit: int = 120,
                   observe: bool = False) -> tuple:
        return acceptance._run_full_suite_to_log(
            self.argv(), root, log, (limit, "тест"), observe)


class DurationsNameTest(PlankRunTest):

    def test_ac4_durations_file_does_not_shift_log_numbers(self):
        """Файл времени лога ветки и базы не сдвигает номер следующего лога.

        Настоящий прогон в файл лога ветки `<id>-suiterun-1.log` и базы
        `<id>-suiterun-1-base.log` каталога задачи `suite-run` оставляет
        `<id>-suiterun-1.durations.tsv` и `<id>-suiterun-1-base.durations.tsv`
        (предпосылка). Сами логи убраны — остались только файлы времени:
        `suite_run._new_log` даёт лог №1. Те же файлы, положенные в
        `config.LOGS`, не сдвигают и номер `agent_log.new_agent_log` того же
        вида — снова №1.

        Ловит мутацию: файл времени назван по шаблону номера лога (имя
        `<id>-suiterun-<n>.log`/`<лог>.<n>.log` вместо `.durations.tsv`) —
        `_new_log`/`new_agent_log` засчитывают его и отдают №2; файл времени
        не заводится вовсе или назван иначе — предпосылка падает.
        """
        task = "01M" + "".join(self.rng.choices(ID_ALPHABET, k=23))
        root = self.project([FAST.format(name=f"fast_{self.word()}")])
        logs = [suite_run._log_path(task, 1), suite_run._log_path(task, 1, "-base")]
        logs[0].parent.mkdir(parents=True, exist_ok=True)
        made = []
        for log in logs:
            green, output = self.run_to_log(root, log)
            self.assertTrue(green, f"зерно {self.seed}; {output[-1500:]}")
            path = durations_path(log)
            self.assertTrue(path.is_file(),
                            f"файла времени {path.name} нет; зерно {self.seed}")
            made.append(path)
        self.assertEqual([p.name for p in made],
                         [f"{task}-suiterun-1.durations.tsv",
                          f"{task}-suiterun-1-base.durations.tsv"])
        for log in logs:
            log.unlink()
        fresh = suite_run._new_log(task)
        self.assertEqual(fresh.name, f"{task}-suiterun-1.log",
                         f"зерно {self.seed}")
        fresh.unlink()
        config.LOGS.mkdir(parents=True, exist_ok=True)
        for path in made:
            shutil.copy(path, config.LOGS / path.name)
        agent = agent_log.new_agent_log(task, suite_run.LOG_KIND)
        self.assertEqual(agent.name, f"{task}-{suite_run.LOG_KIND}-1.log",
                         f"зерно {self.seed}")


class ReaderThreadTest(PlankRunTest):

    def new_threads_alive(self, before: set) -> list:
        return [t for t in threading.enumerate()
                if t not in before and t.is_alive()]

    def test_ac7_thread_failure_changes_nothing_and_thread_is_gone(self):
        """Файл времени не открывается на запись (на его месте каталог): исход, вывод и лог прежние, поток не жив.

        Четыре прогона `_run_full_suite_to_log` с каталогом на месте файла
        времени: зелёный (быстрый и спящий 1 с) и оборванный пределом 3 с
        (быстрый и спящий 30 с), каждый без наблюдения и под наблюдением.
        Зелёный — исход «зелено», вывод равен логу, разбор: 2 прошло;
        оборванный — «не зелено», вывод — текст предела, перевод строки и
        лог, в логе строка хода быстрого теста. В логе нет табуляции (строк
        файла времени); каталог на месте; после возврата ни одного живого
        потока, заведённого прогоном.

        Ловит мутацию: исключение потока при открытии файла времени
        поднимается в прогон (исход/вывод иные или прогон падает); при сбое
        записи поток пишет строки в сам лог; поток не останавливают после
        снятия группы по пределу (жив после возврата).
        """
        cases = (("зелёный", 1, 120, True), ("оборван пределом", 30, 3, False))
        for label, sleep, limit, green_expected in cases:
            for observe in (False, True):
                where = f"{label}, наблюдение {observe}, зерно {self.seed}"
                with self.subTest(case=label, observe=observe, seed=self.seed):
                    fast = f"fast_{self.word()}"
                    root = self.project([
                        FAST.format(name=fast),
                        SLEEPING.format(name=f"sleepy_{self.word()}",
                                        seconds=sleep)])
                    log = self.root / f"run-{self.word()}.log"
                    blocker = durations_path(log)
                    blocker.mkdir()
                    before = set(threading.enumerate())
                    green, output = self.run_to_log(root, log, limit, observe)
                    self.assertEqual(self.new_threads_alive(before), [], where)
                    text = log.read_bytes().decode("utf-8", errors="replace")
                    self.assertEqual(green, green_expected,
                                     f"{where}; {output[-1500:]}")
                    self.assertTrue(blocker.is_dir(), where)
                    self.assertNotIn("\t", text, where)
                    if green_expected:
                        self.assertEqual(output, text, where)
                        parsed = suite_run.parse(green, output)
                        self.assertEqual((parsed.passed, parsed.failed),
                                         (2, 0), where)
                    else:
                        note = acceptance._full_suite_timeout_note(
                            (limit, "тест"))
                        self.assertEqual(output, f"{note}\n{text}", where)
                        self.assertRegex(text, rf"PASSED \S*::test_{fast}",
                                         where)

    def test_ac7_wait_for_thread_after_completion_mark_and_bounded(self):
        """Пульт ждёт поток чтения после отметки конца прогона и не дольше 2 с.

        Ожидание потока наблюдается шпионом `threading.Thread.join` на
        потоках, заведённых самим прогоном (поток — единственный способ
        чтения, который называет SPEC; «ждёт не дольше 2 с» — ожидание
        потока с пределом). Под наблюдением — зелёный прогон и оборванный
        пределом 3 с: ожидание есть, у каждого предел числом не больше 2 с, и
        каждое началось не раньше `acceptance._last_run_completed_at` — в
        длительность прогона для `_signal_near_limit`, снятую по этой
        отметке, оно не входит. Без наблюдения: ожидание есть, предел не
        больше 2 с — добавка к длительности не больше 2 с. После возврата
        поток не жив.

        Ловит мутацию: поток останавливают и ждут до отметки
        `_last_run_completed_at` (ожидание входит в длительность под
        наблюдением); ожидание без предела (`join()`) или с пределом больше
        2 с; поток не ждут вовсе (дочитывание хвоста не гарантировано до
        возврата).
        """
        original = threading.Thread.join
        cases = (("зелёный под наблюдением", 1, 120, True),
                 ("оборван пределом под наблюдением", 30, 3, True),
                 ("зелёный без наблюдения", 1, 120, False))
        for label, sleep, limit, observe in cases:
            where = f"{label}, зерно {self.seed}"
            with self.subTest(case=label, seed=self.seed):
                root = self.project([
                    FAST.format(name=f"fast_{self.word()}"),
                    SLEEPING.format(name=f"sleepy_{self.word()}",
                                    seconds=sleep)])
                log = self.root / f"run-{self.word()}.log"
                before = set(threading.enumerate())
                joins = []

                def spy(thread, timeout=None):
                    if thread not in before:
                        joins.append((acceptance.time.monotonic(), timeout))
                    return original(thread, timeout)

                with mock.patch.object(threading.Thread, "join", spy):
                    green, output = self.run_to_log(root, log, limit, observe)
                self.assertEqual(self.new_threads_alive(before), [], where)
                self.assertTrue(joins, f"{where}: пульт не ждал поток чтения")
                for _at, timeout in joins:
                    self.assertIsNotNone(timeout, f"{where}: ожидание без предела")
                    self.assertLessEqual(timeout, WAIT_LIMIT_SEC, where)
                if observe:
                    mark = acceptance._last_run_completed_at
                    self.assertIsNotNone(mark, where)
                    for at, _timeout in joins:
                        self.assertGreaterEqual(at, mark,
                                                f"{where}: ожидание до отметки")


if __name__ == "__main__":
    unittest.main()
