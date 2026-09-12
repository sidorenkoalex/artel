"""Приёмочные тесты 01M297HFSKV3GVZJ9YF20FZEZE (AC-7..AC-8): предупреждение
`catalog.cmd_new` о расхождении HEAD `config.ROOT` с `origin/<config.
MAIN_BRANCH>` — заведение задачи при этом не блокируется.

Красен до реализации: `orchestrator/catalog.py::cmd_new`/`_new_task_row`
сегодня не делают ни `git fetch origin`, ни сверки HEAD `config.ROOT` с
origin вообще — ни печати предупреждения, ни записи в `store.journal`
про «пин расходится с origin» в кодовой базе нет ни одной (`grep
"расходится с origin"` пуст). `test_ac7_...` красен по этой причине —
искомой подстроки нет ни в stdout, ни в журнале. `test_ac8_...` (оба
метода) зелёные с рождения: сегодняшний `cmd_new` и так не печатает и не
журналирует ничего о расхождении пина — критерий требует ИМЕННО
отсутствия нового вывода там, где расхождения нет (или fetch отказал), а
это уже данность до всякой реализации требования 1/2.

Настоящий git (`config.ROOT` + bare `origin`, тот же приём, что
`tasks/01M1GS5HZ1JXFGKVR95HEW0AEZ/acceptance_tests/_sandbox.py::
HeadInOriginSandbox`): предмет проверки — реальная предковость HEAD
относительно РЕАЛЬНОГО origin после `git fetch`, заглушкой `gitcmd.git`
не изобразить.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, config, store  # noqa: E402
from tests.sandbox import capture, capture_new_task_id, \
    resilient_tmp_cleanup  # noqa: E402


class _CmdNewPinSandbox(unittest.TestCase):
    """`config.ROOT` — настоящий git-репозиторий с одним коммитом на
    `config.MAIN_BRANCH`, синхронным с настоящим bare `origin` на
    старте каждого теста."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, tmp)
        self.root = Path(tmp.name).resolve()

        self.git("init", "-q", "-b", config.MAIN_BRANCH)
        self.git("config", "user.email", "artel-tests@example.invalid")
        self.git("config", "user.name", "artel tests")
        (self.root / "marker.txt").write_text("main\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

        self.origin = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.origin, ignore_errors=True)
        self.git("init", "-q", "--bare", str(self.origin))
        self.git("remote", "add", "origin", str(self.origin))
        self.git("push", "-q", "origin",
                f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")

        for attr, value in (
            ("ROOT", self.root),
            ("DB", self.root / ".artel" / "state.db"),
            ("TASKS", self.root / "tasks"),
            ("LOGS", self.root / ".artel" / "logs"),
            ("ROLE_HOME", self.root / ".artel" / "home"),
            ("ROLE_CONFIG_DIR", self.root / ".artel" / "home" / ".claude"),
            ("WORKTREES", self.root / ".artel" / "worktrees"),
        ):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.capture(catalog.cmd_init)

    # ------------------------------------------------------------ утилиты

    def git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        res = subprocess.run(["git", *args], cwd=self.root,
                             capture_output=True, text=True)
        if check:
            self.assertEqual(res.returncode, 0,
                             f"git {' '.join(args)} упал: {res.stderr}")
        return res

    capture = staticmethod(capture)

    def local_only_commit(self, message: str, filename: str) -> str:
        """Коммит прямо в `config.ROOT`, никогда не запушенный в
        `origin` — тот же класс инцидента, что в «Контексте» SPEC.md
        (документный коммит прямо в главную копию)."""
        (self.root / filename).write_text("x\n", encoding="utf-8")
        self.git("add", filename)
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD").stdout.strip()

    def journal_details(self, task_id: str) -> list:
        return [s["detail"] for s in store.task_steps(store.db(), task_id)]


class CmdNewPinDivergenceWarnsTest(_CmdNewPinSandbox):

    def test_ac7_diverged_pin_warns_and_journals_the_count(self):
        """HEAD `config.ROOT` ушёл на 5 непушенных коммитов вперёд
        `origin/<MAIN_BRANCH>` — `cmd_new` обязан (1) напечатать
        предупреждение с перечнем этих коммитов (sha и первая строка
        каждого) и (2) записать в журнал ЗАВЕДЁННОЙ задачи запись вида
        «пин расходится с origin: 5 коммитов»; заведение задачи при этом
        НЕ блокируется — задача существует после вызова.

        Ловит мутацию: сверка расхождения реализована, но НЕ вызывается
        из `cmd_new`/`_new_task_row` (мёртвый код) — тогда ни в stdout,
        ни в журнале искомых подстрок не появится, хотя расхождение
        реально есть.
        """
        shas = [self.local_only_commit(f"документный коммит {i}",
                                       f"doc{i}.txt") for i in range(1, 6)]

        out, task_id = capture_new_task_id(
            catalog.cmd_new, "Задача под расхождением пина")

        self.assertIn("пин расходится с origin", out)
        for i, sha in enumerate(shas, start=1):
            self.assertIn(sha[:7], out)
            self.assertIn(f"документный коммит {i}", out)

        details = self.journal_details(task_id)
        matches = [d for d in details if "пин расходится с origin" in d]
        self.assertEqual(len(matches), 1,
                         "ровно одна запись журнала о расхождении пина")
        self.assertIn("5 коммит", matches[0])

        self.assertIsNotNone(store.get_task(store.db(), task_id),
                             "заведение задачи не блокируется расхождением")


class CmdNewPinNoDivergenceTest(_CmdNewPinSandbox):

    def test_ac8_synced_pin_prints_and_journals_nothing_extra(self):
        """Пин синхронен с `origin/<MAIN_BRANCH>` (нет непушенных
        коммитов) — `cmd_new` работает как прежде: ни предупреждения в
        выводе, ни записи в журнал о расхождении.

        Ловит мутацию: предупреждение печатается/журналируется
        БЕЗУСЛОВНО (проверка предковости не читается вовсе, либо читается
        инвертированной) — тогда синхронный пин ложно попал бы под то же
        предупреждение, что и AC-7.
        """
        out, task_id = capture_new_task_id(
            catalog.cmd_new, "Задача без расхождения пина")

        self.assertNotIn("расходится с origin", out)
        details = self.journal_details(task_id)
        self.assertEqual(
            [d for d in details if "расходится с origin" in d], [])

    def test_ac8_unreachable_origin_prints_and_journals_nothing_extra(self):
        """`git fetch origin <MAIN_BRANCH>` отказывает (origin недоступен)
        — критерий явно относит этот случай к тому же «без нового
        вывода», что и отсутствие расхождения: `cmd_new` работает как
        прежде.

        Ловит мутацию: отказ fetch трактуется как расхождение (вместо
        «неизвестно — молчим») — предупреждение печаталось бы даже когда
        сверка физически не проведена.
        """
        self.git("remote", "set-url", "origin",
                str(self.root / "no-such-origin-here"))

        out, task_id = capture_new_task_id(
            catalog.cmd_new, "Задача с недоступным origin")

        self.assertNotIn("расходится с origin", out)
        details = self.journal_details(task_id)
        self.assertEqual(
            [d for d in details if "расходится с origin" in d], [])


if __name__ == "__main__":
    unittest.main()
