"""AC-5 (SPEC 01M2B6K3EM7F2J72RC2F520Y2K) — диспетчер `orchestrator/artel.py`,
при ARTEL_ROLE в окружении, отказывает командам `init`, `doctor
--restore`, `canary pool-seal` ДО их выполнения текстом «команда
недоступна процессу роли <роль>»; без ARTEL_ROLE эти три команды
выполняются как прежде.

Красен до реализации: тесты `test_ac5_*_refused_under_role` — диспетчер
сегодня не смотрит ARTEL_ROLE вовсе, все три команды с ARTEL_ROLE в
окружении доходят до `catalog.cmd_init`/`doctor.cmd_doctor`/`canary.
cmd_pool_seal` (замоканных ниже) вместо отказа `SystemExit`.

Зелёный с рождения: тесты `test_ac5_*_runs_without_role` — без
ARTEL_ROLE команды и сегодня доходят до реализации как обычно (гейта
ещё нет, мешать нечему); после появления гейта (требование 3) эти же
тесты становятся регрессионным барьером — покраснеют, если условие на
ARTEL_ROLE перепутано и гейт начнёт срабатывать независимо от него.

Замоканы именно `catalog.cmd_init`/`doctor.cmd_doctor`/
`canary.cmd_pool_seal` — реализации, для которых зона задачи НЕ
разрешает правку (SPEC, «Зоны»: `orchestrator/doctor/`, `catalog.py`,
`canary.py` вне списка). Проверка гейта обязана жить в самом
`artel.py`, поэтому мок фиксирует «дошли ли мы до вызова реализации»
независимо от того, ГДЕ внутри `artel.py` разработчик разместит
условие (перед таблицей диспетчера, внутри лямбды и т.п.).

Песочница — `tests.sandbox.TmpRootTest`: `config.ROOT` уводится во
временный каталог без `.git`, иначе `artel.main()` первым делом
отказывает `_refuse_if_worktree()` (эта копия репозитория — worktree
задачи, `ROOT/.git` — файл-ссылка) ещё до того, как дойдёт до проверки
ARTEL_ROLE.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _helpers import ARTEL_ROLE_VAR  # noqa: E402

from orchestrator import artel, canary, catalog, doctor  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

ROLE = "developer"


class DispatcherRoleGateTest(TmpRootTest):

    def _run(self, argv):
        with mock.patch.object(sys, "argv", ["artel.py", *argv]):
            artel.main()

    def _assert_refused_under_role(self, argv, fake):
        with mock.patch.dict(os.environ, {ARTEL_ROLE_VAR: ROLE}):
            with self.assertRaises(SystemExit) as ctx:
                self._run(argv)
        fake.assert_not_called()
        message = str(ctx.exception)
        self.assertIn("недоступна процессу роли", message)
        self.assertIn(ROLE, message)

    def _assert_runs_without_role(self, argv, fake):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(ARTEL_ROLE_VAR, None)
            self._run(argv)
        fake.assert_called_once()

    def test_ac5_init_refused_under_role(self):
        """`artel.py init` под ARTEL_ROLE отказывает до вызова
        `catalog.cmd_init`.

        Ловит мутацию: гейт покрывает только `doctor --restore`/`canary
        pool-seal`, забыв `init` — тогда `cmd_init` был бы вызван и
        `SystemExit` не поднялся бы.
        """
        with mock.patch.object(catalog, "cmd_init") as fake:
            self._assert_refused_under_role(["init"], fake)

    def test_ac5_init_runs_without_role(self):
        """`artel.py init` без ARTEL_ROLE выполняется как прежде — гейт не
        трогает штатный путь Оператора/CI.

        Ловит мутацию: гейт срабатывает по самому факту команды `init`
        независимо от ARTEL_ROLE (проверка окружения выпала из условия)
        — тогда даже Оператор получил бы отказ.
        """
        with mock.patch.object(catalog, "cmd_init") as fake:
            self._assert_runs_without_role(["init"], fake)

    def test_ac5_doctor_restore_refused_under_role(self):
        """`artel.py doctor --restore` под ARTEL_ROLE отказывает до
        вызова `doctor.cmd_doctor`.

        Ловит мутацию: гейт проверяет только имя команды `doctor` без
        учёта флага `--restore` (или наоборот полностью пропускает
        `doctor` в списке запрещённых команд) — тогда `cmd_doctor` был
        бы вызван вместо отказа.
        """
        with mock.patch.object(doctor, "cmd_doctor") as fake:
            self._assert_refused_under_role(["doctor", "--restore"], fake)

    def test_ac5_doctor_restore_runs_without_role(self):
        """`artel.py doctor --restore` без ARTEL_ROLE выполняется как
        прежде.

        Ловит мутацию: гейт срабатывает независимо от ARTEL_ROLE — тест
        поймает вызов `SystemExit` там, где его быть не должно (через
        `_assert_runs_without_role`, которая ожидает `fake.
        assert_called_once()` без исключений).
        """
        with mock.patch.object(doctor, "cmd_doctor") as fake:
            self._assert_runs_without_role(["doctor", "--restore"], fake)

    def test_ac5_canary_pool_seal_refused_under_role(self):
        """`artel.py canary pool-seal` под ARTEL_ROLE отказывает до вызова
        `canary.cmd_pool_seal`.

        Ловит мутацию: гейт распознаёт только `init`/`doctor --restore`,
        не расширен на `canary pool-seal` (третья команда требования 3
        забыта) — тогда `cmd_pool_seal` был бы вызван.
        """
        with mock.patch.object(canary, "cmd_pool_seal") as fake:
            self._assert_refused_under_role(["canary", "pool-seal"], fake)

    def test_ac5_canary_pool_seal_runs_without_role(self):
        """`artel.py canary pool-seal` без ARTEL_ROLE выполняется как
        прежде.

        Ловит мутацию: гейт срабатывает для `canary pool-seal`
        независимо от ARTEL_ROLE.
        """
        with mock.patch.object(canary, "cmd_pool_seal") as fake:
            self._assert_runs_without_role(["canary", "pool-seal"], fake)


if __name__ == "__main__":
    unittest.main()
