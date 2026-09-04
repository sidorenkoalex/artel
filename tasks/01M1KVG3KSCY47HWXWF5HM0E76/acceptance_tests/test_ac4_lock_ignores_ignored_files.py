"""AC-4 (SPEC): «Сверка лока приёмочных тестов не отклоняет переход
`in_dev -> review`, когда единственная разница между рабочим деревом
`acceptance_tests/` и зафиксированным sha — игнорируемые файлы
(например, ранее занесённые `.pyc`)».

Сценарий инцидента 03.09 (SPEC «Контекст»): после лока (`tests_locked_
sha`) в артефактной ветке появляется `.pyc` — не правка текста теста,
просто хвост локального прогона `python3 -m unittest` — и сегодняшняя
сверка (`fsm_advance.in_dev`, голый `gitcmd.diff_paths(locked, lock_ref,
"tasks/<id>/acceptance_tests")`) видит ЛЮБУЮ разницу как спор с
локом и отказывает переходу, хотя тексты тестов не менялись.

Тест не полагается на починку `checkpoint._commit_external_step_
artifacts` (AC-1/AC-2/AC-3 — отдельная, независимая часть SPEC):
`.pyc` кладётся на артефактную ветку НАПРЯМУЮ, тем же приёмом (`git add
-A` внутри `commit_task_dir`), каким `tests/test_acceptance_tests_flow.
py::LockTest` кладёт правку теста, — сверка лока обязана справляться с
этим независимо от того, откуда взялся игнорируемый файл в ветке.

Красен до реализации: `fsm_advance.in_dev` сегодня сравнивает
`tasks/<id>/acceptance_tests` целиком без учёта `.gitignore` — diff по
одному `.pyc` уже не пуст, переход отклоняется тем же текстом
«acceptance_tests/ изменены после лока», что и настоящая правка теста;
`self.state()` останется `in_dev` вместо `review`.
"""
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import fsm  # noqa: E402
from _sandbox import LockFlowSandbox  # noqa: E402


class LockIgnoresIgnoredFilesTest(LockFlowSandbox):

    def test_ac4_pyc_only_diff_after_lock_does_not_block_advance(self):
        """После лока (`enter_in_dev`, `tests_locked_sha` зафиксирован) в
        `acceptance_tests/__pycache__/` появляется `.pyc` — единственная
        разница с зафиксированным деревом; переход `in_dev -> review`
        обязан пройти.

        Ловит мутацию: возврат к голому `gitcmd.diff_paths(locked,
        lock_ref, "tasks/<id>/acceptance_tests")` без исключения
        игнорируемых путей из сравнения — `self.state()` останется
        `in_dev`, `out` понесёт текст «эскалация» вместо перехода.
        """
        self.enter_in_dev()
        self.on_artifact_branch()
        pycache = self.tdir / "acceptance_tests" / "__pycache__"
        pycache.mkdir(parents=True, exist_ok=True)
        (pycache / "test_ac.cpython-311.pyc").write_bytes(bytes(range(8)))
        self.commit_task_dir("прогон тестов оставил .pyc")

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "review",
                         "разница только по игнорируемым файлам не должна "
                         "останавливать переход")


if __name__ == "__main__":
    unittest.main()
