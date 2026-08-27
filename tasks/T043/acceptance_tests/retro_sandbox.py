"""Общая песочница приёмочных тестов T043 (RETRO), по образцу
`tasks/T042/acceptance_tests/test_map_regen_on_merge.py` (`MapRegenSandboxTest`).

Не файл теста (имя не начинается с `test_`) — `unittest discover` его не
подбирает напрямую, это shared fixture для `test_retro_*.py` этого
каталога.

Поверх `tests.test_invariants.FsmTest` (БД и артефакты во временном
каталоге, `subprocess.run` подменён на уровне `gitcmd.subprocess.run` —
реальный git не исполняется) добавляет:

- второй синтетический `config.ROOT` для `docs/retro/` и
  `docs/codebase-map.md` — тем же приёмом, что `MapRegenSandboxTest`
  (`config.TASKS` из `FsmTest` и `config.ROOT` здесь — два независимых
  временных дерева, ровно как в проде `TASKS = ROOT / "tasks"`, но
  раздельно патчатся: реализации RETRO и T042 читают/пишут только
  `config.ROOT / "docs/..."`, артефакты задачи — только `config.TASKS`);
- `docs/codebase-map.md` с тем же текстом до и «после» регенерации:
  ветка T042 «без содержательных отличий» — коммита карты нет, шаг не
  засоряет журнал/alerts, которые проверяют тесты этого файла;
- фиксированное `store.now()` — детерминизм (AC-4) требует, чтобы два
  независимых прогона песочницы с одинаковыми входными данными писали в
  `steps.ts`/`tasks.created_at` один и тот же текст, а не текущее время
  стенда;
- `MERGE_SHA` — фиксированный ответ `git rev-parse HEAD` (использует и
  `fixation.read` при `confirm_fixation`, и код RETRO при вычислении sha
  коммита мержа для адреса артефактов, требование 8) и вместе с ним sha,
  передаваемый в `cmd_approve` (иначе `confirm_fixation` увидел бы
  ненулевой `current` и потребовал бы sha, который тесты не передают —
  тот же приём, каким довольствовался T042, только там `rev-parse HEAD`
  не переопределялся и `current` оставался пустым).
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import cleanup, config, fsm, gitcmd, store  # noqa: E402
from tests.test_invariants import FsmTest  # noqa: E402

MERGE_SHA = "eeee555566667777888899990000111122223333"
FIXED_NOW = "2026-08-27 12:00:00Z"

COMMITTED_MAP = (
    "---\nbuilt_at_sha: aaaa000011112222333344445555666677778888\n"
    "---\n\n# Карта кодовой базы\n\nСодержимое.\n")

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: {title}

## Контекст

{context_line}
Вторая строка контекста — не должна попасть в дайджест.

## Требования

1. Требование фикстуры.

## Критерии приёмки

AC-1. Критерий фикстуры.

## Не входит

- Ничего.
"""

TASK_TITLE = "тестовая ретро-задача"
CONTEXT_LINE = "Первая строка контекста фикстуры T043."

# Собрана через .replace() плейсхолдеров, а не буквальными именами
# методов/пометками критериев в исходнике: `scripts/guard.py` сканирует
# *.py под tasks/T043/acceptance_tests/ плоским regex'ом по тексту
# (TEST_AC, AC_MARKER — без учёта того, что совпадение внутри строкового
# литерала фикстуры), и буквальные подстроки заразили бы трассируемость
# критериев настоящей задачи T043 фиктивными пометками/тестами.
ACCEPTANCE_TEST_FIXTURE = ('''"""Фикстура приёмочных тестов фиктивной задачи — для RETRO-подсчёта."""
# @AC-3: manual — причина фикстуры.
# @AC-4: skip — причина фикстуры.
import unittest


class FixtureTest(unittest.TestCase):
    def test_@ac1_one(self):
        pass

    def test_@ac2_two(self):
        pass
''').replace("@ac", "ac").replace("@AC", "AC")


