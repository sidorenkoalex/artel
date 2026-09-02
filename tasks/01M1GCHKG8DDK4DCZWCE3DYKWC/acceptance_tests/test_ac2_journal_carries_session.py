"""AC-2: каждая НОВАЯ запись журнала `steps` несёт идентификатор
сессии, её записавшей.

Проверяется на двух командах, которые сегодня журналируют БЕЗ единого
понятия "сессия" вовсе — `pause.cmd_pause`/`cmd_resume` (актор
буквальной строкой `"operator"`, ни разу не резолвящий identity
вызывающего процесса). Способ хранения session_id — решение
разработчика (отдельная колонка либо часть `detail`, SPEC требование
2) — проверка ищет искомую identity среди ВСЕХ полей новой записи
(`_sandbox.row_carries`), не полагаясь на конкретную колонку.

Красный до реализации: сегодня `pause.cmd_pause`/`cmd_resume` не читают
`ARTEL_SESSION_ID` и не резолвят identity вообще — искомая строка не
может появиться ни в одном поле новой записи журнала.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import pause  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import LeaseTaskTest, any_step_carries, capture  # noqa: E402


class JournalCarriesSessionTest(LeaseTaskTest):

    def test_ac2_pause_journal_entry_carries_the_session_identity(self):
        """`pause.cmd_pause` вызывается под явным `ARTEL_SESSION_ID` —
        новая запись журнала, зафиксировавшая факт паузы, обязана нести
        этот идентификатор среди своих полей.

        Ловит мутацию: разработчик резолвит identity сессии и прокидывает
        её в `store.journal` для `cmd_resume`, но забывает сделать то же
        самое для `cmd_pause` (симметричная правка двух соседних функций
        — типичное место разъехаться); тест на resume при этом останется
        зелёным, а этот покраснеет.
        """
        before = len(self.steps())

        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": "sess-ac2-pause"}):
            capture(pause.cmd_pause, self.TASK)

        new_steps = self.steps()[before:]
        self.assertTrue(new_steps, "pause обязан журналировать факт паузы")
        self.assertTrue(
            any_step_carries(new_steps, "sess-ac2-pause"),
            f"новая запись журнала `pause` не несёт идентификатор "
            f"записавшей её сессии (AC-2): {new_steps}")

    def test_ac2_resume_journal_entry_carries_the_session_identity(self):
        """Зеркало предыдущего теста для `pause.cmd_resume`: снятие паузы
        под явным `ARTEL_SESSION_ID` обязано журналироваться с тем же
        идентификатором.

        Ловит мутацию: правка identity-резолва доехала только до
        `cmd_pause`, а `cmd_resume` продолжает журналировать литеральный
        актор `"operator"` без обращения к сессии вызывающего — тот же
        класс рассинхрона, что и у теста на pause, только в обратную
        сторону.
        """
        capture(pause.cmd_pause, self.TASK)  # предпосылка: снимать нечего без паузы
        before = len(self.steps())

        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": "sess-ac2-resume"}):
            capture(pause.cmd_resume, self.TASK)

        new_steps = self.steps()[before:]
        self.assertTrue(new_steps, "resume обязан журналировать снятие паузы")
        self.assertTrue(
            any_step_carries(new_steps, "sess-ac2-resume"),
            f"новая запись журнала `resume` не несёт идентификатор "
            f"записавшей её сессии (AC-2): {new_steps}")


if __name__ == "__main__":
    unittest.main()
