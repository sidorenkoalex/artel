"""AC-8 — 01M31ZHSA6HMH40C2JTDPQJQNZ: ни одна из шести точек требования 3
не разбирает строку вывода сама.

Источник — SPEC.md, «Критерии приёмки»:

AC-8. Ни одна из шести точек требования 3 не разбирает строку вывода
сама: провайдер-заглушка роли шага с другим форматом строки меняет
результат каждой из них (лог, трение, итог запуска, разбивка usage,
частичные токены из файла лога).

Заглушка (`_provider.stub_format_provider_class`) строится НАД
`ClaudeProvider` по составу новой части интерфейса: свой формат строки —
префикс `_provider.STUB_PREFIX`, и строка формата Claude для неё мусор,
из которого не извлекается ничего. Поэтому ОДИН И ТОТ ЖЕ образец потока
обязан дать под ней другой лог, другое трение, другую стоимость и другие
токены — если, конечно, разбирает его провайдер, а не пульт литералами.

Красен до реализации: шесть точек разбирают формат Claude литералами
(`agent_log.render_agent_line`, `_friction_from_events`, `OutputPump.
catch_cost`, `spend.parse_cost_event`, `stream_usage_by_type`,
`partial_tokens_from_log`), провайдер роли на них не влияет — под
заглушкой получаются ТЕ ЖЕ значения, и каждый `assertNotEqual` краснеет.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _provider  # noqa: E402
import _run  # noqa: E402
import _sample  # noqa: E402
from orchestrator import spend  # noqa: E402


class SixPointsTest(_run.StepRunSandbox):

    def use_stub_provider(self):
        """Провайдер роли шага — заглушка с другим форматом строки."""
        stub = _provider.stub_format_provider_class()()
        _provider.register(self, stub, self.ROLE)
        return stub

    def test_ac8_stub_provider_changes_log_friction_cost_and_usage(self):
        """Один и тот же образец под провайдером репозитория и под
        заглушкой даёт разный лог шага, разное трение, разный итог
        запуска и разную разбивку usage.

        Ловит мутацию: разбор переведён на провайдера не везде — скажем,
        `render_agent_line` зовёт провайдера, а `OutputPump.catch_cost`
        по-прежнему читает `total_cost_usd` литералом: лог под заглушкой
        меняется, а стоимость нет, и в пульте живут ДВА разбора одного
        потока (ровно то, что требование 3 запрещает).
        """
        self.run_stream(_sample.STREAM)
        native_log = self.log_text()
        native_friction = self.friction()
        native_spent = self.task_row()["spent_usd"]
        native_known = len(self.details(_run.KNOWN))

        self.assertEqual(native_log, _sample.EXPECTED_LOG_TEXT)
        self.assertEqual(native_friction, _sample.EXPECTED_FRICTION)
        self.assertAlmostEqual(native_spent, _sample.EXPECTED_COST_USD)
        self.assertEqual(native_known, 1)

        self.use_stub_provider()
        self.run_stream(_sample.STREAM)
        stub_spent = self.task_row()["spent_usd"] - native_spent
        stub_known = len(self.details(_run.KNOWN)) - native_known

        self.assertNotEqual(self.log_text(), native_log,
                            "лог шага: строку разбирает не провайдер")
        self.assertNotEqual(self.friction(), native_friction,
                            "трение шага: строку разбирает не провайдер")
        self.assertNotAlmostEqual(
            stub_spent, native_spent,
            msg="итог запуска: строку разбирает не провайдер")
        self.assertNotEqual(
            stub_known, native_known,
            "разбивка usage: строку разбирает не провайдер")

    def test_ac8_stub_provider_changes_partial_tokens_of_the_log_file(self):
        """Постфактум-разбор файла лога под заглушкой даёт другие
        частичные токены, чем под провайдером репозитория.

        Ловит мутацию: `partial_tokens_from_log` осталась единственной
        точкой, читающей формат Claude литералами (провайдера ей не
        передали вовсе) — `pause --now` и учёт таймаута второго
        провайдера молча считают ноль токенов на непустом логе.
        """
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = _sample.log_file(Path(tmp.name) / "raw.log", _sample.STREAM)

        native = _sample.flex(spend.partial_tokens_from_log, path,
                              role=self.ROLE, provider=_provider.claude())
        stub = _sample.flex(spend.partial_tokens_from_log, path,
                            role=self.ROLE,
                            provider=_provider.stub_format_provider_class()())

        self.assertEqual(_sample.normalized(native[0]),
                         _sample.EXPECTED_PARTIAL_BY_KIND)
        self.assertNotEqual(stub, native,
                            "частичные токены: файл разбирает не провайдер")

    def test_ac8_stub_provider_reads_its_own_format(self):
        """Тот же образец, переписанный в формат заглушки, даёт под ней
        ровно то, что под провайдером репозитория давал формат Claude.

        Ловит мутацию: заглушка «меняет результат» только потому, что
        разбор вовсе развалился на неизвестной строке (везде пусто), а
        не потому, что провайдер действительно решает, как читать
        строку, — тогда СВОЙ формат заглушки тоже не разберётся, и лог с
        трением останутся пустыми.
        """
        self.use_stub_provider()

        self.run_stream([_provider.stub_line(line) for line in _sample.STREAM])

        self.assertEqual(self.log_text(), _sample.EXPECTED_LOG_TEXT)
        self.assertEqual(self.friction(), _sample.EXPECTED_FRICTION)
        self.assertAlmostEqual(self.task_row()["spent_usd"],
                               _sample.EXPECTED_COST_USD)


if __name__ == "__main__":
    unittest.main()