class RetroSandboxTest(FsmTest):
    """merge_gate/kill с управляемыми git-ответами на синтетическом ROOT."""

    def setUp(self):
        super().setUp()

        retro_root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, retro_root, ignore_errors=True)
        (retro_root / "docs" / "retro").mkdir(parents=True)
        (retro_root / "docs" / "codebase-map.md").write_text(
            COMMITTED_MAP, encoding="utf-8")
        root_patcher = mock.patch.object(config, "ROOT", retro_root)
        root_patcher.start()
        self.addCleanup(root_patcher.stop)
        self.retro_root = retro_root

        now_patcher = mock.patch.object(store, "now", staticmethod(lambda: FIXED_NOW))
        now_patcher.start()
        self.addCleanup(now_patcher.stop)

        self.calls: list[list[str]] = []

    # ------------------------------------------------------------ фикстуры

    def write_context_spec(self, task=None, title=TASK_TITLE,
                           context_line=CONTEXT_LINE) -> None:
        task = task or self.TASK
        (self.tdir / "SPEC.md").write_text(
            SPEC_TEXT.format(task=task, title=title, context_line=context_line),
            encoding="utf-8")

    def write_acceptance_tests_fixture(self) -> None:
        adir = self.tdir / "acceptance_tests"
        adir.mkdir(parents=True, exist_ok=True)
        (adir / "test_fixture.py").write_text(ACCEPTANCE_TEST_FIXTURE,
                                              encoding="utf-8")

    def add_finished_step(self, actor: str, usd: float, tokens: int,
                          attempt: str = "попытка 1/1") -> None:
        store.journal(store.db(), self.TASK, actor, "agent run finished",
                     f"rc=0, {attempt}, стоимость ${usd:.4f}, токенов {tokens}")

    def add_escalation(self, detail: str) -> None:
        store.journal(store.db(), self.TASK, "fsm", "state -> escalated", detail)

    # ------------------------------------------------------------- git-фейк

    def git_subcommands(self) -> list[str]:
        return [c[1] for c in self.calls if len(c) > 1 and c[0] == "git"]

    def fake_subprocess(self, current_branch=None, fail_git_subcommands=()):
        """`current_branch` — ответ `rev-parse --abbrev-ref HEAD` (kill-путь);
        `fail_git_subcommands` — какие git-подкоманды отвечают отказом.
        `rev-parse HEAD` — всегда `MERGE_SHA` (упрощение: песочница не
        отслеживает настоящее состояние дерева, только код оркестратора,
        как и `MapRegenSandboxTest`)."""
        def fake(cmd, *args, **kwargs):
            cmd = list(cmd)
            self.calls.append(cmd)
            if cmd and cmd[0] == "python3":
                # scripts/codebase_map.py не вызывается T043 напрямую; если
                # что-то её всё же зовёт — файл карты уже «регенерирован»
                # (не изменился), веткой T042 «без диффа» коммит не пойдёт.
                return subprocess.CompletedProcess(cmd, 0, "", "")
            if (len(cmd) > 1 and cmd[0] == "git"
                    and cmd[1] in fail_git_subcommands):
                return subprocess.CompletedProcess(
                    cmd, 1, "", "стенд: git-подкоманда упала")
            if cmd[:3] == ["git", "rev-parse", "HEAD"]:
                return subprocess.CompletedProcess(cmd, 0, MERGE_SHA, "")
            if (cmd[:3] == ["git", "rev-parse", "--abbrev-ref"]
                    and current_branch is not None):
                return subprocess.CompletedProcess(cmd, 0, current_branch, "")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return fake

    def approve(self, **fake_kwargs) -> str:
        fake = self.fake_subprocess(**fake_kwargs)
        with mock.patch.object(gitcmd.subprocess, "run", fake):
            return self.capture(fsm.cmd_approve, self.TASK, MERGE_SHA)

    def kill(self, **fake_kwargs) -> str:
        fake = self.fake_subprocess(**fake_kwargs)
        with mock.patch.object(gitcmd.subprocess, "run", fake):
            return self.capture(cleanup.cmd_kill, self.TASK)

    def retro_path(self, task=None) -> Path:
        return self.retro_root / "docs" / "retro" / f"{task or self.TASK}.md"

    def retro_text(self, task=None) -> str:
        path = self.retro_path(task)
        self.assertTrue(path.exists(),
                        f"{path} не создан — RETRO не сгенерирован")
        return path.read_text(encoding="utf-8")
