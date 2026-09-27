"""AC-6 задачи 01M3FQ3JVC3DGGM33XCX8TC7ME — detail отказа мержа при
красном полном наборе после применения приложений PLAN.

Красен до реализации: `fsm_merge_gate._full_suite_or_refuse` кладёт в
detail сырой хвост `run_full_suite` («приложения ломают тесты: <хвост>»),
своего разбора не имеет и файла лога не пишет — ни имён упавших тестов
отдельно от тела вывода, ни пути к логу в записи нет.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _fixtures import FAILED_NODEIDS, SUMMARY_LINE, red_output  # noqa: E402
from _sandbox import PytestRunStub, capture_exit  # noqa: E402
from orchestrator import acceptance, config, fsm_merge_gate, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

APPENDIX_PATHS = ["tests/test_zones_gate.py"]


class MergeGateFullSuiteDetailTest(TmpRootTest):
    """Прогон полного набора в scratch-дереве мержа вызывается напрямую
    (`_full_suite_or_refuse`), минуя весь цикл гейта мержа: предмет
    проверки — только detail отказа по красному набору. Уборка scratch-
    дерева замокана — она про git, не про запись отказа."""

    TASK = "01M3FQ3JVC3DGGM33XCX8TC7ME"
    BRANCH = "task/01m3fq3jvc3dggm33xcx8tc7me-x"

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        store.insert_task(store.db(), self.TASK, "Отказ мержа по набору",
                          "merge_gate", self.BRANCH, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

        self.scratch = self.root / "scratch"
        (self.scratch / "tests").mkdir(parents=True, exist_ok=True)

        self.pytest_run = PytestRunStub(self.git_spy)
        self.pytest_run.returncode = 1
        self.pytest_run.stdout = red_output()
        run_patcher = mock.patch.object(acceptance.subprocess, "run",
                                        self.pytest_run)
        run_patcher.start()
        self.addCleanup(run_patcher.stop)

        drop_patcher = mock.patch.object(fsm_merge_gate,
                                         "_drop_scratch_worktree")
        drop_patcher.start()
        self.addCleanup(drop_patcher.stop)

        config.LOGS.mkdir(parents=True, exist_ok=True)

    def refuse(self) -> tuple[str, str]:
        ctx = mock.Mock()
        return capture_exit(fsm_merge_gate._full_suite_or_refuse, store.db(),
                            self.TASK, APPENDIX_PATHS, self.scratch, ctx)

    def merge_failed_detail(self) -> str:
        rows = [r for r in store.task_steps(store.db(), self.TASK)
                if "merge" in r["action"]]
        return (rows[-1]["detail"] or "") if rows else ""

    def test_ac6_refusal_detail_names_summary_failed_tests_and_log_path(self):
        """Красный полный набор в scratch-дереве с применёнными
        приложениями PLAN отказывает мерж записью, которая несёт итоговую
        строку pytest, имена упавших тестов и путь к файлу лога прогона.

        Ловит мутацию: гейт мержа оставлен на прежнем сыром хвосте
        `run_full_suite` (общий узел разбора подключён только в автогейте)
        — имена упавших тестов утонут в срезе вывода, а файла лога не
        будет вовсе, и поверхность отказа мержа снова разойдётся с
        автогейтом.
        """
        before = set(p for p in config.LOGS.glob("*.log"))

        _out, exit_text = self.refuse()

        detail = self.merge_failed_detail()
        self.assertNotEqual(detail, "",
                            "отказ мержа не оставил записи журнала")
        self.assertIn(SUMMARY_LINE, detail,
                      f"detail отказа мержа без итоговой строки: {detail!r}")
        for nodeid in FAILED_NODEIDS:
            self.assertIn(nodeid, detail,
                          f"detail отказа мержа не назвал упавший тест "
                          f"{nodeid}: {detail!r}")

        created = [p for p in config.LOGS.glob("*.log") if p not in before]
        self.assertEqual(len(created), 1,
                         f"ожидался один новый файл лога полного набора в "
                         f"{config.LOGS}, появились {created}")
        log_path = created[0]
        self.assertTrue(
            log_path.name in detail or str(log_path) in detail,
            f"detail отказа мержа не называет путь к логу {log_path}: "
            f"{detail!r}")
        self.assertNotEqual(exit_text, "",
                            "отказ мержа обязан остаться именованным отказом")


if __name__ == "__main__":
    unittest.main()
