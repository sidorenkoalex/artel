"""Цвет CI main у `pin-update` и `doctor` читается там, куда был `fetch`
(ревью 01M42PENCS26D0656X8FR7DFA7, R1-F1; SPEC 01M42PENCS26D0656X8FR7DFA7,
требование 4 — `pin` и `doctor/root_pin` работают с главной копией).

Главная копия и клон артели здесь — РАЗНЫЕ репозитории на настоящем git:
главная копия на два коммита впереди клона (push в origin мимо клона, как
коммит Оператора 1dc7c20f). Голова — документный коммит, на котором
проверка `tests` пропущена; под ней — коммит, где `tests` упала. Линия,
прочитанная в главной копии, доходит до падения (красный); линия,
прочитанная в отставшем клоне, обрывается на голове, и красный main
выглядит зелёным. `gh` подменён на уровне `ci.check_runs`.
"""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import ci, config, doctor, pin


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def _commit(repo: Path, rel: str, text: str) -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", rel)
    return _git(repo, "rev-parse", "HEAD")


class MainLineReadsTheFetchedRepoTest(unittest.TestCase):
    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        root = tmp / "pult"
        root.mkdir()
        _git(root, "init", "-q", "-b", config.MAIN_BRANCH)
        _git(root, "config", "user.email", "t@example.invalid")
        _git(root, "config", "user.name", "t")
        base = _commit(root, "kod.py", "VALUE = 0\n")
        projects = tmp / "projects"
        clone = projects / config.DEFAULT_TARGET / "repo"
        clone.parent.mkdir(parents=True)
        subprocess.run(["git", "clone", "-q", str(root), str(clone)],
                       check=True, capture_output=True)
        self.red = _commit(root, "kod.py", "VALUE = 1\n")
        self.head = _commit(root, "docs/zametka.md", "заметка\n")
        self.assertEqual(_git(clone, "rev-parse", "HEAD"), base)
        for name, value in (("ROOT", root), ("PROJECTS", projects)):
            patcher = mock.patch.object(config, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        runs = {self.head: [{"name": "tests", "status": "completed",
                             "conclusion": "skipped"}],
                self.red: [{"name": "tests", "status": "completed",
                            "conclusion": "failure"}]}
        patcher = mock.patch.object(
            ci, "check_runs", lambda sha: (runs.get(sha, []), ""))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_pin_update_sees_red_below_a_docs_head(self):
        """Ловит мутацию: `pin._refuse_unless_main_ci_green` читает линию
        main без `repo=config.ROOT` (в клоне артели, куда fetch не ходил) —
        линия обрывается на документной голове, красный коммит под ней не
        виден, и пин уезжает на красный main вместо отказа."""
        with self.assertRaises(SystemExit) as ctx:
            pin._refuse_unless_main_ci_green(self.head)
        self.assertIn("красный", str(ctx.exception))
        self.assertIn(self.red[:8], str(ctx.exception))

    def test_doctor_main_ci_sees_red_below_a_docs_head(self):
        """Ловит мутацию: `doctor.check_main_ci` читает линию main без
        `repo=config.ROOT` — строка `main-ci` отвечает `ok` на красный main,
        потому что отставший клон не знает коммитов под головой origin."""
        with mock.patch.object(doctor, "fetch_origin_main_sha",
                               lambda: (self.head, "")):
            check = doctor.check_main_ci()
        self.assertEqual(check.status, "fail", check.detail)
        self.assertIn(self.red[:8], check.detail)


if __name__ == "__main__":
    unittest.main()
