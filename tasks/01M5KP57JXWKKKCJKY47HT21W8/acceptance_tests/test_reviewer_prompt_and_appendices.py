"""Промпт ревьювера на дереве «ветка плюс приложения PLAN», неизменность миссий прочих ролей против кода базы ветки, приложения PLAN.

Группа: разовый
Красен до реализации: константы `role_prompt.REVIEWER_FULL_SUITE_RULE` нет — AC-4 падает `AttributeError`; AC-5 находит `suite-run <id>` без флагов в перечне команд ревьювера внешнего проекта; AC-6 находит «— полный набор тестов» в перечне команд ревьювера внешнего проекта, а без приложения 1 — «Прогон полного набора» скила и `unittest discover` образца; PLAN.md задачи ещё не написан — AC-10 не находит приложений; AC-9 на коде базы сравнивает базу с собой и зелёный с рождения (держит неизменность миссий остальных ролей).

Промпт ревьювера (SPEC, требование 5) — миссия
`role_prompt.mission_brief_package(conn, task_id, t, "reviewer", cwd,
docs_dir)` при пустых `brief.developer_brief`, `brief.step_notes_block`,
`review.review_package`, `review.previous_verdict_sha`, к которой по образцу
`runner._build_prompt` приклеены тексты скилов `roles.skills("reviewer")` из
`skills/` дерева прогона и текст `templates/REVIEW.md` того же дерева.
Дерево прогона — `CODE_ROOT` помощника пульта: на рубеже `in_dev ->
verifying` это временное дерево ветки с наложенными приложениями PLAN
(`appendix_tree.suite_tree`). Локальный `plank-run` приложений не
накладывает: там AC-6 красен и при правильной реализации, пока абзац 04.09
скила и `unittest discover` образца на месте (SPEC, требование 6).

Код базы ветки для AC-9 — текст `orchestrator/role_prompt.py` на
`DIFF_BASE` (`git show`), загруженный отдельным модулем пакета
`orchestrator`: прочие модули задача не меняет (зоны SPEC), поэтому обе
сборки идут в одной песочнице при одних входах.

Провалидировано временным стабом реализации (константа, правило после
фразы о проверках, перечень без `suite-run`) с наложенными диффами
приложений из ТЗ — AC-4..AC-6, AC-9 зелёные; стаб и диффы откачены.
"""
import contextlib
import random
import re
import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import (CODE_ROOT, DIFF_BASE, apply_check,  # noqa: E402
                   artifact_text)

sys.path.insert(0, str(CODE_ROOT))
from orchestrator import (brief, config, review, role_prompt,  # noqa: E402
                          roles, store)
from scripts import guard  # noqa: E402
from tests.sandbox import TmpRootTest, artel_target_entry  # noqa: E402

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LETTERS = "abcdefghijkmnpqrstuvwxyz"
FORBIDDEN = ("unittest discover", "Прогон полного набора",
             "— полный набор тестов")
OTHER_ROLES = {"analyst": "analysis", "spec_auditor": "spec_audit",
               "test_author": "tests_writing", "developer": "in_dev"}

EXTERNAL_ENTRY = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
    test_profile:
      command: [uv, run, --frozen, pytest]
      long_lived_dir: backend/tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [backend/tests/**/*.py]
      mutation_claim_scope: [backend/tests/test_*.py]
      report: junit-xml
      install: []
      runner: pytest-own
      workdir: backend
