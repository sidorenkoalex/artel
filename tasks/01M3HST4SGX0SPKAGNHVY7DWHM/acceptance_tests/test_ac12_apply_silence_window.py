"""AC-12 — 01M3HST4SGX0SPKAGNHVY7DWHM: `--apply` при открытом окне тишины
удерживается, `note --flush` отправляет удержанное.

Источник — SPEC.md, «Критерии приёмки»:

AC-12. `--apply` при открытом окне тишины ничего не коммитит: запись
удержана и печатается причина, `note --flush` её отправляет.

Окно оставлено открытым и на время `--flush`: явный флаш обходит окно
решением Оператора (`_flush_pending`, :505; прецедент
`tests/test_notes.py::test_ac6_flush_pushes_held_note_while_window_stays_open`)
— критерий не требует закрывать окно, чтобы отправка состоялась.

Красен до реализации: флага `--apply` у `note` нет (`_parse_args`, :573) —
argparse отказывает кодом 2, и `capture` получает `SystemExit` вместо
вывода об удержании.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402
from orchestrator import notes  # noqa: E402


class ApplySilenceWindowTest(_sandbox.NoteSandbox):

    def test_ac12_open_window_holds_apply_until_flush(self):
        """Окно тишины открыто задачей в состоянии из
        `config.NOTE_SILENCE_WINDOW_STATES`: `--apply` не двигает origin,
        печатает причину удержания и оставляет одну запись в каталоге
        удержанных; `note --flush` доводит заготовку до origin целиком.

        Ловит мутацию: `--apply` проверяет окно тишины ПОСЛЕ коммита и
        push (или не проверяет вовсе, как отдельный от `_run` путь) —
        документ уезжает в origin сразу, и тест красен на сдвинувшемся
        `origin_head()` ещё до `--flush`.
        """
        draft = _sandbox.draft_with_extra_row()
        self.open_silence_window()
        before = self.origin_head()

        output = self.apply_draft(draft, "разнос под окном")

        self.assertEqual(before, self.origin_head())
        self.assertIn("удержан", output, output)
        self.assertTrue(output.split("удержан", 1)[1].strip(), output)
        self.assertEqual(len(notes.pending_notes()), 1, notes.pending_notes())

        self.note("--flush")

        self.assertEqual(self.origin_backlog(), draft)
        self.assertEqual(notes.pending_notes(), [])


if __name__ == "__main__":
    unittest.main()
