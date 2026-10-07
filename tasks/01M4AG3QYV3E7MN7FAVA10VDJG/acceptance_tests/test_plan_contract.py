"""Приложение к правилу автора тестов и замер в PLAN.

Группа: разовый
Красен до реализации: PLAN.md и его приложение ещё не созданы.
"""

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, artifact_text  # noqa: E402


class PlanContractTest(unittest.TestCase):
    def plan(self):
        plan = artifact_text("PLAN.md")
        self.assertIsNotNone(plan, "PLAN.md отсутствует в ссылке документов")
        return plan

    def patched_rule(self):
        """Применяет приложение к файлу из main во временном каталоге."""
        plan = self.plan()
        patches = re.findall(r"```diff\s*\n(.*?)\n```", plan, re.DOTALL)
        if not patches:
            names = re.findall(r"[\w.-]+\.(?:patch|diff)", plan)
            patches = [artifact_text(name) for name in names]
        patches = [patch for patch in patches if patch and
                   "skills/test-authoring.md" in patch]
        self.assertTrue(patches, "нет приложения к skills/test-authoring.md")
        self.assertEqual(len(patches), 1, "приложение должно быть однозначным")
        base = subprocess.run(
            ["git", "show", "main:skills/test-authoring.md"],
            cwd=CODE_ROOT, capture_output=True, text=True, check=True).stdout
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "skills" / "test-authoring.md"
            target.parent.mkdir(parents=True)
            target.write_text(base, encoding="utf-8")
            patch = patches[0].rstrip() + "\n"
            check = subprocess.run(["git", "apply", "--check", "-"],
                                   input=patch, cwd=tmp, capture_output=True,
                                   text=True)
            self.assertEqual(check.returncode, 0,
                             f"git apply --check к main: {check.stderr}")
            subprocess.run(["git", "apply", "-"], input=patch, cwd=tmp,
                           capture_output=True, text=True, check=True)
            added = "\n".join(
                line[1:] for line in patch.splitlines()
                if line.startswith("+") and not line.startswith("+++"))
            self.assertTrue(added.strip(), "приложение не добавляет правила")
            self.assertNotEqual(target.read_text(encoding="utf-8"), base)
            return added

    def test_ac1_pure_properties_and_git_sandbox_rule(self):
        """Приложение к main направляет чистые свойства в модульный тест, а связку git/FSM в песочницу.

        Ловит мутацию: автор правила опускает ограничение на песочницу,
        и текст после применения не различает два вида свойств.
        """
        rule = self.patched_rule().lower()
        self.assertRegex(rule, r"чист\w*|разбор|формат текст|таблиц\w* решен")
        self.assertIn("модульн", rule)
        self.assertIn("tmproottest", rule)
        self.assertIn("realgitsandbox", rule)
        for part in ("команд", "fsm", "баз", "git", "докстринг"):
            self.assertIn(part, rule)

    def test_ac2_finite_variants_share_one_subtest(self):
        """Приложенное правило собирает короткий перечень вариантов в одном тесте.

        Ловит мутацию: требование subTest исчезает — правило допускает
        отдельный метод на каждый вариант перечня.
        """
        rule = self.patched_rule().lower()
        self.assertIn("subtest", rule)
        self.assertRegex(rule, r"коротк\w*|конечн\w*")
        self.assertRegex(rule, r"один тест|одном тесте|одн\w* метод")
        self.assertRegex(rule, r"не\s+(?:отдельн\w*|метод\w* на вариант)|вместо отдельн")

    def test_ac3_clock_is_replaced_and_timeout_is_only_guard(self):
        """Приложение запрещает ожидание события по часам и оставляет таймаут страховкой.

        Ловит мутацию: sleep снова разрешён как условие проверки —
        правило больше не требует подмены времени и пауз.
        """
        rule = self.patched_rule().lower()
        self.assertIn("sleep", rule)
        self.assertRegex(rule, r"подмен\w*|замен\w*")
        self.assertRegex(rule, r"врем\w*|час\w*")
        self.assertRegex(rule, r"пауз\w*")
        self.assertRegex(rule, r"страховк\w*|зависани\w*")
        self.assertRegex(rule, r"не услови\w* проверк\w*")

    def test_ac11_top_twenty_file_times_descend(self):
        """PLAN приводит не менее двадцати файлов main со временем в порядке убывания.

        Ловит мутацию: замер заменён общим временем набора либо строки
        переставлены — список не даёт основания для порога файла.
        """
        plan = self.plan()
        self.assertIn("LONG_LIVED_FILE_WARN_SEC", plan)
        self.assertRegex(plan.lower(), r"main")
        entries = re.findall(
            r"(?m)^.*?(tests/test_[a-z0-9_]+\.py)\s*(?:[|—–:-]|\s)\s*"
            r"(\d+(?:[,.]\d+)?)(?:\s*(?:с|сек|s|seconds))?.*$", plan)
        self.assertGreaterEqual(len(entries), 20, entries)
        times = [float(value.replace(",", ".")) for _, value in entries[:20]]
        self.assertEqual(times, sorted(times, reverse=True), entries[:20])


if __name__ == "__main__":
    unittest.main()
