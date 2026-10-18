"""Дописывание шаблона выкладки в общий `info/exclude` клона — под `flock`.

Файл общий для всех worktree проекта, и задачи дописывают его параллельно:
проверка «шаблон уже есть» и запись идут под блокировкой файла, две задачи
оставляют ровно одну строку шаблона (SPEC 01M57JYJQC8VAHEWMXFNM7D1GS,
требование 6; ANSWER-2, пункт 2).
"""
import fcntl
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

from orchestrator import acceptance


class ExcludeLockTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="artel-exclude-lock-")
        self.addCleanup(tmp.cleanup)
        self.tree = Path(tmp.name)
        subprocess.run(["git", "init", "-q", str(self.tree)], check=True,
                       capture_output=True)
        res = subprocess.run(["git", "-C", str(self.tree), "rev-parse",
                              "--git-path", "info/exclude"], check=True,
                             capture_output=True, text=True)
        path = Path(res.stdout.strip())
        self.exclude = path if path.is_absolute() else self.tree / path
        self.exclude.parent.mkdir(parents=True, exist_ok=True)
        self.exclude.write_text("# своё\n", encoding="utf-8")

    def pattern_lines(self) -> int:
        return self.exclude.read_text(encoding="utf-8").splitlines().count(
            acceptance.PLANK_LAYOUT_EXCLUDE)

    def test_check_and_append_wait_for_lock_holder(self):
        """Пока другой держит `flock` на `info/exclude`, дописывание ждёт и потом видит его строку.

        Ловит мутацию: блокировка снята или проверка «шаблон уже есть»
        вынесена из-под неё — поток не ждёт держателя либо дописывает
        вторую строку шаблона после строки держателя.
        """
        results = []
        with self.exclude.open("a+", encoding="utf-8") as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            worker = threading.Thread(
                target=lambda: results.append(
                    acceptance._exclude_layout(self.tree)))
            worker.start()
            worker.join(0.5)
            self.assertTrue(worker.is_alive(),
                            "дописывание не ждало держателя блокировки")
            held.write(acceptance.PLANK_LAYOUT_EXCLUDE + "\n")
            held.flush()
            fcntl.flock(held, fcntl.LOCK_UN)
        worker.join(10)
        self.assertFalse(worker.is_alive())
        self.assertEqual(results, [""])
        self.assertEqual(self.pattern_lines(), 1)

    def test_parallel_tasks_leave_single_line(self):
        """Два потока дописывают одновременно — в файле ровно одна строка шаблона.

        Ловит мутацию: дописывание без проверки под блокировкой — оба
        потока, прочитав файл без шаблона, дописывают по строке.
        """
        for _ in range(20):
            self.exclude.write_text("# своё\n", encoding="utf-8")
            barrier = threading.Barrier(2)
            results = []

            def task():
                barrier.wait()
                results.append(acceptance._exclude_layout(self.tree))

            workers = [threading.Thread(target=task) for _ in range(2)]
            for w in workers:
                w.start()
            for w in workers:
                w.join(10)
            self.assertEqual(results, ["", ""])
            self.assertEqual(self.pattern_lines(), 1)
            self.assertTrue(self.exclude.read_text(
                encoding="utf-8").startswith("# своё\n"))


if __name__ == "__main__":
    unittest.main()
