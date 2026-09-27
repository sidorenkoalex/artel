"""AC-5 (tasks/01M3HWXFYWVDHGW011P6BZJFYA/SPEC.md): маркер пропуска,
появившийся на имени, которое в базе сравнения ЕСТЬ, остаётся находкой —
в том числе условный и с названной причиной; условный декоратор пропуска
с причиной, появившийся над КЛАССОМ, тоже остаётся находкой.

Зелёный с рождения: сегодня оба случая уже дают находку (узел не
различает, новое имя или существующее) — это тест СОХРАНЕНИЯ рубежа на
границе будущего послабления. Он краснеет на мутации «послабление
привязано к признаку „маркер условный и с причиной“ вместо признака
„имени нет в базе сравнения“»: тогда разработчик гасит ЛЮБОЙ старый тест
одной строкой `@skipUnless(<условие>, "чиню отдельно")`, и рубеж,
который эта задача обязана оставить нетронутым, исчезает.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import (EXISTING_CLASS, EXISTING_PATH,  # noqa: E402
                      EXISTING_WITH_CONDITIONAL_SKIP_ON_CLASS,
                      EXISTING_WITH_CONDITIONAL_SKIP_ON_METHOD,
                      NEW_CLASS_SKIP, NEW_CLASS_SKIP_CLASS,
                      NEW_CLASS_SKIP_PATH, REFUSAL_ACTION, GateSandbox)


class SkipOnExistingNameTest(GateSandbox):

    def test_ac5_conditional_skip_on_existing_method_refuses(self):
        """На методе `test_existing_one`, который есть в базе сравнения,
        появился `@skipUnless(<условие>, "<причина>")`: находка остаётся,
        переход отказывает и называет файл и метод.

        Ловит мутацию: признаком послабления взят сам вид маркера
        (условный + причина) без сверки имени с базой сравнения —
        существующий тест выключается условной строкой без мандата
        Оператора, и требование 4 («названная причина его не снимает»)
        нарушено ровно тем способом, ради которого требование 1 вообще
        разделяет два случая.
        """
        self.apply(EXISTING_PATH, EXISTING_WITH_CONDITIONAL_SKIP_ON_METHOD)

        outcome = self.run_gate()

        self.assertTrue(
            outcome.refused,
            f"пропуск на существующем имени остаётся находкой (AC-5); "
            f"журнал: {outcome.journal}; stdout: {outcome.printed}")
        self.assertIn(REFUSAL_ACTION, outcome.actions, outcome.journal)
        self.assertIn(EXISTING_PATH, outcome.detail)
        self.assertIn("test_existing_one", outcome.detail,
                      f"detail: {outcome.detail}")


class ConditionalSkipOnClassTest(GateSandbox):

    def test_ac5_conditional_skip_on_existing_class_refuses(self):
        """Условный декоратор с причиной появился над классом
        `ExistingTest`, который есть в базе сравнения: находка остаётся,
        detail называет файл и класс.

        Ловит мутацию: послабление применено к любому имени, на котором
        стоит условный маркер с причиной, — один декоратор над классом
        гасит все его тесты разом, а рубеж об этом молчит.
        """
        self.apply(EXISTING_PATH, EXISTING_WITH_CONDITIONAL_SKIP_ON_CLASS)

        outcome = self.run_gate()

        self.assertTrue(
            outcome.refused,
            f"условный пропуск над классом остаётся находкой (AC-5); "
            f"журнал: {outcome.journal}; stdout: {outcome.printed}")
        self.assertIn(REFUSAL_ACTION, outcome.actions, outcome.journal)
        self.assertIn(EXISTING_PATH, outcome.detail)
        self.assertIn(EXISTING_CLASS, outcome.detail,
                      f"detail: {outcome.detail}")

    def test_ac5_conditional_skip_on_new_class_refuses(self):
        """Тот же условный декоратор с причиной стоит над классом НОВОГО
        файла (в базе сравнения этого имени нет вовсе): находка всё равно
        остаётся — послабление действует только на имени МЕТОДА.

        Ловит мутацию: послабление реализовано одним правилом «имени нет
        в базе — пропускаем», без различения метода и класса: новый файл
        целиком выключается одним декоратором над классом с формальной
        причиной, и весь набор тестов такого файла не исполняется ни на
        одной машине, оставаясь зелёным.
        """
        self.apply(NEW_CLASS_SKIP_PATH, NEW_CLASS_SKIP)

        outcome = self.run_gate()

        self.assertTrue(
            outcome.refused,
            f"условный пропуск над КЛАССОМ находкой остаётся и в новом "
            f"файле (AC-5); журнал: {outcome.journal}; "
            f"stdout: {outcome.printed}")
        self.assertIn(REFUSAL_ACTION, outcome.actions, outcome.journal)
        self.assertIn(NEW_CLASS_SKIP_PATH, outcome.detail)
        self.assertIn(NEW_CLASS_SKIP_CLASS, outcome.detail,
                      f"detail: {outcome.detail}")


if __name__ == "__main__":
    unittest.main()
