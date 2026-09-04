"""AC-2 (tasks/01M1KVGD18P9H5WR7VM8TGPV1T/SPEC.md), вторая клауза:
«…и зелёный после перевода PreviousVerdictShaTest и всех прочих тестов,
заводящих задачи через cmd_new без подмены ROOT, на общую точку
подмены.»

Первая клауза (чувствительность самого снимка-сравнения к канареечной
мутации) — отдельный файл `test_ac2_invariant_check_sensitivity.py`
(зелёный с рождения, не зависит от кода задачи).

Красен до реализации: `PreviousVerdictShaTest.setUp` (`tests/
test_review_package.py`) сегодня патчит `DB`/`TASKS`/`LOGS`/`WORKTREES`
и `gitcmd.git` (`fake_git`), но НЕ `config.ROOT` — и заводит задачу
через `catalog.cmd_new`. `cmd_new` коммитит артефакты в артефактную
ветку НАСТОЯЩЕГО репозитория пульта плотницки (`artifact_branch.
commit_files` → `write_commit`), который зовёт `subprocess.run`
напрямую в НАСТОЯЩЕМ `config.ROOT`, мимо `gitcmd.git` и его подмены
(SPEC «Контекст», требование 3). Прогон именно этого класса сегодня
заводит новую ветку `artifact/<id>` в этом репозитории — снимок
«до/после» расходится, тест падает. Зелёный ожидается после того, как
`PreviousVerdictShaTest` переведён на общую точку подмены требования 2
(`tests/sandbox.py`, тот же приём, что `tests.sandbox.TmpRootTest`).

Стаб корректной реализации не готовился: правка `tests/
test_review_package.py`/`orchestrator/artifact_branch.py` — код
репозитория, который test_author не имеет права трогать (SPEC «Не
входит», conventions-core). Чувствительность самого снимка-сравнения
проверена отдельно и дёшево в `test_ac2_invariant_check_sensitivity.py`.
"""
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from orchestrator import config  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _util import diff_refs, refs_snapshot  # noqa: E402


class Ac2PreviousVerdictShaTestMigrationTest(unittest.TestCase):

    def test_ac2_previous_verdict_sha_test_leaves_real_repo_untouched(self):
        """Прогон `tests.test_review_package.PreviousVerdictShaTest` не
        меняет ссылки настоящего репозитория пульта.

        Ловит мутацию: `PreviousVerdictShaTest.setUp` мигрирован на общую
        точку подмены НЕПОЛНО (например, `config.ROOT` подменён, но
        `catalog.cmd_new` вызван до подмены; или подмена не покрывает
        путь `artifact_branch.write_commit`/`commit_files`) — прогон
        этого класса по-прежнему заводит/двигает ветку в настоящем
        репозитории, снимок расходится, тест красный.
        """
        before = refs_snapshot()
        result = subprocess.run(
            [sys.executable, "-m", "unittest",
             "tests.test_review_package.PreviousVerdictShaTest", "-q"],
            cwd=config.ROOT, capture_output=True, text=True, timeout=120)
        self.assertIn(
            result.returncode, (0, 1),
            f"прогон PreviousVerdictShaTest не завершился штатно "
            f"(код {result.returncode}): {result.stderr[-2000:]}")
        after = refs_snapshot()
        changed = diff_refs(before, after)
        self.assertEqual(
            {}, changed,
            f"PreviousVerdictShaTest изменил ссылки настоящего "
            f"репозитория пульта: {changed}")


if __name__ == "__main__":
    unittest.main()
