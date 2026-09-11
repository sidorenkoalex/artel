"""Общая фикстура приёмочных тестов 01M290PYPV5T2NFW1Y0HB8BD6E: реальный
неразрешаемый конфликт подтяжки из `in_dev` (`pull.evaluate`/
`fsm._pull_main_or_escalate`) + цикл `auto` поверх него.

Не копия `tests/sandbox.py::LightTransitionSandbox` (скил test-authoring,
«Лёгкая песочница переходов — не копия, импорт») — тонкая надстройка
поверх неё: конфликт подтяжки заводится ЕДИНСТВЕННЫМ новым узлом
(`conflict_handler`, через уже существующую точку расширения
`self.in_repo_handlers`), агент-заглушку цикла `auto` (`FakeRun`) эта
песочница тоже не копирует, а берёт готовой из `tests/test_auto_cycle.py`
(тот же класс, что уже использует `tasks/01M1VBEDGMEXHVGWAH42FTDZ4X/
acceptance_tests/_sandbox.py` для того же самого цикла).
"""
import subprocess
import sys
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tests"))

from orchestrator import auto, config, fsm, gitcmd, runner, store  # noqa: E402
from tests.sandbox import LightTransitionSandbox  # noqa: E402
from tests.test_auto_cycle import FakeRun  # noqa: E402

__all__ = ["PullConflictAutoSandbox", "CONFLICT_FILE"]

CONFLICT_FILE = "module.py"


class PullConflictAutoSandbox(LightTransitionSandbox):
    """`LightTransitionSandbox` + агент-заглушка `auto` + помощник
    конфликта подтяжки, специфичные ровно этой планке."""

    def setUp(self):
        super().setUp()
        self.agent = FakeRun()
        run_patcher = mock.patch.object(runner, "cmd_run", self.agent)
        run_patcher.start()
        self.addCleanup(run_patcher.stop)

    # ------------------------------------------------------- конфликт

    def conflict_handler(self, files: list, merge_stdout: str = "",
                         merge_stderr: str = "") -> callable:
        """Хук `self.in_repo_handlers`: `git merge` конфликтует, `git
        diff --name-only --diff-filter=U` называет `files`, `merge
        --abort` всегда успешен — то, чего сценарий этой планки требует
        от подтяжки (сам конфликт), остальное (checkout/reset/commit
        WIP-чекпоинта) делегируется дефолту `LightTransitionSandbox`
        (`fake_git`, безусловный успех — тот же приём, что и в её
        собственных тестах)."""
        def handler(repo, *args) -> subprocess.CompletedProcess | None:
            if args[:1] == ("merge",) and "--abort" in args:
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 0, "", "")
            if args[:1] == ("merge",):
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 1, merge_stdout,
                    merge_stderr)
            if args[:2] == ("diff", "--name-only"):
                text = "\n".join(files) + ("\n" if files else "")
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 0, text, "")
            return None
        return handler

    def escalate_in_dev_via_pull_conflict(
            self, *, conflict_files: tuple = (CONFLICT_FILE,),
            merge_stdout: str = "CONFLICT (content): Merge conflict in "
                                f"{CONFLICT_FILE}\n",
            behind: int = 3) -> str:
        """Проводит свежую задачу через `in_dev -> escalated` реальным
        неразрешаемым конфликтом подтяжки (`pull.Conflict`, не карта —
        `CONFLICT_FILE` не совпадает с `docs/codebase-map.md`, авторазрешение
        T067 не применяется). Возвращает вывод `fsm.cmd_advance`."""
        self.in_repo_handlers.append(
            self.conflict_handler(list(conflict_files), merge_stdout))
        behind_patcher = mock.patch.object(
            gitcmd, "commits_behind", return_value=behind)
        behind_patcher.start()
        self.addCleanup(behind_patcher.stop)
        return self.advance_from_in_dev()

    # ------------------------------------------------------- возврат

    def write_answer(self) -> Path:
        """Следующий `ANSWER-n.md` — безвредно независимо от того, требует
        ли `approve` именно его (`answer_baseline` может остаться `None`
        для этого класса эскалации, SPEC «Контекст»/AC-1)."""
        existing = sorted(self.tdir.glob("ANSWER-*.md"))
        n = len(existing) + 1
        path = self.tdir / f"ANSWER-{n}.md"
        path.write_text(
            f"---\ntask: {self.TASK}\ntype: answer\nauthor_role: operator\n"
            f"schema_version: 1\n---\n\n# ANSWER-{n}\n\nКонфликт подтяжки "
            f"разобран, продолжаем.\n", encoding="utf-8")
        return path

    def approve(self) -> str:
        self.write_answer()
        return self.capture(fsm.cmd_approve, self.TASK)

    # ------------------------------------------------------------ auto

    def auto(self) -> str:
        self.agent.arm(config.AUTO_MAX_STEPS)
        return self.capture(auto.cmd_auto, self.TASK)

    def role_run_count(self) -> int:
        return len(self.agent.calls)

    def journal_rows(self) -> list:
        return store.task_steps(store.db(), self.TASK)
