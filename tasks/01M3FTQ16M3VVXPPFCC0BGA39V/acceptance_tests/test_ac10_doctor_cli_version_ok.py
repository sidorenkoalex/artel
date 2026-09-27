"""AC-10 — 01M3FTQ16M3VVXPPFCC0BGA39V: `doctor.check_cli_version` даёт
`ok` на установленной 2.1.267, и сам `orchestrator/doctor/` не правится.

Источник — SPEC.md, «Критерии приёмки»:

AC-10. `doctor.check_cli_version` при установленной версии CLI 2.1.267
даёт статус `ok` (без правок в `orchestrator/doctor/`).

«Установленная версия CLI» подставляется подменой `doctor.cli_version`
(единственный источник версии для этой проверки — разбор `claude
--version`, orchestrator/doctor/preflight.py:22-32): реальная версия на
машине прогона — свойство среды, а критерий говорит о поведении проверки
при заданной версии.

Красен до реализации: пин в `orchestrator/config.py` — 2.1.236, поэтому
сверка `version != config.CLI_VERSION_PIN` даёт `warn` с текстом
«установлена 2.1.267, пин 2.1.236» — `test_ac10_check_is_ok_for_the_
installed_version` падает. `test_ac10_doctor_package_is_untouched`
зелёный и сейчас: ветка `orchestrator/doctor/` ещё не трогала, и трогать
не должна.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402
from orchestrator import doctor  # noqa: E402

INSTALLED_VERSION = "2.1.267"
DOCTOR_ZONE = "orchestrator/doctor/"


class DoctorCliVersionTest(unittest.TestCase):

    def test_ac10_check_is_ok_for_the_installed_version(self):
        """При версии CLI 2.1.267 проверка `cli-version` даёт статус `ok`
        (а не `warn` о расхождении с пином).

        Ловит мутацию: пин поднят не до установленной версии (опечатка в
        одной цифре, лишний пробел внутри строки) — сверка в
        `check_cli_version` снова даст `warn`, и `assertEqual` покраснеет,
        назвав фактический detail проверки.
        """
        with mock.patch.object(doctor, "cli_version",
                               return_value=INSTALLED_VERSION):
            check = doctor.check_cli_version()
        self.assertEqual("cli-version", check.name)
        self.assertEqual(
            "ok", check.status,
            f"при установленной {INSTALLED_VERSION} проверка обязана быть ok "
            f"(AC-10), а вернула {check.status}: {check.detail}")

    def test_ac10_doctor_package_is_untouched(self):
        """Ветка задачи не меняет ни одного файла в `orchestrator/doctor/`
        — статус `ok` обязан получиться подъёмом пина, а не правкой самой
        проверки.

        Ловит мутацию: расхождение «починено» в проверке
        (`check_cli_version` перестаёт сравнивать версию с пином или
        сравнивает по префиксу) — файл `orchestrator/doctor/preflight.py`
        появится в дифе ветки, и тест покраснеет, хотя проверка выше
        стала бы зелёной.
        """
        changed = _util.changed_paths_since_base(DOCTOR_ZONE)
        self.assertEqual(
            [], changed,
            f"{DOCTOR_ZONE} — только чтение для этой задачи (AC-10), а в "
            f"дифе ветки изменены: {changed}")


if __name__ == "__main__":
    unittest.main()
