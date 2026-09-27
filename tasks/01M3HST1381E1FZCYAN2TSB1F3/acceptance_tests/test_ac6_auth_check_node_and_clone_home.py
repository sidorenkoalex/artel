"""AC-6 — 01M3HST1381E1FZCYAN2TSB1F3: проверка входа — тот же узел, что у
`doctor`, и с домом роли КЛОНА.

Источник — SPEC.md, «Критерии приёмки»:

AC-6. Проверка входа идёт тем же узлом, что у `doctor`
(`doctor.check_codex_chatgpt_auth`), и с домом роли КЛОНА: окружение
собранного вызова несёт `HOME` и `CODEX_HOME` внутри каталога клона, не
дома роли пульта.

«Тот же узел» наблюдается подменой самой функции в обоих местах, где
реализация законно может до неё добраться: атрибут пакета `doctor` и любое
имя модуля `canary`, чьё значение — та же функция (`_util.auth_check_
targets`). Своя копия логики проверки мимо узла наблюдения не оставит, и
первый же ассерт её назовёт.

«Дом роли КЛОНА» читается из окружения ФАКТИЧЕСКОГО процесса `codex login
status` (`_util.RunSpy.login_calls`), а не из того, что проверка сообщила о
себе в `detail`: критерий говорит про окружение собранного вызова.

Имена переменных берутся у провайдера (`codex_provider.HOME_ENV`), не
литералами: адрес каталога знает провайдер, и его переименование не должно
красить планку.

Красен до реализации: прогон канарейки проверку входа не зовёт вовсе — ни
одного вызова узла и ни одного процесса `codex login status`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402
from orchestrator import doctor  # noqa: E402
from orchestrator.providers import codex as codex_provider  # noqa: E402


class AuthCheckNodeAndCloneHomeTest(_util.CodexClonePlankSandbox):

    def test_ac6_the_run_calls_doctors_own_auth_check_node(self):
        """Проверку входа делает `doctor.check_codex_chatgpt_auth`, а не
        собственная копия её логики внутри канарейки.

        Ловит мутацию: канарейка собирает `codex login status` сама (свой
        argv, свой разбор вывода) — расхождение с `doctor` копилось бы
        молча: `ok` у канарейки при красной строке `doctor` (или наоборот),
        и «вход и шаг задают один способ авторизации» перестало бы
        держаться одной константой.
        """
        outcome = self.run_canary(set_name=_util.SET_NAME)

        self.assertTrue(
            outcome.auth_calls,
            "узел doctor.check_codex_chatgpt_auth не вызван; процессы "
            f"login status: {outcome.spy.login_calls}")
        self.assertEqual(doctor.CODEX_AUTH_CHECK,
                         outcome.auth_calls[0].check.name)

    def test_ac6_the_assembled_call_carries_the_clone_home_not_the_pult_one(self):
        """`HOME` и `CODEX_HOME` собранного вызова лежат внутри каталога
        клона, а не в доме роли пульта.

        Ловит мутацию: проверка вызвана СНАРУЖИ блока клона (до входа или
        после выхода) — `config.ROLE_HOME` указывал бы на дом роли пульта,
        и прогон подтверждал бы вход Оператора вместо входа того дома, с
        которым реально пойдёт шаг в клоне: зелёная проверка при заведомо
        невходящем клоне.
        """
        outcome = self.run_canary(set_name=_util.SET_NAME)

        self.assertTrue(outcome.spy.login_calls,
                        f"процесса `codex login status` не было: "
                        f"{outcome.text}")
        self.assertTrue(outcome.auth_calls, "узел проверки входа не вызван")
        _argv, kwargs = outcome.spy.login_calls[0]
        env = kwargs.get("env") or {}
        clone_root = outcome.auth_calls[0].root

        self.assertNotEqual(self.root, clone_root,
                            "проверка звалась вне эфемерного клона")
        for name in ("HOME", codex_provider.HOME_ENV):
            with self.subTest(variable=name):
                value = env.get(name)
                self.assertIsNotNone(value, f"{name} в окружении вызова нет: "
                                            f"{sorted(env)}")
                self.assertTrue(
                    Path(value).is_relative_to(clone_root),
                    f"{name}={value} вне каталога клона {clone_root}")
                self.assertFalse(
                    Path(value).is_relative_to(self.pult_home),
                    f"{name}={value} внутри дома роли пульта")

    def test_ac6_the_clone_home_of_the_call_is_the_one_holding_the_pointer(self):
        """`HOME` собранного вызова — тот самый дом роли клона, в который
        перенесён указатель.

        Ловит мутацию: указатель положен в один каталог клона, а проверка
        позвана с `HOME` другого (например, `config.ROLE_HOME` снят до
        переноса, а перенос сделан в подкаталог) — `codex login status`
        по-прежнему не нашёл бы связку, и проверка краснела бы на исправно
        перенесённом указателе.
        """
        outcome = self.run_canary(set_name=_util.SET_NAME)

        self.assertTrue(outcome.spy.login_calls,
                        f"процесса `codex login status` не было: "
                        f"{outcome.text}")
        self.assertTrue(outcome.auth_calls, "узел проверки входа не вызван")
        _argv, kwargs = outcome.spy.login_calls[0]
        home = Path((kwargs.get("env") or {}).get("HOME", ""))
        clone_root = outcome.auth_calls[0].root

        self.assertEqual(
            clone_root / self.pult_home.relative_to(self.root), home,
            "дом роли вызова не совпадает с домом роли клона")


if __name__ == "__main__":
    unittest.main()
