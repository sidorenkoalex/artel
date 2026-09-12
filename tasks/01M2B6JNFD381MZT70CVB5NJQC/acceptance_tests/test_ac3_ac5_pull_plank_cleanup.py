"""AC-3, AC-5 (вторая половина) (tasks/01M2B6JNFD381MZT70CVB5NJQC/SPEC.md):
`pull._materialize_and_run_plank` после прогона приёмочных тестов убирает
материализованный каталог `tasks/<task_id>/acceptance_tests/` из
worktree, если до материализации этого каталога там не было; файлы,
лежавшие в worktree ДО материализации, не трогает. Уборка, которой
нечего убирать, не создаёт новой записи журнала.

Красен до реализации: `pull._materialize_and_run_plank` сегодня не
убирает материализованный каталог планки вовсе (orchestrator/pull.py) —
кода уборки нет, каталог остаётся в worktree неотслеживаемым после
прогона независимо от того, был ли он там до материализации.

Материализация (`acceptance.materialize_from_branch`) и прогон
(`acceptance.run`) — оба вне зоны этой задачи (SPEC «Не входит»),
поэтому здесь оба замоканы: предмет проверки — только логика уборки
ВОКРУГ них внутри `_materialize_and_run_plank`, не сама
материализация/прогон (те уже покрыты `tests/test_acceptance.py`).
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import acceptance, artifact_source, config, pull, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

LEGACY_SPEC_NO_AC_MARKUP = (
    "---\ntask: x\ntype: spec\nauthor_role: analyst\n"
    "status: ready\nschema_version: 1\n---\n\n# SPEC\n")


class MaterializeAndRunPlankCleanupTest(TmpRootTest):

    TASK = "01PULLPLANKCLEANUPUT1"
    BRANCH = f"task/{TASK.lower()}-x"

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, self.TASK,
                          "Тест уборки материализованной планки",
                          "in_dev", self.BRANCH, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        self.wt = self.root / "wt"
        self.wt.mkdir()
        self.tdir = self.wt / "tasks" / self.TASK
        self.acc_dir = self.tdir / "acceptance_tests"

        resolve_patcher = mock.patch.object(
            artifact_source, "resolve",
            return_value=(f"artifact/{self.TASK}", True))
        resolve_patcher.start()
        self.addCleanup(resolve_patcher.stop)

    def _materialize_fresh(self, *_args) -> Path:
        """Заглушка `acceptance.materialize_from_branch`, кладущая планку в
        `self.tdir` ровно так, как материализация делала бы её из
        источника — вызывающему коду важно только то, что каталог
        появился ИМЕННО этим вызовом, не то, что реально читалось из
        ветки (сама материализация вне зоны этой задачи)."""
        self.acc_dir.mkdir(parents=True, exist_ok=True)
        (self.acc_dir / "test_stub.py").write_text(
            "import unittest\n\n\nclass StubTest(unittest.TestCase):\n\n"
            "    def test_stub(self):\n        pass\n", encoding="utf-8")
        return self.tdir

    def _call(self, read_branch_text_or_refuse=None):
        return pull._materialize_and_run_plank(
            self.conn, self.TASK, self.BRANCH, "origin/main", self.wt,
            "in_dev", "deadbeefcafefeed",
            read_branch_text_or_refuse or mock.Mock(return_value=None))

    def journal_len(self) -> int:
        return len(store.task_steps(self.conn, self.TASK))

    def test_ac3_removes_materialized_dir_that_did_not_exist_before(self):
        """Каталога `acceptance_tests/` в worktree не было ДО вызова —
        материализация (замокана) кладёт его, прогон (замокан) зелёный —
        после возврата `Pulled` каталог обязан исчезнуть из worktree
        целиком: источник истины планки остаётся артефактная ветка, не
        диск.

        Ловит мутацию: код уборки не добавлен вовсе (сегодняшнее
        поведение) либо убирает не тот каталог — `self.acc_dir.exists()`
        остался бы `True` после возврата `Pulled`.
        """
        with mock.patch.object(acceptance, "materialize_from_branch",
                               side_effect=self._materialize_fresh), \
             mock.patch.object(acceptance, "run", return_value=(True, "ok")):
            outcome = self._call()

        self.assertIsInstance(outcome, pull.Pulled)
        self.assertFalse(
            self.acc_dir.exists(),
            "материализованный каталог планки обязан быть убран из "
            "worktree после прогона, если до материализации его там не "
            "было")

    def test_ac3_leaves_pre_existing_dir_and_its_files_untouched(self):
        """Каталог `acceptance_tests/` уже лежал в worktree ДО вызова (со
        своим файлом) — материализация (замокана) не меняет его
        содержимого, прогон (замокан) зелёный — после возврата `Pulled`
        каталог и файл, лежавший в нём до материализации, остаются на
        месте: уборка трогает только то, что появилось этим самым
        вызовом.

        Ловит мутацию: уборка не проверяет, существовал ли каталог ДО
        материализации, и удаляет его безусловно после каждого зелёного
        прогона — `marker.is_file()` вернул бы `False` после возврата
        `Pulled`, хотя файл не имеет отношения к текущей материализации.
        """
        self.acc_dir.mkdir(parents=True, exist_ok=True)
        marker = self.acc_dir / "existing_before.py"
        marker.write_text(
            "# уже лежал в worktree до материализации\n", encoding="utf-8")

        with mock.patch.object(acceptance, "materialize_from_branch",
                               return_value=self.tdir), \
             mock.patch.object(acceptance, "run", return_value=(True, "ok")):
            outcome = self._call()

        self.assertIsInstance(outcome, pull.Pulled)
        self.assertTrue(self.acc_dir.is_dir())
        self.assertTrue(marker.is_file())

    def test_ac5_cleanup_with_nothing_to_remove_does_not_journal(self):
        """Планка отсутствует в источнике (материализация не кладёт
        каталог) и SPEC не несёт AC-разметки (легитимный вырожденный
        случай, `guard.requires_ac_markup` — `False`) — `_materialize_
        and_run_plank` возвращает `Pulled` без единого нового обращения
        к журналу: уборке нечего убирать, отдельной записи об этом не
        появляется (штатное поведение, требование 3 SPEC).

        Ловит мутацию: уборка добавляет запись журнала БЕЗУСЛОВНО
        (например, «планка убрана: 0 файлов» при пустой уборке) вместо
        тихого пропуска, когда убирать нечего — `journal_len()` после
        вызова оказался бы больше на одну запись сверх значения до
        вызова.
        """
        before = self.journal_len()

        with mock.patch.object(acceptance, "materialize_from_branch",
                               return_value=self.tdir):
            outcome = self._call(read_branch_text_or_refuse=mock.Mock(
                return_value=LEGACY_SPEC_NO_AC_MARKUP))

        self.assertIsInstance(outcome, pull.Pulled)
        self.assertFalse(self.acc_dir.exists())
        self.assertEqual(self.journal_len(), before)


if __name__ == "__main__":
    unittest.main()
