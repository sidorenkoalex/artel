"""Приёмочные тесты T042 — авто-коммит регенерированной карты кодовой базы
оркестратором на `merge_gate` (SPEC.md, критерии AC-1..AC-6).

Песочница AC-1..AC-4 — `tests.test_invariants.FsmTest` (та же фикстура, на
которой уже стоят `MergeOnlyFromMergeGateTest`/`MergeNeedsGreenCiTest`/
`MergeSuccessStillClosesTaskTest` для той же merge-последовательности, и
которую уже переиспользовал tasks/T036/acceptance_tests): БД и артефакты во
временном каталоге, `subprocess.run` подменён на уровне
`gitcmd.subprocess.run` — реальный git не исполняется.

Поверх неё `MapRegenSandboxTest` дополнительно подменяет `config.ROOT` на
синтетическое дерево с единственным файлом `docs/codebase-map.md`: реальный
`docs/codebase-map.md` пульта трогать нельзя (это файл рабочего дерева
репозитория, в котором гоняются тесты, не фикстура), а без подмены ROOT
поведение «сверка содержимым» пришлось бы наблюдать на настоящей карте
пульта. Заглушка `subprocess.run` внутри `approve()` играет роль и
`scripts/codebase_map.py` (пишет заданный текст в `self.map_path` при
вызове `python3 ...`), и git (по образцу T036 `_fail_at`/`fake_git_*`) —
включая побочный эффект `git checkout -- docs/codebase-map.md`, который сама
реализация должна выполнить, чтобы АС-2 (никакого коммита при отсутствии
содержательных отличий) прошёл: тест не утверждает «был вызван checkout»
напрямую, а проверяет наблюдаемый результат — файл откатился к
закоммиченному тексту (иначе заглушка ничего не перезапишет, и итоговое
содержимое не совпадёт с ожидаемым).

Отличие содержимого карты моделируется отдельно от `built_at_sha` — та же
пара случаев, что различают требования 2 и 3 SPEC: у AC-1 меняются и
`built_at_sha`, и текст карты; у AC-2 только `built_at_sha`.

AC-4 — статическая проверка исходника `fsm.py`, по образцу
`tasks/T036/acceptance_tests/test_merge_gitcmd.py`
(`NoDirectGitSubprocessRunTest`), но сужена до git-вызовов конкретно
(`subprocess.run(["git", ...])`): требование 6 запрещает новым GIT-вызовам
идти в обход `gitcmd.git`, а не любому `subprocess.run` вообще — регенерация
карты (`scripts/codebase_map.py`) законно зовётся напрямую, тем же приёмом,
что и `brief._regenerate_map` (SPEC, материалы).

AC-5 («существующий набор тестов зелёный») размечена `manual` — тот же
довод и прецедент, что `tasks/T036` AC-4: критерий уже покрыт
`.github/workflows/ci.yml` (`unittest discover -s tests -v` на каждый пуш в
чистом раннере); повтор той же проверки подпроцессом внутри
acceptance_tests ловил бы экологические условия машины разработчика, а не
дефект этой задачи.

AC-6 — реальная проверка диффа ТЕКУЩЕЙ ветки задачи относительно `main` в
самом репозитории (не песочница): критерий буквально про то, какие пути
задел дифф задачи, и это наблюдаемо без единого мока, тем же способом, что
и `protected-paths` в `.github/workflows/ci.yml`.
"""
# AC-5: manual — критерий уже покрыт `.github/workflows/ci.yml` (джоб
# `python`, `unittest discover -s tests -v` на каждый пуш в чистом раннере);
# повтор прогона всего набора подпроцессом внутри acceptance_tests ловил бы
# экологические условия машины разработчика, а не дефект этой задачи
# (прецедент tasks/T036 AC-4).

import ast
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import alerts, config, fsm, gitcmd, store  # noqa: E402
from tests.test_invariants import FsmTest  # noqa: E402


# --------------------------------------------------------------------------
# AC-1, AC-2, AC-3: сквозной путь через `fsm.cmd_approve` из `merge_gate`.

