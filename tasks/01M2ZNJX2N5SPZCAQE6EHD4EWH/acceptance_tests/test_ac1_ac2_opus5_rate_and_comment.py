"""AC-1, AC-2: курс всех четырёх agent-ролей — прейскурант opus-5 с
датой калибровки 2026-09-20, и комментарий НАД таблицей объясняет эту
калибровку.

Цены в AC-1 названы числами самим критерием, поэтому здесь они —
литералы: брать их из `config.TOKEN_RATES` значило бы сверять таблицу с
самой собой. Остальные файлы планки, наоборот, не знают ни одной цены —
они считают расчёт через `spend.partial_cost_usd`.

Красен до реализации: `config.TOKEN_RATES` сегодня несёт цены Sonnet
($3/$15 за миллион, `calibrated_at: "2026-09-05"`), а комментарий над
таблицей рассказывает о калибровке 04.09 — ни коэффициента 1.009, ни 93
шагов, ни модели opus в нём нет.
"""
import inspect
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config  # noqa: E402

# Четыре agent-роли конвейера, перечисленные AC-1 поимённо.
AGENT_ROLES = ("analyst", "test_author", "developer", "reviewer")

# Прейскурант opus-5 за ТОКЕН — числа AC-1 дословно.
EXPECTED_PRICES = {
    "input_usd_per_token": 0.000005,
    "output_usd_per_token": 0.000025,
    "cache_creation_usd_per_token": 0.00000625,
    "cache_read_usd_per_token": 0.0000005,
}
EXPECTED_CALIBRATED_AT = "2026-09-20"

TABLE_ANCHOR = "TOKEN_RATES = {"


def comment_block_above(source: str, anchor: str) -> str:
    """Непрерывный блок строк-комментариев прямо над строкой `anchor`.

    Читается из уже импортированного модуля (`inspect.getsource`), не с
    диска по собранному пути: комментарий — часть исходника, а не
    артефакт задачи.
    """
    lines = source.splitlines()
    starts = [i for i, line in enumerate(lines) if line.startswith(anchor)]
    if not starts:
        return ""
    block = []
    index = starts[0] - 1
    while index >= 0 and lines[index].lstrip().startswith("#"):
        block.append(lines[index])
        index -= 1
    return "\n".join(reversed(block))


class Opus5RateTest(unittest.TestCase):
    """AC-1: таблица курса несёт прейскурант opus-5 по всем четырём ролям."""

    def test_ac1_every_agent_role_carries_the_opus5_price_list(self):
        """Курс каждой из четырёх agent-ролей — четыре цены прейскуранта
        opus-5 и дата калибровки 2026-09-20.

        Ловит мутацию: разработчик правит цены не во всех четырёх
        записях таблицы (копипаста трёх блоков из четырёх — `reviewer`
        остаётся на ценах Sonnet) либо поднимает цены, забыв сдвинуть
        `calibrated_at`, — тогда сверка с датой из AC-5/AC-4 идёт по
        старой дате, и `subTest` упавшей роли назовёт её поимённо.
        """
        for role in AGENT_ROLES:
            with self.subTest(role=role):
                rate = config.TOKEN_RATES.get(role)
                self.assertIsNotNone(
                    rate, f"AC-1: роль {role!r} обязана нести курс токенов")
                for field, price in EXPECTED_PRICES.items():
                    self.assertIn(field, rate,
                                  f"AC-1: курс {role!r} без цены {field!r}")
                    self.assertEqual(
                        rate[field], price,
                        f"AC-1: {role}.{field} — прейскурант opus-5 {price}")
                self.assertEqual(
                    rate.get("calibrated_at"), EXPECTED_CALIBRATED_AT,
                    f"AC-1: дата калибровки курса {role!r} — "
                    f"{EXPECTED_CALIBRATED_AT}")


class CalibrationCommentTest(unittest.TestCase):
    """AC-2: комментарий над таблицей объясняет калибровку 20.09."""

    def setUp(self):
        self.block = comment_block_above(inspect.getsource(config),
                                         TABLE_ANCHOR)

    def assertMentions(self, variants: tuple, what: str) -> None:
        """Блок комментария называет хотя бы одно из написаний `variants`."""
        lowered = self.block.lower()
        self.assertTrue(
            any(variant in lowered for variant in variants),
            f"AC-2: комментарий над {TABLE_ANCHOR} не называет {what} "
            f"(ни одного из {variants})")

    def test_ac2_comment_names_model_coefficient_steps_and_method(self):
        """Комментарий прямо над таблицей курса называет калибровку
        20.09: модель, коэффициент 1.009 по 93 шагам, метод «прейскурант
        плюс сверка» и отказ от подгонки курса по журналу.

        Ловит мутацию: разработчик меняет числа таблицы, оставив над ней
        прежний абзац о калибровке 04.09 (эмпирическая ставка $0.45/млн)
        — комментарий разойдётся с курсом, который он объясняет, и
        следующий читатель снова не поймёт, откуда взялись цены; ни
        «1.009», ни «93» в блоке не появится.
        """
        self.assertTrue(
            self.block,
            f"AC-2: над строкой {TABLE_ANCHOR} нет блока комментария вовсе")
        self.assertMentions(("20.09", "2026-09-20"), "дату калибровки 20.09")
        self.assertMentions(("opus",), "модель")
        self.assertMentions(("1.009",), "коэффициент 1.009")
        self.assertMentions(("93",), "число шагов сверки — 93")
        self.assertMentions(("прейскурант",), "метод «прейскурант плюс сверка»")
        self.assertMentions(("сверк",), "сверку как часть метода")
        self.assertMentions(("подгон", "подбор"),
                            "причину отказа от подгонки курса по журналу")


if __name__ == "__main__":
    unittest.main()
