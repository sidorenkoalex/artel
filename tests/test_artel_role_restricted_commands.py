"""Юнит-тесты гейта диспетчера `orchestrator/artel.py` (SPEC
01M2B6K3EM7F2J72RC2F520Y2K, требование 3): `init`, `doctor --restore`,
`canary pool-seal` отказывают процессу роли (`ARTEL_ROLE` в окружении)
до вызова реализации; без признака роли команды выполняются как прежде.

Замоканы `catalog.cmd_init`/`doctor.cmd_doctor`/`canary.cmd_pool_seal` —
проверка гейта живёт в самом `artel.py`, реализации команд к зоне этой
задачи не относятся.
"""
import os
import sys
import unittest
from unittest import mock

from orchestrator import artel, canary, catalog, config, doctor
from tests.sandbox import TmpRootTest

ROLE = "developer"


class DispatcherRoleGateTest(TmpRootTest):

    def _run(self, argv):
        with mock.patch.object(sys, "argv", ["artel.py", *argv]):
            artel.main()

    def _assert_refused_under_role(self, argv, fake):
        with mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ROLE}):
            with self.assertRaises(SystemExit) as ctx:
                self._run(argv)
        fake.assert_not_called()
        message = str(ctx.exception)
        self.assertIn("недоступна процессу роли", message)
        self.assertIn(ROLE, message)

    def _assert_runs_without_role(self, argv, fake):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(config.ARTEL_ROLE_ENV, None)
            self._run(argv)
        fake.assert_called_once()

    def test_init_refused_under_role(self):
        """Ловит мутацию: гейт покрывает только `doctor --restore`/`canary
        pool-seal`, забыв `init` — тогда `cmd_init` был бы вызван вместо
        отказа `SystemExit`.
        """
        with mock.patch.object(catalog, "cmd_init") as fake:
            self._assert_refused_under_role(["init"], fake)

    def test_init_runs_without_role(self):
        """Ловит мутацию: гейт срабатывает по факту команды `init`
        независимо от `ARTEL_ROLE` — тогда Оператор получил бы отказ.
        """
        with mock.patch.object(catalog, "cmd_init") as fake:
            self._assert_runs_without_role(["init"], fake)

    def test_doctor_restore_refused_under_role(self):
        """Ловит мутацию: гейт проверяет только имя команды `doctor` без
        флага `--restore` — тогда голый `doctor` без флага отказывал бы
        тоже (здесь конкретно проверяем именно форму с флагом).
        """
        with mock.patch.object(doctor, "cmd_doctor") as fake:
            self._assert_refused_under_role(["doctor", "--restore"], fake)

    def test_doctor_restore_runs_without_role(self):
        """Ловит мутацию: гейт срабатывает независимо от `ARTEL_ROLE` —
        `cmd_doctor` не был бы вызван даже без роли в окружении.
        """
        with mock.patch.object(doctor, "cmd_doctor") as fake:
            self._assert_runs_without_role(["doctor", "--restore"], fake)

    def test_canary_pool_seal_refused_under_role(self):
        """Ловит мутацию: гейт распознаёт только `init`/`doctor --restore`,
        не расширен на `canary pool-seal` — тогда `cmd_pool_seal` был бы
        вызван вместо отказа.
        """
        with mock.patch.object(canary, "cmd_pool_seal") as fake:
            self._assert_refused_under_role(["canary", "pool-seal"], fake)

    def test_canary_pool_seal_runs_without_role(self):
        """Ловит мутацию: гейт срабатывает для `canary pool-seal`
        независимо от `ARTEL_ROLE`.
        """
        with mock.patch.object(canary, "cmd_pool_seal") as fake:
            self._assert_runs_without_role(["canary", "pool-seal"], fake)

    def test_bare_doctor_runs_under_role(self):
        """Голый `doctor` (без `--restore`) не входит в список
        ограниченных команд — доступен процессу роли как прежде.

        Ловит мутацию: гейт распознаёт `doctor` по одному имени команды
        без учёта флага `--restore` — тогда даже безобидный `doctor`
        отказывал бы под ARTEL_ROLE.
        """
        with mock.patch.object(doctor, "cmd_doctor") as fake:
            with mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ROLE}):
                self._run(["doctor"])
        fake.assert_called_once()


if __name__ == "__main__":
    unittest.main()
