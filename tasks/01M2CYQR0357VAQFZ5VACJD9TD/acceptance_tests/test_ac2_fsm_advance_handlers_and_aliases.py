"""Приёмочный тест AC-2 (tasks/01M2CYQR0357VAQFZ5VACJD9TD/SPEC.md):
`orchestrator/fsm_advance.py` сохраняет обработчики состояний, эффекты
вердиктов и алиасы старых имён на все перенесённые в `orchestrator/
gates/` функции/константы; `orchestrator/answer.py` не изменён и
продолжает работать без правок.

Список алиасов ниже — объединение (а) имён, явно названных требованием
1 SPEC (та же выборка, что test_ac1_gates_package_created.py), и (б)
имён, чью доступность как `fsm_advance.<имя>` подтверждает сам текст
SPEC/код репозитория уже сегодня: девять тестовых файлов требования 4
зовут `fsm_advance._zones_gate_refuses`/`_capacity_gate_refuses`/
`_review_rework_gate_refuses`/`_run_gates`/`GateRefusal`/
`_review_escalation_sha_gate`/`_mutation_claim_gate` НАПРЯМУЮ (требование
4: только импорты/пути патчей меняются — сама точка вызова
`fsm_advance.<имя>` остаётся), а `orchestrator/answer.py` — требование 2
буквально — берёт `_split_zone_paths`, `_plan_zones_extension_paths`,
`_ZONES_MANDATE_MARKER` из `fsm_advance` тем же способом.

Красен до реализации: `orchestrator/gates/` не существует —
`test_ac2_all_transferred_names_are_true_aliases_to_gates_objects`
падает на первом же `importlib.import_module("orchestrator.gates.
_base")` (ModuleNotFoundError).
"""
import importlib
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

_STATE_HANDLERS = ["spec_writing", "tests_writing", "review", "verifying",
                  "in_dev"]
_EFFECTS = ["_review_approved", "_in_dev_plan_escalate", "_apply_plan_budget"]

# имя -> подмодуль orchestrator.gates.<...>, где объект физически живёт
# после переноса.
_ALIASED_NAMES = {
    "GateRefusal": "_base",
    "_run_gates": "_base",
    "_zones_gate": "zones",
    "_zones_gate_refuses": "zones",
    "_split_zone_paths": "zones",
    "_plan_zones_extension_paths": "zones",
    "_ZONES_MANDATE_MARKER": "zones",
    "_capacity_gate": "capacity",
    "_capacity_gate_refuses": "capacity",
    "CAPACITY_GATE_REASON": "capacity",
    "_EMPTY_DIFF_TEXT": "capacity",
    "_review_escalation_sha_gate": "review",
    "_mutation_claim_gate": "review",
    "_review_rework_gate": "review",
    "_review_rework_gate_refuses": "review",
    "_acceptance_lock_refuses": "acceptance",
    "_acceptance_run_refuses": "acceptance",
    "_origin_push_gate": "tests_writing",
    "_registry_gate": "tests_writing",
    "_freshness_refuses": "tests_writing",
    "_tests_writing_stray_plank_files_gate": "tests_writing",
    "_tests_writing_acceptance_dir": "tests_writing",
    "_tests_writing_dry_collect_gate": "tests_writing",
}


