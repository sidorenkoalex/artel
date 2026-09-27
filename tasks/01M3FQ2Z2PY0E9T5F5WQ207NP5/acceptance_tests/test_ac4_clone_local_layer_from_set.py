"""AC-4 — 01M3FQ2Z2PY0E9T5F5WQ207NP5: локальный слой эфемерного клона
собран из набора.

Источник — SPEC.md, «Критерии приёмки»:

AC-4. При `--set <имя>` локальный слой клона собран из набора, а не из
`models.LOCAL_TEMPLATE`: ярус каждой названной роли указывает на модель
набора, ярусы остальных ролей — как в шаблоне, каждая
`experimental`-модель набора разрешена записью `allow_experimental`,
переопределения тарифа выбранных моделей из локального слоя пульта
перенесены в `overrides:` слоя клона.

Слой читается ИЗНУТРИ клона тем же разбором, которым его будут читать шаги
роли (`models.load_local()` на `config.MODELS_LOCAL`, уже переадресованном
в клон), а не сверкой текста с образцом: критерий говорит о содержании
слоя — ярусах, разрешении и тарифе, — а не о порядке строк в файле.
Наблюдение снимается в момент, когда клон собран, но задача ещё не
заведена (`_util.CanarySetSandbox.clone_probe`).

Ярусы ролей и статус модели в каталоге читаются динамически
(`roles.model_tier`, `models.catalog_model`): и карта исполнителей, и
каталог — крутилки Оператора, и их поворот не должен красить планку.

Красен до реализации: `canary.cmd_canary` не знает параметра набора —
`_util.set_param_name` падает именованным `AssertionError`; слой клона
сегодня всегда текст `models.LOCAL_TEMPLATE`.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import config, models, roles  # noqa: E402


def _template_layer():
    """Локальный слой ШАБЛОНА (`models.LOCAL_TEMPLATE`), разобранный тем же
    разбором — источник ожиданий для ярусов, не названных набором."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "models.yaml"
        path.write_text(models.local_template_text(), encoding="utf-8")
        return models.load_local(path)


class CloneLocalLayerFromSetTest(_util.CanarySetSandbox):

    def _probe(self):
        def probe():
            return {"layer": models.load_local(),
                    "text": config.MODELS_LOCAL.read_text(encoding="utf-8")}
        return self.clone_probe(probe, set_name=_util.SET_NAME)

    def test_ac4_named_roles_tier_points_at_the_set_model(self):
        """Ярус каждой роли набора в слое клона указывает на модель
        набора, а сам слой уже не текст шаблона.

        Ловит мутацию: ветка набора собрана, но `catalog.cmd_init()`
        зовётся ПОСЛЕ неё и шаблон ложится поверх собранного слоя (либо
        слой пишется по пути пульта, а не клона) — прогон «на Codex» шёл
        бы на модели шаблона, и метрики приписались бы набору, которым не
        шли.
        """
        got = self._probe()

        for role in _util.SET_ROLES:
            self.assertEqual(_util.SET_MODEL,
                             got["layer"].tiers.get(roles.model_tier(role)),
                             f"ярус роли {role} в слое клона: "
                             f"{got['layer'].tiers}")
        self.assertNotEqual(models.local_template_text(), got["text"])

    def test_ac4_other_tiers_stay_as_in_the_template(self):
        """Ярусы, которых набор не называет, в слое клона — те же, что в
        шаблоне локального слоя.

        Ловит мутацию: слой клона собирается ТОЛЬКО из ярусов набора —
        роль, чей ярус набор не называет, осталась бы без модели вовсе
        («ярус не назван в tiers:»), и прогон встал бы на первом же её
        шаге вместо того, чтобы идти как пульт.
        """
        got = self._probe()

        template = _template_layer()
        named_tiers = {roles.model_tier(role) for role in _util.SET_ROLES}
        rest = [tier for tier in models.TIERS if tier not in named_tiers]
        self.assertTrue(rest, "предпосылка: есть ярусы, не названные набором")
        for tier in rest:
            self.assertEqual(template.tiers.get(tier),
                             got["layer"].tiers.get(tier),
                             f"ярус {tier} слоя клона разошёлся с шаблоном")

    def test_ac4_experimental_model_of_the_set_is_allowed_in_the_clone(self):
        """Модель набора со статусом `experimental` в каталоге разрешена
        записью `allow_experimental` слоя клона.

        Ловит мутацию: разрешение не собирается (или собирается значением,
        отличным от `true`, — разбор считает разрешением РОВНО `true`) —
        каждый шаг роли в клоне отказывал бы «модель имеет статус
        experimental и не разрешена явно», и прогон на Codex был бы
        невозможен при исправном наборе.
        """
        self.assertEqual(models.STATUS_EXPERIMENTAL,
                         models.catalog_model(_util.SET_MODEL).status,
                         "предпосылка сценария: модель набора experimental")

        got = self._probe()

        self.assertIn(_util.SET_MODEL, got["layer"].allow_experimental)

    def test_ac4_pult_tariff_override_of_the_set_model_is_carried_over(self):
        """Собственный тариф модели набора из локального слоя ПУЛЬТА
        перенесён в `overrides:` слоя клона — теми же четырьмя ценами.

        Ловит мутацию: `overrides:` слоя клона собирается пустым (или
        переносится тариф не той модели) — стоимость шага в клоне считалась
        бы по прейскуранту каталога, и метрика стоимости прогона разошлась
        бы с тарифом пульта, на который она же и сравнивается с бейзлайном.
        """
        got = self._probe()

        override = got["layer"].overrides.get(_util.SET_MODEL)
        self.assertIsNotNone(override,
                             f"overrides слоя клона: {got['layer'].overrides}")
        self.assertEqual(
            models.Tariff(*[_util.PULT_OVERRIDE[kind]
                            for kind in models.PRICE_KINDS]),
            override.tariff)


if __name__ == "__main__":
    unittest.main()
