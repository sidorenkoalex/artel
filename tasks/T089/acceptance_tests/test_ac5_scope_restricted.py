"""AC-5 (tasks/T089/SPEC.md): ни один файл вне `tests/` и
`tasks/*/acceptance_tests/` не изменён — правки не затрагивают
`orchestrator/`, `scripts/` и прочий боевой код.

Собственные артефакты задачи T089 (`tasks/T089/*.md` — SPEC/PLAN/REVIEW и
т.п., НЕ `tasks/T089/acceptance_tests/`, которая уже разрешена
`tasks/*/acceptance_tests/`) — обычная часть работы любой роли
(`conventions-core`: «Артефакты коммитятся в ту же ветку задачи вместе с
кодом») и не то, что критерий называет «боевым кодом» (его собственный
пример — `orchestrator/`, `scripts/`); без этого исключения красным
навсегда стал бы сам факт написания этого файла приёмочных тестов и
любого PLAN.md/REVIEW.md T089, что критерий явно не имеет в виду.

Зелёный с рождения: на момент написания этого теста единственные правки
в ветке — сами артефакты T089 (`SPEC.md`, `TZ.md`) и то, что пишет этот
коммит (`tasks/T089/acceptance_tests/`) — оба пути разрешены (исключение
выше и `tasks/*/acceptance_tests/` соответственно), боевой код ещё не
трогали.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _repo_scan import changed_files, repo_root, resolve_base_ref  # noqa: E402


def _is_allowed(rel: str) -> bool:
    parts = Path(rel).parts
    if parts and parts[0] == "tests":
        return True
    if len(parts) >= 3 and parts[0] == "tasks" and parts[2] == "acceptance_tests":
        return True
    if (len(parts) == 3 and parts[0] == "tasks" and parts[1] == "T089"
            and rel.endswith(".md")):
        return True
    return False


class ScopeRestrictedTest(unittest.TestCase):

    def test_ac5_diff_touches_only_tests_and_acceptance_tests(self):
        root = repo_root()
        base_ref = resolve_base_ref(root)
        changed = changed_files(root, base_ref)

        offenders = sorted(rel for rel in changed if not _is_allowed(rel))

        self.assertEqual(
            offenders, [],
            "изменения затрагивают файлы вне tests/ и "
            f"tasks/*/acceptance_tests/ (боевой код?): {offenders}")


if __name__ == "__main__":
    unittest.main()
