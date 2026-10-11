"""Команда `artifact-history-snapshots` (SPEC 01M4M68557TT4KYN814H8AZ01A):
отказы origin и отчёт о файле, которого в снимке нет, — то, что не
покрывает долгоживущий файл задачи
(`tests/test_01m4m68557tt4kyn814h8az01a_history_snapshots.py`)."""

import contextlib
import io
import shutil
import stat
import tempfile
from pathlib import Path

from orchestrator import config, snapshot, store
from tests.sandbox import OriginRealGitSandbox

TASK = "T042"


class HistoryCommandSandbox(OriginRealGitSandbox):
    """Клон артели — репозиторий песочницы, рядом bare `origin`; каталог
    задачи `TASK` — только в `origin/main` (коммит вспомогательного
    клона)."""

    def setUp(self):
        super().setUp()
        self.add_origin()
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        scratch = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        self.scratch = str(Path(scratch) / "clone")
        self.git("clone", "-q", self.bare, self.scratch)
        self.git("-C", self.scratch, "config", "user.name", "artel tests")
        self.git("-C", self.scratch, "config", "user.email",
                 "tests@artel.invalid")

    def commit_main(self, files: dict) -> None:
        for rel, text in files.items():
            path = Path(self.scratch) / "tasks" / TASK / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("-C", self.scratch, "add", "-A")
        self.git("-C", self.scratch, "commit", "-q", "-m", "каталог задачи")
        self.git("-C", self.scratch, "push", "-q", "origin",
                 f"HEAD:{config.MAIN_BRANCH}")

    def refs(self, *where: str) -> str:
        return self.git(*where, "for-each-ref", "refs/artifacts/")

    def history_records(self) -> list:
        return store.steps_of_action(store.db(), snapshot.HISTORY_ACTION)

    def run_command(self, dry_run: bool = False) -> tuple:
        """(код выхода, вывод) команды; код 0 — успех."""
        out = io.StringIO()
        code = 0
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                snapshot.cmd_artifact_history_snapshots(dry_run)
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else 1
                out.write(f"\n{exc.code}")
        return code, out.getvalue()


class OriginRefusalTest(HistoryCommandSandbox):

    def test_unreachable_origin_creates_nothing(self):
        """origin не отвечает — отказ до любой записи: ни ссылки, ни журнала.

        Ловит мутацию: отказ fetch проглатывается и команда идёт дальше по
        устаревшему `origin/main` и неполному перечню ссылок origin —
        причина «origin не ответил» в выводе не названа.
        """
        self.commit_main({"SPEC.md": "спека\n"})
        self.git("fetch", "-q", "origin")
        self.git("remote", "set-url", "origin",
                 str(Path(self.bare).parent / "нет-такого-origin"))

        code, out = self.run_command()

        self.assertNotEqual(code, 0, out)
        self.assertIn("origin не ответил", out)
        self.assertEqual(self.refs(), "", out)
        self.assertEqual(self.history_records(), [], out)

    def test_rejected_push_leaves_no_ref_and_no_record(self):
        """origin отклонил push снимка — локальной ссылки и записи журнала нет, команда кончается отказом с причиной.

        Ловит мутацию: локальная ссылка или запись журнала пишутся до
        push (или несмотря на его отказ) — `doctor` получил бы запись о
        снимке, которого в origin нет, а повторный запуск счёл бы ссылку
        существующей и уже не отправил бы её.
        """
        self.commit_main({"SPEC.md": "спека\n"})
        hook = Path(self.bare) / "hooks" / "pre-receive"
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text("#!/bin/sh\necho 'запрещено тестом' >&2\nexit 1\n",
                        encoding="utf-8")
        hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP
                   | stat.S_IXOTH)

        code, out = self.run_command()

        self.assertNotEqual(code, 0, out)
        self.assertIn(f"refs/artifacts/{TASK}: не создана", out)
        self.assertEqual(self.refs(), "", out)
        self.assertEqual(self.refs("-C", self.bare), "", out)
        self.assertEqual(self.history_records(), [], out)


class MissingInSnapshotTest(HistoryCommandSandbox):

    def test_file_only_in_main_is_reported_with_absent_snapshot_sha(self):
        """Файл main, которого в существующем снимке нет, попадает в отчёт строкой с sha main и «нет» вместо sha снимка; ссылка прежняя.

        Ловит мутацию: отчёт перебирает только общие для main и снимка
        файлы — файл, который пропал бы при уборке `tasks/` из main, в
        отчёт не попадает.
        """
        self.commit_main({"SPEC.md": "спека\n"})
        self.git("fetch", "-q", "origin")
        code, _out = self.run_command()
        self.assertEqual(code, 0, _out)
        head = self.git("rev-parse", f"refs/artifacts/{TASK}").strip()
        self.commit_main({"ANSWER-1.md": "ответ после мержа\n"})

        code, out = self.run_command()

        self.assertEqual(code, 0, out)
        blob = self.git("-C", self.bare, "rev-parse",
                        f"{config.MAIN_BRANCH}:tasks/{TASK}/ANSWER-1.md").strip()
        rows = [line for line in out.splitlines()
                if f"tasks/{TASK}/ANSWER-1.md" in line]
        self.assertEqual(len(rows), 1, out)
        self.assertIn(blob, rows[0])
        self.assertIn("снимок нет", rows[0])
        self.assertEqual(
            self.git("rev-parse", f"refs/artifacts/{TASK}").strip(), head)
        self.assertEqual(len(self.history_records()), 1, out)


if __name__ == "__main__":
    import unittest
    unittest.main()
