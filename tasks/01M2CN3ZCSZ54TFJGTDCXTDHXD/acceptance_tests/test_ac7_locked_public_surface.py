"""AC-7 (SPEC.md): имена `run_agent_once`, `spawn_agent`, `role_env`,
`role_cwd`, `role_cmd`, `cmd_run`, `_cmd_run`, `step_role`,
`wave_breaker_alerts_open` остаются глобалами модуля
`orchestrator/runner.py` с прежними сигнатурами; новый модуль не
создаётся — разбор выполнен целиком внутри `orchestrator/runner.py`.

Ожидаемые сигнатуры сняты буквально с исходника orchestrator/runner.py
ДО разбора (эта же ревизия): 38 тестовых файлов патчат эти девять имён
101 раз (SPEC «Контекст», docs/audits/code-revision-2026-09-13.md,
CR-2026-09-13-1) — расхождение любой сигнатуры (лишний/потерянный
параметр, другой порядок, другое значение по умолчанию) ломает эти
патчи независимо от того, вызывается ли функция.

Зелёный с рождения: сигнатуры девяти имён рефакторинг не имеет права
менять (SPEC, требование 3) — тест уже проходит на дорефакторном коде
и обязан остаться зелёным после него; красный тест здесь означал бы,
что регресс тестового набора ловит именно этот файл.
"""
import inspect
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import runner  # noqa: E402

# (имя, ожидаемые имена параметров в порядке объявления) — снято с
# orchestrator/runner.py на голове этой ветки перед началом рефакторинга.
LOCKED_SIGNATURES = {
    "run_agent_once": ["conn", "task_id", "role", "prompt", "attempt"],
    "spawn_agent": ["cmd", "kwargs"],
    "role_env": ["role", "task_id"],
    "role_cwd": ["conn", "task_id", "target"],
    "role_cmd": [],
    "cmd_run": ["task_id", "session_id"],
    "_cmd_run": ["conn", "task_id"],
    "step_role": ["t"],
    "wave_breaker_alerts_open": ["conn"],
}


class LockedPublicSurfaceTest(unittest.TestCase):

    def test_ac7_locked_names_keep_signatures_and_stay_module_globals(self):
        """Каждое из девяти зафиксированных AC-7 имён — атрибут МОДУЛЯ
        `orchestrator.runner` (не класса, не реэкспорт из нового модуля)
        с тем же списком имён параметров, что и до разбора.

        Ловит мутацию: `role_cwd`/`role_env` переезжают в новый модуль
        `orchestrator/runner_phases.py` с реэкспортом старого имени через
        `from .runner_phases import role_cwd` — атрибут `orchestrator.
        runner.role_cwd` формально существует, но SPEC требование 6
        («новый модуль не создаётся») нарушено; либо `spawn_agent`
        получает новый именованный параметр вместо `**kwargs` — список
        имён параметров разойдётся, `assertEqual` откажет.
        """
        for name, expected_params in LOCKED_SIGNATURES.items():
            with self.subTest(name=name):
                self.assertIn(name, vars(runner),
                              f"{name} не найден как глобал orchestrator.runner")
                fn = getattr(runner, name)
                self.assertTrue(callable(fn), f"{name} не является функцией")
                sig = inspect.signature(fn)
                self.assertEqual(list(sig.parameters), expected_params,
                                 f"сигнатура {name} изменилась")

    def test_ac7_no_new_sibling_module_carries_runner_phase_helpers(self):
        """Разбор не заводит новый модуль рядом (например
        `orchestrator/runner_phases.py`, `orchestrator/step_runner.py`)
        — единственное место декомпозиции фаз шага роли остаётся
        `orchestrator/runner.py`.

        Ловит мутацию: приватные фазы (`_prepare_step` и остальные из
        AC-1/AC-4) выносятся в отдельный файл этой же зоны, а
        `orchestrator/runner.py` оставляет только тонкие обёртки-реэкспорты
        — `orchestrator/__init__.py` не меняется этой задачей (SPEC:
        «новый модуль не создаётся»), а его отсутствие в списке
        подмодулей — наблюдаемый признак этого нарушения.
        """
        import pkgutil
        import orchestrator

        module_names = {name for _, name, _ in
                        pkgutil.iter_modules(orchestrator.__path__)}
        suspicious = {n for n in module_names
                     if "runner" in n and n != "runner"}
        self.assertEqual(suspicious, set(),
                         f"обнаружены модули-кандидаты на вынос фаз runner.py: "
                         f"{suspicious}")
