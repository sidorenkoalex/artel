"""AC-1, AC-2, AC-3 — 01M41JYGHTP8ZVXVPEF8K8W381: проверка на минимальной
версии Python — отдельное задание CI, параллельное заданию `python`.

Группа: разовый

Предмет — `.github/workflows/ci.yml` ПОСЛЕ применения приложения PLAN.md
(путь защищён, в ветку задачи правка не коммитится): после мержа приложение
уже в main и проверять его как приложение не на чем. Разбор `ci.yml` — по
отступам (`_appendix.py`), без YAML-библиотеки.

Красен до реализации: PLAN.md с приложением к ci.yml ещё не написан (его пишет developer) — без приложения шаги минимальной версии остаются в задании `python`, отдельного задания нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _appendix as ap  # noqa: E402


def _applied_ci() -> str:
    return ap.applied_text(ap.CI_YML)


class CiMinPythonJobTest(unittest.TestCase):

    def setUp(self):
        self.state = ap.state()
        self.diag = self.state.diagnosis()
        self.assertTrue(ap.appendices_for(ap.CI_YML),
                        f"в PLAN.md нет приложения к {ap.CI_YML}; {self.diag}")
        self.assertEqual((), self.state.apply_failures, self.diag)
        self.text = _applied_ci()
        self.job = ap.min_job(self.text)
        self.assertIsNotNone(
            self.job, f"в ci.yml после приложения нет задания (кроме "
                      f"`python`) с шагом `{ap.MIN_MARK}`; {self.diag}")
        self.block = ap.job_block(self.text, self.job)
        self.python = ap.job_block(self.text, "python")
        self.assertTrue(self.python, f"задание `python` пропало; {self.diag}")

    def test_ac1_min_python_steps_live_in_own_job_with_same_trigger(self):
        """Шаги минимальной версии — в отдельном задании с `needs: changes` и условием `python`.

        Сценарий: к ci.yml базы сравнения применяется приложение PLAN; в
        задании, несущем `scripts/stack_ci.py --min`, по порядку есть
        определение версии (шаг с `id`), `setup-python` с версией из
        выхода этого шага, установка `requirements.lock` и прогон
        `tests/test_invariants.py`; у задания `python` ни одного из этих
        шагов нет; `needs` нового задания содержит `changes` и не содержит
        `python`; собственное `if:` нового задания совпадает с `if:`
        задания `python`.

        Ловит мутацию: новое задание объявлено с `needs: [changes, python]`
        (идёт после полного прогона, а не параллельно) — `needs` содержит
        `python`, тест краснеет; либо скопировано без `if:` — условия
        расходятся; либо шаги скопированы, а из `python` не убраны — у
        `python` остаётся `stack_ci.py --min`.
        """
        steps = ap.steps(self.block)
        idx_min = next((i for i, s in enumerate(steps)
                        if ap.MIN_MARK in s.text), None)
        min_id = steps[idx_min].scalar("id") if idx_min is not None else None
        self.assertTrue(min_id, f"шаг `{ap.MIN_MARK}` без `id:` — версию "
                                f"нечем передать setup-python; {self.diag}")
        idx_setup = next(
            (i for i, s in enumerate(steps)
             if (s.scalar("uses") or "").startswith("actions/setup-python")
             and any(f"steps.{min_id}.outputs.version" in w
                     for w in s.with_items())), None)
        idx_pip = next((i for i, s in enumerate(steps)
                        if any("pip install -r requirements.lock" in c
                               for c in s.run_commands())), None)
        idx_pytest = next(
            (i for i, s in enumerate(steps)
             if any("pytest" in c and "tests/test_invariants.py" in c
                    for c in s.run_commands())), None)
        order = [idx_min, idx_setup, idx_pip, idx_pytest]
        self.assertNotIn(None, order,
                         f"в задании {self.job} нет одного из шагов "
                         f"[--min, setup-python min, pip lock, pytest "
                         f"test_invariants]: {order}; {self.diag}")
        self.assertEqual(sorted(order), order,
                         f"шаги задания {self.job} не в порядке "
                         f"--min → setup-python → pip → pytest: {order}")
        idx_pip_after = [i for i, s in enumerate(steps)
                         if i > idx_setup and any(
                             "pip install -r requirements.lock" in c
                             for c in s.run_commands())]
        self.assertTrue(idx_pip_after and idx_pip_after[0] < idx_pytest,
                        f"установки requirements.lock между setup-python "
                        f"минимальной версии и pytest в {self.job} нет")

        python_text = "\n".join(self.python)
        self.assertNotIn(ap.MIN_MARK, python_text,
                         "задание `python` всё ещё определяет минимальную "
                         "версию Python")
        self.assertEqual([], ap.invariants_pytest_steps(self.python),
                         "задание `python` всё ещё гоняет отдельный шаг "
                         "pytest tests/test_invariants.py")

        job_needs = ap.needs(self.block)
        self.assertIn("changes", job_needs, f"needs задания {self.job}: "
                                            f"{job_needs}")
        self.assertNotIn("python", job_needs, f"задание {self.job} ждёт "
                                              f"`python` — не параллельно")
        py_if = ap.own_scalar(self.python, "if")
        self.assertIsNotNone(py_if, "у задания `python` пропало `if:`")
        self.assertEqual(py_if, ap.own_scalar(self.block, "if"),
                         f"`if:` задания {self.job} не совпадает с `if:` "
                         f"задания `python`")

    def test_ac2_invariants_run_parallel_or_named_instability(self):
        """`tests/test_invariants.py` в новом задании — с `-n auto -p xdist -o timeout=120`.

        Сценарий: в задании минимальной версии ищется шаг pytest по
        `tests/test_invariants.py`; его команда несёт `-n auto`, `-p xdist`
        и `-o timeout=120`. Допустимая ветка критерия: команды без
        `-n auto` — тогда в ней есть `-o timeout=120`, а PLAN своими
        словами (вне блоков диффа) называет нестабильность параллельного
        прогона.

        Ловит мутацию: шаг перенесён в новое задание как есть (`pytest
        tests/test_invariants.py -p timeout -o timeout=120` без `-n auto`),
        а нестабильность в PLAN не названа — тест краснеет; либо `-n auto`
        добавлен без `-p xdist` — тоже красный.
        """
        inv = ap.invariants_pytest_steps(self.block)
        self.assertTrue(inv, f"в задании {self.job} нет pytest по "
                             f"tests/test_invariants.py")
        cmd = " ".join(c for c in inv[0].run_commands() if "pytest" in c)
        self.assertIn("-o timeout=120", cmd, cmd)
        if "-n auto" in cmd:
            self.assertIn("-p xdist", cmd, cmd)
        else:
            self.assertIn("нестабил", ap.plan_prose().lower(),
                          f"прогон без -n auto ({cmd}), а PLAN не называет "
                          f"нестабильность параллельного прогона")

    def test_ac3_python_job_keeps_other_steps_and_nothing_optional(self):
        """Прочие шаги `python` сохраняют команды; необязательных шагов нет.

        Сценарий: из задания `python` ci.yml БАЗЫ берутся шаги до первого
        шага `stack_ci.py --min`, их команды (`uses`, `with`, `run` без
        комментариев) — в том же порядке обязаны найтись среди шагов
        задания `python` после приложения; ни задание `python`, ни новое
        задание, ни их шаги не несут `continue-on-error`, шаги не несут
        собственного `if:`, а команды pytest — `|| true`/`|| exit 0`.

        Ловит мутацию: при переносе задета соседняя строка — из полного
        прогона выпал `-o timeout=120` или пропал шаг сверки ссылок после
        прогона — команды базы не находятся по порядку, тест краснеет; либо
        новому заданию дан `continue-on-error: true` («пусть не красит, пока
        обкатываем») — красный.
        """
        base = ap.base_text(ap.CI_YML)
        self.assertTrue(base, f"ci.yml базы не прочитан; {self.diag}")
        base_steps = ap.steps(ap.job_block(base, "python"))
        cut = next((i for i, s in enumerate(base_steps)
                    if ap.MIN_MARK in s.text), len(base_steps))
        wanted = [s.signature() for s in base_steps[:cut]]
        self.assertTrue(wanted, "в задании `python` базы нет шагов")
        got = [s.signature() for s in ap.steps(self.python)]
        pos = 0
        for sig in got:
            if pos < len(wanted) and sig == wanted[pos]:
                pos += 1
        self.assertEqual(
            len(wanted), pos,
            f"команда шага `python` базы не найдена по порядку после "
            f"приложения: {wanted[pos] if pos < len(wanted) else None}")

        for name, block in (("python", self.python), (self.job, self.block)):
            text = "\n".join(block)
            self.assertNotIn("continue-on-error", text,
                             f"задание {name} несёт continue-on-error")
            for step in ap.steps(block):
                self.assertIsNone(step.scalar("if"),
                                  f"шаг задания {name} условный: "
                                  f"{step.text[:200]}")
                for cmd in step.run_commands():
                    if "pytest" in cmd:
                        self.assertNotRegex(
                            cmd, r"\|\|\s*(true|exit 0|:)",
                            f"pytest задания {name} не красит: {cmd}")


if __name__ == "__main__":
    unittest.main()
