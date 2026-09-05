"""AC-12, AC-13 (tasks/01M1RDCAFENSW2VVAPECHCVGMM/SPEC.md, требование 6):
`artel.py version` дополнен строкой версии Python и результатом
`check_stack()`.

Красен до реализации: сегодняшний `cmd_version()` не печатает ни версию
Python, ни результат `check_stack()` — AC-12 отказывает на отсутствующей
строке, AC-13 падает `ModuleNotFoundError` на подмене ещё
не существующего `orchestrator.stack.check_stack`.

Подмена `orchestrator.stack.check_stack` (не `doctor.check_stack` —
проверка стека объявлена в `orchestrator/stack.py`, требование 4)
предполагает, что `version.py` зовёт её как `stack.check_stack()`
(атрибут модуля, не `from .stack import check_stack`) — тем же приёмом
импорта, что уже используют ВСЕ соседние модули пульта (`from . import
config, doctor` в текущем `version.py`; `alerts.raise_alert`,
`gitcmd.head_sha`, `targets.load()` и т.д. в `doctor.py`) — в этом
кодовом стиле подмена атрибута модуля перехватывает вызов независимо от
того, кто его делает.
"""
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import version  # noqa: E402


def _capture_version_output() -> str:
    buf = StringIO()
    with redirect_stdout(buf):
        version.cmd_version()
    return buf.getvalue()


class VersionOutputNewLinesTest(unittest.TestCase):

    def test_ac12_output_includes_the_actually_running_python_version(self):
        """Требование 6/AC-12: строка с версией Python, ФАКТИЧЕСКИ
        запущенной у исполнителя (не пином, не строкой из манифеста) —
        сверяется с реальным `sys.version_info` процесса, в котором
        гоняется тест.

        Ловит мутацию: `cmd_version()` печатает версию из манифеста
        (`stack.REQUIRED_PYTHON`, например «3.11») вместо фактической
        версии исполнителя — на любом интерпретаторе новее 3.11 (в
        частности на том, где гоняется этот тест) настоящая версия и
        манифестная разойдутся, и `assertIn` по фактической откажет.
        """
        out = _capture_version_output()
        running = ".".join(str(part) for part in sys.version_info[:3])

        self.assertIn(
            running, out,
            f"вывод version не содержит фактическую версию Python "
            f"исполнителя ({running!r}): {out!r}")

    def test_ac13_output_includes_the_check_stack_result(self):
        """Требование 6/AC-13: строка(-и) с результатом `check_stack()` —
        подмена `stack.check_stack()` на заведомо уникальный маркер
        доказывает, что `cmd_version()` печатает ИМЕННО его результат, а
        не собственную независимую копию проверки.

        Ловит мутацию: `cmd_version()` не зовёт `check_stack()` вовсе
        (например, печатает только версию Python без результата
        проверки стека) — уникальный маркер не появится в выводе,
        `assertIn` откажет.
        """
        marker = "МАРКЕР-ПРОВЕРКИ-СТЕКА-7f19a3"
        FakeCheck = type("FakeCheck", (), {})

        def fake_check_stack():
            fake = FakeCheck()
            fake.name, fake.status, fake.detail = "python", "ok", marker
            return [fake]

        with mock.patch("orchestrator.stack.check_stack",
                        side_effect=fake_check_stack):
            out = _capture_version_output()

        self.assertIn(
            marker, out,
            f"вывод version не содержит результат check_stack() "
            f"(маркер {marker!r} не найден): {out!r}")


if __name__ == "__main__":
    unittest.main()
