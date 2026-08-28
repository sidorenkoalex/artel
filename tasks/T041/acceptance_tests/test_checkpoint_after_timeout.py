"""Приёмочные тесты T041 — протокол рестарта после таймаута шага:
WIP-чекпоинт оркестратора.

Источник — tasks/T041/SPEC.md, «Критерии приёмки» (AC-1..AC-5).

Чекпоинт коммитит РЕАЛЬНОЕ рабочее дерево ветки задачи (`git add -A` +
`git commit`) — заглушкой `gitcmd.git` эту механику не проверить и не
отличить от отсутствия коммита вовсе. Песочница — `RealPultGitTest`
(tests/test_git_fixation.py): временный каталог САМ настоящий
git-репозиторий, `fixation.check_integrity` работает по-настоящему
(тот же довод, что у `IntegrityIncidentBlocksRunTest` в том же модуле).
Процесс агента при этом подложный (`TimeoutThenKilledProc`/`FailedProc`
ниже, тот же приём, что `tests/test_agent_log.py` и
`tasks/T040/acceptance_tests`): таймаут коротко замыкает `proc.wait()`
без реального 30-минутного ожидания. WIP, который агент «успел
оставить» до таймаута/провала, — файл, дописываемый прямо внутри
`wait()` (а не до запуска шага): написать его РАНЬШЕ означало бы
подсунуть уже испорченное дерево на вход `fixation.check_integrity`
этого же запуска и сорвать сценарий на СТАРТЕ шага, а не на его обрыве.

AC-2 испытан через `run` (restart того же шага `in_dev`), не `advance`:
`advance` в состоянии `in_dev` не про эту роль (следующий переход ждёт
готового PLAN.md разработчика, которого оборванный таймаутом шаг не
оставляет, — отказ по guard'у, а не по обсуждаемой в критерии «грязной
копии»). Именно `run` использует `fixation.check_integrity`, сверяющую
не только чистоту дерева, но и sha с зафиксированным на входе шага
(`orchestrator/fixation.py`) — критерий требует, чтобы «хвосты
оборванного шага» не эскалировали рестарт вовсе (SPEC, Контекст:
сегодня рестарт «уводит задачу в escalated»), поэтому тест сверяет
итоговое состояние задачи после рестарта, не только текст сообщения
о «грязной копии».

WIP оставляется файлом ИМЕННО под `tasks/<id>/` (не где-то в дереве
репозитория): `fixation._fix_dogfood` (`orchestrator/fixation.py`)
сверяет чистоту узко — `gitcmd.is_clean(f"tasks/{task_id}")`, — грязный
файл вне этого каталога `check_integrity` вообще не заметит, и сценарий
«таймаут → грязная копия → эскалация рестарта» на нём не воспроизвести
(проверено прогоном на немодифицированном коде: WIP-файл в корне
рабочего дерева не мешает рестарту и без чекпоинта, то есть тест на нём
был бы тавтологией, не критерием).
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, gitcmd, runner, store, workspace  # noqa: E402
from tests.test_git_fixation import FakeProc, RealPultGitTest  # noqa: E402


class FakeStream:
    """Пайп процесса: отдаёт заготовленные строки, чисто заканчивается EOF."""

    def __init__(self, lines):
        self.lines = iter(lines)
        self.closed = False

    def __iter__(self):
        return self

    def __next__(self) -> str:
        return next(self.lines)

    def close(self) -> None:
        self.closed = True


class TimeoutThenKilledProc:
    """Таймаут шага: `wait()` сначала бросает `TimeoutExpired` (после
    опционального побочного эффекта `leaves_wip` — файла, который агент
    успел написать до того, как замолчал), затем отдаёт код убитого
    процесса. Тот же приём, что
    `tests/test_agent_log.py::CmdRunLoggingTest.test_timeout_kills_process_and_journals`
    и `tasks/T040/acceptance_tests` (`timeout_then_killed_proc`)."""

    def __init__(self, lines, leaves_wip=None):
        self.stdout = FakeStream(lines)
        self._calls = 0
        self._leaves_wip = leaves_wip

    def wait(self, timeout=None) -> int:
        self._calls += 1
        if self._calls == 1:
            if self._leaves_wip:
                self._leaves_wip()
            raise subprocess.TimeoutExpired(cmd="claude",
                                            timeout=config.AGENT_TIMEOUT_SEC)
        return -9

    def kill(self) -> None:
        pass


class FailedProc:
    """Провал по коду возврата — НЕ таймаут (AC-3): `wait()` сразу отдаёт
    `returncode`, опционально оставив WIP до этого — то, что агент успел
    написать перед падением."""

    def __init__(self, lines, returncode, leaves_wip=None):
        self.stdout = FakeStream(lines)
        self.returncode = returncode
        self._leaves_wip = leaves_wip

    def wait(self, timeout=None) -> int:
        if self._leaves_wip:
            self._leaves_wip()
        return self.returncode

    def kill(self) -> None:
        pass


class CheckpointAfterTimeoutTest(RealPultGitTest):
    """AC-1..AC-4: WIP-чекпоинт оркестратора при таймауте шага `developer`."""

    def run_agent(self, proc) -> str:
        """Тот же приём, что `RealPultGitTest.run_faked`, но с заданным
        подложным процессом агента вместо всегда успешного `FakeProc`."""
        real_popen = subprocess.Popen

        def side_effect(cmd, *args, **kwargs):
            if cmd and cmd[0] == "claude":
                return proc
            return real_popen(cmd, *args, **kwargs)

        with mock.patch.object(runner, "spawn_agent", side_effect=side_effect):
            return self.capture(runner.cmd_run, self.TASK)

    def write_wip(self, name: str = "wip_from_agent.md") -> Path:
        """Незакоммиченный файл — то, что реально оставляет оборванный
        агент в рабочем дереве ветки задачи. Каталог `tasks/<id>/` —
        не произвольный выбор: `fixation.check_integrity` сверяет
        чистоту узко по нему (см. модульный докстринг). Адрес — worktree
        задачи (`workspace.path`), не диск main (`config.TASKS`): с
        SPEC T045/T048 роль работает в собственном worktree, `config.TASKS`
        для догфуд-задачи вообще не существует на диске (дефект SPEC
        T059, «Контекст», из-за которого этот файл падал на текущем
        коде до правки адреса)."""
        path = workspace.path(self.TASK) / "tasks" / self.TASK / name
        path.write_text("работа агента, оборванная посреди шага\n",
                        encoding="utf-8")
        return path

    def orchestrator_steps(self) -> list:
        return [r for r in store.task_steps(store.db(), self.TASK)
               if r["actor"] == "orchestrator"]

    def task_row(self):
        return store.get_task(store.db(), self.TASK)

    def test_ac1_timeout_with_dirty_tree_creates_checkpoint_commit(self):
        self.enter_in_dev()

        out = self.run_agent(TimeoutThenKilledProc(
            ["агент работает, потом молчит\n"], leaves_wip=self.write_wip))

        self.assertIn("таймаут", out)
        self.assertTrue(
            gitcmd.is_clean(repo=workspace.path(self.TASK)),
            "AC-1: чекпоинт коммитит WIP — рабочее дерево worktree "
            "задачи снова чистое")
        subject = self.git_in_worktree("log", "-1", "--format=%s").strip()
        self.assertEqual(
            subject,
            f"{self.TASK}: WIP-чекпоинт после таймаута шага developer",
            f"AC-1: сообщение коммита-чекпоинта — фактическое: {subject!r}")

        entries = self.orchestrator_steps()
        self.assertEqual(
            len(entries), 1,
            f"AC-1: запись журнала задачи actor=orchestrator по факту "
            f"чекпоинта — найдено {len(entries)}")
        marker = f"{entries[0]['action']} {entries[0]['detail']}".lower()
        self.assertIn(
            "таймаут", marker,
            f"AC-1: запись журнала обязана нести пометку таймаута — "
            f"фактическая запись: {entries[0]['action']!r} / "
            f"{entries[0]['detail']!r}")

    def test_ac2_restart_after_checkpoint_does_not_escalate(self):
        self.enter_in_dev()
        self.run_agent(TimeoutThenKilledProc(
            ["агент работает, потом молчит\n"], leaves_wip=self.write_wip))
        self.assertEqual(
            self.task_row()["state"], "in_dev",
            "предусловие: сам таймаут (без рестарта) не эскалирует задачу")

        out = self.run_agent(FakeProc(["готово\n"]))

        self.assertNotIn(
            "инцидент целостности", out,
            "AC-2: рестарт после чекпоинта по AC-1 не эскалирует задачу "
            "по «грязной копии» хвостов оборванного шага")
        self.assertEqual(
            self.task_row()["state"], "in_dev",
            f"AC-2: рестарт шага после чекпоинта обязан пройти без "
            f"эскалации — фактический вывод рестарта:\n{out}")

    def test_ac3_return_code_failure_does_not_checkpoint(self):
        self.enter_in_dev()
        before = self.head()

        with mock.patch.object(config, "AGENT_ATTEMPTS", 1), \
                mock.patch.object(runner.time, "sleep", lambda _: None):
            self.run_agent(FailedProc(["падаю с кодом возврата\n"],
                                      returncode=1, leaves_wip=self.write_wip))

        self.assertEqual(
            self.head(), before,
            "AC-3: провал по коду возврата (rc != 0, не таймаут) не "
            "коммитит чекпоинт")
        self.assertFalse(
            gitcmd.is_clean(repo=workspace.path(self.TASK)),
            "AC-3: рабочее дерево worktree задачи остаётся "
            "незакоммиченным, как до этой задачи")

    def test_ac4_timeout_on_clean_tree_creates_no_empty_checkpoint(self):
        self.enter_in_dev()
        self.assertTrue(
            gitcmd.is_clean(repo=workspace.path(self.TASK)),
            "предусловие: дерево worktree задачи чистое")
        before = self.head()

        self.run_agent(TimeoutThenKilledProc(["агент молчит, ничего не "
                                              "менял\n"]))

        self.assertEqual(
            self.head(), before,
            "AC-4: таймаут при чистом рабочем дереве не создаёт пустой "
            "коммит-чекпоинт")
        self.assertTrue(gitcmd.is_clean(repo=workspace.path(self.TASK)))


# AC-5: manual — CI (`.github/workflows/ci.yml`, шаг `unittest discover -s
# tests -v`) уже гоняет полный набор `tests/` на каждый пуш; дублировать
# прогон подпроцессом внутри acceptance_tests того же смысла не добавляет
# и рискует ложным красным из-за окружения этой машины (тот же довод, что
# в tasks/T040/acceptance_tests, AC-4, и tasks/T037/acceptance_tests,
# AC-5). Число тестов «до этой задачи» — 618 (`python3 -c "import
# unittest; print(unittest.TestLoader().discover('tests').countTestCases())"`,
# ветка task/t041-protokol-restarta-posle-taymau от свежего main) —
# планка для сверки Оператором/ревьювером на приёмке, что набор не
# уменьшился и не покраснел, без повторного авто-подсчёта здесь.


if __name__ == "__main__":
    unittest.main()
