"""Правило о полном наборе тестов у ревьювера — одна константа `role_prompt.REVIEWER_FULL_SUITE_RULE`, в миссии ревьювера ровно один раз сразу после фразы о проверках.

Группа: долгоживущий
Красен до реализации: константы `role_prompt.REVIEWER_FULL_SUITE_RULE` нет — обращение к ней падает `AttributeError` (AC-1, AC-2, AC-8), а перечень команд ревьювера внешнего проекта ещё называет `suite-run <id>` — полный набор тестов (AC-3); AC-7 держит прежний перечень и зелёный с рождения.

Стенд — `tests.sandbox.TmpRootTest`: пути `config` (БД, области
проектов, `targets.yaml`) во временном каталоге. Задачи — строки БД
песочницы: задача артели и задача учебного внешнего проекта (запись
`targets.yaml` песочницы без настоящего клона). Миссии собирает
`role_prompt.mission_brief_package`; компоненты брифа, записки шагов и
ревью-пакет подменены пустыми (публичные функции `brief`/`review`) —
предмет теста только текст миссии. Идентификаторы задач и имя внешнего
проекта — от зерна; зерно печатается и входит в текст каждого провала.
"""
import contextlib
import random
import unittest
from unittest import mock

from orchestrator import brief, config, review, role_prompt, store
from tests.sandbox import TmpRootTest, artel_target_entry

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LETTERS = "abcdefghijkmnpqrstuvwxyz"

RULE_TEXT = (
    "Полный набор тестов в шаге ревью не запускай — ни командой пульта "
    "`suite-run`, ни `pytest` или `unittest` по всему `tests/`: его гоняют CI "
    "и гейты пульта (приёмка и мерж). В шаге — планка задачи и тесты файлов "
    "задачи.")
ARTEL_CHECKS = ("Права не сужены: тесты, guard и другие исполняемые проверки "
                "запускай, когда они доказывают или опровергают замечание.")
CHECKS_TAIL = "запускай их, когда они доказывают или опровергают замечание."
OTHER_ROLES = ("analyst", "spec_auditor", "test_author", "developer")

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


class ReviewerRuleStand(TmpRootTest):
    """Задачи артели и учебного внешнего проекта в БД песочницы; миссии с
    пустыми компонентами брифа."""

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

    def pult(self) -> str:
        return f"python3 {config.ROOT / 'orchestrator' / 'artel.py'}"

    def new_task(self, target: str, state: str) -> str:
        task_id = "01" + "".join(self.rng.choice(CROCKFORD) for _ in range(24))
        store.insert_task(self.conn, task_id, "Учебная задача", state,
                          f"task/{task_id.lower()}-x", target, 25.0)
        return task_id

    def mission(self, target: str, role: str, state: str = "review"):
        """(id задачи, миссия роли `role` задачи проекта `target`)."""
        task_id = self.new_task(target, state)
        t = store.get_task(self.conn, task_id)
        mission, _b, _p = role_prompt.mission_brief_package(
            self.conn, task_id, t, role, "/tmp/cwd",
            config.PROJECTS / target / "tasks" / task_id)
        return task_id, mission

    def projects(self):
        """Оба вида проекта в случайном порядке — несколько входов."""
        kinds = [config.DEFAULT_TARGET, self.ext]
        self.rng.shuffle(kinds)
        return kinds


