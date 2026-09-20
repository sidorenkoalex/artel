"""AC-4: роль с незарегистрированным провайдером — именованный отказ
`run`/`auto` до старта агента и красная строка `doctor`.

Красен до реализации: поля `provider:` сегодня не читает никто — шаг
роли с незнакомым именем провайдера спокойно запускает агента, а
`doctor` о нём молчит.
"""
import unittest
from unittest import mock

from orchestrator import config, doctor, store
from _sandbox import (UNKNOWN_PROVIDER, DoctorSandbox, ProviderStepSandbox,
                      offline_doctor, rendered_checks,
                      roles_yaml_with_provider)


def refusal_line(role: str) -> str:
    return f"провайдер {UNKNOWN_PROVIDER} роли {role} не зарегистрирован"


class UnknownProviderStepTest(ProviderStepSandbox):
    """Шаг роли `developer`, у которой в `roles.yaml` стоит имя
    провайдера, которого нет в реестре."""

    def setUp(self):
        super().setUp()
        self.set_provider(UNKNOWN_PROVIDER)
        self.set_cli_version("9.9.9")

    def test_ac4_run_refuses_by_name_and_does_not_start_the_agent(self):
        """`run` отказывает строкой критерия, агент не стартует.

        Ловит мутацию: неизвестное имя провайдера резолвится дефолтом
        (`registry.get(name, claude_provider)`) — шаг молча уходит на
        `claude` и запускает агента вместо отказа; либо отказ есть, но
        безымянный (`KeyError`/трейсбек), и Оператор не видит, какое имя
        и у какой роли чинить.
        """
        out = self.run_step()

        self.spawn.assert_not_called()
        self.assertIn(refusal_line(self.ROLE), self.refusal_text(out))

    def test_ac4_auto_refuses_with_the_same_line(self):
        """`auto` отказывает тем же текстом и тоже не запускает агента.

        Ловит мутацию: проверка провайдера вставлена только в путь
        `cmd_run` мимо общего `_refuse_before_start` — `auto` её не
        видит и крутит шаги дальше.
        """
        out = self.run_auto()

        self.spawn.assert_not_called()
        self.assertIn(refusal_line(self.ROLE), self.refusal_text(out))


class UnknownProviderDoctorTest(DoctorSandbox):
    """`doctor` на той же карте исполнителей."""

    ROLE = "developer"

    def setUp(self):
        super().setUp()
        path = self.root / "roles-under-test.yaml"
        path.write_text(
            roles_yaml_with_provider(self.ROLE, UNKNOWN_PROVIDER,
                                     "claude-opus-5"), encoding="utf-8")
        patcher = mock.patch.object(config, "ROLES", path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_ac4_doctor_gives_a_red_line_about_the_unknown_provider(self):
        """Среди проверок `doctor` есть красная (`fail`), называющая
        незарегистрированное имя провайдера.

        Ловит мутацию: `doctor` печатает провайдеров ролей строкой, но
        не проверяет их регистрацию (статус всегда `ok`) — пульт узнаёт
        о незнакомом имени только в момент отказа шага.
        """
        self.touch_backup()
        with offline_doctor():
            checks = doctor.all_checks(store.db())

        red = [c for c in checks
               if c.status == "fail" and UNKNOWN_PROVIDER in c.detail]
        self.assertTrue(red, f"нет красной строки про провайдера "
                             f"{UNKNOWN_PROVIDER}:\n{rendered_checks(checks)}")


if __name__ == "__main__":
    unittest.main()
