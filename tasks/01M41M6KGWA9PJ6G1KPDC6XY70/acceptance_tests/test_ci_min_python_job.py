"""Проверка на минимальной версии Python — отдельным параллельным заданием CI (AC-1…AC-4).

Группа: разовый

Красен до реализации: в ссылке документов задачи ещё нет PLAN.md с приложением к `.github/workflows/ci.yml` — чтение PLAN/наложение приложения отказывает.

Группа «разовый»: предмет — `ci.yml` в дереве ветки с наложенным
приложением PLAN этой задачи (SPEC, преамбула «Критериев приёмки»); после
мержа приложения в PLAN проверять не на чем.

Дерево строит `_plank.applied_tree`: копия HEAD ветки (`git archive`), на
которую подряд ложатся все приложения PLAN, прочитанного из ссылки
документов `refs/artifacts/<id>` (не с диска). `ci.yml` разбирается по
блокам отступов (`_plank.jobs`), как в
`tests/test_invariants.py::CiWorkflowKeepsARunForEveryPushTest`.
"""
import re
import unittest

from _plank import (CI_REL, PYTHON_JOB, applied_tree, jobs, min_jobs,
                    own_field, pytest_lines, step_index, steps)

PYTHON_IF = "!cancelled() && needs.changes.outputs.code != 'false'"
INVARIANTS_PYTEST = r"\bpytest\b.*tests/test_invariants\.py"


