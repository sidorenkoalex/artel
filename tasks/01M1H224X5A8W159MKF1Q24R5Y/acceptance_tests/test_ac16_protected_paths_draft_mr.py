"""AC-16: Draft-MR задачи артели, диф которой затрагивает хотя бы один
путь из `config.PROTECTED_PATHS`, несёт комментарий или пункт чек-листа
адаптера, называющий затронутые защищённые пути — независимо от
предупреждения, которое уже печатает CI-job protected-paths.

Проверяется через `orchestrator/github_adapter.py::ensure_draft_mr` (тот
же публичный узел, что уже входит в SPEC T079 — «Первый прогон — на самой
артели», докстринг модуля) с полностью замоканным `ci.gh`: тест перехватывает
ВСЕ вызовы `ci.gh` за время `ensure_draft_mr` и ищет затронутый защищённый
путь (`gates.yaml`) в аргументах ЛЮБОГО из них — не привязываясь к тому,
попадёт ли пометка в исходное тело PR (`pr create --body`) или в отдельный
последующий вызов (`pr comment`/`pr edit`), раз AC-16 сама говорит
«комментарий ИЛИ пункт чек-листа» — оба исхода это `ci.gh`.

Красен до реализации: `ensure_draft_mr` сегодня не читает дифф задачи
вовсе (`orchestrator/github_adapter.py`) — тело PR несёт фиксированный
текст без списка файлов, ни один вызов `ci.gh` не назовёт `gates.yaml`.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import ci, config, github_adapter, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import ArtelSelfTargetSandbox  # noqa: E402

TASK = "01ARTELPROTECTEDDIFF01"
PROTECTED_REL = "gates.yaml"


class DraftMrFlagsProtectedPathsTest(ArtelSelfTargetSandbox):

    def setUp(self):
        super().setUp()
        self.branch = f"task/{TASK.lower()}-x"
        self.git("checkout", "-q", "-b", self.branch)
        (self.root / PROTECTED_REL).write_text(
            "gates: {}\n", encoding="utf-8")
        self.git("add", PROTECTED_REL)
        self.git("commit", "-q", "-m", f"{TASK}: правка {PROTECTED_REL}")
        self.git("checkout", "-q", config.MAIN_BRANCH)
        self.insert_task(TASK, self.branch, "in_dev")

    def capture_gh_calls(self, t):
        calls = []

        def fake_gh(*args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(
                list(args), 0, "https://example.invalid/pr/1", "")

        with mock.patch.object(ci, "gh", fake_gh):
            github_adapter.ensure_draft_mr(store.db(), t["id"], t)
        return calls

    def test_ac16_gh_call_names_the_touched_protected_path(self):
        """Диф ветки задачи артели трогает `gates.yaml`
        (`config.PROTECTED_PATHS`) — среди вызовов `ci.gh`, сделанных
        `ensure_draft_mr`, обязан найтись хотя бы один, чьи аргументы
        называют `gates.yaml`.

        Ловит мутацию: `ensure_draft_mr`, который не читает
        `config.PROTECTED_PATHS`/дифф ветки вовсе (сегодняшнее
        состояние) — ни один аргумент ни одного вызова `ci.gh` не
        назовёт `gates.yaml`.
        """
        t = store.get_task(store.db(), TASK)

        calls = self.capture_gh_calls(t)

        self.assertTrue(
            any(PROTECTED_REL in " ".join(a) for a in calls),
            f"ни один вызов ci.gh не назвал {PROTECTED_REL}: {calls}")

    def test_ac16_no_protected_path_touched_no_special_mention_required(self):
        """Контроль: задача, чей дифф НЕ трогает `config.PROTECTED_PATHS`
        (только обычный файл) — АС-16 не требует ничего особенного;
        `ensure_draft_mr` по-прежнему успешно заводит Draft MR (не
        отказывает и не падает из-за отсутствия защищённых путей)."""
        other_task = "01ARTELUNPROTECTEDDIF1"
        other_branch = f"task/{other_task.lower()}-x"
        self.git("checkout", "-q", "-b", other_branch)
        (self.root / "app.py").write_text("print('ok')\n", encoding="utf-8")
        self.git("add", "app.py")
        self.git("commit", "-q", "-m", f"{other_task}: app.py")
        self.git("checkout", "-q", config.MAIN_BRANCH)
        self.insert_task(other_task, other_branch, "in_dev")
        t = store.get_task(store.db(), other_task)

        calls = self.capture_gh_calls(t)

        self.assertTrue(any(args and args[0] == "pr" for args in calls),
                        f"Draft MR не заведён вовсе: {calls}")
        row = store.get_task(store.db(), other_task)
        self.assertEqual(row["draft_mr_created"], 1)


if __name__ == "__main__":
    unittest.main()