class MapRegenSandboxTest(FsmTest):
    """merge_gate с готовыми артефактами + управляемая карта на подменённом
    `config.ROOT`."""

    COMMITTED_MAP = (
        "---\nbuilt_at_sha: aaaa000011112222333344445555666677778888\n"
        "---\n\n# Карта кодовой базы\n\nСодержимое A.\n")

    def setUp(self):
        super().setUp()
        self.write_spec("ready")
        self.write_plan("ready")
        self.write_review("approved", 1)
        self.set_state("merge_gate")

        map_root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, map_root, ignore_errors=True)
        (map_root / "docs").mkdir()
        self.map_path = map_root / "docs" / "codebase-map.md"
        self.map_path.write_text(self.COMMITTED_MAP, encoding="utf-8")
        root_patcher = mock.patch.object(config, "ROOT", map_root)
        root_patcher.start()
        self.addCleanup(root_patcher.stop)

        self.calls: list[list[str]] = []

    def git_subcommands(self) -> list[str]:
        return [c[1] for c in self.calls if len(c) > 1 and c[0] == "git"]

    def fake_subprocess(self, regen_rc=0, regen_stderr="", regen_text=None,
                        fail_git_subcommands=()):
        """Заглушка `subprocess.run` на время approve: запоминает все
        вызовы; `python3 ...` — имитация `scripts/codebase_map.py`
        (пишет `regen_text` в `self.map_path` при успехе); `git checkout --
        docs/codebase-map.md` — откатывает файл к закоммиченному тексту
        (побочный эффект, который должна произвести сама реализация);
        git-подкоманды из `fail_git_subcommands` отвечают отказом."""
        def fake(cmd, *args, **kwargs):
            cmd = list(cmd)
            self.calls.append(cmd)
            if cmd and cmd[0] == "python3":
                if regen_rc == 0 and regen_text is not None:
                    self.map_path.write_text(regen_text, encoding="utf-8")
                return subprocess.CompletedProcess(cmd, regen_rc, "",
                                                   regen_stderr)
            if (len(cmd) > 1 and cmd[0] == "git"
                    and cmd[1] in fail_git_subcommands):
                return subprocess.CompletedProcess(
                    cmd, 1, "", "стенд: git-подкоманда упала")
            if (len(cmd) > 1 and cmd[0] == "git" and cmd[1] == "checkout"
                    and "docs/codebase-map.md" in cmd):
                self.map_path.write_text(self.COMMITTED_MAP, encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return fake

    def approve(self, **fake_kwargs) -> None:
        fake = self.fake_subprocess(**fake_kwargs)
        with mock.patch.object(gitcmd.subprocess, "run", fake):
            self.capture(fsm.cmd_approve, self.TASK)


class Ac1ContentChangedMapGetsCommittedTest(MapRegenSandboxTest):
    """AC-1: merge, после которого карта содержательно стухла, оставляет в
    main два коммита — merge и регенерированная карта; карта после этого
    содержательно свежа."""

    def test_ac1_two_commits_and_fresh_map_after_merge(self):
        regenerated = self.COMMITTED_MAP.replace(
            "aaaa000011112222333344445555666677778888",
            "cccc111122223333444455556666777788889999",
        ).replace("Содержимое A.", "Содержимое B.")

        self.approve(regen_text=regenerated)

        subcommands = self.git_subcommands()
        self.assertIn("merge", subcommands)
        self.assertIn(
            "commit", subcommands,
            "содержательно изменённая карта не закоммичена отдельным "
            "коммитом")
        self.assertLess(
            subcommands.index("merge"), subcommands.index("commit"),
            "коммит карты должен идти после merge-коммита")

        commit_calls = [c for c in self.calls if c[:2] == ["git", "commit"]]
        message = " ".join(commit_calls[-1])
        self.assertIn(self.TASK, message,
                      "сообщение коммита карты не называет id смерженной "
                      "задачи")
        self.assertIn("регенерация", message.lower())

        self.assertEqual(
            subcommands.count("push"), 1,
            "merge-коммит и коммит карты должны уйти одним git push")
        self.assertLess(subcommands.index("commit"), subcommands.index("push"))

        self.assertEqual(
            self.map_path.read_text(encoding="utf-8"), regenerated,
            "карта после merge_gate должна остаться содержательно свежей")
        self.assertEqual(self.state(), "done")


class Ac2NoContentDiffMeansNoSecondCommitTest(MapRegenSandboxTest):
    """AC-2: merge, не меняющий карту содержательно, второго коммита не
    порождает; рабочее дерево после merge_gate остаётся чистым."""

    def test_ac2_only_built_at_sha_differs_no_commit_and_clean_tree(self):
        regenerated = self.COMMITTED_MAP.replace(
            "aaaa000011112222333344445555666677778888",
            "dddd444455556666777788889999000011112222",
        )  # тот же текст карты — расходится только built_at_sha

        self.approve(regen_text=regenerated)

        self.assertTrue(
            any(c and c[0] == "python3" for c in self.calls),
            "регенерация карты (scripts/codebase_map.py) не была запущена "
            "на merge_gate")
        subcommands = self.git_subcommands()
        self.assertIn("merge", subcommands)
        self.assertNotIn(
            "commit", subcommands,
            "карта без содержательных отличий (кроме built_at_sha) не "
            "должна коммититься")
        self.assertEqual(
            self.map_path.read_text(encoding="utf-8"), self.COMMITTED_MAP,
            "рабочее дерево должно быть откачено к закоммиченной карте "
            "(git checkout -- docs/codebase-map.md, по образцу brief.py) — "
            "иначе после merge_gate остаётся незакоммиченная правка")
        self.assertEqual(self.state(), "done")


class Ac3MapStepFailureDoesNotBlockMergeTest(MapRegenSandboxTest):
    """AC-3: провал регенерации или коммита карты не отменяет merge —
    задача уходит в done, в журнале есть запись о провале, в alerts открыт
    инцидент kind=incident с source вида fsm.map_regen."""

    def _assert_merge_still_completed_with_incident(self):
        self.assertEqual(
            self.state(), "done",
            "провал шага карты не должен отменять merge и переход в done")
        self.assertIn(
            "push", self.git_subcommands(),
            "git push обязан выполниться независимо от исхода шага карты")

        journal_text = "\n".join(
            f"{s['action']} {s['detail']}"
            for s in store.task_steps(store.db(), self.TASK)).lower()
        self.assertTrue(
            any(k in journal_text for k in ("карт", "map"))
            and any(k in journal_text
                   for k in ("failed", "провал", "не удал", "ошиб")),
            "в журнале нет записи о провале шага регенерации/коммита карты")

        incidents = alerts.open_alerts(store.db(), "incident")
        matching = [a for a in incidents
                   if (a["source"] or "").startswith("fsm.map_regen")]
        self.assertTrue(
            matching,
            "не заведён incident-алерт с source вида fsm.map_regen "
            "(SPEC, требование 5)")

    def test_ac3_regeneration_failure_still_completes_merge(self):
        self.approve(regen_rc=1, regen_stderr="стенд: генератор карты упал")

        self._assert_merge_still_completed_with_incident()
        self.assertNotIn(
            "commit", self.git_subcommands(),
            "регенерация упала — коммитить в принципе нечего")

    def test_ac3_map_commit_failure_still_completes_merge(self):
        regenerated = self.COMMITTED_MAP.replace(
            "Содержимое A.", "Содержимое C.")

        self.approve(regen_text=regenerated,
                     fail_git_subcommands=("add", "commit"))

        self._assert_merge_still_completed_with_incident()


# --------------------------------------------------------------------------
# AC-4: новые git-вызовы этой задачи идут только через `gitcmd.git`.

class NewGitCallsGoThroughGitcmdTest(unittest.TestCase):
    """AC-4: в `fsm.py` не должно быть `subprocess.run(["git", ...])`
    напрямую — только регенерация карты (`python3 scripts/codebase_map.py`,
    не git) вправе звать `subprocess.run` в обход `gitcmd.git` (по образцу
    `brief._regenerate_map`, требование 6 SPEC говорит именно про
    git-вызовы)."""

    def test_ac4_fsm_has_no_direct_git_subprocess_run(self):
        source = (REPO_ROOT / "orchestrator" / "fsm.py").read_text(
            encoding="utf-8")
        tree = ast.parse(source, filename="fsm.py")
        offending_lines = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            is_subprocess_run = (
                isinstance(func, ast.Attribute) and func.attr == "run"
                and isinstance(func.value, ast.Name)
                and func.value.id == "subprocess")
            if not is_subprocess_run or not node.args:
                continue
            first = node.args[0]
            if isinstance(first, (ast.List, ast.Tuple)) and first.elts:
                head = first.elts[0]
                if isinstance(head, ast.Constant) and head.value == "git":
                    offending_lines.append(node.lineno)
        self.assertEqual(
            offending_lines, [],
            f"остались прямые subprocess.run(['git', ...]) в fsm.py на "
            f"строках {offending_lines} — должны идти через gitcmd.git")


# --------------------------------------------------------------------------
# AC-6: `.github/` и `skills/` в диффе задачи не затронуты.

class ProtectedPathsUntouchedTest(unittest.TestCase):
    """AC-6: реальная проверка диффа текущей ветки задачи относительно
    `main` — без единого мока, тем же принципом, что и `protected-paths`
    в `.github/workflows/ci.yml`."""

    @staticmethod
    def _git(*args: str) -> str:
        res = subprocess.run(["git", *args], cwd=REPO_ROOT,
                             capture_output=True, text=True, check=True)
        return res.stdout.strip()

    def test_ac6_branch_diff_does_not_touch_github_or_skills(self):
        branch = self._git("rev-parse", "--abbrev-ref", "HEAD")
        if branch == "main":
            self.skipTest("рабочее дерево на main — диффить не с чем")
        merge_base = self._git("merge-base", "main", branch)
        changed = self._git("diff", "--name-only", merge_base,
                            branch).splitlines()
        offending = [p for p in changed
                    if p.startswith(".github/") or p.startswith("skills/")]
        self.assertEqual(
            offending, [],
            f"дифф ветки {branch} относительно main трогает защищённые "
            f"пути: {offending}")


if __name__ == "__main__":
    unittest.main()
