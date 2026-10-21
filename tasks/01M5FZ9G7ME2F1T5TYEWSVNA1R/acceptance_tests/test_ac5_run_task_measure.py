"""AC-5: строка `canary_runs`, написанная подкомандой `canary run-task`, совпадает со строкой последовательного прогона; базовая строка другой пары не тронута.

Группа: разовый
Красен до реализации: подкоманды `run-task` нет — вызов отказывает в ветке прогона `cmd_canary` («нужен параметр --k»), строки подкоманды в `canary_runs` нет.

Почему разовый: критерий требует подменить фазу 1 — закрытую
`_run_task_in_ephemeral_clone`; правила долгоживущего файла `tests/` такие
подмены запрещают.

Песочница — `tests.sandbox.InitializedTmpRootTest`; пул канарейки из одного
учебного шаблона — в подменённом домашнем каталоге (`Path.home`).
`_run_one_task` настоящий в обоих прогонах; фаза 1 подменена функцией,
возвращающей метрики с `code_sha`. Последовательный прогон —
`canary.cmd_canary(k=1, sha=…, templates=[шаблон])` с подменённым
`_resolve_target_sha` (он ходит к git; подкоманде его звать нельзя, поэтому
у неё он подменён отказом). План набора — настоящий `_set_plan` набора по
умолчанию. Значения порождаются от зерна; зерно печатается и входит в текст
провала.
"""
import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _runtask import RunTaskMixin, invoke  # noqa: E402

from orchestrator import canary, config, store  # noqa: E402
from tests.sandbox import InitializedTmpRootTest  # noqa: E402

COMPARED = ("run_stamp", "title", "set_name", "models_summary", "main_sha", "verdict")


class RunTaskMeasureTest(RunTaskMixin, InitializedTmpRootTest):
    """Последовательный прогон и подкоманда на одной подмене фазы 1."""

    def setUp(self):
        super().setUp()
        self.setup_runtask()
        home = mock.patch.object(Path, "home", return_value=self.home)
        home.start()
        self.addCleanup(home.stop)

    def phase_one(self, code_sha: str):
        """Подмена фазы 1: результат процесса клона с `code_sha` в метриках."""
        normal = code_sha == self.sha

        def fake(template_path, run_stamp, explicit_target_sha, *args, **kwargs):
            metrics = {"steps": 3, "cost_usd": 1.25, "review_iterations": 1,
                       "escalations": [], "dev_retries": 0,
                       "outcome": "killed", "kill_note": "штатно",
                       "test_author_visited": True, "ceiling_exhausted": False,
                       "ceiling_raise": None, "code_sha": code_sha,
                       "target_sha": explicit_target_sha}
            return ("01FIXTURE" + self.token(8).upper(), Path(template_path).stem,
                    None, [], metrics, False, False, normal, None)

        return mock.patch.object(canary, "_run_task_in_ephemeral_clone",
                                 side_effect=fake)

    def sequential(self, code_sha: str) -> dict:
        out = io.StringIO()
        known = {r["id"] for r in self.rows()}
        with self.phase_one(code_sha), contextlib.redirect_stdout(out), \
                mock.patch.object(canary, "_resolve_target_sha",
                                  return_value=(self.sha, None)):
            canary.cmd_canary(k=1, sha=self.sha, templates=[self.template_name])
        rows = [r for r in self.rows() if r["id"] not in known]
        self.assertEqual(len(rows), 1, self.msg(f"{rows}\n{out.getvalue()}"))
        return rows[0]

    def subcommand(self, stamp: str, summary: str, code_sha: str):
        self.put_mark(stamp, self.ppid)
        with contextlib.ExitStack() as stack:
            self.guards(stack)
            stack.enter_context(self.phase_one(code_sha))
            outcome = invoke(self.argv(stamp, config.CANARY_DEFAULT_SET, summary))
        (self.registry() / f"{stamp}.lock").unlink(missing_ok=True)
        return outcome

    def baseline(self, title: str, set_name: str):
        row = store.canary_baseline(store.db(), title, set_name)
        return None if row is None else dict(row)

    def test_ac5_row_matches_sequential_run_and_other_pair_untouched(self):
        """Код клона совпадает с проверяемым sha (штатно) и отличается от него.

        Сценарий: базовая строка пары (шаблон, другой набор) заведена; идёт
        последовательный прогон шаблона набором по умолчанию, затем
        подкоманда с его `run_stamp`, тем же `--sha` и сводкой настоящего
        плана. Наблюдение: у строки подкоманды `run_stamp`, `set_name`,
        `models_summary`, `main_sha` (коммит, сообщённый клоном), `verdict`
        те же, что у строки последовательного прогона; строка
        последовательного прогона после подкоманды та же; базовая строка
        другой пары до и после вызова подкоманды одинакова; код 0.

        Ловит мутацию: подкоманда ведёт задачу без плана (`plan=None` —
        `models_summary` пуст и набор по умолчанию вместо сводки), пишет
        `main_sha` проверяемым `--sha` вместо коммита клона, либо сверяет
        бейзлайн по одному шаблону без набора и переписывает строку другой
        пары.
        """
        real = canary._set_plan(config.CANARY_DEFAULT_SET)
        self.assertEqual(real.codex_roles, (), self.msg("набор песочницы с Codex"))
        other_set = "nabor-" + self.token(5)
        store.set_canary_baseline(store.db(), self.template_name, 11, 7.5, 4, other_set)
        for case, code_sha in (("штатно", self.sha), ("другой код", self.hexsha())):
            with self.subTest(случай=case):
                seq = self.sequential(code_sha)
                seq_after_ids = {r["id"] for r in self.rows()}
                other_before = self.baseline(self.template_name, other_set)
                outcome = self.subcommand(seq["run_stamp"], real.summary, code_sha)
                ctx = self.msg(f"{case}: {outcome!r}")
                self.assertEqual(outcome.code, 0, ctx)
                new = [r for r in self.rows() if r["id"] not in seq_after_ids]
                self.assertEqual(len(new), 1, self.msg(f"{case}: {new}; {outcome!r}"))
                row = new[0]
                self.assertEqual({k: row[k] for k in COMPARED},
                                 {k: seq[k] for k in COMPARED}, ctx)
                self.assertEqual(row["main_sha"], code_sha, ctx)
                self.assertEqual([r for r in self.rows() if r["id"] == seq["id"]],
                                 [seq], ctx)
                self.assertEqual(self.baseline(self.template_name, other_set),
                                 other_before, ctx)
                self.assertIsNotNone(other_before, ctx)


if __name__ == "__main__":
    unittest.main()
