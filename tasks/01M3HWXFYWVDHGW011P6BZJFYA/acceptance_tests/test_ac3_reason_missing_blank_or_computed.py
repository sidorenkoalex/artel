"""AC-3 (tasks/01M3HWXFYWVDHGW011P6BZJFYA/SPEC.md): пропуск в новом
тестовом методе БЕЗ аргумента причины, с пустой (или пробельной) причиной
либо с причиной-выражением остаётся находкой, и переход отказывает
прежним именованным действием «переход отклонён: гейт неослабления
тестов».

Зелёный с рождения: сегодня узел даёт находку на любой появившийся маркер
пропуска, поэтому все три сценария уже отказывают — это тест СОХРАНЕНИЯ
рубежа на границе будущего послабления. Он краснеет ровно на мутации
«послабление применено шире формулировки требования 2»: причина не
проверяется вовсе, проверяется без `strip()`, либо вычисляемое выражение
(переменная, f-строка) засчитывается за названную причину — именно этим
способом обходят рубеж, не написав ревьюверу ни слова.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import (BLANK_REASON, BLANK_REASON_METHODS,  # noqa: E402
                      BLANK_REASON_PATH, COMPUTED_REASON,
                      COMPUTED_REASON_METHODS, COMPUTED_REASON_PATH,
                      NO_REASON, NO_REASON_METHOD, NO_REASON_PATH,
                      REFUSAL_ACTION, GateSandbox)


class ReasonlessSkipInNewTestTest(GateSandbox):

    def _assert_refused(self, outcome, path: str, methods) -> None:
        self.assertTrue(
            outcome.refused,
            f"пропуск без названной причины остаётся находкой (AC-3); "
            f"журнал: {outcome.journal}; stdout: {outcome.printed}")
        self.assertIn(
            REFUSAL_ACTION, outcome.actions,
            f"отказ обязан идти ПРЕЖНИМ именованным действием (AC-3); "
            f"журнал: {outcome.journal}")
        self.assertIn(path, outcome.detail,
                      f"detail обязан назвать файл; detail: {outcome.detail}")
        for method in methods:
            self.assertIn(
                method, outcome.detail,
                f"detail обязан назвать метод {method} (AC-3); "
                f"detail: {outcome.detail}")

    def test_ac3_skip_without_reason_argument_refuses(self):
        """Новый метод выключен условно, но у вызова пропуска аргумента
        причины нет вовсе (`pytest.skip()` внутри `if`): находка остаётся,
        переход отказывает прежним действием.

        Ловит мутацию: признаком послабления взята одна лишь условность
        (`if`/`skipIf`), а наличие аргумента причины не сверяется — любой
        условный пропуск в новом файле проходит рубеж молча, и ревьювер
        не получает того самого текста, ради которого послабление введено.
        """
        self.apply(NO_REASON_PATH, NO_REASON)

        self._assert_refused(self.run_gate(), NO_REASON_PATH,
                             (NO_REASON_METHOD,))

    def test_ac3_blank_reason_refuses(self):
        """Причина у пропуска есть, но пустая (`""`) либо из одних
        пробелов (`"   "`): оба метода остаются находками.

        Ловит мутацию: непустота причины проверена как `if reason:` — без
        отбрасывания пробелов, которого требование 2 требует дословно:
        `self.skipTest("   ")` сходит за названную причину, и рубеж
        обходится одним пробелом внутри кавычек.
        """
        self.apply(BLANK_REASON_PATH, BLANK_REASON)

        self._assert_refused(self.run_gate(), BLANK_REASON_PATH,
                             BLANK_REASON_METHODS)

    def test_ac3_computed_reason_refuses(self):
        """Причина задана ВЫЧИСЛЯЕМЫМ выражением — переменной у
        `@skipUnless` и f-строкой у `self.skipTest`: оба метода остаются
        находками (рубеж закрывается в пользу находки).

        Ловит мутацию: аргумент причины проверен на «есть узел» вместо
        «строковая константа» — узел `ast.Name`/`ast.JoinedStr` считается
        названной причиной, хотя её текст статическим разбором не
        восстановить, и в журнал AC-2 уйдёт либо пустая строка, либо
        исходный код выражения вместо объяснения для ревьювера.
        """
        self.apply(COMPUTED_REASON_PATH, COMPUTED_REASON)

        self._assert_refused(self.run_gate(), COMPUTED_REASON_PATH,
                             COMPUTED_REASON_METHODS)


if __name__ == "__main__":
    unittest.main()
