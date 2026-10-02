"""Юнит-тесты базы удержанного `doc-commit` и команд `note --pending`/
`note --drop-pending` (SPEC 01M3Y75X6K2ZMD85971TCWV41E) — свойства, не
покрытые долгоживущим файлом задачи: база при сетевом удержании, строка
перечня многострочного содержимого, отказ снятия по чужому id.
"""
import io
import json
import os
import shutil
import tempfile
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from orchestrator import config, notes, store
from tests.sandbox import RealGitSandbox


def run_command(fn, argv) -> str:
    buf = io.StringIO()
    exit_text = ""
    with redirect_stdout(buf), redirect_stderr(buf):
        try:
            fn(list(argv))
        except SystemExit as exc:
            exit_text = "" if exc.code is None else str(exc.code)
    return buf.getvalue() + "\n" + exit_text


class HeldBaseUnitSandbox(RealGitSandbox):

    def setUp(self):
        super().setUp()
        role_patcher = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        role_patcher.start()
        self.addCleanup(role_patcher.stop)
        self.doc = self.root / "docs" / "roadmap.md"
        self.doc.parent.mkdir(parents=True, exist_ok=True)
        self.doc.write_text("# Роадмап\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "документ")
        self.source_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.source_dir, ignore_errors=True)

    def pending_dir(self) -> Path:
        return config.ROOT / ".artel" / "notes-pending"

    def write_pending(self, record: dict) -> str:
        d = self.pending_dir()
        d.mkdir(parents=True, exist_ok=True)
        record_id = f"{int(time.time() * 1000):013d}-abcdef01"
        (d / f"{record_id}.json").write_text(
            json.dumps(record, ensure_ascii=False), encoding="utf-8")
        return record_id


class NetworkHoldBaseTest(HeldBaseUnitSandbox):

    def test_network_hold_stores_head_blob(self):
        """Удержание сетевым отказом (origin недоступен) тоже несёт базу.

        Сценарий: origin указывает на несуществующий каталог, `doc-commit`
        отказывает «не удалось отправить» и удерживает запись — в ней поле
        `notes.HELD_BASE_KEY` с blob-sha `HEAD:docs/roadmap.md`.

        Ловит мутацию: база добавляется только на ветке окна тишины в
        `_run`, а не в `_hold_pending` — запись сетевого удержания уходит
        без базы и на флаше идёт по пиновой сверке (сценарий 02.10).
        """
        self.git("remote", "add", "origin",
                 str(Path(self.source_dir) / "нет-такого"))
        source = Path(self.source_dir) / "new.md"
        source.write_text("# Роадмап\n\nновое\n", encoding="utf-8")
        base = self.git("rev-parse", "HEAD:docs/roadmap.md").strip()

        out = run_command(notes.cmd_doc_commit,
                          ["docs/roadmap.md", "--from", str(source),
                           "--message", "правка"])

        records = notes.pending_notes()
        self.assertEqual(len(records), 1, out)
        self.assertEqual(records[0].get(notes.HELD_BASE_KEY), base, out)


class PendingLineTest(HeldBaseUnitSandbox):

    def test_multiline_content_stays_one_line_and_truncated(self):
        """Многострочное содержимое `doc-commit` даёт ОДНУ строку перечня
        с выдержкой не длиннее 80 знаков содержимого.

        Ловит мутацию: выдержка берётся без замены переводов строк —
        запись `note --pending` рвётся на несколько строк вывода, и id
        стоит только на первой; либо обрезка снята.
        """
        content = "# Заголовок\n" + "строка текста\n" * 20
        record_id = self.write_pending(
            {"kind": notes.DOC_COMMIT_KIND, "path": "docs/roadmap.md",
             "content": content, "message": "м"})

        out = run_command(notes.cmd_note, ["--pending"])

        lines = [line for line in out.split("\n") if line.strip()]
        self.assertEqual(len(lines), 1, out)
        self.assertIn(record_id, lines[0])
        self.assertIn(content[:80].replace("\n", " "), lines[0])
        self.assertNotIn(content[:81].replace("\n", " "), lines[0])

    def test_empty_pending_says_so(self):
        """Пустой каталог удержанных записей — именованная строка.

        Ловит мутацию: пустой перечень печатает ничего — Оператор не
        отличит «записей нет» от сбоя команды.
        """
        out = run_command(notes.cmd_note, ["--pending"])
        self.assertIn("удержанных записей нет", out)


class DropPendingRefusalTest(HeldBaseUnitSandbox):

    def test_unknown_or_traversal_id_refuses_without_removal(self):
        """Id, которого нет среди файлов каталога (в том числе «../…»),
        отказывает: ни одна запись не снята, файл вне каталога цел,
        журнал не пишется.

        Ловит мутацию: id склеивается в путь `_pending_dir() / f"{id}.json"`
        без сверки с перечнем — «../outside» снимает файл вне каталога.
        """
        record_id = self.write_pending(
            {"kind": "insert", "section": "копилка", "text": "т"})
        outside = config.ROOT / ".artel" / "outside.json"
        outside.write_text("{}", encoding="utf-8")
        before = store.db().execute("SELECT COUNT(*) FROM steps").fetchone()[0]

        for bad in ("../outside", "нет-такой"):
            out = run_command(notes.cmd_note, ["--drop-pending", bad])
            self.assertIn("note --pending", out)

        self.assertTrue(outside.exists())
        self.assertTrue((self.pending_dir() / f"{record_id}.json").exists())
        after = store.db().execute("SELECT COUNT(*) FROM steps").fetchone()[0]
        self.assertEqual(after, before)
