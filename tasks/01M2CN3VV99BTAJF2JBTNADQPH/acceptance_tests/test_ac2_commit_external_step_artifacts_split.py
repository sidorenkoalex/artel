"""Приёмочный тест AC-2 (tasks/01M2CN3VV99BTAJF2JBTNADQPH/SPEC.md):
`_commit_external_step_artifacts` сохраняет прежнюю сигнатуру
(`conn, task_id, role, target, timeout=False`) и реально разбита на
приватные функции-фазы, а не только формально сокращена.

Поведенческая часть критерия (ранние `return ""` :679-684/:771-776,
порядок записей журнала — SPEC требование 2/3) здесь НЕ дублируется:
её покрывает существующий `tests/test_checkpoint_external_step_
artifacts.py` (например `test_check_ignore_failure_degrades_silently_
without_committing`, `test_no_tasks_dir_written_is_not_an_error`,
`test_journal_records_the_autocommit`) — зелёность ЭТОГО набора при
полном прогоне `tests/` (AC-3) и есть подтверждение неизменности
поведения; переписывать те же сценарии здесь было бы копией планки
`tests/`, запрещённой скилом test-authoring для задач класса
«рефакторинг». Точное соответствие имён/аргументов пяти фаз (`files`,
`existing`, `baseline_sha`, `own_commit_marker`, строка задачи) SPEC не
фиксирует буквальными именами новых функций — эту часть по диффу
сверяет ревьюер, не тест ниже.

Красен до реализации: сегодняшняя `_commit_external_step_artifacts`
несёт все пять фаз одним телом (252 строки, SPEC «Контекст») — не
вызывает НИ ОДНОЙ новой приватной функции-фазы бару-именем изнутри
своего тела. `test_ac2_body_delegates_to_at_least_five_private_phase_
functions` красный уже сегодня.
"""
import ast
import inspect
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

_TARGET_FUNCTION = "_commit_external_step_artifacts"
_EXPECTED_PARAMS = ("conn", "task_id", "role", "target", "timeout")
# Приватные помощники, уже вызываемые бару-именем из тела функции ДО
# рефакторинга (SPEC «Не входит»: фильтр посторонних файлов планки/
# корня — не часть дедупликации требования 2, не считается новой фазой).
_PRE_EXISTING_BARE_CALLS = {
    "_is_stray_acceptance_test_file", "_is_extraneous_task_root_file",
}
_MIN_NEW_PHASE_FUNCTIONS = 5


def _bare_private_calls_in(func) -> set[str]:
    """Имена функций, вызванных ИЗ ТЕЛА `func` голым идентификатором
    (`_foo(...)`, не `module.foo(...)`) и начинающихся с `_`."""
    tree = ast.parse(inspect.getsource(func))
    calls = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id.startswith("_")):
            calls.add(node.func.id)
    return calls


class CommitExternalStepArtifactsSplitTest(unittest.TestCase):

    def test_ac2_signature_unchanged(self):
        """Сигнатура `_commit_external_step_artifacts` — ровно `(conn,
        task_id, role, target, timeout=False)`, как до разбиения на фазы.

        Ловит мутацию: при выносе фаз в отдельные функции сигнатура
        самой `_commit_external_step_artifacts` случайно меняется
        (например, теряется дефолт `timeout=False` или переставляется
        параметр) — `inspect.signature` расходится с зафиксированным
        порядком/дефолтом.
        """
        from orchestrator import checkpoint

        fn = getattr(checkpoint, _TARGET_FUNCTION)
        sig = inspect.signature(fn)
        self.assertEqual(tuple(sig.parameters.keys()), _EXPECTED_PARAMS)
        self.assertEqual(sig.parameters["timeout"].default, False)

    def test_ac2_body_delegates_to_at_least_five_private_phase_functions(self):
        """Тело `_commit_external_step_artifacts` вызывает голым именем
        не менее пяти НОВЫХ приватных функций (не считая уже
        существовавших до рефакторинга `_is_stray_acceptance_test_file`/
        `_is_extraneous_task_root_file`) — признак того, что пять фаз
        (сбор файлов; журнал посторонних; конфликт-гвард; кандидаты на
        удаление; коммит) реально вынесены наружу, а не просто
        визуально переразбиты комментариями внутри одного тела.

        Ловит мутацию: разработчик оставляет монолитное тело как было
        (либо выносит только 1-2 вспомогательных функции вместо пяти
        заявленных SPEC фаз) — количество новых голых вызовов
        `_что-то(...)` останется меньше пяти.
        """
        from orchestrator import checkpoint

        fn = getattr(checkpoint, _TARGET_FUNCTION)
        new_calls = _bare_private_calls_in(fn) - _PRE_EXISTING_BARE_CALLS
        self.assertGreaterEqual(
            len(new_calls), _MIN_NEW_PHASE_FUNCTIONS,
            f"найдено новых приватных вызовов-фаз: {sorted(new_calls)}, "
            f"ожидалось не менее {_MIN_NEW_PHASE_FUNCTIONS}")


if __name__ == "__main__":
    unittest.main()
