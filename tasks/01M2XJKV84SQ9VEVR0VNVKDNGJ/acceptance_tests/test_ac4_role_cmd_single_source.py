"""Приёмочные тесты AC-4 (tasks/01M2XJKV84SQ9VEVR0VNVKDNGJ/SPEC.md):
`role_cmd()` остаётся единственным источником argv шага и вызывается из
`orchestrator/doctor/isolation.py` без аргументов, структурная сверка
`--strict-mcp-config` в `doctor.isolation_smoke` продолжает ловить свою
мутацию, `orchestrator/doctor/` задачей не меняется.

Зелёный с рождения: все три свойства — сохранение существующего
поведения (нулевая сигнатура `role_cmd()`, живая сверка смоука,
нетронутый пакет doctor); критерий требует, чтобы правка argv[0] их НЕ
задела, поэтому тесты обязаны быть зелёными и до, и после реализации —
покраснеют ровно тогда, когда реализация возьмёт у `role_cmd()`
параметр, ослабит смоук или залезет в `orchestrator/doctor/`.
"""
import inspect
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (REPO_ROOT, files_at, merge_base_or_skip,  # noqa: E402
                      text_at, text_on_disk)
from orchestrator import doctor, runner  # noqa: E402
from tests.sandbox import DeveloperBriefTmpRootTest  # noqa: E402

DOCTOR_PACKAGE = "orchestrator/doctor"


class RoleCmdIsTheSingleArgvSourceTest(DeveloperBriefTmpRootTest):
    """Офлайн-сверка изоляции во временном каталоге: та же песочница, в
    которой живёт `tests/test_doctor.py::IsolationSmokeTest`."""

    def test_ac4_role_cmd_takes_no_arguments_and_isolation_calls_it_so(self):
        """`role_cmd()` зовётся без аргументов — и в doctor, и в реальном
        запуске; резолв инструментов прячется внутрь функции, а не
        протекает наружу параметром.

        Ловит мутацию: резолв вынесен в параметр (`role_cmd(resolved)` /
        `role_cmd(claude_path=...)`), а вызов в
        `orchestrator/doctor/isolation.py` подогнан под него — офлайн
        сверка перестаёт видеть тот же argv, что и реальный шаг.
        """
        params = list(inspect.signature(runner.role_cmd).parameters)

        self.assertEqual(params, [], "у role_cmd() не должно быть параметров")
        isolation = (REPO_ROOT / "orchestrator" / "doctor"
                     / "isolation.py").read_text(encoding="utf-8")
        self.assertIn("role_cmd()", isolation,
                      "isolation.py обязан звать role_cmd() без аргументов")

    def test_ac4_isolation_smoke_still_catches_the_missing_strict_mcp_flag(self):
        """Структурная сверка `--strict-mcp-config` жива: на чистом argv
        смоук зелёный, на argv без флага — `fail` с именованием
        MCP-вектора.

        Ловит мутацию: правка `role_cmd()` роняет `--strict-mcp-config`
        из списка флагов либо сверка в смоуке сводится к «argv не пуст».
        """
        clean = doctor.isolation_smoke()
        self.assertEqual(clean.status, "ok", clean.detail)

        with mock.patch.object(doctor.runner, "role_cmd",
                               return_value=["claude", "-p"]):
            leaking = doctor.isolation_smoke()

        self.assertEqual(leaking.status, "fail")
        self.assertIn("MCP-вектор", leaking.detail)


class DoctorPackageUntouchedTest(unittest.TestCase):
    """Сверка с базой ветки задачи: пакет doctor — не зона этой задачи."""

    def test_ac4_doctor_package_is_not_modified_by_the_task(self):
        """Ни один файл `orchestrator/doctor/` не отличается от своего
        состояния на базе ветки задачи.

        Ловит мутацию: вместо правки `role_cmd()` разработчик «чинит»
        офлайн-сверку на месте — правит `orchestrator/doctor/isolation.py`
        (или заводит там новую проверку модели), выходя за зоны задачи.
        """
        base = merge_base_or_skip(self)
        changed = []

        for path in files_at(base, DOCTOR_PACKAGE):
            if text_at(base, path) != text_on_disk(path):
                changed.append(path)
        added = [p for p in (REPO_ROOT / DOCTOR_PACKAGE).rglob("*.py")
                 if str(p.relative_to(REPO_ROOT)) not in files_at(base,
                                                                  DOCTOR_PACKAGE)]

        self.assertEqual(changed, [], f"{DOCTOR_PACKAGE} правкой затронут")
        self.assertEqual([str(p.relative_to(REPO_ROOT)) for p in added], [],
                         f"в {DOCTOR_PACKAGE} добавлены файлы")


if __name__ == "__main__":
    unittest.main()
