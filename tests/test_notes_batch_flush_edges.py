"""Края пакетного сброса удержанных записей (`notes._flush_pending`,
`notes._flush_batch`, SPEC 01M5N8A5JBEQ15DCHDP95EBDZR), не покрытые
долгоживущим файлом задачи: предупреждение об удержании без базы у правки
конфигурации при явном флаше (R1-F1 ревью итерации 1) и снятие
недописанной правки записи пакета с общего рабочего дерева (R1-F2).

Стенд — `tests/test_doc_commit_suite_gate.py::SuiteGateSandbox` (настоящий
bare `origin`, клон артели, шпион полного набора).
"""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, notes  # noqa: E402
from tests.sandbox import capture  # noqa: E402
from tests.test_doc_commit_suite_gate import (CONFIG_REL,  # noqa: E402
                                              NEW_CONFIG_TEXT,
                                              SuiteGateSandbox)


class ConfigRecordNoBaseWarningTest(SuiteGateSandbox):

    def hold_config_without_base(self, text: str = NEW_CONFIG_TEXT) -> None:
        """Удержанная правка конфигурации без `held_base` — как запись
        старого формата либо после сетевого отказа fetch."""
        self.open_silence_window()
        self.doc_commit(CONFIG_REL, "--from",
                        str(self.source_file(text, "config-draft.yaml")),
                        "--message", "поворот крутилки")
        self.close_silence_window()
        pending = sorted((config.ROOT / ".artel" / "notes-pending").glob("*.json"))
        self.assertEqual(len(pending), 1, pending)
        record = json.loads(pending[0].read_text(encoding="utf-8"))
        record.pop(notes.HELD_BASE_KEY, None)
        pending[0].write_text(json.dumps(record, ensure_ascii=False),
                              encoding="utf-8")

    def test_explicit_flush_warns_about_missing_base_of_config_record(self):
        """Явный флаш (`note --flush` и `doc-commit --flush`) удержанной
        без базы правки конфигурации печатает `<путь>: NO_BASE_WARNING` и
        отправляет её прежним путём — правила правок конфигурации пакетный
        сброс не меняет (требование 3).

        Ловит мутацию: ветка `_suite_gate_applies` в `_flush_pending`
        уходит в `continue` раньше проверки `HELD_BASE_KEY` — правка
        уходит, а предупреждения в выводе нет.
        """
        self.spy_suite(green=True)
        for name, fn in (("note", notes.cmd_note),
                         ("doc-commit", notes.cmd_doc_commit)):
            with self.subTest(entry=name):
                text = f"developer:\n  model: {name}\n"
                self.hold_config_without_base(text)

                out = capture(fn, ["--flush"])

                self.assertIn(f"{CONFIG_REL}: {notes.NO_BASE_WARNING}", out)
                self.assertEqual(self.origin_show(CONFIG_REL), text)
                self.assertEqual(notes.pending_notes(), [])

    def test_opportunistic_flush_still_skips_config_record_silently_on_base(self):
        """Попутный сброс правку конфигурации по-прежнему пропускает
        прежней строкой причины и о базе не говорит: запись не
        отправляется, предупреждать не о чем.

        Ловит мутацию: предупреждение о базе вынесено до проверки
        `explicit` — попутный сброс в начале обычной `note` печатает
        `NO_BASE_WARNING` записи, которую не отправляет.
        """
        self.spy_suite(green=True)
        self.hold_config_without_base()

        out = self.note_row("ЗАМЕТКАБЕЗБАЗЫ")

        self.assertIn("попутно не отправляется", out)
        self.assertNotIn(notes.NO_BASE_WARNING, out)
        self.assertEqual(len(notes.pending_notes()), 1)


class BatchWriteFailureTest(SuiteGateSandbox):

    def test_half_written_record_does_not_become_batch_head_for_next(self):
        """`OSError` при записи файла записи пакета после частичной записи
        снимает правку с общего рабочего дерева: следующая запись пакета
        того же пути (`docs/backlog.md`) строится от головы пакета, а не от
        недописанного файла.

        Ловит мутацию: ветка `except OSError` в `_flush_batch` просто
        продолжает цикл — вторая заметка читает `_read_backlog` из грязного
        дерева, и мусор первой записи уезжает в origin (либо вторая запись
        отказывает валидацией разметки).
        """
        self.open_silence_window()
        self.note_row("ПЕРВАЯЗАМЕТКА")
        self.note_row("ВТОРАЯЗАМЕТКА")
        self.close_silence_window()
        self.assertEqual(len(notes.pending_notes()), 2)
        real_write = notes._write_backlog
        calls = []

        def write_then_fail(work_dir, text):
            calls.append(text)
            if len(calls) == 1:
                (work_dir / notes.BACKLOG_REL).write_text(
                    "НЕДОПИСАННЫЙМУСОР", encoding="utf-8")
                raise OSError("диск отказал посреди записи")
            real_write(work_dir, text)

        with mock.patch.object(notes, "_write_backlog", write_then_fail):
            capture(notes.cmd_note, ["--flush"])

        backlog = self.origin_show(notes.BACKLOG_REL)
        self.assertIn("ВТОРАЯЗАМЕТКА", backlog)
        self.assertNotIn("НЕДОПИСАННЫЙМУСОР", backlog)
        self.assertNotIn("ПЕРВАЯЗАМЕТКА", backlog)
        self.assertEqual(len(notes.pending_notes()), 1)


if __name__ == "__main__":
    unittest.main()
