"""Общая песочница приёмочных тестов 01M1REVP9WGRHDDNVEVE8BBH0Z (SPEC:
критерий сироты для `doctor --fix` и предпросмотр кандидатов).

Реальный git с настоящим bare `origin` (не заглушка `gitcmd.git`): предмет
проверки — расхождение локального дерева и origin (ветка есть локально,
но опубликована ли на origin) и отказ самого origin — заглушкой
`gitcmd.git`, отвечающей одним и тем же фиксированным успехом/провалом на
ЛЮБОЙ git-вызов, эти два состояния (сирота/не сирота, доступен/недоступен)
неотличимы друг от друга и от остальных git-вызовов `doctor` в том же
прогоне (`root-pin` тоже зовёт `git ls-remote`). Тот же приём и то же
обоснование, что `tests/test_gitcmd_branch_reads.py::RemoteBranchShaTest`
(SPEC 01M1GS5HZ1JXFGKVR95HEW0AEZ) и SPEC этой задачи, «Материалы»:
«origin в тестах — локальный репозиторий-фикстура, не сеть» (инвариант 35).

Локальный контракт (SPEC оставляет реализацию разработчику — так же, как
tasks/01M1KVGD18P9H5WR7VM8TGPV1T зафиксировал контракт для AC-4 своей
задачи; этот контракт фиксирует ПЛАНКУ для данной задачи):

- `doctor._orphan_artifact_branches(conn) -> list[str] | None` — `None`,
  если origin не ответил на `git ls-remote --heads origin 'artifact/*'`
  (критерий не вычислим, требование 6); иначе — отсортированный список
  веток `artifact/<id>` пульта, для которых НЕТ строки в `state.db` И
  которых нет среди веток `artifact/*` origin (AC-1/AC-2). Тот же приём
  вырождения, что уже несёт `gitcmd.list_branches` (`None` — git не
  ответил, `[]` — легитимный пустой ответ).
- `doctor.sweep_orphan_artifact_branches(conn) -> list[str] | None` —
  `None`, если origin недоступен: уборка НЕ ВЫПОЛНЯЕТСЯ вообще (ни одна
  ветка не удаляется, `git branch -D` не вызывается, incident не
  заводится, требование 5); иначе — прежнее поведение (список ФАКТИЧЕСКИ
  удалённых веток).
- `doctor.cmd_doctor(restore=False, fix=False)`:
  - `fix=False` (предпросмотр, требование 3/6): либо печатает «критерий
    не вычислим без origin» (origin недоступен), либо число кандидатов
    и первые `config.DOCTOR_ORPHAN_PREVIEW_LIMIT` их имён с пометкой,
    что их удалит `doctor --fix`; ни одна ветка не трогается.
  - `fix=True` (требование 4/5): печатает тот же предпросмотр ДО удаления,
    затем — при доступном origin — число фактически удалённых после
    попытки; при недоступном origin — FAIL с именованной, отличимой от
    прочих FAIL, причиной и завершает процесс ненулевым кодом, удаление
    не запускается вовсе (требование 5).
  - Ровно один `git ls-remote --heads origin 'artifact/*'` за весь прогон
    команды — что в режиме предпросмотра, что в режиме `--fix` (AC-3).
"""
import shutil
import sys
import tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import gitcmd  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402


class ArtifactOriginSandbox(RealGitSandbox):
    """`self.root` — репозиторий пульта (main + один коммит, `RealGitSandbox`)
    с настоящим bare `origin`, заведённым отдельным временным каталогом."""

    def setUp(self):
        super().setUp()
        self.origin_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.origin_dir, ignore_errors=True)
        self.git("init", "-q", "--bare", self.origin_dir)
        self.git("remote", "add", "origin", self.origin_dir)

    def local_only_artifact_branch(self, task_id: str) -> str:
        """Заводит `artifact/<task_id>` ТОЛЬКО в локальном репозитории
        (не публикует на origin) — кандидат AC-1, если `task_id` вдобавок
        не заведён в БД."""
        name = f"artifact/{task_id}"
        head = self.git("rev-parse", "HEAD").strip()
        self.git("branch", name, head)
        return name

    def push_artifact_branch(self, task_id: str) -> str:
        """Заводит `artifact/<task_id>` и публикует её на bare `origin`
        (AC-2: присутствие на origin снимает статус сироты)."""
        name = self.local_only_artifact_branch(task_id)
        self.git("push", "-q", "origin", name)
        return name

    def make_origin_unreachable(self) -> None:
        """`origin` указывает на несуществующий локальный путь: `git
        ls-remote --heads origin ...` отвечает ненулевым кодом возврата —
        настоящий отказ git, не сеть (путь абсолютный и локальный,
        инвариант 35), не заглушка."""
        gone = Path(self.origin_dir) / "__does_not_exist__"
        self.git("remote", "set-url", "origin", str(gone))

    def branch_exists_locally(self, name: str) -> bool:
        return name in self.git("branch", "--list", name)

    def spy_on_gitcmd_git(self):
        """Контекст-менеджер, подменяющий `gitcmd.git` на спай, который
        считает вызовы и делегирует НАСТОЯЩЕМУ `gitcmd.git` (не фейкует
        git — только считает argv настоящих вызовов). Возвращает
        `(context_manager, calls)`: `calls` наполняется по ходу
        `with context_manager:`."""
        calls = []
        real_git = gitcmd.git

        def spy(*args):
            calls.append(args)
            return real_git(*args)

        return mock.patch.object(gitcmd, "git", spy), calls
