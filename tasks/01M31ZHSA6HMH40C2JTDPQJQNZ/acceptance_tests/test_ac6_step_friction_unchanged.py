"""AC-6 — 01M31ZHSA6HMH40C2JTDPQJQNZ: трение шага на образце не
изменилось ни на постфактум-разборе файла, ни на накоплении вживую.

Источник — SPEC.md, «Критерии приёмки»:

AC-6. Трение шага на том же образце даёт то же число, что до задачи, — и
на постфактум-разборе файла (`agent_log.step_friction`), и на накоплении
вживую (`OutputPump.friction`).

Образец несёт два вызова инструмента, второй из которых — повторное
чтение уже прочитанного файла: один непродуктивный из двух, 0.5
(`_sample.EXPECTED_FRICTION`).

Зелёный с рождения: трение образца сегодня уже 0.5 обоими путями — тест
сохранения существующего поведения. Красным он станет, если переезд
разбора к провайдеру потеряет вызов инструмента, его ключевой аргумент
или результат: число трения молча поедет, а метрика шага пишется в
журнал каждым прогоном и ложь в ней не видна ниоткуда.
"""
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _provider  # noqa: E402
import _sample  # noqa: E402
from orchestrator import agent_log  # noqa: E402


class StepFrictionTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tdir = Path(tmp.name)

    def test_ac6_friction_of_the_sample_file_is_unchanged(self):
        """Постфактум-разбор файла сырого лога образца даёт то же число
        трения, что до задачи.

        Ловит мутацию: разбор вызова инструмента у провайдера перестаёт
        отдавать ключевой аргумент (`file_path`), и повторное чтение
        одного и того же файла больше не опознаётся повтором — трение
        падает с 0.5 до 0.0 на образце, где оно заведомо есть.
        """
        log_path = _sample.log_file(self.tdir / "step.log", _sample.STREAM)

        value = _sample.flex(agent_log.step_friction, log_path,
                             provider=_provider.claude())

        self.assertEqual(value, _sample.EXPECTED_FRICTION)

    def test_ac6_live_pump_friction_matches_the_file_parse(self):
        """Накопление вживую по тем же строкам потока даёт то же число,
        что постфактум-разбор файла.

        Ловит мутацию: на провайдера переведён только один из двух путей
        (например `step_friction`), а `OutputPump` продолжает копить
        события собственным разбором формата Claude — два разбора одного
        потока разъезжаются, и трение реального шага (в журнал его пишет
        именно живой путь) перестаёт совпадать с разбором его лога.
        """
        log_path = self.tdir / "live.log"
        pump = _sample.flex(agent_log.OutputPump, iter(_sample.STREAM),
                            log_path, provider=_provider.claude())
        with redirect_stdout(io.StringIO()):
            pump.start()
            pump.join(5)

        self.assertEqual(pump.friction, _sample.EXPECTED_FRICTION)


if __name__ == "__main__":
    unittest.main()
