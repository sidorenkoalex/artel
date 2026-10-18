"""Выкладка планки `pytest-own` без исключения из git не делается.

Рабочая копия — каталог вне git (`git rev-parse --git-path info/exclude`
отказывает): `run`, `collect` и `run_plank` называют отказ выкладки, pytest
не запускается, каталога `.artel-plank` в дереве нет (SPEC
01M57JYJQC8VAHEWMXFNM7D1GS, требование 6: исключение — до записи файлов).
То же при сбое записи `info/exclude` в настоящем репозитории (ANSWER-2,
пункт 1: отказ с именованной причиной до выкладки).
"""
import errno
import os
import random
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import acceptance, project_profile, targets


class PlankLayoutRefusalTest(unittest.TestCase):

    def setUp(self):
        self.seed = random.randrange(1 << 30)
        rng = random.Random(self.seed)
        word = "".join(rng.choice("abcdefgh") for _ in range(6))
        tmp = tempfile.TemporaryDirectory(prefix="artel-layout-refusal-")
        self.addCleanup(tmp.cleanup)
        self.tree = Path(tmp.name)
        self.task_id = f"T{word.upper()}"
        self.workdir = f"wd{word}"
        self.profile = project_profile.Profile(
            command=("python3", "-m", "pytest"),
            long_lived_dir=f"{self.workdir}/tests",
            long_lived_name="test_<id>_<name>.py",
            weakening_scope=(), mutation_claim_scope=(),
            runner=targets.PROFILE_RUNNER_OWN, workdir=self.workdir)
        (self.tree / self.workdir / "tests").mkdir(parents=True)
        self.tdir = self.tree / "tasks" / self.task_id
        plank = self.tdir / "acceptance_tests"
        plank.mkdir(parents=True)
        (plank / f"test_ac1_{word}.py").write_text(
            "def test_ok():\n    assert True\n", encoding="utf-8")

    def layout_dirs(self) -> list:
        return [top for top, dirs, _f in os.walk(self.tree)
                if Path(top).name == acceptance.PLANK_LAYOUT_DIR]

    def test_refusal_without_exclude_launches_nothing(self):
        """git не назвал `info/exclude` — отказ выкладки, pytest не запущен, выкладки нет.

        Ловит мутацию: отказ `_exclude_layout` пропускается и файлы
        выкладки пишутся, видимые git, — pytest запускается, текста отказа
        в выводе нет.
        """
        places = (
            ("run", lambda: acceptance.run(self.tdir, cwd=self.tree,
                                           command=self.profile)),
            ("collect", lambda: acceptance.collect(self.tdir, cwd=self.tree,
                                                   command=self.profile)),
            ("run_plank", lambda: acceptance.run_plank(
                [f"tasks/{self.task_id}/acceptance_tests"], self.tree,
                profile=self.profile, task_id=self.task_id)),
        )
        for label, call in places:
            with self.subTest(place=label, seed=self.seed), \
                    mock.patch.object(acceptance, "_run_pytest",
                                      side_effect=AssertionError("pytest")) as popen:
                first, output = call()
                note = f"зерно: {self.seed}; {label}: {output}"
                self.assertIn(first, (False, acceptance.REFUSED_EXIT_CODE), note)
                self.assertIn("отказ выкладки планки", output, note)
                popen.assert_not_called()
                self.assertEqual(self.layout_dirs(), [], note)

    def places(self):
        return (
            ("run", lambda: acceptance.run(self.tdir, cwd=self.tree,
                                           command=self.profile)),
            ("collect", lambda: acceptance.collect(self.tdir, cwd=self.tree,
                                                   command=self.profile)),
            ("run_plank", lambda: acceptance.run_plank(
                [f"tasks/{self.task_id}/acceptance_tests"], self.tree,
                profile=self.profile, task_id=self.task_id)),
        )

    def init_git(self) -> Path:
        subprocess.run(["git", "init", "-q", str(self.tree)], check=True,
                       capture_output=True)
        res = subprocess.run(["git", "-C", str(self.tree), "rev-parse",
                              "--git-path", "info/exclude"], check=True,
                             capture_output=True, text=True)
        path = Path(res.stdout.strip())
        return path if path.is_absolute() else self.tree / path

    def assert_refused(self, reason: str):
        for label, call in self.places():
            with self.subTest(place=label, seed=self.seed), \
                    mock.patch.object(acceptance, "_run_pytest",
                                      side_effect=AssertionError("pytest")) as popen:
                first, output = call()
                note = f"зерно: {self.seed}; {label}: {output}"
                self.assertIn(first, (False, acceptance.REFUSED_EXIT_CODE), note)
                self.assertIn("отказ выкладки планки", output, note)
                self.assertIn(reason, output, note)
                popen.assert_not_called()
                self.assertEqual(self.layout_dirs(), [], note)

    def test_refusal_when_exclude_not_writable(self):
        """`info/exclude` не записать (на его месте каталог) — отказ с причиной, pytest не запущен, выкладки нет.

        Ловит мутацию: ошибка записи `info/exclude` глотается (`except` без
        отказа) — выкладка создаётся видимой git и pytest запускается.
        """
        exclude = self.init_git()
        if exclude.exists():
            exclude.unlink()
        exclude.mkdir(parents=True)
        self.assert_refused("не записан")

    def test_refusal_on_lock_io_error(self):
        """Ошибка ввода-вывода на блокировке `info/exclude` — отказ с причиной до выкладки.

        Ловит мутацию: сбой `flock` не превращается в отказ (исключение
        ловится выше или игнорируется) — выкладка создаётся, pytest
        запускается.
        """
        self.init_git()
        err = OSError(errno.EIO, "сбой ввода-вывода")
        with mock.patch.object(acceptance.fcntl, "flock", side_effect=err):
            self.assert_refused("сбой ввода-вывода")


if __name__ == "__main__":
    unittest.main()
