"""Заведение рабочего каталога роли берёт базу ветки fetch'ем, который не
трогает ссылки отслеживания `refs/remotes/origin/*`.

Группа: долгоживущий

Красен до реализации: fetch базы ветки в `workspace.ensure` по имени удалённого репозитория попутно обновляет `refs/remotes/origin/<MAIN_BRANCH>` — при файле блокировки этой ссылки fetch падает «cannot lock ref» (AC-3 красный), без блокировки ссылка отслеживания уезжает на новую голову (AC-4 красный); AC-5 (именованный отказ при недоступном remote) держит существующее поведение и зелёный.

Сценарий на настоящем git: пульт — `self.root` с bare-репозиторием
`origin`, синхронным с `MAIN_BRANCH` (`add_synced_origin`); ссылка
отслеживания `refs/remotes/origin/<MAIN_BRANCH>` заведена пушем. Голова
`origin` уходит вперёд коммитом, запушенным ПО ПУТИ bare-репозитория (не по
имени `origin`), — так ссылка отслеживания пульта остаётся на прежнем
коммите. Затем `workspace.ensure` для задачи, ветки которой ещё нет.
Номер задачи, имя ветки и число коммитов, на которые `origin` ушёл вперёд,
— из `random`, зерно печатается и входит в текст провала.
"""
import random
import shutil
import tempfile
import unittest
from pathlib import Path

from orchestrator import config, workspace
from tests.sandbox import RealGitSandbox


class WorkspaceFetchSandbox(RealGitSandbox):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.origin = self.add_synced_origin()
        self.task_id = f"T{self.rng.randrange(100, 1000)}"
        self.branch = (f"task/{self.task_id.lower()}-"
                       f"{self.rng.choice(('baza', 'fetch', 'vetka'))}"
                       f"{self.rng.randrange(100)}")
        self.tracking = f"refs/remotes/origin/{config.MAIN_BRANCH}"
        self.tracking_before = self.rev(self.tracking)
        self.assertTrue(self.tracking_before, self.note(
            "предпосылка: ссылки отслеживания нет после пуша"))

    def note(self, text: str) -> str:
        return f"{text} (зерно {self.seed})"

    def rev(self, ref: str) -> str:
        out = self.git("for-each-ref", "--format=%(objectname)", ref)
        return out.strip()

    def origin_head(self) -> str:
        out = self.git("ls-remote", str(self.origin),
                       f"refs/heads/{config.MAIN_BRANCH}")
        return out.split()[0] if out.split() else ""

    def advance_origin(self) -> str:
        """Голова `origin` уходит вперёд на 1–3 коммита пушем по пути
        bare-репозитория: ссылка отслеживания пульта не обновляется."""
        sha = self.git("rev-parse", config.MAIN_BRANCH).strip()
        for n in range(self.rng.randint(1, 3)):
            sha = self.git("commit-tree", f"{sha}^{{tree}}", "-p", sha, "-m",
                           f"origin впереди {n} ({self.seed})").strip()
        self.git("push", "-q", str(self.origin),
                 f"{sha}:refs/heads/{config.MAIN_BRANCH}")
        self.assertEqual(self.origin_head(), sha, self.note(
            "предпосылка: голова origin не сдвинута"))
        self.assertEqual(self.rev(self.tracking), self.tracking_before,
                         self.note("предпосылка: пуш по пути сдвинул ссылку "
                                   "отслеживания"))
        return sha

    def lock_tracking_ref(self) -> Path:
        """Файл блокировки ссылки отслеживания — как у параллельного
        процесса, который в эту секунду её обновляет."""
        lock = (self.root / ".git" / "refs" / "remotes" / "origin"
                / f"{config.MAIN_BRANCH}.lock")
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(f"{self.tracking_before}\n", encoding="utf-8")
        return lock

    def branch_listed(self) -> bool:
        return bool(self.git("branch", "--list", self.branch).strip())


