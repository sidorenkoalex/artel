"""Причина автогейта для правила планки не по умолчанию — текст до гейта неослабления по исходам (G3б).

Группа: разовый
Красен до реализации: `fsm_autogate._plank_rule_refusal` для правила не по умолчанию отдаёт прежний текст «… до выкладки plank_layout (G2а-2) не исполняется …», а не текст G3б требования 8.

Файл разовый: текст причины — временный, SPEC сам ограничивает его сроком
«до G3б» (решение Оператора 19.10, п. 9; G3б снимает запрет вместе с
текстом), поэтому после мержа свойство живёт до следующей задачи волны, а
не как постоянное свойство кода. Функция — `orchestrator/fsm_autogate.py:
_plank_rule_refusal`, названная в SPEC (требование 8); правила планки
строятся публичными `guard.PlankRule`/`guard.PlankComponent` без
песочницы. Имена компонентов и текст отказа построения — из `random`,
зерно печатается.
"""
import random
import unittest

from orchestrator import fsm_autogate
from scripts import guard

LETTERS = "abcdefghijkmnpqrstuvwxyz"
G3B_TEXT = ("автогейт: прогон планки компонента {names} по правилу — до гейта "
            "неослабления по исходам (G3б) не исполняется; приёмку решает "
            "Оператор")


class Ac23AutogateReasonTest(unittest.TestCase):

    def setUp(self):
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def word(self) -> str:
        return "".join(self.rng.choice(LETTERS) for _ in range(6))

    def test_ac23_non_default_rule_reason_text(self):
        """Правило не по умолчанию — причина ровно «автогейт: прогон планки компонента <имена> по правилу — до гейта неослабления по исходам (G3б) не исполняется; приёмку решает Оператор».

        Сценарий: правило из одного–двух компонентов с меткой `AC-<n>: `
        (маски `.test.jsx`, пометки `//`) и, в половине случаев, ещё одного
        компонента по умолчанию (pytest); имена в причине — те, что отдаёт
        `labelled_components()` правила, через «, ». Причина равна тексту
        G3б целиком.

        Ловит мутацию: текст оставлен прежним (G2а-2) — строки не равны;
        имена компонентов собраны из всех компонентов, включая компонент по
        умолчанию, — лишнее имя.
        """
        for _ in range(4):
            labelled = [guard.PlankComponent(f"c{self.word()}",
                                             (f"src/**/*.test.jsx",),
                                             guard.LABEL_AC, guard.MARKER_SLASH)
                        for _ in range(self.rng.randint(1, 2))]
            comps = list(labelled)
            if self.rng.random() < 0.5:
                comps.append(guard.PlankComponent(f"p{self.word()}", ()))
            rule = guard.PlankRule(components=tuple(comps))
            with self.subTest(components=[c.name for c in comps], seed=self.seed):
                self.assertFalse(rule.is_default)
                names = ", ".join(rule.labelled_components())
                self.assertEqual(fsm_autogate._plank_rule_refusal(rule),
                                 G3B_TEXT.format(names=names),
                                 f"зерно: {self.seed}")

    def test_ac23_build_refusal_and_default_rule_unchanged(self):
        """Отказ построения правила — прежний текст «автогейт: <причина>»; правило по умолчанию — без причины.

        Сценарий: правило с `refusal` (случайный текст причины) — причина
        автогейта «автогейт: <причина>»; `guard.DEFAULT_PLANK_RULE` —
        `None`.

        Ловит мутацию: новый текст G3б отдаётся и при отказе построения —
        причина отказа потеряна; правило по умолчанию получает причину —
        автогейт закрыт для артели.
        """
        reason = f"у компонента {self.word()} нет tests — фикстура {self.seed}"
        self.assertEqual(
            fsm_autogate._plank_rule_refusal(guard.PlankRule(refusal=reason)),
            f"автогейт: {reason}", f"зерно: {self.seed}")
        self.assertIsNone(fsm_autogate._plank_rule_refusal(guard.DEFAULT_PLANK_RULE),
                          f"зерно: {self.seed}")


if __name__ == "__main__":
    unittest.main()