class CiMinPythonJobTest(unittest.TestCase):

    def setUp(self):
        self.text = (applied_tree(self) / CI_REL).read_text(encoding="utf-8")
        self.jobs = jobs(self.text)
        self.assertIn(PYTHON_JOB, self.jobs, "задание python пропало из ci.yml")

    def new_job(self) -> tuple[str, list[str]]:
        """Единственное задание вне `python`, которое зовёт `stack_ci.py --min`
        и гоняет pytest на `tests/test_invariants.py`."""
        found = {name: block for name, block in min_jobs(self.text).items()
                 if any(re.search(INVARIANTS_PYTEST, ln)
                        for ln in pytest_lines(block))}
        self.assertEqual(len(found), 1,
                         f"ждали ровно одно задание вне python с "
                         f"`stack_ci.py --min` и pytest tests/test_invariants.py, "
                         f"нашли: {sorted(found)}")
        return next(iter(found.items()))

    def test_ac1_min_python_check_moved_to_separate_job(self):
        """Минимальная версия, зависимости и прогон `tests/test_invariants.py` — в отдельном задании, из `python` ушли.

        Сценарий: в `ci.yml` дерева с наложенным приложением ищется
        задание вне `python`, где по порядку: шаг `stack_ci.py --min`,
        `actions/setup-python`, чья `python-version` берёт вывод этого шага
        (output шага по его `id` либо переменная `$GITHUB_ENV`, которую
        этот шаг пишет), установка `pip install -r requirements.lock` и
        pytest на `tests/test_invariants.py`. В блоке задания `python` нет
        ни `stack_ci.py --min`, ни pytest на `tests/test_invariants.py`.

        Ловит мутацию: шаги скопированы в новое задание, но не удалены из
        `python` (прогон на минимальной версии идёт дважды и `python` не
        укорачивается); в новом задании забыта установка
        `requirements.lock`; `setup-python` нового задания ставит версию
        манифеста (`stack_ci.py` без `--min`) или стоит после pytest.
        """
        name, block = self.new_job()
        texts = steps(block)
        i_min = step_index(texts, r"stack_ci\.py\s+--min")
        i_setup = step_index(texts, r"uses:\s*actions/setup-python")
        i_pip = step_index(texts, r"pip install -r requirements\.lock")
        i_test = step_index(texts, INVARIANTS_PYTEST)
        for label, idx in (("stack_ci.py --min", i_min),
                           ("actions/setup-python", i_setup),
                           ("pip install -r requirements.lock", i_pip),
                           ("pytest tests/test_invariants.py", i_test)):
            self.assertIsNotNone(idx, f"в задании {name} нет шага {label}")
        self.assertLess(i_min, i_setup, f"{name}: setup-python раньше --min")
        self.assertLess(i_setup, i_pip, f"{name}: зависимости до setup-python")
        self.assertLess(i_pip, i_test, f"{name}: pytest до установки зависимостей")

        min_step = texts[i_min]
        version = re.search(r"python-version:\s*(.+)", texts[i_setup])
        self.assertIsNotNone(version, f"{name}: setup-python без python-version")
        step_id = re.search(r"\bid:\s*(\S+)", min_step)
        env_var = re.search(r"([A-Za-z_][A-Za-z0-9_]*)=.*>>\s*\"?\$GITHUB_ENV",
                            min_step)
        refs = []
        if step_id:
            refs.append(f"steps.{step_id.group(1)}.outputs")
        if env_var:
            refs.append(f"env.{env_var.group(1)}")
        self.assertTrue(any(ref in version.group(1) for ref in refs),
                        f"{name}: python-version {version.group(1)!r} не берёт "
                        f"вывод шага `stack_ci.py --min` (ждали одно из {refs})")

        python_block = "\n".join(self.jobs[PYTHON_JOB])
        self.assertNotRegex(python_block, r"stack_ci\.py\s+--min",
                            "задание python всё ещё зовёт stack_ci.py --min")
        self.assertFalse(
            [ln for ln in pytest_lines(self.jobs[PYTHON_JOB])
             if re.search(INVARIANTS_PYTEST, ln)],
            "задание python всё ещё гоняет tests/test_invariants.py")

    def test_ac2_new_job_runs_in_parallel_with_python(self):
        """Новое задание зависит только от `changes` и запускается при том же условии, что `python`.

        Сценарий: собственное поле `needs:` нового задания (строка, список
        в скобках или блочный список) — ровно `changes`; собственное поле
        `if:` совпадает с `if:` задания `python` и несёт условие
        `!cancelled() && needs.changes.outputs.code != 'false'`.

        Ловит мутацию: `needs: [changes, python]` (задание ждёт полный
        `tests/` и идёт последовательно — выигрыша нет); `if:` нового
        задания потерян (задание идёт и на документных пушах) или записан
        как `== 'true'` (fail-open при упавшем `changes`).
        """
        name, block = self.new_job()
        self.assertEqual(own_field(block, "needs"), ["changes"],
                         f"needs задания {name}")
        own_if = own_field(block, "if")
        python_if = own_field(self.jobs[PYTHON_JOB], "if")
        self.assertIsNotNone(own_if, f"у задания {name} нет собственного if:")
        self.assertIsNotNone(python_if, "у задания python нет собственного if:")
        self.assertEqual(own_if, python_if,
                         f"if: задания {name} расходится с if: задания python")
        self.assertIn(PYTHON_IF, own_if[0], f"if: задания {name}")

    def test_ac3_new_job_pytest_is_parallel_with_timeout(self):
        """Pytest нового задания идёт параллельно (`-n auto`, `-p xdist`) с таймаутом `-p timeout -o timeout=120`.

        Сценарий: команда pytest на `tests/test_invariants.py` в новом
        задании (продолжения строк `\\` склеены) содержит каждый из
        четырёх флагов.

        Ловит мутацию: перенесена прежняя команда как есть — без `-n auto`
        и `-p xdist` (прогон остаётся однопроцессным, ~110 с); потерян
        `-o timeout=120` или `-p timeout` (зависший тест держит задание до
        потолка `timeout-minutes`).
        """
        name, block = self.new_job()
        lines = [ln for ln in pytest_lines(block)
                 if re.search(INVARIANTS_PYTEST, ln)]
        self.assertTrue(lines, f"в задании {name} нет pytest на test_invariants")
        for flag in (r"-n\s+auto\b", r"-p\s+xdist\b", r"-p\s+timeout\b",
                     r"-o\s+timeout=120\b"):
            self.assertTrue(all(re.search(flag, ln) for ln in lines),
                            f"{name}: в команде pytest нет {flag!r}: {lines}")

    def test_ac4_python_job_keeps_other_steps_no_continue_on_error(self):
        """Задание `python` сохраняет все прочие шаги в прежнем порядке; `continue-on-error` нет ни в одном из двух заданий.

        Сценарий: в блоке `python` есть шаг `stack_ci.py` без `--min`,
        `actions/setup-python`, `pip install -r requirements.lock`,
        `py_compile`, снимок ссылок `refs-before` до pytest, pytest на
        `tests` с `-n auto -p timeout -p xdist -o timeout=120`, сверка
        ссылок `refs-after` + `diff` после pytest; ни блок `python`, ни
        блок нового задания не содержат `continue-on-error`.

        Ловит мутацию: при переносе вырезан шаг сверки ссылок после
        прогона или снимок до него; потерян `-n auto`/`-o timeout=120`
        у полного прогона; новому заданию или `python` дописан
        `continue-on-error: true` (красный прогон перестаёт красить CI).
        """
        block = self.jobs[PYTHON_JOB]
        texts = steps(block)
        found = {
            "stack_ci.py без --min": step_index(
                texts, r"stack_ci\.py(?![^\n]*--min)"),
            "actions/setup-python": step_index(
                texts, r"uses:\s*actions/setup-python"),
            "pip install -r requirements.lock": step_index(
                texts, r"pip install -r requirements\.lock"),
            "py_compile": step_index(texts, r"py_compile"),
            "снимок ссылок до прогона": step_index(
                texts, r"for-each-ref[^\n]*refs-before"),
            "pytest tests": step_index(
                texts, r"\bpytest\s+tests(\s|$)"),
            "сверка ссылок после прогона": step_index(
                texts, r"refs-after(?s:.*)diff\b"),
        }
        missing = [k for k, v in found.items() if v is None]
        self.assertEqual(missing, [], "в задании python пропали шаги")
        self.assertLess(found["снимок ссылок до прогона"], found["pytest tests"])
        self.assertLess(found["pytest tests"], found["сверка ссылок после прогона"])

        full = [ln for ln in pytest_lines(block)
                if re.search(r"\bpytest\s+tests(\s|$)", ln)]
        self.assertTrue(full, "нет команды pytest tests в задании python")
        for flag in (r"-n\s+auto\b", r"-p\s+timeout\b", r"-p\s+xdist\b",
                     r"-o\s+timeout=120\b"):
            self.assertTrue(all(re.search(flag, ln) for ln in full),
                            f"python: в pytest tests нет {flag!r}: {full}")

        name, new_block = self.new_job()
        for job, lines in ((PYTHON_JOB, block), (name, new_block)):
            self.assertNotIn("continue-on-error", "\n".join(lines),
                             f"в задании {job} появился continue-on-error")


if __name__ == "__main__":
    unittest.main()
