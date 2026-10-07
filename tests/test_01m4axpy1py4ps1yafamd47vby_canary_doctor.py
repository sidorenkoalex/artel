"""Doctor наблюдает временные каталоги канарейки и чинит только сироты.
Группа: долгоживущий
Красен до реализации: doctor ещё не распознаёт владельца клонов и прогонов suite-run.
"""

import json
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

from orchestrator import canary, catalog, config, doctor, store
from tests.sandbox import RealGitSandbox, capture


class CanaryDoctorTest(RealGitSandbox):
    """Маркер берётся у настоящего клона канарейки, имя файла тест не задаёт."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.temp_root = self.root / ".artel" / "canary-test-tmp"
        self.temp_root.mkdir(parents=True)
        temp_patch = mock.patch.object(tempfile, "tempdir", str(self.temp_root))
        temp_patch.start()
        self.addCleanup(temp_patch.stop)
        env_patch = mock.patch.dict(os.environ, {"TMPDIR": str(self.temp_root)})
        env_patch.start()
        self.addCleanup(env_patch.stop)
        entry = self.root / canary.CANARY_DRIVE_ENTRY
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_text("# ведение заменено наблюдателем\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "fixture drive")
        self.sha = self.git("rev-parse", "HEAD").strip()
        self.home = Path(tempfile.mkdtemp(prefix="canary-doctor-home-"))
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        pool = self.home / config.CANARY_POOL_DIRNAME
        pool.mkdir()
        (pool / "fixture.md").write_text("# учебная задача\n", encoding="utf-8")
        self.paths = []
        self.procs = []
        self.addCleanup(self.clean_fixtures)

    def clean_fixtures(self):
        for proc in self.procs:
            if proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
            proc.wait(timeout=5)
        for path in self.paths:
            shutil.rmtree(path, ignore_errors=True)

    def snapshot(self, owner_alive):
        """Копирует наблюдаемый клон до штатной уборки и меняет только pid владельца."""
        real_popen = subprocess.Popen
        found = {}

        def launch(argv, *args, **kwargs):
            if list(argv[:3]) != [sys.executable, "-m", canary.CANARY_DRIVE_MODULE]:
                return real_popen(argv, *args, **kwargs)
            clone = Path(kwargs["cwd"])
            marker = None
            for path in clone.rglob("*"):
                if path.is_file() and ".git" not in path.parts:
                    try:
                        content = path.read_text(encoding="utf-8")
                        if len(content) < 1024 and re.search(
                                rf"(?<!\d){os.getpid()}(?!\d)", content):
                            marker = path.relative_to(clone)
                            break
                    except (OSError, UnicodeError):
                        pass
            found["marker"] = marker
            if marker is None:
                raise AssertionError("клон канарейки не несёт файл с pid владельца")
            git_config = (clone / ".git" / "config").read_text(encoding="utf-8")
            remote = re.search(r'\[remote "origin"\]\s*url\s*=\s*(\S+)',
                               git_config)
            self.assertIsNotNone(remote, f"зерно: {self.seed}; origin клона")
            origin = remote.group(1)
            copy = Path(tempfile.mkdtemp(prefix="artel-canary-"))
            self.paths.append(copy)
            shutil.copytree(clone, copy, dirs_exist_ok=True)
            origin_copy = Path(tempfile.mkdtemp(prefix="artel-canary-origin-"))
            self.paths.append(origin_copy)
            shutil.copytree(origin, origin_copy, dirs_exist_ok=True)
            (copy / ".git" / "config").write_text(
                git_config.replace(origin, str(origin_copy), 1),
                encoding="utf-8")
            if not owner_alive:
                path = copy / marker
                path.write_text(path.read_text(encoding="utf-8").replace(
                    str(os.getpid()), "99999999", 1), encoding="utf-8")
            found.update(clone=copy, origin=origin_copy)
            result = Path(argv[argv.index("--result") + 1])
            result.write_text(json.dumps({
                "task_id": "01FIXTURE", "head": self.sha,
                "outcome": "killed", "escalated": False,
                "metrics": {"steps": 1, "cost_usd": 0.0,
                            "review_iterations": 0, "escalations": [],
                            "dev_retries": 0, "outcome": "killed",
                            "kill_note": "штатно", "test_author_visited": False,
                            "ceiling_exhausted": False, "ceiling_raise": None},
                "steps": [],
            }))
            return real_popen([sys.executable, "-c", "pass"], *args, **kwargs)

        with mock.patch.object(Path, "home", return_value=self.home), \
             mock.patch.object(catalog, "cmd_init"), \
             mock.patch.object(subprocess, "Popen", launch):
            capture(lambda: canary.cmd_canary(k=1, sha=self.sha,
                                               templates=["fixture"]))
        return found

    def suite_base_for(self, snapshot):
        """Копия того же признака владельца в каталоге базы suite-run."""
        base = Path(tempfile.mkdtemp(prefix="artel-suite-base-"))
        self.paths.append(base)
        marker = snapshot["marker"]
        target = base / marker
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((snapshot["clone"] / marker).read_bytes())
        return base

    def process_in(self, cwd):
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(90)"],
                                cwd=cwd, start_new_session=True,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        self.procs.append(proc)
        return proc

    def simulated_ps(self, proc, cwd):
        real_run = subprocess.run
        age = int(config.HUNG_TEST_RUN_AGE_SEC) + 10
        etime = f"{age // 3600}:{age // 60 % 60:02}:{age % 60:02}"

        def run(argv, *args, **kwargs):
            if list(argv[:2]) == ["ps", "-axww"]:
                return subprocess.CompletedProcess(
                    argv, 0, f"{proc.pid} {etime} python -m pytest\n", "")
            if list(argv[:1]) == ["lsof"]:
                return subprocess.CompletedProcess(argv, 0,
                                                   f"p{proc.pid}\nn{cwd}\n", "")
            return real_run(argv, *args, **kwargs)

        return mock.patch.object(subprocess, "run", run)

    def doctor_fix(self):
        with mock.patch.object(doctor, "all_checks", return_value=[]):
            capture(lambda: doctor.cmd_doctor(fix=True))

    def test_ac6_dead_canary_pytest_is_reported_in_clone_and_suite_base(self):
        """Просроченный pytest в двух видах каталога мёртвой канарейки становится находкой.

        Ловит мутацию: сторож по-прежнему смотрит только рабочие копии задач — находок в обоих временных каталогах нет.
        """
        snap = self.snapshot(owner_alive=False)
        for cwd in (snap["clone"], self.suite_base_for(snap)):
            with self.subTest(cwd=cwd.name):
                proc = self.process_in(cwd)
                with self.simulated_ps(proc, cwd):
                    checks = doctor.check_hung_test_runs(store.db())
                self.assertTrue(any(c.status == "fail" and str(proc.pid) in c.detail
                                    for c in checks), f"зерно: {self.seed}; {checks}")

    def test_ac7_live_canary_pytest_is_neither_reported_nor_killed(self):
        """Живой владелец защищает pytest как от находки, так и от --fix.

        Ловит мутацию: сторож игнорирует pid маркера — живой pytest объявляется зависшим и его группа снимается.
        """
        snap = self.snapshot(owner_alive=True)
        for cwd in (snap["clone"], self.suite_base_for(snap)):
            with self.subTest(cwd=cwd.name):
                proc = self.process_in(cwd)
                with self.simulated_ps(proc, cwd):
                    checks = doctor.check_hung_test_runs(store.db())
                    self.assertFalse(any(c.status == "fail" for c in checks),
                                     f"зерно: {self.seed}; {checks}")
                    self.doctor_fix()
                self.assertIsNone(proc.poll(), f"зерно: {self.seed}; pid={proc.pid}")

    def test_ac8_fix_kills_the_hung_pytest_group(self):
        """После --fix процесс из находки сторожа прекращается.

        Ловит мутацию: doctor сообщает находку, но забывает вызвать групповое снятие при --fix — pytest продолжает жить.
        """
        snap = self.snapshot(owner_alive=False)
        proc = self.process_in(snap["clone"])
        with self.simulated_ps(proc, snap["clone"]):
            self.doctor_fix()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.fail(f"зерно: {self.seed}; pytest pid={proc.pid} пережил --fix")

    def test_ac9_dead_directories_are_orphans_and_live_are_not(self):
        """Клон, origin и база мёртвого владельца названы сиротами; живого нет.

        Ловит мутацию: поиск сирот не обходит временные каталоги канарейки — мёртвые каталоги не попадают в вывод.
        """
        dead = self.snapshot(owner_alive=False)
        dead_base = self.suite_base_for(dead)
        live = self.snapshot(owner_alive=True)
        live_base = self.suite_base_for(live)
        checks = doctor.check_orphans(store.db())
        details = " ".join(c.detail for c in checks if c.status == "fail")
        for path in (dead["clone"], dead["origin"], dead_base):
            self.assertIn(str(path), details, f"зерно: {self.seed}; {checks}")
        for path in (live["clone"], live["origin"], live_base):
            self.assertNotIn(str(path), details, f"зерно: {self.seed}; {checks}")

    def test_ac10_fix_removes_only_orphan_among_live_owners(self):
        """Починка удаляет сироту и сохраняет клон живой канарейки и базу живого suite-run.

        Ловит мутацию: --fix удаляет все каталоги с нужным префиксом без проверки живого владельца.
        """
        dead = self.snapshot(owner_alive=False)
        live = self.snapshot(owner_alive=True)
        live_base = self.suite_base_for(dead)
        suite = self.process_in(live_base)
        run = config.LOGS / "suite-run" / "fixture" / "run.json"
        run.parent.mkdir(parents=True, exist_ok=True)
        run.write_text(json.dumps({"pid": suite.pid}))
        self.doctor_fix()
        self.assertFalse(dead["clone"].exists(), f"зерно: {self.seed}")
        self.assertFalse(dead["origin"].exists(), f"зерно: {self.seed}")
        for path in (live["clone"], live["origin"], live_base):
            self.assertTrue(path.exists(), f"зерно: {self.seed}; {path}")
