"""AC-6: вход не подтверждён домом роли ПУЛЬТА — прогон отказывает до
первого шага роли, а текст отказа называет однократный шаг Оператора
`codex login` (рецепт `doctor.CODEX_AUTH_RECIPE`).

Зелёный с рождения: сегодня прогон отказывает по неподтверждённому входу и
приписывает к отказу `detail` проверки, который несёт этот рецепт целиком —
тест держит существующее поведение для ПЕРВОГО из двух случаев требования
6, чтобы различение случаев не отобрало рецепт у того исхода, где он
Оператору и нужен.

Настоящий клиент Codex не запускается, связка ключей не спрашивается: узел
проверки входа подменён, git фальшивый.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _clone_env import CloneEnvCase  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import canary, doctor  # noqa: E402


class RefusalWithoutPultLoginTest(CloneEnvCase):
    """AC-6: отказ, когда вход не подтверждён и домом роли пульта."""

    def test_ac6_a_login_missing_in_the_pult_role_home_is_refused_with_the_recipe(self):
        """Вход не подтверждён ни домом роли пульта, ни окружением шага
        клона: блок клона отказывает `SystemExit` ДО своего тела, и текст
        отказа несёт рецепт двух однократных шагов Оператора.

        Ловит мутацию: различение двух случаев написано так, что рецепт
        снят с ОБОИХ исходов (отказ во всех случаях говорит «дефект
        пульта») — Оператор, у которого вход просто не сделан, получал бы
        строку без единственной команды, которой она чинится, и однократный
        шаг остался бы несделанным.
        """
        entered = []

        with self.fake_git(), self.login_check(pult="fail", clone="fail"):
            with self.assertRaises(SystemExit) as ctx:
                with canary._ephemeral_clone(codex_auth=self.auth()):
                    entered.append("тело блока клона")

        self.assertEqual([], entered)
        self.assertIn(doctor.CODEX_AUTH_RECIPE, str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
