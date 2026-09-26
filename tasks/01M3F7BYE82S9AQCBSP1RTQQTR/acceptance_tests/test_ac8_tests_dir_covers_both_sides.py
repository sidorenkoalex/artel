"""AC-8 — 01M3F7BYE82S9AQCBSP1RTQQTR: тест в `tests/` проверяет обе
стороны сужения окружения по провайдеру.

Источник — SPEC.md, «Критерии приёмки»:

AC-8. Тест в tests/ при заданных ambient-переменных проверяет обе
стороны: в окружении шага роли на Codex нет ни одного имени из
`secret_env_names` провайдера claude; в окружении шага роли на Claude нет
имён секретов провайдера codex (сегодня их набор пуст — проверяется
пустотой).

Кандидаты отбираются по СЦЕНАРИЮ метода (сам метод, его `setUp` и
исходники помощников, на которые он ссылается): тест обеих сторон обязан
звать сборку окружения (`role_env`) и спрашивать имена секретов у РЕЕСТРА
(`secret_env_names`), а не перечислять их литералами — иначе следующий
провайдер придётся дописывать в двух местах. Что кандидаты РАЗЛИЧАЮТ
утечку, а не просто проходят, планка проверяет подменой сборки окружения:
под ней `role_env` возвращает шагу секреты чужого провайдера обратно, и
хотя бы один кандидат обязан покраснеть.

Красен до реализации: в `tests/` сегодня нет ни одного тестового метода,
чей сценарий упоминает разом `role_env` и `secret_env_names` — отбор
пуст, и первый assert падает до всякой подмены.
"""
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import providers, runner  # noqa: E402

LEAKED_VALUE = "tok-vernuvshiysya-v-shag"


@contextmanager
def role_env_leaking_foreign_secrets():
    """Подмена сборки окружения: `role_env` отдаёт шагу секреты
    провайдера `claude` независимо от того, чей это шаг, — состояние
    пульта ДО требования 4."""
    real_role_env = runner.role_env

    def leaky(role=None, task_id=None):
        env = real_role_env(role, task_id)
        for name in providers.get("claude").secret_env_names():
            env.setdefault(name, LEAKED_VALUE)
        return env

    with mock.patch.object(runner, "role_env", leaky):
        yield


class TestsDirCoversBothSidesTest(unittest.TestCase):

    def test_ac8_tests_dir_test_names_both_providers_and_catches_the_leak(self):
        """В `tests/` есть проходящий тест, чьё тело зовёт `role_env` и
        спрашивает имена секретов у `secret_env_names`; кандидаты
        называют обоих сегодняшних провайдеров (обе стороны критерия), и
        под подменённой сборкой окружения, возвращающей шагу чужой
        секрет, хотя бы один из них краснеет.

        Ловит мутацию: тест в `tests/` написан на одну сторону («шаг на
        Codex не получает токен Claude») и молчит про обратную, либо
        сверяет не собранное окружение, а накладку провайдера — тогда
        подменённый `role_env` его не трогает, и `failing()` останется
        пустым.
        """
        ids = _util.test_methods_mentioning("role_env", "secret_env_names")
        self.assertTrue(
            ids,
            "в tests/ нет тестового метода, чей сценарий упоминает разом "
            "role_env и secret_env_names (AC-8)")

        outcomes = _util.run_test_methods(ids)
        self.assertEqual(
            [], _util.failing(outcomes),
            "тест(ы) tests/ про сужение окружения по провайдеру не "
            "проходят на сегодняшнем коде: " + repr(outcomes))

        bodies_mention = set()
        for test_id in ids:
            body = _util.method_source(*test_id).lower()
            for provider_name in providers.PROVIDERS:
                if provider_name in body:
                    bodies_mention.add(provider_name)
        self.assertEqual(
            set(providers.PROVIDERS), bodies_mention,
            "тесты обеих сторон обязаны называть обоих провайдеров "
            f"реестра; названы: {sorted(bodies_mention)}")

        with role_env_leaking_foreign_secrets():
            mutated = _util.run_test_methods(_util.passing(outcomes))

        self.assertTrue(
            _util.failing(mutated),
            "ни один тест tests/ не покраснел, когда сборка окружения "
            "вернула шагу секрет чужого провайдера — проверены: "
            + _util.describe(_util.passing(outcomes)))


if __name__ == "__main__":
    unittest.main()
