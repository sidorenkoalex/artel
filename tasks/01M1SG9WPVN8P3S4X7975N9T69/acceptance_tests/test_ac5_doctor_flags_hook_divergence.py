"""Приёмочный тест AC-5 (tasks/01M1SG9WPVN8P3S4X7975N9T69/SPEC.md,
«Критерии приёмки»).

AC-5. `tests/test_doctor.py` несёт тест: если развёрнутый
`.artel/home/.claude/hooks/bash_guard.py` отсутствует или отличается
побайтово от референса, `orchestrator.doctor.check_role_home_reference()`
возвращает статус `warn` с упоминанием `hooks/bash_guard.py` в перечне
расхождений. Существующий обход `_role_home_diff` (`reference.rglob("*")`)
уже проходит по вложенным каталогам референса — код
`orchestrator/doctor.py` для этого критерия менять не требуется, тест
фиксирует поведение как регресс-гвардию.

Проверяем поведение НАПРЯМУЮ (вызовом `doctor.check_role_home_reference()`
на временном каталоге), а не косвенно через факт наличия строки в
`tests/test_doctor.py` — критерий про наблюдаемое поведение функции, а
не про присутствие текста в файле; тот же приём песочницы, что и
`tasks/01M1RDCEF0JZ4AVQRE43JFH8TN/acceptance_tests/
test_ac13_doctor_role_home_reference_diff.py` и уже существующий
`tests/test_doctor.py::_RoleHomeReferenceTmpRootTest`.

Зелёный с рождения: `_role_home_diff`/`check_role_home_reference`
(`orchestrator/doctor.py`) не менялись этой задачей (SPEC, «Не входит») —
обход `reference.rglob("*")` уже видит любой файл референса, включая
вложенные в `hooks/`, ДО того, как AC-1/AC-2 восстановят сам
`hooks/bash_guard.py`. Пока файла нет на диске референса вовсе (текущее
состояние, коммит dea8016b), сверка идёт по КОРОТКОМУ референсу без
`hooks/` — тест ниже сам создаёт файл в референсе временно (не трогая
репозиторий), поэтому не зависит от того, восстановлен ли AC-1/AC-2 к
моменту прогона этой планки.
"""
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import config, doctor  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


class _RoleHomeReferenceWithHookTest(TmpRootTest):
    """Песочница: `ROLE_HOME`/`ROLE_CONFIG_DIR` — во временном каталоге,
    `ROOT` — настоящее дерево репозитория. Референс временно копируется
    в свой собственный tmp-каталог и подменяется через `config.ROOT`,
    чтобы тест не зависел от наличия `hooks/bash_guard.py` в РЕАЛЬНОМ
    референсе репозитория на момент прогона (AC-1/AC-2 этой же задачи
    могут ещё не быть материализованы кодовой веткой к моменту, когда
    гоняется эта планка)."""

    PATCHED_ATTRS = ("ROLE_HOME", "ROLE_CONFIG_DIR")

    def setUp(self):
        super().setUp()
        real_reference = (config.ROOT / "docs" / "reference" / "role-home"
                          / "claude")
        self.fake_root = self.root / "fake-repo-root"
        fake_reference = self.fake_root / "docs" / "reference" / "role-home" / "claude"
        shutil.copytree(real_reference, fake_reference)
        (fake_reference / "hooks").mkdir(parents=True, exist_ok=True)
        self.hook_in_reference = fake_reference / "hooks" / "bash_guard.py"
        self.hook_in_reference.write_text(
            "#!/usr/bin/env python3\nprint('referencia hook stub')\n",
            encoding="utf-8")

        root_patcher = mock.patch.object(config, "ROOT", self.fake_root)
        root_patcher.start()
        self.addCleanup(root_patcher.stop)

        # Развёрнутый слой начинает совпадающим с референсом — каждый
        # тестовый класс сам портит/удаляет копию хука.
        shutil.copytree(fake_reference, config.ROLE_CONFIG_DIR)


class MissingHookInDeployedLayerTest(_RoleHomeReferenceWithHookTest):

    def test_ac5_missing_deployed_hook_produces_warn_naming_it(self):
        """Развёрнутый `hooks/bash_guard.py` отсутствует (например,
        деплой референса произошёл до восстановления файла) — `warn`,
        причина называет `hooks/bash_guard.py`.

        Ловит мутацию: сверка, ограниченная плоским списком файлов
        верхнего уровня референса (без рекурсии во вложенные каталоги
        `hooks/`) — тогда отсутствие файла ВНУТРИ `hooks/` не попало бы
        в перечень расхождений, и статус остался бы `ok`.
        """
        (config.ROLE_CONFIG_DIR / "hooks" / "bash_guard.py").unlink()

        check = doctor.check_role_home_reference()

        self.assertEqual(check.status, "warn")
        self.assertIn("hooks/bash_guard.py", check.detail,
                      f"причина не называет отсутствующий файл хука: {check.detail}")


class DivergedHookInDeployedLayerTest(_RoleHomeReferenceWithHookTest):

    def test_ac5_byte_diverged_deployed_hook_produces_warn_naming_it(self):
        """Развёрнутый `hooks/bash_guard.py` отличается побайтово от
        референса (устаревшая копия, деплой без повторной раскатки после
        правки референса) — `warn`, причина называет `hooks/bash_guard.py`.

        Ловит мутацию: сравнение только по имени файла/факту существования
        без сверки содержимого — правка файла, оставляющая его на месте,
        не изменила бы статус, и регрессия (устаревший хук в проде) не
        подсвечивалась бы никогда.
        """
        deployed_hook = config.ROLE_CONFIG_DIR / "hooks" / "bash_guard.py"
        deployed_hook.write_text(
            deployed_hook.read_text(encoding="utf-8") + "\n# устаревшая копия\n",
            encoding="utf-8")

        check = doctor.check_role_home_reference()

        self.assertEqual(check.status, "warn")
        self.assertIn("hooks/bash_guard.py", check.detail,
                      f"причина не называет разошедшийся файл хука: {check.detail}")


if __name__ == "__main__":
    unittest.main()
