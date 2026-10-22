"""Отказ автогейта по правилу планки `fsm_autogate._plank_rule_refusal`
(SPEC 01M5J0JYW3GZSSHHK3TYCYTQ3J, требование 10; AC-28, AC-29): правило
не по умолчанию снимает отказ «до G3б» только у задачи в границе гейта
исходов — профиль в `in_outcome_bounds`, не канарейка.

Граница считается настоящим `outcome_integrity._bounds`; подменено только
решение профиля `project_profile.decide` — без записи `targets.yaml`.
"""
import unittest
from unittest import mock

from orchestrator import fsm_autogate, project_profile
from scripts import guard

G3B = "до гейта неослабления по исходам (G3б) не исполняется"
RULE = guard.PlankRule(components=(guard.PlankComponent(
    "web", ("web/src/**/*.test.jsx",), label=guard.LABEL_AC),))


def profile(**fields):
    values = dict(command=("npx", "vitest"), long_lived_dir="web/src",
                  long_lived_name="{id}.test.jsx",
                  weakening_scope=("web/src/**",), mutation_claim_scope=(),
                  report="report.json", from_components=True)
    values.update(fields)
    return project_profile.Profile(**values)


class PlankRuleRefusalTest(unittest.TestCase):

    def refusal(self, rule, decision, is_canary=0):
        task = {"is_canary": is_canary, "target": "shop"}
        with mock.patch.object(project_profile, "decide",
                               return_value=decision):
            return fsm_autogate._plank_rule_refusal(rule, task)

    def test_non_default_rule_in_bounds_is_not_refused(self):
        """Правило не по умолчанию у задачи не канарейки с профилем компонента с отчётом — отказа нет, условия идут дальше.

        Ловит мутацию: прежний безусловный отказ правилу не по умолчанию
        (решение 19.10 «до G3б») возвращён — причина «… (G3б) не
        исполняется» вместо `None`.
        """
        self.assertIsNone(self.refusal(
            RULE, project_profile.Decision("shop", profile=profile())))

    def test_canary_in_bounds_keeps_g3b_refusal(self):
        """Канареечная задача с тем же профилем в границе — прежний отказ «до G3б» с именем компонента с меткой.

        Ловит мутацию: граница снятия — только `in_outcome_bounds`
        профиля, без признака канарейки (`_bounds` без `is_canary`) —
        канарейка проходит автогейт без отказа.
        """
        text = self.refusal(
            RULE, project_profile.Decision("shop", profile=profile()),
            is_canary=1)
        self.assertEqual(
            text, f"автогейт: прогон планки компонента web по правилу — "
                  f"{G3B}; приёмку решает Оператор")

    def test_out_of_bounds_profile_keeps_g3b_refusal(self):
        """Профиль вне границы (без `report`, не из `components:`, отказ или пропуск решения) — прежний отказ «до G3б».

        Ловит мутацию: отказ снимается любым правилом не по умолчанию
        либо без проверки отказа/пропуска решения профиля — задача вне
        границы гейта исходов проходит автогейт.
        """
        cases = {
            "без report": project_profile.Decision(
                "shop", profile=profile(report="")),
            "не из components": project_profile.Decision(
                "shop", profile=profile(from_components=False)),
            "отказ решения": project_profile.Decision(
                "shop", profile=profile(), refusal="нет клона"),
            "пропуск": project_profile.Decision("shop", skip="без профиля"),
        }
        for name, decision in cases.items():
            with self.subTest(name):
                self.assertIn(G3B, self.refusal(RULE, decision))

    def test_rule_build_refusal_keeps_its_text(self):
        """Отказ построения правила — текст «автогейт: <причина>» и у задачи в границе.

        Ловит мутацию: граница проверяется раньше отказа построения
        правила — задача в границе проходит автогейт при сломанной записи.
        """
        rule = guard.PlankRule(refusal="запись components сломана")
        self.assertEqual(
            self.refusal(rule,
                         project_profile.Decision("shop", profile=profile())),
            "автогейт: запись components сломана")

    def test_default_rule_is_not_refused(self):
        """Правило по умолчанию — отказа нет и вне границы (прежнее поведение).

        Ловит мутацию: отказ «до G3б» распространён на правило по
        умолчанию — автогейт артели отказывает всегда.
        """
        self.assertIsNone(self.refusal(
            guard.PlankRule(), project_profile.Decision("artel")))


if __name__ == "__main__":
    unittest.main()
