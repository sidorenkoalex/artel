"""Приёмочные тесты задачи 01M1TT9BPBRYMDXXEWVZSRG51V: контрактная часть
разреза `orchestrator/doctor.py` на пакет — импорт, фиксированный список
экспортов, ленивый доступ к коллаборантам, порядок/статус `all_checks`
(AC-2, AC-4, AC-5, AC-10, AC-11).

Зелёный с рождения: сегодня `orchestrator/doctor.py` — один файл, поэтому
«фасад» и «функция, которая его использует» физически одно и то же
пространство имён — оба стиля импорта уже работают, фиксированный список
имён уже присутствует, `mock.patch.object(doctor, "subprocess", ...)` уже
видно функции `cli_version` (она же читает голое имя `subprocess` из
глобалей ТОГО ЖЕ модуля), а `all_checks` — это просто вызов сегодняшнего
кода. Тесты фиксируют этот уже действующий контракт ДО разреза, чтобы
после разреза (когда фасад и подмодули — разные файлы) он не сломался:
AC-4 станет содержательным именно тогда, когда подмодуль сможет иметь
СВОЙ собственный `subprocess` вместо чтения `doctor.subprocess` — сейчас
такой развилки просто не существует.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import subprocess as real_subprocess  # noqa: E402

from orchestrator import config, store  # noqa: E402
from orchestrator import doctor  # noqa: E402
from tests.sandbox import claude_only_popen, claude_only_run  # noqa: E402
from tests.test_doctor import (FakeLiveSmokeProc, TmpRootTest,  # noqa: E402
                               _REAL_WHICH, result_event)

from _shared import ALL_REQUIRED_FACADE_NAMES, EXPECTED_CHECKS_IN_ORDER  # noqa: E402


class ImportCompatibilityTest(unittest.TestCase):
    """AC-2: оба стиля импорта продолжают работать, а конкретные атрибуты,
    на которые опираются реальные вызывающие модули (fsm/auto/catalog/
    artel), резолвятся и вызываемы."""

    REAL_CALLER_ATTR_NAMES = [
        # Реальные (не строковые-фрагменты alert-source) имена из списка
        # AC-2: `doctor.check_leases`, `doctor.check_map_growth`,
        # `doctor.live_smoke`, `doctor.isolation_smoke`,
        # `doctor.recovery_check`, `doctor.preflight_checks`,
        # `doctor.cmd_doctor`. Остальные позиции формулировки AC-2
        # («doctor.recovery», «doctor.orphans», «doctor.task_counter»,
        # «doctor.hung_test_runs», «doctor.merge_lock», «doctor.leases»,
        # «doctor.cleanup») сегодня не Python-атрибуты, а куски строк
        # alert-source (`"doctor.recovery.sha"`, `"doctor.task_counter"` и
        # т.п.) внутри тела функций — сверено `grep` 06.09, hasattr-проверка
        # по ним была бы тавтологией на несуществующей вещи.
        "check_leases", "check_map_growth", "live_smoke", "isolation_smoke",
        "recovery_check", "preflight_checks", "cmd_doctor",
    ]

    def test_ac2_both_import_styles_resolve_the_same_module(self):
        """`import orchestrator.doctor as doctor` и `from orchestrator
        import doctor` дают ссылку на один и тот же объект модуля/пакета.

        Ловит мутацию: `__init__.py` пакета случайно оборачивает старые
        имена в другой объект (например, экспортирует их в
        `orchestrator/__init__.py` вместо `orchestrator/doctor/__init__.py`)
        — тогда один из способов импорта либо падает, либо даёт другой
        объект.
        """
        import orchestrator.doctor as doctor_a
        from orchestrator import doctor as doctor_b

        self.assertIs(doctor_a, doctor_b)

    def test_ac2_real_caller_attribute_chains_resolve_and_are_callable(self):
        """Атрибуты фасада, которыми реально пользуются `fsm.py`/`auto.py`/
        `catalog.py`/`artel.py` (список — из формулировки AC-2, очищенный
        от строковых фрагментов alert-source), присутствуют и вызываемы;
        сами эти модули по-прежнему импортируются без ошибок.

        Ловит мутацию: один из подмодулей после переноса не пробрасывает
        свою функцию в `__init__.py` (например, `preflight_checks` осталась
        только внутри подмодуля) — `hasattr`/`callable` находят недостачу
        раньше, чем сломается реальный вызывающий код в проде.
        """
        missing = [n for n in self.REAL_CALLER_ATTR_NAMES
                  if not callable(getattr(doctor, n, None))]
        self.assertEqual(missing, [],
                         f"не резолвится или не вызываем: {missing}")

        import orchestrator.artel  # noqa: F401
        import orchestrator.auto  # noqa: F401
        import orchestrator.catalog  # noqa: F401
        import orchestrator.fsm  # noqa: F401


class FacadeFixedExportListTest(unittest.TestCase):
    """AC-10: фасад экспортирует полный зафиксированный список имён."""

    def test_ac10_facade_exports_the_fixed_name_list(self):
        """Каждое имя из `ALL_REQUIRED_FACADE_NAMES` (зафиксирован в
        `_shared.py`, снят по методике AC-1) присутствует на
        `orchestrator.doctor`.

        Ловит мутацию: убрали один экспорт (например, `LABELS`, которым
        пользуется `orchestrator/version.py:28`, или коллаборант `canary`,
        которым пользуется `tests/test_doctor_canary_pool.py`) —
        соответствующий `hasattr` возвращает `False`, список `missing`
        перестаёт быть пустым.
        """
        missing = [n for n in ALL_REQUIRED_FACADE_NAMES if not hasattr(doctor, n)]
        self.assertEqual(missing, [],
                         f"фасад orchestrator.doctor не экспортирует: {missing}")


class LazyCollaboratorAccessTest(unittest.TestCase):
    """AC-4: коллаборанты читаются через атрибут фасада в момент вызова,
    не через собственный импорт submodule'я."""

    class _FakeSubprocess:
        TimeoutExpired = real_subprocess.TimeoutExpired

        def __init__(self, stdout: str):
            self.calls = []
            self._stdout = stdout

        def run(self, args, **kwargs):
            self.calls.append(args)
            return real_subprocess.CompletedProcess(args, 0, self._stdout, "")

    def test_ac4_cli_version_reads_subprocess_via_the_facade_attribute_live(self):
        """Подмена ЦЕЛОГО атрибута `doctor.subprocess` (не одного метода на
        настоящем модуле `subprocess`) фейковым объектом меняет поведение
        `doctor.cli_version()` — значит, вызов идёт через
        `doctor.subprocess...` в момент исполнения, а не через `subprocess`,
        захваченный локальным `import subprocess` при загрузке подмодуля
        (тот вообще не заметил бы подмену чужого атрибута `doctor.subprocess`).

        Ловит мутацию: подмодуль с `cli_version` вернул себе прямой
        `import subprocess` — тогда `doctor.subprocess.run` фейка ни разу
        не будет вызван, и тест либо получит другую версию, либо упадёт на
        `assertEqual(len(fake.calls), 1)`.
        """
        fake = self._FakeSubprocess("9.9.9 (Claude Code)\n")
        with mock.patch.object(doctor, "subprocess", fake):
            version = doctor.cli_version()

        self.assertEqual(version, "9.9.9")
        self.assertEqual(len(fake.calls), 1)