"""


def bare_full_run(text: str, task_id: str) -> list[str]:
    """Вхождения `suite-run <id>` (полный id либо `<id>`), за которыми не
    идёт ` --failed` или ` --wait` — форма `bare_full_run` из
    `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py`."""
    found = []
    for name in (re.escape(task_id), re.escape("<id>")):
        for match in re.finditer(rf"suite-run {name}(?! --failed)(?! --wait)",
                                 text):
            found.append(text[max(0, match.start() - 40):match.end() + 40])
    return found


def base_role_prompt():
    """Модуль `orchestrator.role_prompt` в редакции базы ветки."""
    res = subprocess.run(
        ["git", "-C", str(CODE_ROOT), "show",
         f"{DIFF_BASE}:orchestrator/role_prompt.py"],
        capture_output=True, text=True, check=True)
    module = types.ModuleType("orchestrator.role_prompt_at_base")
    module.__package__ = "orchestrator"
    module.__file__ = str(Path(CODE_ROOT) / "orchestrator" / "role_prompt.py")
    exec(compile(res.stdout, f"{DIFF_BASE}:orchestrator/role_prompt.py",
                 "exec"), module.__dict__)
    return module


def tz_appendix_diffs(text: str) -> list[str]:
    """Блоки ```diff раздела ТЗ «## Приложения PLAN» — в форме разбора
    `guard.plan_appendices` (строки блока + перевод строки)."""
    section = text.split("## Приложения PLAN", 1)[1]
    nxt = re.search(r"^##\s", section, re.M)
    if nxt:
        section = section[:nxt.start()]
    return [body + "\n" for body in
            re.findall(r"^```diff\n(.*?)\n```\s*$", section, re.M | re.S)]


class PromptStand(TmpRootTest):
    """Задачи артели и учебного внешнего проекта в БД песочницы, компоненты
    брифа и ревью-пакет пустые."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        store.create_schema(store.db())
        self.conn = store.db()
        self.ext = "sled" + "".join(self.rng.choice(LETTERS) for _ in range(6))
        config.TARGETS.write_text(
            "targets:\n" + artel_target_entry() + EXTERNAL_ENTRY.format(
                name=self.ext, base=config.MAIN_BRANCH), encoding="utf-8")
        stack = contextlib.ExitStack()
        for target, attr in ((brief, "developer_brief"),
                             (brief, "step_notes_block"),
                             (brief, "analyst_map_component"),
                             (brief, "test_author_answer_component"),
                             (brief, "spec_auditor_brief"),
                             (review, "review_package"),
                             (review, "previous_verdict_sha")):
            stack.enter_context(mock.patch.object(target, attr,
                                                  return_value=""))
        self.addCleanup(stack.close)

    def msg(self, text: str = "") -> str:
        return f"зерно {self.seed}: {text}"

    def new_task(self, target: str, state: str) -> str:
        task_id = "01" + "".join(self.rng.choice(CROCKFORD) for _ in range(24))
        store.insert_task(self.conn, task_id, "Учебная задача", state,
                          f"task/{task_id.lower()}-x", target, 25.0)
        return task_id

    def mission(self, module, task_id: str, target: str, role: str) -> str:
        t = store.get_task(self.conn, task_id)
        mission, _b, _p = module.mission_brief_package(
            self.conn, task_id, t, role, "/tmp/cwd",
            config.PROJECTS / target / "tasks" / task_id)
        return mission

    def reviewer_prompt(self, target: str) -> tuple[str, str]:
        """(id задачи, промпт ревьювера требования 5)."""
        task_id = self.new_task(target, "review")
        mission = self.mission(role_prompt, task_id, target, "reviewer")
        root = Path(CODE_ROOT)
        skills = "\n\n".join(
            (root / "skills" / f"{name}.md").read_text(encoding="utf-8")
            for name in roles.skills("reviewer"))
        form = (root / "templates" / "REVIEW.md").read_text(encoding="utf-8")
        return task_id, (f"{mission}\n\n--- СКИЛЫ РОЛИ ---\n\n{skills}"
                         f"\n\n--- РЕВЬЮ-ПАКЕТ ---\n\n{form}")

    def projects(self):
        kinds = [config.DEFAULT_TARGET, self.ext]
        self.rng.shuffle(kinds)
        return kinds


class ReviewerPromptTest(PromptStand):

    def test_ac4_rule_once_in_reviewer_prompt(self):
        """Правило о полном наборе встречается в промпте ревьювера ровно один раз.

        Сценарий: для задачи артели и задачи учебного внешнего проекта
        собран промпт ревьювера (миссия + скилы ревьювера + образец
        REVIEW.md дерева прогона); текст `REVIEWER_FULL_SUITE_RULE` в нём
        один раз.

        Ловит мутацию: правило не вставлено в миссию одного из видов
        проекта — вхождений 0; текст правила скопирован ещё и в скил или
        образец (дубль между слоями) — вхождений 2."""
        rule = role_prompt.REVIEWER_FULL_SUITE_RULE
        for target in self.projects():
            task_id, prompt = self.reviewer_prompt(target)
            with self.subTest(target=target, task=task_id, seed=self.seed):
                self.assertEqual(prompt.count(rule), 1, self.msg(target))

    def test_ac5_no_bare_suite_run_in_reviewer_prompt(self):
        """В промпте ревьювера нет `suite-run <id>` без ` --failed`/` --wait`.

        Сценарий: промпт ревьювера задачи артели и задачи внешнего проекта;
        поиск формой `bare_full_run` по полному id задачи и по `<id>` пуст.

        Ловит мутацию: перечень команд ревьювера внешнего проекта сохранил
        «`<pult> suite-run <id>` — полный набор тестов» либо в скил
        вернулась подсказка `suite-run <id>` без флагов — находка не пуста."""
        for target in self.projects():
            task_id, prompt = self.reviewer_prompt(target)
            with self.subTest(target=target, task=task_id, seed=self.seed):
                self.assertEqual(bare_full_run(prompt, task_id), [],
                                 self.msg(target))

    def test_ac6_no_full_suite_phrasing_in_reviewer_prompt(self):
        """В промпте ревьювера на дереве с приложениями нет `unittest discover`, «Прогон полного набора», «— полный набор тестов».

        Сценарий: промпт ревьювера задачи артели и задачи внешнего проекта
        собран из миссии и скилов/образца дерева прогона; ни одной из трёх
        подстрок в нём нет.

        Ловит мутацию: приложение 1 не перенесено в PLAN или перенесено без
        хунка скила — абзац 04.09 «Прогон полного набора и планки…» на
        месте; хунк образца потерян — `unittest discover -s tests` в
        образце; перечень внешнего проекта сохранил «— полный набор
        тестов»."""
        for target in self.projects():
            task_id, prompt = self.reviewer_prompt(target)
            for phrase in FORBIDDEN:
                with self.subTest(target=target, phrase=phrase, seed=self.seed):
                    self.assertFalse(phrase in prompt,
                                     self.msg(f"{target}: «{phrase}» в промпте"))


class OtherMissionsAgainstBaseTest(PromptStand):

    def test_ac9_other_missions_match_base_code(self):
        """Миссии analyst, spec_auditor, test_author, developer кода ветки побайтно равны миссиям кода базы при одних входах.

        Сценарий: для задачи артели и задачи внешнего проекта (строки БД
        песочницы в состоянии роли) миссия каждой из четырёх ролей собрана
        `mission_brief_package` текущего `orchestrator/role_prompt.py` и
        той же функцией редакции `DIFF_BASE`; строки равны.

        Ловит мутацию: правило ревьювера попало в общий хвост миссий; при
        правке `_reviewer_checks_note` задет общий помощник (`_pult_command`,
        `_guard_tool`) или `suite_run_note` разработчика — текст миссии
        отличается от базы."""
        base = base_role_prompt()
        for target in self.projects():
            roles_order = list(OTHER_ROLES)
            self.rng.shuffle(roles_order)
            for role in roles_order:
                task_id = self.new_task(target, OTHER_ROLES[role])
                with self.subTest(target=target, role=role, seed=self.seed):
                    now = self.mission(role_prompt, task_id, target, role)
                    was = self.mission(base, task_id, target, role)
                    self.assertEqual(now, was, self.msg(f"{target} {role}"))


class PlanAppendicesTest(unittest.TestCase):

    def test_ac10_plan_carries_tz_appendices_applicable(self):
        """PLAN.md несёт оба диффа раздела ТЗ «Приложения PLAN» дословно, и каждый применим к дереву ветки.

        Сценарий: из TZ.md задачи взяты блоки ```diff раздела «Приложения
        PLAN» (приложение 1 — `skills/review-checklist.md`,
        `templates/REVIEW.md`; приложение 2 — `skills/code-revision.md`);
        PLAN.md разобран `guard.plan_appendices` без ошибок, склейка его
        приложений по порядку содержит каждый блок ТЗ дословно, и
        `apply_check` каждого блока пуст (`git apply --check` согласен).
        Ветка задачи `skills/`/`templates/` не правит (защищённые пути),
        поэтому дерево HEAD по этим путям равно дереву базы ветки.

        Ловит мутацию: в PLAN перенесено одно приложение из двух; дифф
        перенесён с правкой (сдвинут хедер хунка, потеряна строка
        контекста) — блока ТЗ нет в склейке либо `git apply --check`
        отказывает; приложение лежит вне раздела «## Приложение…» — разбор
        его не видит."""
        tz = artifact_text("TZ.md")
        self.assertIsNotNone(tz, "TZ.md задачи не прочитан")
        expected = tz_appendix_diffs(tz)
        self.assertEqual(len(expected), 2, "в ТЗ ожидались два диффа")
        plan = artifact_text("PLAN.md")
        self.assertIsNotNone(plan, "PLAN.md задачи нет")
        appendices, errors = guard.plan_appendices(plan)
        self.assertEqual(errors, [])
        joined = "".join(a.diff for a in appendices)
        for number, diff in enumerate(expected, 1):
            with self.subTest(appendix=number):
                self.assertIn(diff, joined)
                self.assertEqual(apply_check(diff), "")


if __name__ == "__main__":
    unittest.main()
