"""AC-7: вход домом роли ПУЛЬТА подтверждён, а проверка окружением шага
клона не прошла — прогон отказывает до первого шага роли, а текст отказа
называет это дефектом пульта, а не несделанным действием Оператора, и не
сводится к рецепту «войдите».

Красен до реализации: сегодня прогон зовёт проверку входа ровно один раз и
отказывает одним и тем же текстом на любой её неуспех — отказ этого случая
неотличим от отказа AC-6 и несёт тот же рецепт `codex login`, которого
критерий здесь как раз не допускает.

«Не сводится к рецепту» читается буквально: рецепта `doctor.
CODEX_AUTH_RECIPE` в тексте нет — приписать его рядом с объяснением
значило бы снова адресовать Оператору шаг, который он уже сделал.

Настоящий клиент Codex не запускается, связка ключей не спрашивается: узел
проверки входа подменён, git фальшивый. Различитель подмены —
`config.ROLE_HOME` в момент вызова: именно от него настоящий узел берёт
`HOME` процесса `codex login status`, а его сигнатуру задача менять не
вправе (`orchestrator/doctor/` — только для чтения).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _clone_env import CloneEnvCase  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import canary, doctor  # noqa: E402


class RefusalWithPultLoginTest(CloneEnvCase):
    """AC-7: отказ, когда вход пульта есть, а проверка окружением клона
    не прошла."""

    def refusal(self, *, pult: str) -> str:
        """Текст `SystemExit`, которым блок клона отказывает ДО своего тела
        при неуспешной проверке окружением шага клона."""
        entered = []
        with self.fake_git(), self.login_check(pult=pult, clone="fail"):
            with self.assertRaises(SystemExit) as ctx:
                with canary._ephemeral_clone(codex_auth=self.auth()):
                    entered.append("тело блока клона")
        self.assertEqual([], entered, "отказ обязан быть до первого шага роли")
        return str(ctx.exception)

    def test_ac7_a_confirmed_pult_login_turns_the_refusal_into_a_pult_defect(self):
        """Вход домом роли пульта подтверждён, а проверка окружением шага
        клона не прошла — прогон отказывает текстом БЕЗ рецепта «войдите» и
        не тем же самым, каким отказывает несделанному входу.

        Ловит мутацию: различение не сделано — исход проверки окружением
        клона по-прежнему пересказывается одним текстом с рецептом
        `codex login`; Оператор, у которого вход есть, получал бы указание
        войти ещё раз, а настоящая причина (перенос `CODEX_HOME` в клон
        сломан) оставалась бы неназванной и искалась бы руками.
        """
        defect = self.refusal(pult="ok")
        not_logged_in = self.refusal(pult="fail")

        self.assertNotIn(doctor.CODEX_AUTH_RECIPE, defect)
        self.assertNotEqual(not_logged_in, defect)


if __name__ == "__main__":
    unittest.main()
