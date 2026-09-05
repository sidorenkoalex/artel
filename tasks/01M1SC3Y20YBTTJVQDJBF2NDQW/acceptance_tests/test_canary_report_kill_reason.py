"""Приёмочный тест AC-4 (SPEC 01M1SC3Y20YBTTJVQDJBF2NDQW): отчёт прогона
`cmd_canary`/`_run_one_task` печатает причину исхода для задачи, убитой
(`killed`) — «штатно» на `merge_gate`/`verifying`, «не сошлась:
<причина>» иначе, с текстом причины из журнала.

Красен до реализации: `orchestrator/canary.py::_run_one_task` (строки
765-769) сегодня печатает только `исход={metrics['outcome']}` — для
ЛЮБОГО `killed` одинаково, без разбора «штатно»/«не сошлась». Ни слово
«штатно», ни строка «не сошлась: …» в выводе сегодня не появляются
никогда — все три теста ниже падают на `assertIn`.

`_drive_task` подменена (реальный маршрут ролей — вне предмета этого
файла, он и так уже гоняется существующими приёмочными тестами SPEC
01M1NEEWH5K1XPFRDGRMPYSBXJ): важен только наблюдаемый след, который
ОСТАВЛЯЮТ ЗА СОБОЙ настоящие `_kill_at_merge_gate`/`_kill_at_verifying`/
`_kill_inconclusive` (они вызваны здесь по-настоящему, не переизобретены
— `cleanup.cmd_kill` внутри них подменена, тем же приёмом, что и
`tests/test_canary.py::DriveTaskStallCapTest`). Остальное — настоящий
git: `_ephemeral_clone`, `catalog.cmd_new`, `workspace.ensure` не
подменены, тот же приём, что и `tests/sandbox.py::RealGitSandbox`/старая
`_sandbox.CanarySandbox` этого же семейства задач.
"""
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import canary, store  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402


class RunOneTaskKillReasonReportTest(RealGitSandbox):
    """Настоящий эфемерный клон (`RealGitSandbox` — git-репозиторий с
    патчем всех путей `config`, которые `_ephemeral_clone` пересчитывает
    под клон), `_drive_task` подменена симуляцией конкретного пути
    убийства."""

    def setUp(self):
        super().setUp()
        tmp_tpl = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_tpl.cleanup)
        self.template_dir = Path(tmp_tpl.name)

    def _write_template(self, name: str) -> Path:
        path = self.template_dir / name
        path.write_text("# ТЗ\n\nсодержимое канареечного шаблона.\n",
                        encoding="utf-8")
        return path

    @staticmethod
    def _mark_killed(task_id: str) -> None:
        # То, что в продакшене делает настоящий `cleanup.cmd_kill` —
        # переводит задачу в `killed`; сам `cleanup.cmd_kill` здесь
        # подменён (см. докстринг класса), поэтому финальный переход
        # состояния воспроизводит подмена, а не убранный код.
        store.update_task(store.db(), task_id, state="killed")

    def _run(self, template_name: str, run_stamp: str,
             fake_drive) -> str:
        template = self._write_template(template_name)
        with mock.patch.object(canary.cleanup, "cmd_kill",
                               side_effect=lambda tid: self._mark_killed(tid)), \
             mock.patch.object(canary, "_drive_task", side_effect=fake_drive):
            buf = io.StringIO()
            with redirect_stdout(buf):
                canary._run_one_task(template, run_stamp, 0.5)
            return buf.getvalue()

    def test_ac4_merge_gate_kill_is_reported_as_normal(self):
        """Задача, убитая на `merge_gate` (штатный путь канарейки — она
        никогда не approve-ит merge_gate), печатает в отчёте слово
        «штатно», не «не сошлась».

        Ловит мутацию: реализация, печатающая «не сошлась: …» для
        ЛЮБОГО `killed` без разбора состояния, из которого убили задачу,
        не даст слову «штатно» появиться в выводе.
        """
        out = self._run(
            "merge-gate.md", "20260101T000000Z",
            lambda conn, task_id: canary._kill_at_merge_gate(conn, task_id))

        self.assertIn("штатно", out)
        self.assertNotIn("не сошлась", out)

    def test_ac4_verifying_kill_is_also_reported_as_normal(self):
        """Тот же «штатно» — для второго названного ТЗ состояния,
        `verifying` (канарейка не дожидается CI и убивает задачу сама).

        Ловит мутацию: реализация, узнающая только `merge_gate` (например,
        сравнение по буквальному тексту одной-единственной журнальной
        записи `_kill_at_merge_gate`, без учёта `_kill_at_verifying`),
        пропустит этот случай в «не сошлась».
        """
        out = self._run(
            "verifying.md", "20260101T000001Z",
            lambda conn, task_id: canary._kill_at_verifying(conn, task_id))

        self.assertIn("штатно", out)
        self.assertNotIn("не сошлась", out)

    def test_ac4_inconclusive_kill_reports_the_journaled_reason(self):
        """Задача, убитая ЛЮБЫМ другим путём (`_kill_inconclusive` —
        общий случай «не сошлась», включая короткое замыкание AC-3),
        печатает «не сошлась: <причина>» с ТЕМ ЖЕ текстом причины, что
        был передан в журнал.

        Ловит мутацию: печать общей заглушки («не сошлась» без текста
        причины, либо текст, отличный от журнального) не пройдёт
        `assertIn` на буквальную строку "не сошлась: <reason>" ниже.
        """
        reason = ("canary: рабочий каталог роли не создан: [Errno 13] "
                  "Permission denied — задача не сходится")

        out = self._run(
            "inconclusive.md", "20260101T000002Z",
            lambda conn, task_id: canary._kill_inconclusive(
                conn, task_id, reason))

        self.assertIn(f"не сошлась: {reason}", out)


if __name__ == "__main__":
    unittest.main()
