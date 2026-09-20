"""AC-12: `runner._resolved_role_model` и `runner._refuse_before_start`
берут модель шага через `models.resolve_role`, и агент роли не стартует
без явного `--model`.

Красен до реализации: фикстура падает на отсутствующем `models.yaml`
(каталог создаёт эта задача), а `runner._resolved_role_model` всё равно
читает поле `model:` роли — модель шага не зависит ни от яруса, ни от
локального слоя.
"""
import unittest

import _models
from _sandbox import TierStepSandbox
from orchestrator import runner


class RunnerUsesResolvedChainTest(TierStepSandbox):
    """Шаг роли `developer` на ярусе `strong` с управляемым локальным
    слоем."""

    def setUp(self):
        super().setUp()
        self.set_cli_version("9.9.9")

    def seed_tier_model(self, model: str) -> None:
        """Полная цепочка, где ярус `strong` указывает на `model`."""
        self.seed_chain(
            tier="strong",
            local_text=_models.local_texts(
                {tier: model for tier in _models.TIERS})[0])

    def test_ac12_resolved_role_model_returns_the_model_of_the_tier(self):
        """`runner._resolved_role_model(role)` отдаёт модель, на которую
        указывает ярус роли в локальном слое, — и следует за его правкой.

        Ловит мутацию: функция продолжает читать поле `model:` роли (либо
        кеширует первое разрешение на процесс) — правка локального слоя
        Оператором не меняет модель шага, и весь слой становится
        декорацией.
        """
        self.seed_tier_model(_models.OPUS)
        self.assertEqual(runner._resolved_role_model(self.ROLE), _models.OPUS)

        self.seed_tier_model(_models.SONNET)
        self.assertEqual(runner._resolved_role_model(self.ROLE), _models.SONNET)

    def test_ac12_agent_starts_with_an_explicit_model_flag_from_the_chain(self):
        """Шаг запускает агента с явным `--model`, и значение флага —
        модель разрешённой цепочки.

        Ловит мутацию: разрешение цепочки сделано ради `doctor`/`models`,
        а argv шага собирается по-старому (поле роли или дефолт CLI) —
        пульт печатал бы одну модель, а платил бы за другую.
        """
        self.seed_tier_model(_models.SONNET)

        self.run_step()

        argv = self.argv()
        self.assertIn("--model", argv)
        self.assertEqual(argv[argv.index("--model") + 1], _models.SONNET)

    def test_ac12_agent_does_not_start_when_the_chain_is_not_resolved(self):
        """Цепочка не разрешается (ярус роли не назван в `tiers:`) — агент
        не стартует вовсе, вместо запуска без `--model`.

        Ловит мутацию: неразрешённая цепочка деградирует к «модель не
        задана — дефолт CLI» (сегодняшнее поведение поля `model:`) —
        инвариант «агент роли не стартует без явного `--model`»
        нарушается ровно там, где цепочка и должна его держать.
        """
        self.seed_chain(
            tier="strong",
            local_text=_models.local_texts(
                {"standard": _models.SONNET, "cheap": _models.SONNET})[0])

        self.run_step()

        self.spawn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