class _HealthyDoctorSandbox(TmpRootTest):
    """Тот же приём здорового репо, что `tests.test_doctor.
    DoctorCommandTest.healthy_mocks` — воспроизведён здесь (не
    унаследован от `DoctorCommandTest`), чтобы не подхватить discover'ом
    её собственные `test_*` вторым классом."""

    def _which(self, name):
        if name == "claude":
            return "/usr/bin/claude"
        return _REAL_WHICH(name)

    def _healthy_mocks(self):
        self.touch_backup()
        return (
            mock.patch.object(doctor.shutil, "which", side_effect=self._which),
            mock.patch.object(
                doctor.subprocess, "run",
                side_effect=claude_only_run(f"{config.CLI_VERSION_PIN} (Claude Code)\n")),
            mock.patch.object(
                doctor.subprocess, "Popen",
                side_effect=claude_only_popen(FakeLiveSmokeProc(result_event(0.01)))),
        )

    def _run_all_checks(self):
        p1, p2, p3 = self._healthy_mocks()
        with p1, p2, p3:
            return doctor.all_checks(store.db())


class CheckOrderAndStatusPreservationTest(_HealthyDoctorSandbox):
    """AC-5/AC-11: состав, порядок и статус проверок `all_checks` не
    меняются разрезом (сверка на пустой БД со здоровым репо)."""

    def test_ac11_all_checks_name_order_is_unchanged(self):
        """Список имён `Check.name` в порядке вызова `all_checks(conn)`
        совпадает с зафиксированным до разреза (`EXPECTED_CHECKS_IN_ORDER`
        в `_shared.py`).

        Ловит мутацию: секция при переносе попала в `all_checks` в другом
        месте (например, `check_map_growth` перенесли перед циклом по
        target'ам) — порядок имён расходится с зафиксированным.
        """
        checks = self._run_all_checks()
        actual_order = [c.name for c in checks]
        expected_order = [name for name, _status in EXPECTED_CHECKS_IN_ORDER]
        self.assertEqual(actual_order, expected_order)

    def test_ac5_all_checks_names_and_statuses_are_unchanged(self):
        """Пары `(Check.name, Check.status)` в порядке вызова совпадают с
        зафиксированными до разреза — то есть `doctor` на пустой БД даёт
        тот же исход по каждой проверке, что и до разреза (детали текста,
        завязанные на хост — например, точное число мегабайт свободного
        диска, — из сравнения намеренно исключены: они не относятся к
        переносу кода и меняются от машины к машине независимо от него).

        Ловит мутацию: перенос сломал условие внутри проверки (например,
        `check_target_layout` стала возвращать `"ok"` вместо `"warn"` для
        неинициализированного artel) — статус в найденной паре расходится
        с зафиксированным.
        """
        checks = self._run_all_checks()
        actual = [(c.name, c.status) for c in checks]
        self.assertEqual(actual, EXPECTED_CHECKS_IN_ORDER)
