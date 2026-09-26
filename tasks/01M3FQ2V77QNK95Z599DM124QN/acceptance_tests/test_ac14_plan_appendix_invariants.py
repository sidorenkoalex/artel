"""AC-14 (tasks/01M3FQ2V77QNK95Z599DM124QN/SPEC.md): приложение к PLAN по
защищённым путям — строка 38 первой таблицы `docs/invariants.md`,
обновление перечня рубежей перехода in_dev -> verifying и запись о тесте
инварианта; патч приложения проходит `git apply --check`, и это в PLAN
подтверждено.

PLAN.md читается ТОЛЬКО из артефактной ветки (`gitcmd.show` +
`artifact_branch.branch_name`): в среде прогона планки пультом на диске
лежит один `acceptance_tests/` (`skills/test-authoring.md`, «Источник
артефактов задачи — только артефактная ветка»).

Красен до реализации: PLAN.md задачи ещё не существует — его создаёт роль
developer, приложение к PLAN пишет она же; все три теста падают на
пустом источнике.

Валидация стабом прошла не через артефактную ветку (писать в неё вправе
только автокоммит оркестратора, не роль), а подменой `gitcmd.show` на
синтетический PLAN с НАСТОЯЩИМ диффом `docs/invariants.md`, снятым
`git diff` с реальной правки файла: `git apply --check` в тесте
исполнялся по-настоящему, на чистом дереве базы интеграции.
"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import REPO_ROOT  # noqa: E402
from orchestrator import artifact_branch, gitcmd  # noqa: E402

TASK_ID = "01M3FQ2V77QNK95Z599DM124QN"

# Фенсированные ```diff-блоки приложения — по одному на защищённый путь.
_DIFF_BLOCK_RE = re.compile(r"```diff\n(diff --git .*?)\n```", re.DOTALL)


def _plan_text() -> str | None:
    text, _reason = gitcmd.show(artifact_branch.branch_name(TASK_ID),
                                f"tasks/{TASK_ID}/PLAN.md")
    return text or None


def _merge_base() -> str:
    res = subprocess.run(["git", "merge-base", "origin/main", "HEAD"],
                         cwd=REPO_ROOT, capture_output=True, text=True)
    if res.returncode != 0:
        res = subprocess.run(["git", "merge-base", "main", "HEAD"],
                             cwd=REPO_ROOT, capture_output=True, text=True,
                             check=True)
    return res.stdout.strip()


class PlanAppendixInvariantsTest(unittest.TestCase):

    def setUp(self):
        self.plan = _plan_text()
        self.assertIsNotNone(
            self.plan,
            f"tasks/{TASK_ID}/PLAN.md не найден в артефактной ветке — "
            f"приложение AC-14 оформляет роль developer")
        self.diffs = [m.group(1) + "\n" for m in _DIFF_BLOCK_RE.finditer(self.plan)]

    def test_ac14_plan_attaches_invariants_row_and_gate_count_update(self):
        """Приложение к PLAN трогает `docs/invariants.md`, заводит в первой
        таблице строку с номером 38 об этом инварианте (с адресом теста и
        ссылкой на этот SPEC) и обновляет перечень рубежей перехода
        in_dev -> verifying; инвариант закреплён либо записью в
        `tests/test_invariants.py`, либо строкой второй таблицы
        `docs/invariants.md`.

        Ловит мутацию: приложение вносит только строку таблицы, а
        перечень рубежей («Восемь рубежей», строка 67) остаётся прежним —
        docs/invariants.md начинает противоречить сам себе, называя
        восемь рубежей там, где их девять, и следующая задача,
        сверяющаяся с этим перечнем, унаследует ложное число.
        """
        self.assertTrue(
            self.diffs,
            "PLAN.md не несёт ни одного фенсированного ```diff-блока "
            "приложения (AC-14)")
        appendix = "\n".join(self.diffs)

        self.assertIn(
            "docs/invariants.md", appendix,
            "приложение обязано править docs/invariants.md (AC-14)")
        invariants_diff = "\n".join(
            d for d in self.diffs if "docs/invariants.md" in d)
        added = "\n".join(line for line in invariants_diff.splitlines()
                          if line.startswith("+"))
        self.assertRegex(
            added, r"(?m)^\+\s*\|?\s*38\b",
            f"первая таблица docs/invariants.md обязана получить строку с "
            f"номером 38 (AC-14); добавленные строки:\n{added}")
        self.assertIn(
            TASK_ID, added,
            "строка инварианта обязана ссылаться на этот SPEC (AC-14)")
        self.assertRegex(
            added, r"рубеж|рубежей",
            f"перечень рубежей перехода in_dev -> verifying обязан "
            f"обновиться тем же приложением (AC-14); добавленные строки:\n"
            f"{added}")
        self.assertTrue(
            "tests/test_invariants.py" in appendix
            or "тестом не выражаются" in added,
            "инвариант обязан быть закреплён записью в "
            "tests/test_invariants.py либо строкой второй таблицы "
            "docs/invariants.md (AC-14)")

    def test_ac14_attached_patches_apply_to_a_clean_tree(self):
        """Каждый ```diff-блок приложения накладывается `git apply --check`
        на чистое дерево базы интеграции (либо уже применён — тогда
        накладывается обратной стороной).

        Ловит мутацию: хедер хунка (`@@ -67,7 +67,7 @@`) не совпадает с
        реальным диапазоном файла — ровно тот дефект, который дважды
        подряд проходил глазомер автора (T046, T047 итерация 1):
        `git apply --check` отвечает ненулевым кодом, и тест краснеет
        вместо тихого «приложение оформлено».
        """
        self.assertTrue(self.diffs, "приложения к PLAN нет вовсе (AC-14)")
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(
                ["git", "worktree", "add", "--detach", "--quiet", tmp,
                 _merge_base()],
                cwd=REPO_ROOT, check=True, capture_output=True, text=True)
            try:
                for diff_text in self.diffs:
                    direct = subprocess.run(
                        ["git", "apply", "--check", "-"], cwd=tmp,
                        input=diff_text, capture_output=True, text=True)
                    if direct.returncode == 0:
                        continue
                    reverse = subprocess.run(
                        ["git", "apply", "--check", "--reverse", "-"], cwd=tmp,
                        input=diff_text, capture_output=True, text=True)
                    self.assertEqual(
                        0, reverse.returncode,
                        f"дифф приложения не накладывается ни прямо, ни "
                        f"обратно:\n{direct.stderr}\n{reverse.stderr}\n"
                        f"--- дифф ---\n{diff_text}")
            finally:
                subprocess.run(
                    ["git", "worktree", "remove", "--force", tmp],
                    cwd=REPO_ROOT, check=True, capture_output=True, text=True)

    def test_ac14_plan_confirms_the_check_was_run(self):
        """PLAN.md словами подтверждает, что `git apply --check` на чистом
        дереве прогонялся (требование 9, последняя фраза).

        Ловит мутацию: приложение сдано без прогона проверки, а строка
        подтверждения не написана — `skills/conventions-core.md` требует
        именно подтверждения в PLAN, а не только применимого диффа
        (класс, за который уже заплачено дважды: T046 и T047 итерация 1).
        """
        self.assertIn(
            "git apply --check", self.plan,
            "PLAN.md обязан подтвердить прогон `git apply --check` на "
            "чистом дереве (AC-14, требование 9)")


if __name__ == "__main__":
    unittest.main()
