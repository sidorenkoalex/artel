"""Приёмочный тест AC-1 (tasks/01M2CYQR0357VAQFZ5VACJD9TD/SPEC.md): пакет
`orchestrator/gates/` создан с файлами `__init__.py`, `_base.py`,
`zones.py`, `capacity.py`, `review.py`, `acceptance.py`,
`tests_writing.py`; функции/константы, перечисленные ДОСЛОВНО
требованием 1 SPEC, физически перенесены в соответствующий файл (не
переопределены заново — само определение, `__module__`, указывает на
новый файл).

Требование 1 называет явно только часть переносимых имён по каждому
файлу («и его прямые помощники», «их помощники дат/sha» — без
перечисления) — тест сверяет ровно те имена, что названы буквально,
плюс явно поименованный глоб `_tests_writing_*` (три текущие функции с
этим префиксом), не изобретая проверку для неназванных помощников
(test-authoring: «тест на то, что не написано в AC — такой же дефект»).

Красен до реализации: `orchestrator/gates/` ещё не существует —
`orchestrator.gates` сегодня резолвится в старый флэт-модуль
`orchestrator/gates.py` (политика `gates.yaml`, ADR-0007/T066), у
которого нет ни `__path__` (не пакет), ни атрибутов `_base`/`zones`/
`capacity`/`review`/`acceptance`/`tests_writing` — первая же проверка
`test_ac1_package_directory_with_required_files_exists` падает.
"""
import importlib
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

# Файл -> явно поименованные требованием 1 функции/константы этого файла.
_REQUIRED_FILES = (
    "__init__.py", "_base.py", "zones.py", "capacity.py", "review.py",
    "acceptance.py", "tests_writing.py",
)

_EXPECTED_LOCATION = {
    "_base": ["GateRefusal", "_run_gates"],
    "zones": ["_zones_gate"],
    "capacity": ["_capacity_gate", "_EMPTY_DIFF_TEXT", "CAPACITY_GATE_REASON"],
    "review": ["_review_escalation_sha_gate", "_mutation_claim_gate",
               "_review_rework_gate"],
    "acceptance": ["_acceptance_lock_refuses", "_acceptance_run_refuses"],
    "tests_writing": ["_origin_push_gate", "_registry_gate",
                      "_freshness_refuses",
                      "_tests_writing_stray_plank_files_gate",
                      "_tests_writing_acceptance_dir",
                      "_tests_writing_dry_collect_gate"],
}


class GatesPackageCreatedTest(unittest.TestCase):

    def test_ac1_package_directory_with_required_files_exists(self):
        """`orchestrator/gates/` — каталог-пакет на диске, несущий ровно
        семь файлов, перечисленных требованием 1 (`__init__.py` плюс
        шесть тематических модулей).

        Ловит мутацию: перенос сделан ОДНИМ файлом
        (`orchestrator/gates/__init__.py` целиком, без разбивки на
        `zones.py`/`capacity.py`/...) — часть путей из списка не
        существует, хотя пакет как таковой есть и даже импортируется.
        """
        gates_dir = REPO_ROOT / "orchestrator" / "gates"
        missing = [name for name in _REQUIRED_FILES
                  if not (gates_dir / name).is_file()]
        self.assertEqual(
            missing, [],
            f"orchestrator/gates/ не несёт файлов: {missing}")

    def test_ac1_named_functions_and_constants_physically_moved(self):
        """Каждое имя, названное требованием 1 буквально, — атрибут
        соответствующего подмодуля `orchestrator.gates.<file>`, причём
        ОПРЕДЕЛЁННЫЙ там же (`__module__` указывает на этот подмодуль),
        а не реэкспортирован из `orchestrator.fsm_advance`.

        Ловит мутацию: функция физически ОСТАЁТСЯ в
        `orchestrator/fsm_advance.py`, а в нужный файл `gates/`
        добавляется только `from ..fsm_advance import _capacity_gate` —
        имя формально доступно как `orchestrator.gates.capacity.
        _capacity_gate`, но `__module__` этой функции остаётся
        `orchestrator.fsm_advance`, а не `orchestrator.gates.capacity`
        (переезд не дословный, а обратный реэкспорт).
        """
        mismatches = []
        for file_stem, names in _EXPECTED_LOCATION.items():
            module_name = f"orchestrator.gates.{file_stem}"
            module = importlib.import_module(module_name)
            for name in names:
                if not hasattr(module, name):
                    mismatches.append(f"{module_name}.{name}: отсутствует")
                    continue
                obj = getattr(module, name)
                # Строковые константы не несут __module__ — их место
                # проверяет сам факт наличия атрибута в нужном подмодуле
                # (у строк нет понятия "где физически определены").
                actual_module = getattr(obj, "__module__", module_name)
                if actual_module != module_name:
                    mismatches.append(
                        f"{module_name}.{name}: определено в "
                        f"{actual_module}, не в {module_name}")
        self.assertEqual(mismatches, [], "; ".join(mismatches))


if __name__ == "__main__":
    unittest.main()
