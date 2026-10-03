"""AC-4, AC-5 — 01M41JYGHTP8ZVXVPEF8K8W381: приложение PLAN к ci.yml
применимо, читатели структуры ci.yml названы и не сломаны, время задания
`python` до и после — в PLAN.

Группа: разовый

PLAN.md читается с артефактной ветки задачи (`_appendix.state`); «что PLAN
говорит своими словами» — его текст без блоков ```diff (`plan_prose`).

Красен до реализации: PLAN.md ещё не написан (его пишет developer) — нет ни приложения к ci.yml, ни подтверждения `git apply --check`, ни замеров.
"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _appendix as ap  # noqa: E402

DURATION_RE = re.compile(r"\d+(?:[.,]\d+)?\s*(?:с|сек|s|мин|min|m)\b",
                         re.I)


class PlanCiAppendixTest(unittest.TestCase):

    def setUp(self):
        self.state = ap.state()
        self.diag = self.state.diagnosis()
        self.assertIsNotNone(self.state.plan, self.diag)

    def test_ac4_ci_appendix_applies_and_plan_confirms_check(self):
        """Приложение к ci.yml проходит `git apply --check` на дереве базы; PLAN это подтверждает.

        Сценарий: файлы базы сравнения ветки кладутся во временный каталог,
        приложения PLAN, предшествующие приложению к ci.yml, применяются
        подряд (тем же вызовом, что у гейта), затем приложение к ci.yml
        проверяется `git apply --check`; текст PLAN вне блоков диффа
        содержит `git apply --check`.

        Ловит мутацию: хунк приложения к ci.yml написан руками с неверным
        диапазоном строк (`@@ -232,14 +232,4 @@` при реальных 13 строках)
        — `git apply --check` отвечает отказом, тест краснеет; либо PLAN
        не упоминает прогон проверки — красный по второму утверждению.
        """
        ci = ap.appendices_for(ap.CI_YML)
        self.assertTrue(ci, f"в PLAN.md нет приложения к {ap.CI_YML}; "
                            f"{self.diag}")
        self.assertTrue(self.state.base_sha, self.diag)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for appendix in self.state.appendices:
                for rel in appendix.paths:
                    text = ap.gitcmd.show(self.state.base_sha, rel)[0]
                    dest = root / rel
                    if text is not None and not dest.exists():
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_text(text, encoding="utf-8")
            for appendix in self.state.appendices:
                if appendix in ci:
                    patch = root.parent / f"{root.name}-ci.diff"
                    patch.write_text(appendix.diff, encoding="utf-8")
                    try:
                        res = subprocess.run(
                            ["git", "apply", "--check", str(patch)],
                            cwd=root, capture_output=True, text=True)
                    finally:
                        patch.unlink()
                    self.assertEqual(0, res.returncode,
                                     f"git apply --check: {res.stderr}")
                answer = ap.plan_appendix.git_apply(root, appendix)
                self.assertEqual("", answer,
                                 f"{appendix.paths}: {answer}; {self.diag}")
        self.assertIn("git apply --check", ap.plan_prose(),
                      "PLAN не подтверждает прогон `git apply --check`")

    def test_ac4_ci_yml_readers_listed_in_plan_and_pass(self):
        """Читатели содержимого ci.yml названы в PLAN и зелёные на ci.yml после приложения.

        Сценарий: во временной копии дерева кода ветки с наложенными
        приложениями находятся модули `orchestrator/`, `scripts/`, `tests/`,
        читающие файл `ci.yml` (литерал пути в вызове чтения или в имени,
        которое такой вызов читает); каждый назван путём в тексте PLAN вне
        блоков диффа, а модули `tests/` из них проходят pytest в этой
        копии (`tests/test_invariants.py` — общим с AC-6 прогоном).

        Ловит мутацию: новое задание названо так, что сторож CI в
        `tests/test_invariants.py` (разбор заданий `python`/`guard`) больше
        не находит нужного блока, или задание `python` переименовано — его
        прогон в копии с приложением краснеет; либо PLAN не перечисляет
        читателей ci.yml — красный по первому утверждению.
        """
        self.assertTrue(ap.appendices_for(ap.CI_YML), self.diag)
        with ap.scratch_tree() as (tmp, failures):
            self.assertEqual([], failures, self.diag)
            readers = ap.ci_yml_readers(tmp)
            others = [r for r in readers
                      if r.startswith("tests/") and r != ap.INVARIANTS]
            res = ap.run_pytest(tmp, others) if others else None
        self.assertTrue(readers, "читателей ci.yml не найдено — разбор "
                                 "планки сломан (сегодня их читает "
                                 "tests/test_invariants.py)")
        prose = ap.plan_prose()
        missing = [r for r in readers if r not in prose]
        self.assertEqual([], missing,
                         "PLAN не называет читателей структуры ci.yml")
        if res is not None:
            self.assertEqual(0, res.returncode,
                             f"{others}:\n{(res.stdout + res.stderr)[-3000:]}")
        if ap.INVARIANTS in readers:
            code, out, fails = ap.invariants_run_applied()
            self.assertEqual((), fails, self.diag)
            self.assertEqual(0, code, out)

    def test_ac5_plan_has_python_job_time_before_and_after(self):
        """PLAN даёт время задания `python` до и после с именами заданий и длительностями.

        Сценарий: текст PLAN вне блоков диффа называет задание `python`
        (идентификатором или его `name:`) и задание минимальной версии из
        ci.yml после приложения (идентификатором или `name:`), содержит
        слова «до» и «после» и не меньше двух длительностей
        (`314 с`, `3 мин`, `110s`) — `python` до и `python` после.

        Ловит мутацию: PLAN даёт только оценку «станет быстрее» без
        замеров ветки или называет одно задание — тест краснеет на
        отсутствии имени нового задания или длительностей.
        """
        text = ap.applied_text(ap.CI_YML)
        job = ap.min_job(text)
        self.assertIsNotNone(job, f"нового задания нет; {self.diag}")
        prose = ap.plan_prose()
        low = prose.lower()

        def named(job_id):
            title = ap.own_scalar(ap.job_block(text, job_id), "name") or ""
            return (re.search(rf"(?<![\w-]){re.escape(job_id)}(?![\w-])",
                              prose) is not None
                    or (title and title.strip("'\"") in prose))

        self.assertTrue(named("python"), "PLAN не называет задание python")
        self.assertTrue(named(job), f"PLAN не называет задание {job}")
        self.assertRegex(low, r"(?<!\w)до(?!\w)", "в PLAN нет «до»")
        self.assertIn("после", low, "в PLAN нет «после»")
        self.assertGreaterEqual(len(DURATION_RE.findall(prose)), 2,
                                "в PLAN меньше двух длительностей заданий")


if __name__ == "__main__":
    unittest.main()
