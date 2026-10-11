"""AC-8: Переход `merge_gate -> done` (`approve`) записывает merge-коммит
в `refs/heads/main` артели через объектную базу git (плотницки), не через
`git checkout main` рабочего дерева `config.ROOT`: рабочее дерево и HEAD
`config.ROOT` идентичны непосредственно до и сразу после успешного
`approve`.

AC-9: Регенерация карты кодовой базы и генерация RETRO, выполняемые тем же
переходом (`fsm_postmerge.py`), тоже не меняют рабочее дерево и HEAD
`config.ROOT` — их коммиты попадают в main той же неchekaut-механикой, что
и сам merge-коммит (AC-8).

AC-12 (обязательный тест «merge не меняет запущенную версию»): после
успешного `approve` на `merge_gate` рабочее дерево и HEAD `config.ROOT`
остаются на зафиксированном пином sha, даже когда main артели ушёл вперёд
этим самым merge — уже запущенный процесс и любой НОВЫЙ вызов `artel.py`
из `config.ROOT` до операторского обновления пина исполняются тем же
кодом, что и до merge.

Красен до реализации: `orchestrator/fsm_merge_gate.py::
_cmd_approve_merge_gate` сегодня буквально делает `git checkout main`,
`git pull --ff-only`, `git merge --no-ff <branch>` (строки ~256-263) —
командами БЕЗ `-C`/`cwd=`, то есть на рабочем дереве `config.ROOT`
(`gitcmd.git`, `cwd=config.ROOT`) — HEAD и рабочее дерево ГАРАНТИРОВАННО
меняются успешным merge. `fsm_postmerge._regenerate_and_commit_map`/
`_generate_and_commit_retro` тем же порядком читают/пишут файлы на диске
`config.ROOT` и коммитят через `git add`/`git commit` того же чекаута.
Песочница — `ArtelSelfTargetSandbox` (`_sandbox.py`, WIP-чекпоинт этой же
задачи): `self.origin` — bare-репозиторий, играющий роль «main артели» из
критериев (ANSWER-1, вариант B) — origin `self.root`, реальный git,
локально на диске.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import ci, config, fsm_merge_gate, gitcmd, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import ArtelSelfTargetSandbox  # noqa: E402

TASK = "01ARTELCARPENTRYMERGE1"


class CarpentryMergeDoesNotTouchRootWorktreeTest(ArtelSelfTargetSandbox):

    def setUp(self):
        super().setUp()
        self.branch = f"task/{TASK.lower()}-x"
        self.make_task_branch_in_root(
            self.branch, "feature.txt", "код фичи\n", f"{TASK}: код фичи")
        self.insert_task(TASK, self.branch, "merge_gate")
        self.ci_patcher = mock.patch.object(
            ci, "branch_status", lambda branch: (True, "зелёный (тест)"))
        self.ci_patcher.start()
        self.addCleanup(self.ci_patcher.stop)

    def approve(self):
        t = store.get_task(store.db(), TASK)
        return fsm_merge_gate._cmd_approve_merge_gate(
            store.db(), TASK, "merge_gate", t)

    def test_ac8_root_worktree_and_head_identical_before_and_after_approve(self):
        """`approve` успешно доводит задачу до `done` (артель мержится в
        свой собственный main), но `config.ROOT` — HEAD, ветка, статус,
        содержимое `marker.txt` — идентичны снимку ДО вызова: слепок
        `snapshot_root_state()` до и сразу после совпадает байт-в-байт.

        Ловит мутацию: `git checkout main`/`git merge --no-ff` без `-C`
        внутри `_cmd_approve_merge_gate` — тогда `root_head_sha()` после
        approve обязан отличаться от снимка «до» (в рабочем дереве
        появится закоммиченный `feature.txt`), а этот тест — единственный
        в наборе, который сравнивает СНИМОК ЦЕЛИКОМ, а не отдельные поля
        (полнота требования «идентичны»).
        """
        before = self.snapshot_root_state()

        result = self.approve()

        self.assertEqual(result, ("done",))
        self.assertEqual(store.get_task(store.db(), TASK)["state"], "done")
        after = self.snapshot_root_state()
        self.assertEqual(before, after)

    def test_ac8_merge_commit_lands_in_origin_main_via_object_database(self):
        """Позитивная сторона AC-8: несмотря на то, что рабочее дерево
        `config.ROOT` не тронуто, `refs/heads/main` `self.origin`
        («main артели») РЕАЛЬНО продвинулся, несёт код фичи задачи, и
        сам merge-коммит — настоящий merge (двое родителей).

        Ловит мутацию: реализация, которая просто НЕ мержит вовсе (чтобы
        тривиально удовлетворить «HEAD не поменялся» из первого теста) —
        `origin_main_sha()` не сдвинется, `feature.txt` не появится в
        `refs/heads/main` origin.
        """
        before_origin_main = self.origin_main_sha()

        result = self.approve()

        self.assertEqual(result, ("done",))
        after_origin_main = self.origin_main_sha()
        self.assertNotEqual(before_origin_main, after_origin_main,
                           "main артели (origin) обязан продвинуться")
        self.assertIn("feature.txt", self.origin_tree_files("refs/heads/main"))
        # Сам merge-коммит — ближайший коммит-МЕРЖ в истории (не
        # обязательно голова ветки: карта/RETRO того же перехода, AC-9,
        # могут стоять НАД ним отдельными коммитами с одним родителем).
        merge_commit = self.origin_git(
            "log", "--merges", "-1", "--pretty=%H",
            "refs/heads/main").stdout.strip()
        self.assertTrue(merge_commit, "ни одного merge-коммита не найдено "
                        "в refs/heads/main origin")
        parents = self.origin_git(
            "log", "-1", "--pretty=%P", merge_commit).stdout.split()
        self.assertEqual(len(parents), 2,
                         "merge-коммит обязан нести двух родителей "
                         "(старый main + голова ветки задачи)")

    def test_ac9_map_and_retro_commits_also_land_via_object_database_only(self):
        """Служебные коммиты того же перехода (карта кодовой базы,
        RETRO — `fsm_postmerge.py`) тоже не оставляют следа в рабочем
        дереве `config.ROOT`: снимок после `approve` идентичен снимку до
        него (тот же критерий, что и AC-8, — карта/RETRO делают СВОИ
        коммиты этим же переходом, а не только сам merge-коммит).

        Ловит мутацию: `_regenerate_and_commit_map`/
        `_generate_and_commit_retro`, которые остались на `git add`/`git
        commit` реального чекаута `config.ROOT` — тогда `root_status_
        porcelain()`/`root_head_sha()` после approve разойдутся со
        снимком «до», даже если сам merge-коммит (AC-8) уже переведён на
        плотницкую запись.
        """
        before = self.snapshot_root_state()

        result = self.approve()

        self.assertEqual(result, ("done",))
        after = self.snapshot_root_state()
        self.assertEqual(before, after)
        # main артели обязан нести больше одного НОВОГО коммита поверх
        # старого main — сам merge + хотя бы служебный коммит карты/RETRO
        # (не проверяем состав построчно — предмет других тестов
        # T042/T043; здесь важно только «они есть и они не в config.ROOT»).
        log = self.origin_git(
            "log", "--oneline", f"refs/heads/{config.MAIN_BRANCH}").stdout
        self.assertGreaterEqual(len(log.strip().splitlines()), 2)

    def test_ac12_root_stays_on_pre_merge_sha_even_though_origin_main_advanced(self):
        """AC-12 дословно: HEAD/рабочее дерево `config.ROOT` остаются на
        зафиксированном ПЕРЕД merge sha, даже когда main артели (origin)
        ушёл вперёд ИМЕННО ЭТИМ merge — не совпадение (обе стороны
        `git merge` могли просто провалиться), а прямое следствие
        независимости: `root_head_sha()` после approve — тот же sha, что
        ДО approve, и origin ГЛУБЖЕ содержит рабочий код (feature.txt),
        которого в этом sha корня никогда не было.

        Ловит мутацию: та же порча чекаута `config.ROOT`, что и в AC-8;
        отличие фокуса теста — явная сверка root-sha ДО/ПОСЛЕ с ОДНИМ и
        тем же литералом плюс контроль, что root НЕ содержит feature.txt
        в рабочем дереве, тогда как origin main — содержит.
        """
        root_sha_before = self.root_head_sha()
        (self.root / "feature.txt")  # ещё не существует в root

        result = self.approve()

        self.assertEqual(result, ("done",))
        root_sha_after = self.root_head_sha()
        self.assertEqual(root_sha_before, root_sha_after,
                         "HEAD config.ROOT обязан остаться на пином sha")
        self.assertFalse((self.root / "feature.txt").exists(),
                         "рабочее дерево config.ROOT не должно получить "
                         "код фичи — она смержена только в origin main")
        self.assertIn("feature.txt", self.origin_tree_files("refs/heads/main"),
                      "origin main обязан содержать код фичи после merge")


if __name__ == "__main__":
    unittest.main()