class ReviewerRuleTest(ReviewerRuleStand):

    def test_ac1_rule_constant_text(self):
        """Модуль `role_prompt` несёт строковую константу правила с текстом требования 1 побайтно.

        Сценарий: читается атрибут модуля `REVIEWER_FULL_SUITE_RULE`; он —
        строка и совпадает с текстом требования 1 символ в символ.

        Ловит мутацию: константа названа иначе или не заведена —
        `AttributeError`; в тексте потерян фрагмент «(приёмка и мерж)» или
        `suite-run` записан без обратных кавычек — сравнение строк падает."""
        rule = getattr(role_prompt, "REVIEWER_FULL_SUITE_RULE", None)
        self.assertIsInstance(rule, str)
        self.assertEqual(rule, RULE_TEXT)

    def test_ac2_rule_once_right_after_checks_note(self):
        """Миссия ревьювера несёт правило ровно один раз, отделённое от фразы о проверках только пробельными символами.

        Сценарий: для задачи артели и задачи учебного внешнего проекта
        (по три случайных id каждого вида) собрана миссия ревьювера. В ней
        `REVIEWER_FULL_SUITE_RULE` встречается один раз; текст перед ним без
        хвостовых пробельных символов кончается фразой о проверках: у артели
        — «Права не сужены: …замечание.», у внешнего проекта — «…запускай
        их, когда они доказывают или опровергают замечание.».

        Ловит мутацию: правило не вставлено в миссию либо вставлено только в
        ветку одного вида проекта — вхождений 0; вставлено и после фразы, и
        в хвост миссии — вхождений 2; поставлено перед фразой о проверках
        или после следующего предложения «Проведи обе фазы…» — текст перед
        правилом кончается не фразой о проверках."""
        rule = role_prompt.REVIEWER_FULL_SUITE_RULE
        for target in self.projects():
            for _ in range(3):
                task_id, mission = self.mission(target, "reviewer")
                with self.subTest(target=target, task=task_id, seed=self.seed):
                    text = self.msg(mission)
                    self.assertEqual(mission.count(rule), 1, text)
                    before = mission[:mission.index(rule)].rstrip()
                    ending = (ARTEL_CHECKS if target == config.DEFAULT_TARGET
                              else CHECKS_TAIL)
                    self.assertTrue(before.endswith(ending), text)

    def test_ac3_checks_note_lists_guard_and_plank_run_only(self):
        """Фраза о проверках внешнего проекта называет guard и plank-run без suite-run; у артели — прежняя.

        Сценарий: миссии ревьювера задач артели и внешнего проекта
        (несколько случайных id). Берётся строка миссии, на которой стоит
        фраза о проверках (последняя непустая строка перед правилом), без
        текста правила. У внешнего проекта в ней по порядку
        «`<pult> guard <id> [<файл>]` — структура артефактов»,
        «`<pult> plank-run <id> [<файл>]` — планка и долгоживущие файлы
        задачи» и «запускай их, когда они доказывают или опровергают
        замечание.», и нет `suite-run`; у артели миссия содержит прежнюю
        фразу «Права не сужены: …» побайтно.

        Ловит мутацию: из перечня внешнего проекта не убран
        «`<pult> suite-run <id>` — полный набор тестов» — `suite-run` в
        строке; при чистке перечня пропал `plank-run` или подпись
        «— структура артефактов»; хвост «запускай их…» оказался перед
        перечнем; правка задела фразу артели — её нет в миссии побайтно."""
        rule = role_prompt.REVIEWER_FULL_SUITE_RULE
        pult = self.pult()
        for target in self.projects():
            for _ in range(2):
                task_id, mission = self.mission(target, "reviewer")
                with self.subTest(target=target, task=task_id, seed=self.seed):
                    text = self.msg(mission)
                    if target == config.DEFAULT_TARGET:
                        self.assertIn(ARTEL_CHECKS, mission, text)
                        continue
                    line = mission[:mission.index(rule)].rstrip()
                    line = line.rsplit("\n", 1)[-1]
                    self.assertNotIn("suite-run", line, text)
                    guard = (f"`{pult} guard {task_id} [<файл>]` — структура "
                             f"артефактов")
                    plank = (f"`{pult} plank-run {task_id} [<файл>]` — планка "
                             f"и долгоживущие файлы задачи")
                    for part in (guard, plank, CHECKS_TAIL):
                        self.assertIn(part, line, text)
                    self.assertLess(line.index(guard), line.index(plank), text)
                    self.assertLess(line.index(plank), line.index(CHECKS_TAIL),
                                    text)

    def test_ac7_external_reviewer_names_pult_commands_full_path(self):
        """Миссия ревьювера внешнего проекта называет plank-run и guard полным путём пульта.

        Сценарий: учебный внешний проект, три задачи со случайными id;
        миссия ревьювера каждой содержит
        «`python3 <config.ROOT>/orchestrator/artel.py plank-run <id>» и
        «`python3 <config.ROOT>/orchestrator/artel.py guard <id>».

        Ловит мутацию: при чистке перечня от `suite-run` команды записаны
        короткой формой `artel.py plank-run <id>` без полного пути пульта
        (белый список роли внешнего проекта такую не пропустит) или
        `guard` выпал из перечня — подстроки с полным путём нет."""
        pult = self.pult()
        for _ in range(3):
            task_id, mission = self.mission(self.ext, "reviewer")
            with self.subTest(task=task_id, seed=self.seed):
                text = self.msg(mission)
                self.assertIn(f"`{pult} plank-run {task_id}", mission, text)
                self.assertIn(f"`{pult} guard {task_id}", mission, text)

    def test_ac8_other_roles_missions_lack_rule(self):
        """Миссии analyst, spec_auditor, test_author, developer правила ревьювера не несут.

        Сценарий: для задачи артели и задачи внешнего проекта собраны миссии
        каждой из четырёх ролей (состояние задачи — то, в котором роль
        работает); ни в одной нет текста `REVIEWER_FULL_SUITE_RULE`. Контроль
        стенда: в миссии ревьювера той же сборки правило есть.

        Ловит мутацию: правило дописано в общий хвост миссий
        (`knowledge_hint_note`/`docs_dir_note` после развилки ролей) или в
        `suite_run_note` разработчика — текст правила в миссии чужой роли."""
        rule = role_prompt.REVIEWER_FULL_SUITE_RULE
        states = {"analyst": "analysis", "spec_auditor": "spec_audit",
                  "test_author": "tests_writing", "developer": "in_dev"}
        for target in self.projects():
            roles = list(OTHER_ROLES)
            self.rng.shuffle(roles)
            for role in roles:
                task_id, mission = self.mission(target, role, states[role])
                with self.subTest(target=target, role=role, seed=self.seed):
                    self.assertNotIn(rule, mission, self.msg(mission))
            _task, control = self.mission(target, "reviewer")
            self.assertIn(rule, control, self.msg(control))


if __name__ == "__main__":
    unittest.main()
