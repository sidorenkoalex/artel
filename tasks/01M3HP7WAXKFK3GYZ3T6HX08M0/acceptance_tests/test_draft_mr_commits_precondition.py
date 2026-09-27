"""Планка AC-8, AC-9, AC-10: черновик запроса на слияние заводится только
когда в кодовой ветке есть коммит относительно базы — и заводится
обязательно, к моменту входа задачи в `verifying`.

Красен до реализации: локальной проверки коммитов перед обращением к
GitHub ещё нет — на пустой ветке `github_adapter.ensure_draft_mr` идёт
прямо в `git push`/`gh pr create` (AC-8 видит вызов push и инцидент
`github_adapter` вместо тихого пропуска), а рубеж `in_dev -> verifying`
черновик не заводит вовсе (AC-9 не находит запроса на слияние после
рубежа). AC-10 — сохранение сегодняшнего поведения, он зелёный с
рождения и охраняет реализацию от того, чтобы новый пропуск проглотил
настоящие отказы push/`gh`.

Песочница — `tests.sandbox.RealGitSandbox`: НАСТОЯЩИЙ git-репозиторий во
временном каталоге. Заглушкой здесь обойтись нельзя — «есть ли в ветке
коммит относительно базы» проверяется локальным git, и каким именно
примитивом (`rev-list`, `merge-base`, `diff`) решает разработчик в PLAN:
настоящий репозиторий даёт правильный ответ любому из них, а фейк —
только заранее угаданному.

Наружу из песочницы не уходит ничего: `git push` перехватывается
подменой `subprocess.run` (заодно она и считает попытки push), `gh` —
подменой `github_adapter.ci.gh`.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import config, fsm, github_adapter, gitcmd, store  # noqa: E402
from orchestrator.advance_gates import tests_writing  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

from _util import (DRAFT_MR_CREATED_ACTION,  # noqa: E402
                   DRAFT_MR_FAILED_ACTION, GITHUB_ADAPTER_ALERT_SOURCE,
                   targets_yaml_text)

# Записи, которые пишет сам переход в `in_dev` (`store.set_state`), — всё
# остальное, что появилось в журнале после него, принадлежит узлу черновика.
TRANSITION_ACTIONS = ("state -> in_dev", "sha зафиксирован")


class DraftMrCommitsPreconditionTest(RealGitSandbox):
    """Узел черновика запроса на слияние против настоящего git."""

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        config.TARGETS.write_text(targets_yaml_text(), encoding="utf-8")

        self.gh_calls: list = []
        self.gh_returncode = 0
        self.push_calls: list = []
        self.push_returncode = 0
        self._real_run = subprocess.run
        self.patch(gitcmd.subprocess, "run", self._recording_run)
        self.patch(github_adapter.ci, "gh", self._spy_gh)
        # Сверка фиксации к предмету планки отношения не имеет (тот же
        # приём, что `tests/test_fsm_draft_mr_reentry.py`).
        self.patch(fsm, "confirm_fixation", lambda *a: True)

    # ------------------------------------------------------------ подмены

    def patch(self, target, attr, value) -> None:
        patcher = mock.patch.object(target, attr, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    @staticmethod
    def _subcommand(cmd) -> str:
        """Подкоманда git сквозь ведущие пары `-C <путь>` (тот же разбор,
        что `tests.sandbox.SpyRun.git_subcommands`)."""
        if not cmd or cmd[0] != "git":
            return ""
        i = 1
        while i + 1 < len(cmd) and cmd[i] == "-C":
            i += 2
        return cmd[i] if i < len(cmd) else ""

    def _recording_run(self, cmd, *args, **kwargs):
        """Настоящий git для всего, кроме `push`: наружу песочница не
        ходит, а попытки push — предмет AC-8/AC-10, поэтому считаются."""
        if self._subcommand(cmd) == "push":
            self.push_calls.append(list(cmd))
            stderr = ("" if self.push_returncode == 0
                      else "permission denied: deploy key is read-only")
            return subprocess.CompletedProcess(list(cmd),
                                               self.push_returncode, "", stderr)
        return self._real_run(cmd, *args, **kwargs)

    def _spy_gh(self, *args, **kwargs):
        self.gh_calls.append(list(args))
        stdout = ("https://github.com/artel/artel/pull/1\n"
                  if self.gh_returncode == 0 else "")
        stderr = "" if self.gh_returncode == 0 else "HTTP 403: forbidden"
        return subprocess.CompletedProcess(list(args), self.gh_returncode,
                                           stdout, stderr)

    # ------------------------------------------------------------ фикстуры

    def seed_task(self, task_id: str, with_commit: bool) -> str:
        """Задача в `verifying` со своей кодовой веткой от базы; коммит в
        ветке — по флагу. Возвращает имя ветки."""
        branch = f"task/{task_id.lower()}-shum"
        self.checkout(config.MAIN_BRANCH)
        self.checkout(branch, create=True)
        if with_commit:
            self.commit_on(branch, f"{task_id}.txt")
        self.checkout(config.MAIN_BRANCH)
        store.insert_task(self.conn, task_id, "Шум журнала и алертов",
                          "verifying", branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        return branch

    def commit_on(self, branch: str, name: str) -> None:
        """Один коммит в ветке — та самая «ветка с коммитом относительно
        базы» критериев AC-9/AC-10. Рабочая копия возвращается на базу:
        сценарии планки не зависят от того, какая ветка под HEAD."""
        self.checkout(branch)
        (self.root / name).write_text("работа разработчика\n", encoding="utf-8")
        self.git("add", name)
        self.git("commit", "-q", "-m", f"{name}: правка")
        self.checkout(config.MAIN_BRANCH)

    def enter_in_dev(self, task_id: str) -> None:
        """Настоящий вход задачи в `in_dev` (`reject` из `verifying`) — та
        точка, на которой узел черновика и срабатывает."""
        self.capture(fsm._cmd_reject, self.conn, task_id, "возврат в работу")

    def cross_verifying_rubicon(self, task_id: str):
        """Рубеж перехода `in_dev -> verifying` (SPEC «Материалы»:
        `advance_gates/tests_writing.py::_origin_push_gate` — через него на
        этом переходе вызывается `github_adapter.ensure_head_in_origin`)."""
        return tests_writing._origin_push_gate(
            self.conn, task_id, store.get_task(self.conn, task_id))

    # ------------------------------------------------------------ наблюдения

    def journal_actions(self, task_id: str) -> list[str]:
        return [r["action"] for r in store.task_steps(self.conn, task_id)]

    def draft_mr_flag(self, task_id: str) -> int:
        return store.get_task(self.conn, task_id)["draft_mr_created"]

    def adapter_alerts(self) -> list[str]:
        return [r["message"] for r in store.open_alerts(self.conn)
                if r["source"] == GITHUB_ADAPTER_ALERT_SOURCE]

    def pr_create_calls(self) -> list:
        return [call for call in self.gh_calls
                if call[:2] == ["pr", "create"]]

    # ------------------------------------------------------------- сценарии

    def test_ac8_empty_branch_skips_github_entirely(self):
        """Вход в `in_dev` с кодовой веткой без коммитов относительно базы:
        ни `git push`, ни `gh pr create` не вызываются, в журнал идёт
        запись обычного уровня о пропуске, открытых алертов
        `github_adapter` эта попытка не добавляет.

        Ветка заведена от базы и ничего в неё не коммитилось — ровно
        состояние задачи на входе в `in_dev` на прямом пути без возвратов.

        Ловит мутацию: проверка коммитов поставлена ПОСЛЕ публикации ветки
        (или после `gh pr create`) — push на пустой ветке всё равно
        случится, а GitHub ответит «No commits between», и вместо тихого
        пропуска в журнале снова окажется `Draft MR FAILED` с открытым
        инцидентом `github_adapter`.
        """
        task_id = "T001"
        self.seed_task(task_id, with_commit=False)

        self.enter_in_dev(task_id)

        self.assertEqual(self.push_calls, [])
        self.assertEqual(self.gh_calls, [])
        self.assertEqual(self.adapter_alerts(), [])
        actions = self.journal_actions(task_id)
        self.assertNotIn(DRAFT_MR_FAILED_ACTION, actions)
        skip_records = [a for a in actions if a not in TRANSITION_ACTIONS]
        self.assertTrue(skip_records,
                        f"запись о пропуске обязана появиться: {actions}")

    def test_ac9_a_branch_with_a_commit_has_a_merge_request_before_verifying(self):
        """Ветка с коммитом относительно базы (github-target, не канарейка):
        черновик заведён, и к моменту входа задачи в `verifying` запрос на
        слияние существует.

        Две задачи — две половины критерия. У первой коммит есть уже на
        входе в `in_dev`: черновик заводится там же. У второй ветка на
        входе в `in_dev` пуста (черновик законно пропущен), коммит
        появляется позже — и рубеж перехода `in_dev -> verifying` обязан
        завести черновик тогда: именно этот случай 27.09 оставлял задачу в
        `verifying` вовсе без запроса на слияние.

        Ловит мутацию: пропуск на пустой ветке выставляет признак
        «черновик заведён» (или заведение черновика подключено только к
        входу в `in_dev`) — вторая задача дошла бы до `verifying` без
        запроса на слияние, и `pr create` в списке вызовов `gh` не
        появился бы.
        """
        ready = "T001"
        self.seed_task(ready, with_commit=True)

        self.enter_in_dev(ready)

        self.assertEqual(len(self.pr_create_calls()), 1, self.gh_calls)
        self.assertIn("--draft", self.pr_create_calls()[0])
        self.assertEqual(self.draft_mr_flag(ready), 1)
        self.assertIn(DRAFT_MR_CREATED_ACTION, self.journal_actions(ready))

        later = "T002"
        branch = self.seed_task(later, with_commit=False)
        self.enter_in_dev(later)
        self.assertEqual(self.draft_mr_flag(later), 0,
                         "фикстура: на пустой ветке черновик не заводился")
        self.commit_on(branch, f"{later}.txt")
        self.gh_calls.clear()

        refusal = self.cross_verifying_rubicon(later)

        self.assertIsNone(refusal, "рубеж перехода не обязан отказывать")
        self.assertEqual(len(self.pr_create_calls()), 1, self.gh_calls)
        self.assertEqual(self.draft_mr_flag(later), 1)
        self.assertEqual(self.adapter_alerts(), [])

    def test_ac10_failures_with_a_commit_stay_incidents(self):
        """Отказ push или создания запроса на слияние при НАЛИЧИИ коммита
        (сеть/права) даёт запись `Draft MR FAILED` и открытый инцидент
        `github_adapter` — как сегодня.

        Два прогона: у первой задачи отказывает `git push`, у второй он
        проходит, но отказывает `gh pr create`. Обе ветки несут коммит —
        новый пропуск требования 8 к ним отношения не имеет.

        Ловит мутацию: пропуск написан шире критерия «нет коммитов» (git
        не ответил, база не прочитана, любой отказ адаптера) — настоящие
        отказы по сети и правам превратились бы в тихую запись о пропуске,
        и 121 накопленный инцидент сменился бы полной слепотой к сбоям
        публикации.
        """
        cases = (("T001", 1, 0), ("T002", 0, 1))
        for task_id, push_rc, gh_rc in cases:
            with self.subTest(task=task_id, push_rc=push_rc, gh_rc=gh_rc):
                self.seed_task(task_id, with_commit=True)
                self.push_returncode = push_rc
                self.gh_returncode = gh_rc

                self.enter_in_dev(task_id)

                self.assertEqual(len(self.push_calls), 1, self.push_calls)
                self.assertIn(DRAFT_MR_FAILED_ACTION,
                              self.journal_actions(task_id))
                self.assertEqual(self.draft_mr_flag(task_id), 0)
                self.assertTrue(self.adapter_alerts(), "инцидент обязан быть")
                self.push_calls.clear()
                self.gh_calls.clear()


if __name__ == "__main__":
    unittest.main()