class LockedTrackingRefTest(WorkspaceFetchSandbox):

    def test_ac3_ensure_succeeds_with_locked_tracking_ref(self):
        """Ссылка отслеживания занята чужим процессом — рабочий каталог заводится, ветка на голове `origin`.

        Сценарий: голова `origin` ушла вперёд; в git пульта лежит файл
        блокировки `refs/remotes/origin/<MAIN_BRANCH>.lock`; ветки задачи
        нет. `workspace.ensure` возвращает причину `None`, ветка задачи
        заведена и стоит ровно на голове `MAIN_BRANCH` в `origin` (не на
        локальной `MAIN_BRANCH` и не на прежней ссылке отслеживания).

        Ловит мутацию: fetch базы идёт по имени `origin` с обновлением
        ссылок отслеживания (как на пине) — git не может взять блокировку,
        fetch отказывает, `ensure` возвращает «база ветки недоступна»;
        ветка заводится от локальной `MAIN_BRANCH` или от
        `refs/remotes/origin/<MAIN_BRANCH>` вместо свежей головы.
        """
        head = self.advance_origin()
        self.lock_tracking_ref()

        wt_path, error = workspace.ensure(self.task_id, self.branch)

        self.assertIsNone(error, self.note(
            f"заведение рабочего каталога отказало при занятой ссылке: {error}"))
        self.assertEqual(self.rev(f"refs/heads/{self.branch}"), head, self.note(
            "ветка задачи не на голове origin"))
        self.assertTrue(wt_path.is_dir(), self.note("рабочего каталога нет"))


class TrackingRefUntouchedTest(WorkspaceFetchSandbox):

    def test_ac4_ensure_fetch_does_not_move_tracking_ref(self):
        """Fetch базы при заведении рабочего каталога не двигает `refs/remotes/origin/<MAIN_BRANCH>`.

        Сценарий: голова `origin` ушла вперёд на 1–3 коммита, блокировки
        нет; ветки задачи нет. После `workspace.ensure` (без отказа, ветка
        на новой голове) ссылка отслеживания указывает на прежний коммит.

        Ловит мутацию: fetch идёт `git fetch origin <refspec>` с
        настроенным `remote.origin.fetch` (как на пине) — git попутно
        переписывает ссылку отслеживания на новую голову; либо fetch
        заменён на `git fetch origin` с последующим чтением
        `origin/<MAIN_BRANCH>`.
        """
        head = self.advance_origin()

        _wt_path, error = workspace.ensure(self.task_id, self.branch)

        self.assertIsNone(error, self.note(f"заведение отказало: {error}"))
        self.assertEqual(self.rev(f"refs/heads/{self.branch}"), head, self.note(
            "предпосылка: ветка задачи не на голове origin"))
        self.assertEqual(self.rev(self.tracking), self.tracking_before, self.note(
            f"ссылка отслеживания сдвинута fetch'ем базы на "
            f"{self.rev(self.tracking)} (голова origin {head})"))


class UnavailableRemoteTest(WorkspaceFetchSandbox):

    def test_ac5_unavailable_remote_named_refusal_without_branch(self):
        """Remote недоступен — именованный отказ «база ветки недоступна: fetch origin не удался», ветки задачи нет.

        Сценарий: адрес `origin` переставлен (случайно) на несуществующий
        путь либо на пустой каталог, не являющийся git-репозиторием;
        ветки задачи нет. `workspace.ensure` возвращает причину,
        начинающуюся с «база ветки недоступна: fetch origin не удался»;
        ветка задачи не заведена, рабочий каталог не зарегистрирован.

        Ловит мутацию: при переделке fetch отказ стал откатываться на
        локальную `MAIN_BRANCH` (ветка заведена, причина `None`); отказ
        fetch теряет именованный префикс (возвращается сырой stderr git).
        """
        kind = self.rng.choice(("несуществующий путь", "не git-репозиторий"))
        scratch = Path(tempfile.mkdtemp(prefix="artel-no-remote-"))
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        target = (scratch / f"absent-{self.rng.randrange(1000)}"
                  if kind == "несуществующий путь" else scratch)
        self.git("remote", "set-url", "origin", str(target))

        wt_path, error = workspace.ensure(self.task_id, self.branch)

        self.assertIsNotNone(error, self.note(
            f"remote «{kind}»: заведение не отказало"))
        self.assertTrue(error.startswith(
            "база ветки недоступна: fetch origin не удался"), self.note(
            f"remote «{kind}»: отказ без именованного префикса: {error}"))
        self.assertFalse(self.branch_listed(), self.note(
            f"remote «{kind}»: ветка задачи заведена на отказе"))
        registered = {Path(p).resolve() for p in workspace.registered_paths()}
        self.assertNotIn(wt_path.resolve(), registered, self.note(
            f"remote «{kind}»: рабочий каталог зарегистрирован на отказе"))


if __name__ == "__main__":
    unittest.main()
