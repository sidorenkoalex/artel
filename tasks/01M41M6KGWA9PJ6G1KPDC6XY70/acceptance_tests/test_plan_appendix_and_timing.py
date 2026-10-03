"""PLAN задачи: применимое приложение, перечень читателей `ci.yml`, замер времени заданий (AC-5, AC-6).

Группа: разовый

Красен до реализации: в ссылке документов задачи ещё нет PLAN.md — чтение PLAN из ссылки отказывает.

Группа «разовый»: предмет — PLAN.md этой задачи и его приложения; после
мержа проверять не на чем.

PLAN.md читается из ссылки документов `refs/artifacts/<id>`
(`gitcmd.show(artifact_branch.branch_name(TASK_ID), …)`), не с диска;
приложения разбирает тот же узел, что гейт приложений PLAN
(`guard.plan_appendices`). Прозу PLAN тесты читают без блоков ```diff —
строка хунка не подтверждает ни перечень, ни замер.
"""
import re
import unittest

from _plank import (CI_REL, INV_REL, PYTHON_JOB, appendices_or_fail,
                    applied_tree, clean_tree, git, jobs, min_jobs, own_field,
                    plan_or_fail)

CODE_PATH = r"(?:tests|orchestrator|scripts)/[\w/.-]+\.py"
NONE_WORDS = r"(?:нет|не найден|отсутству|ни один|ни одного|никто)"
DURATION = (r"(?<![\w.,])\d+(?:[.,]\d+)?\s*(?:с|сек\w*|s|мин\w*|min|m)(?!\w)"
            r"|(?<![\w:])\d{1,2}:\d{2}(?![\w:])")


def prose(plan_text: str) -> list[str]:
    """Строки PLAN вне огороженных блоков кода."""
    out, fenced = [], False
    for ln in plan_text.splitlines():
        if ln.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            out.append(ln)
    return out


def mentions(line: str, job_id: str, job_name: str | None) -> bool:
    if re.search(rf"(?<![\w-]){re.escape(job_id)}(?![\w-])", line):
        return True
    return bool(job_name) and job_name in line


class PlanAppendixAndTimingTest(unittest.TestCase):

    def test_ac5_appendix_applies_and_ci_readers_listed(self):
        """Приложение PLAN к `ci.yml` и `tests/test_invariants.py` проходит `git apply --check` на чистом дереве ветки; PLAN называет читателей `ci.yml`.

        Сценарий: приложения PLAN разбираются без ошибок и вместе
        покрывают оба файла; на копии чистого дерева HEAD ветки каждое по
        порядку проходит `git apply --check` и ложится `git apply` (порядок
        мержа). В прозе PLAN (вне блоков ```diff) есть строка, называющая
        `ci.yml` вместе с путём кода `tests/…py`/`orchestrator/…py`/
        `scripts/…py` либо с явным «таких нет».

        Ловит мутацию: хунк приложения с диапазоном, не совпадающим с
        текущим текстом файла (`git apply --check` отказывает); правка
        `tests/test_invariants.py` внесена в ветку напрямую, а не
        приложением (приложения к нему нет); PLAN молчит о тестах и коде,
        читающих структуру `ci.yml`.
        """
        appendices = appendices_or_fail(self)
        covered = {p for a in appendices for p in a.paths}
        for rel in (CI_REL, INV_REL):
            self.assertIn(rel, covered, f"в PLAN нет приложения к {rel}")

        tree = clean_tree("artel-ci-min-check-")
        for appendix in appendices:
            for args in (["--check"], []):
                res = git("apply", *args, "-", cwd=tree, input=appendix.diff)
                self.assertEqual(
                    res.returncode, 0,
                    f"git apply {' '.join(args)} приложения {appendix.paths}: "
                    f"{(res.stderr or res.stdout).strip()[:500]}")

        lines = [ln for ln in prose(plan_or_fail(self)) if "ci.yml" in ln]
        listed = [ln for ln in lines
                  if re.search(CODE_PATH, ln) or re.search(NONE_WORDS, ln,
                                                           re.IGNORECASE)]
        self.assertTrue(listed, "PLAN не перечисляет тесты/код, читающие "
                                "структуру ci.yml, и не фиксирует, что их нет")

    def test_ac6_plan_has_job_timings_before_after(self):
        """PLAN несёт длительности задания `python` до и после и длительность нового задания.

        Сценарий: имя нового задания (ключ и его `name:`) берётся из
        `ci.yml` дерева с наложенным приложением. В прозе PLAN строки,
        называющие задание `python` (ключ или `name:`) и не называющие
        новое, несут вместе не меньше двух длительностей (до и после);
        строки, называющие новое задание, — хотя бы одну.

        Ловит мутацию: PLAN даёт одну цифру «после» без «до»; PLAN
        называет только `python`, без длительности нового задания; оценка
        дана прозой («стало быстрее») без чисел.
        """
        text = (applied_tree(self) / CI_REL).read_text(encoding="utf-8")
        all_jobs = jobs(text)
        news = list(min_jobs(text).items())
        self.assertTrue(news, "в ci.yml нет задания вне python со stack_ci.py --min")
        new_id, new_block = news[0]
        new_name = (own_field(new_block, "name") or [None])[0]
        py_name = (own_field(all_jobs[PYTHON_JOB], "name") or [None])[0]

        body = prose(plan_or_fail(self))
        py_durations = [d for ln in body
                        if mentions(ln, PYTHON_JOB, py_name)
                        and not mentions(ln, new_id, new_name)
                        for d in re.findall(DURATION, ln)]
        new_durations = [d for ln in body if mentions(ln, new_id, new_name)
                         for d in re.findall(DURATION, ln)]
        self.assertGreaterEqual(
            len(py_durations), 2,
            f"PLAN: у задания python нет длительностей до и после "
            f"(нашли {py_durations})")
        self.assertGreaterEqual(
            len(new_durations), 1,
            f"PLAN: нет длительности нового задания {new_id} "
            f"({new_name!r})")


if __name__ == "__main__":
    unittest.main()
