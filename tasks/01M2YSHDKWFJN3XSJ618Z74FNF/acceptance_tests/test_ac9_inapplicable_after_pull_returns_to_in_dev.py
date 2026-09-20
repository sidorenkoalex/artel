"""AC-9 (SPEC 01M2YSHDKWFJN3XSJ618Z74FNF): приложение, не применимое в
scratch-дереве после подтяжки main, не завершает процесс `sys.exit`'ом —
задача возвращается в `in_dev` с причиной «приложение PLAN неприменимо
после подтяжки: <путь>», scratch-дерево убрано.

Красен до реализации: приложения на мерже не применяются вовсе, поэтому неприменимое приложение никак не влияет на исход — задача доезжает до `done`, а причины «приложение PLAN неприменимо после подтяжки» в журнале нет ни одной.

Сценарий «main сдвинулся» разыгран приложением, чей хунк не совпадает ни
с одной строкой файла (`_sandbox.stale_diff_block`, класс инцидента
11.09): для `git apply` в scratch-дереве это ровно тот же исход, что и
устаревшее после подтяжки приложение, а зависимости от гонки двух пультов
у теста нет.

Провалидировано стабом (решение Оператора 03.09): временный возврат в
`in_dev` с именованной причиной и уборкой scratch-дерева на провале
`git apply` зеленит тест; стаб удалён, репозиторий не тронут.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _parse  # noqa: E402
import _sandbox  # noqa: E402

from orchestrator import config  # noqa: E402


class InapplicableAfterPullTest(_sandbox.MergeAppendixSandbox):

    def setUp(self):
        super().setUp()
        self.commit_plan([_parse.appendix_section(
            [_sandbox.stale_diff_block(_parse.PROTECTED_FILE,
                                       "правка Оператора")],
            suffix=f": устаревшее приложение {_parse.PROTECTED_FILE}")])

    def test_ac9_task_returns_to_in_dev_and_scratch_is_dropped(self):
        """Неприменимое в scratch приложение: процесс не завершён,
        задача в `in_dev`, причина возврата несёт префикс «приложение
        PLAN неприменимо после подтяжки:» и путь приложения, main origin
        не продвинут, scratch-worktree дерегистрирован.

        Ловит мутацию: провал `git apply` в scratch обработан тем же
        `sys.exit`, что инфраструктурные отказы этого гейта (или, хуже,
        не проверен вовсе и приложение доезжает до main половиной
        хунков) — задача осталась бы на `merge_gate` решением человека
        вместо возврата разработчику, а `assertEqual(self.state(),
        "in_dev")` это поймает. Проверка списка worktree ловит вторую
        мутацию: возврат в `in_dev` сделан без уборки scratch-дерева, и
        каждый такой мерж оставляет висящую запись `.git/worktrees/`.
        """
        before_main = self.origin_main_sha()

        outcome, exit_text = self.approve_catching_exit()

        self.assertEqual(
            exit_text, "",
            f"цикл мержа завершил процесс вместо возврата задачи в "
            f"in_dev: {exit_text!r}")
        self.assertEqual(
            self.state(), "in_dev",
            f"исход тела гейта: {outcome!r}; журнал:\n{self.journal_blob()}")
        self.assertIn(_sandbox.AFTER_PULL_REASON_PREFIX, self.journal_blob())
        reason_records = [f"{a} | {d}" for a, d in self.journal()
                          if _sandbox.AFTER_PULL_REASON_PREFIX in d]
        self.assertTrue(
            any(_parse.PROTECTED_FILE in r for r in reason_records),
            f"причина возврата не называет путь приложения: "
            f"{reason_records!r}")
        self.assertEqual(
            self.origin_main_sha(), before_main,
            "main origin не имеет права продвинуться: приложение не "
            "применилось")
        self.assertEqual(
            self.worktree_paths(config.ROOT), [str(config.ROOT)],
            "scratch-worktree обязан быть дерегистрирован")


if __name__ == "__main__":
    unittest.main()