class FsmAdvanceHandlersAndAliasesTest(unittest.TestCase):

    def test_ac2_state_handlers_and_verdict_effects_stay_defined_in_module(self):
        """Пять обработчиков состояний и три эффекта вердиктов
        (`_review_approved`, `_in_dev_plan_escalate`, `_apply_plan_budget`)
        остаются реально ОПРЕДЕЛЕНЫ в `orchestrator/fsm_advance.py`
        (`__module__` указывает на сам этот модуль), а не становятся
        алиасами на `orchestrator.gates.*`.

        Ловит мутацию: разработчик по ошибке заодно переносит один из
        эффектов (например, `_review_approved`, который зовёт
        `_registry_gate` — сосед перенесённых функций по тексту файла)
        в `orchestrator/gates/acceptance.py`, оставляя в
        `fsm_advance.py` только алиас — `__module__` эффекта укажет на
        `orchestrator.gates.acceptance`, не на `orchestrator.fsm_advance`.
        """
        from orchestrator import fsm_advance

        mismatches = []
        for name in _STATE_HANDLERS + _EFFECTS:
            if not hasattr(fsm_advance, name):
                mismatches.append(f"{name}: отсутствует в fsm_advance")
                continue
            obj = getattr(fsm_advance, name)
            if getattr(obj, "__module__", None) != "orchestrator.fsm_advance":
                mismatches.append(
                    f"{name}: __module__={getattr(obj, '__module__', None)}, "
                    f"ожидалось orchestrator.fsm_advance")
        self.assertEqual(mismatches, [], "; ".join(mismatches))

    def test_ac2_all_transferred_names_are_true_aliases_to_gates_objects(self):
        """Каждое перенесённое в `orchestrator/gates/` имя остаётся
        доступным как `orchestrator.fsm_advance.<имя>` И является ТЕМ ЖЕ
        объектом (`is`), что и `orchestrator.gates.<файл>.<имя>` — то
        есть настоящим алиасом (`from .gates.zones import _zones_gate`),
        а не независимой копией/переопределением под старым именем.

        Ловит мутацию: `fsm_advance.py` не импортирует перенесённые
        имена вовсе — обращения к ним в оставшихся обработчиках
        (например, `_capacity_gate_refuses` внутри `in_dev`) ломаются
        `NameError` при первом же вызове; `hasattr`/`is`-проверка здесь
        ловит это ещё на уровне статического наличия атрибута, не дожидаясь
        рантайма конкретного перехода.
        """
        from orchestrator import fsm_advance

        mismatches = []
        for name, file_stem in _ALIASED_NAMES.items():
            module_name = f"orchestrator.gates.{file_stem}"
            module = importlib.import_module(module_name)
            if not hasattr(fsm_advance, name):
                mismatches.append(f"fsm_advance.{name}: отсутствует")
                continue
            if not hasattr(module, name):
                mismatches.append(f"{module_name}.{name}: отсутствует")
                continue
            if getattr(fsm_advance, name) is not getattr(module, name):
                mismatches.append(
                    f"{name}: fsm_advance.{name} — не тот же объект, что "
                    f"{module_name}.{name} (не алиас, а копия/переопределение)")
        self.assertEqual(mismatches, [], "; ".join(mismatches))

    def test_ac2_answer_module_imports_and_keeps_using_fsm_advance_names(self):
        """`orchestrator/answer.py` импортируется без ошибок и
        продолжает видеть `fsm_advance._split_zone_paths`,
        `fsm_advance._plan_zones_extension_paths`,
        `fsm_advance._ZONES_MANDATE_MARKER` — три имени, которые
        `answer.py` берёт исключительно через атрибут модуля
        `fsm_advance` (не прямым импортом), требование 2 SPEC.

        Ловит мутацию: перенос заводит алиасы только для «гейтовых»
        функций (`_zones_gate` и т.п.), забыв про эти три
        вспомогательных имени, которыми пользуется ИСКЛЮЧИТЕЛЬНО
        `answer.py` — импорт `orchestrator.answer` пройдёт (он не
        обращается к ним на уровне модуля), но `hasattr` ниже поймает
        разрыв раньше первого реального вызова `cmd_answer`.
        """
        from orchestrator import answer, fsm_advance  # noqa: F401

        for name in ("_split_zone_paths", "_plan_zones_extension_paths",
                    "_ZONES_MANDATE_MARKER"):
            self.assertTrue(hasattr(fsm_advance, name),
                            f"fsm_advance.{name} отсутствует — answer.py "
                            f"опирается на этот атрибут")


if __name__ == "__main__":
    unittest.main()
