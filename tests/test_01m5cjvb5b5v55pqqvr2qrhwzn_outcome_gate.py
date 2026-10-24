"""Гейт неослабления по исходам на переходе `in_dev -> verifying`: `PASS_TO_PASS`, перепрогоны, сравнение отчётов, мандат, отказы и журнал.

Группа: долгоживущий
Красен до реализации: гейта исходов нет — `advance` из `in_dev` у компонента `components:` с `report` не гоняет полный набор на выписках базы и головы, не перепрогоняет красные тесты, не сравнивает отчёты, не пишет ни отказов «переход отклонён: гейт неослабления по исходам…», ни записи пройденного гейта, ни строки «нестабилен и на базе: …» — сломанный, нестабильный, исчезнувший и ставший пропуском тест уходит в `verifying`; зелены и на базе ветки методы, держащие отсутствие гейта и прогонов: граница (оба метода AC-1), отказ гейта по тексту без прогона исходов (первый метод AC-2) и «пропуск на ветке не перепрогоняется» (второй метод AC-6).

Стенд — настоящий git (`tests.sandbox.GitignoreCommittedRealGitSandbox`):
клон артели — корень песочницы с bare `origin`; учебный внешний проект —
`tests.sandbox.make_project_repo` со своим `origin` и записью `components:`
в `targets.yaml` песочницы (один компонент `junit-xml` на поддельном
`pytest` либо один `pult-vitest`). Задача проходит настоящий выход из
`tests_writing` (планка с тестом критерия, красным на базе), затем шаг
developer: коммит правки кода (и, по сценарию, файлов `tests/`) в кодовую
ветку, PLAN.md `ready` чекпоинтом шага, `fsm.cmd_advance`. Исход —
состояние задачи и записи журнала (действие и деталь).

Раннеры подменены без Node и без сети шпионом `subprocess.Popen`: запуск
`node_modules/.bin/vitest` (и `--version`), поддельного `pytest` вне дерева
и установки `install` записывает argv, рабочий каталог, сторону и предел
времени и пишет отчёт сценария (JSON отчётчика пульта по `--outputFile`
либо JUnit по `--junitxml`). СТОРОНА различается по выписке, не по номеру
прогона: метка — файл `app.py` в дереве прогона (`APP = 'base'` на базе,
`APP = 'head-…'` на голове кодовой ветки). Исход теста задаётся сценарием
последовательностью по стороне: первый прогон стороны, где тест есть
среди файлов раннера, — первый элемент, следующий — второй и т. д.
Прогоны полного набора (`acceptance.full_suite`) наблюдаются обёрткой
`wraps`: корень выписки, профиль, `fresh`.

Сбои подготовки — шпион `subprocess.run`: отказ git только для вызовов,
в стеке которых есть кадр модуля гейта
`orchestrator.advance_gates.outcome_integrity` (имя модуля — из требования
1 SPEC): `merge-base` (база не определена), чтение кодовой ветки (голова
не прочитана), выписка (`worktree add`/`clone`/`archive`) с sha нужной
стороны.

Мандат — `answer.cmd_answer` Оператора (ANSWER-n с маркером «Ослабление
тестов разрешено:» и матрицей неослабления) либо ANSWER, положенный
автокоммитом шага developer.

Имена проектов, файлов, тестов, числа тестов и пределы — из `random`;
зерно печатается и входит в текст каждого провала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
модуль гейта с выписками базы/головы, `PASS_TO_PASS`, перепрогонами по
записям теста, сравнением отчётов, мандатом, порядком находок, тремя
действиями и записью пройденного гейта — все методы файла зелёные.
"""
from tests.outcome_gate_sandbox import (
    Path, SimpleNamespace, checkpoint, config, mock, os, project_profile, re,
    store, unittest, workspace, OutcomeGateSandbox, js_source, py_source, ulid,
    BROKEN_ACTION, FLAKY_ON_BASE, OUTCOME_ACTION, PASSED_NOTE, PREPARE_ACTION,
    REVIEW_CHANGES, REWORK_ACTION, SEP, TASKS_DIR, TEXT_GATE_ACTION,
    TEXT_GATE_SKIP, VITEST_KIND)


# ---------------------------------------------------------------- AC-1

class Ac1OutOfBoundsTest(OutcomeGateSandbox):

    def assert_no_gate(self, rows, output) -> None:
        self.assertEqual(self.suite_calls, [], self.explain(rows, output))
        self.assertEqual(self.gate_rows(rows), [], self.explain(rows, output))
        self.assertEqual(self.full_runs(), [], self.explain(rows, output))

    def test_ac1_artel_and_test_profile_no_gate(self):
        """Артель и запись `test_profile` с `report: junit-xml`: полного набора нет, записей гейта исходов нет, переход как прежде.

        Сценарий (подслучай — свежая задача): (а) задача артели с зелёной
        планкой; (б) учебный проект с `test_profile` (`runner: pytest-own`,
        `report: junit-xml`) и тестом, который на ветке падает. Шаг
        developer, `advance` из `in_dev`: `acceptance.full_suite` не
        звался, раннер полного набора на выписке не запускался, ни одной
        записи с «по исходам», в (б) — «приёмочные тесты пройдены» и
        `verifying`.

        Ловит мутацию: граница по `reported(profile)` без
        `from_components` — у `test_profile` с `report` гейт создан: полный
        набор прогнан, сломанный тест даёт отказ «… — сломан правкой»;
        гейт создаётся у любого профиля — у артели звался `full_suite`.
        """
        with self.subTest(case="артель", seed=self.seed):
            t = self.artel_in_dev_task()
            self.current = t.id
            rows, output = self.developer_advance(t)
            self.assert_no_gate(rows, output)
            self.assertEqual(self.state(t), "verifying", self.explain(rows, output))
        with self.subTest(case="test_profile", seed=self.seed):
            rel, name = self.py_rel(), self.py_name()
            project = self.junit_project({rel: [name]}, test_profile=True)
            t = self.task(project)
            self.cases[(rel, name)] = {"base": ["passed"], "head": ["failed"]}
            rows, output = self.developer_advance(t)
            self.assert_no_gate(rows, output)
            self.assertTrue(self.details(rows, PASSED_NOTE), self.explain(rows, output))
            self.assertEqual(self.state(t), "verifying", self.explain(rows, output))

    def test_ac1_decide_skip_refusal_and_canary_no_gate(self):
        """Пропуск и отказ решения `decide` и канареечная задача: гейт исходов не создаётся.

        Сценарий (подслучай): (а) канареечная задача проекта с компонентом
        `junit-xml`, тест базы на ветке падает; (б) проект задачи без
        `test_profile` и `components:` (пропуск решения; переход доходит
        до записи пропуска гейта по тексту); (в) `decide`, позванный из
        модуля гейта, отдаёт отказ (подмена публичного
        `project_profile.decide` только для кадров гейта), тест базы на
        ветке падает. Во всех — `acceptance.full_suite` не звался, раннер
        полного набора на выписке не запускался, записей с «по исходам»
        нет; в (а) и (в) задача ушла в `verifying`.

        Ловит мутацию: условие `t["is_canary"]` пропущено — у канарейки
        полный набор прогнан и отказ «… — сломан правкой»; отказ решения
        `decide` у гейта исходов — отказ перехода (запись с «по исходам»)
        или прогон по профилю записи в обход решения — `full_suite` звался.
        """
        with self.subTest(case="канарейка", seed=self.seed):
            rel, name = self.py_rel(), self.py_name()
            project = self.junit_project({rel: [name]})
            t = self.task(project, canary=True)
            self.cases[(rel, name)] = {"base": ["passed"], "head": ["failed"]}
            rows, output = self.developer_advance(t)
            self.assert_no_gate(rows, output)
            self.assertEqual(self.state(t), "verifying", self.explain(rows, output))
        with self.subTest(case="пропуск decide", seed=self.seed):
            project = self.bare_project()
            self.assertTrue(project_profile.decide(project.name).skip,
                            self.note("решение не пропуск"))
            tid = ulid(self.rng)
            branch = f"task/{tid.lower()}-{self.word()}"
            store.insert_task(self.conn, tid, "Фикстура", "in_dev", branch,
                              project.name, 25.0)
            wt, error = workspace.ensure(tid, branch)
            self.assertIsNone(error, self.note(str(error)))
            t = SimpleNamespace(id=tid, branch=branch, target=project.name,
                                wt=Path(wt), project=project,
                                docs=config.PROJECTS / project.name / TASKS_DIR / tid)
            self.current = tid
            rows, output = self.developer_advance(t)
            self.assert_no_gate(rows, output)
            # Переход дошёл до соседа гейта: пропуск гейта по тексту записан.
            self.assertTrue(self.details(rows, TEXT_GATE_SKIP), self.explain(rows, output))
        with self.subTest(case="отказ decide", seed=self.seed):
            rel, name = self.py_rel(), self.py_name()
            project = self.junit_project({rel: [name]})
            t = self.task(project)
            self.cases[(rel, name)] = {"base": ["passed"], "head": ["failed"]}
            real = project_profile.decide
            refusal = f"профиль сценария {self.word()} не прочитан"

            def decide(target, *args, **kwargs):
                if self.in_gate():
                    return project_profile.Decision(target, refusal=refusal)
                return real(target, *args, **kwargs)
            with mock.patch.object(project_profile, "decide", decide):
                rows, output = self.developer_advance(t)
            self.assert_no_gate(rows, output)
            self.assertEqual(self.state(t), "verifying", self.explain(rows, output))


# ---------------------------------------------------------------- AC-2

class Ac2PlaceTest(OutcomeGateSandbox):

    def test_ac2_text_gate_refusal_first_no_outcome_runs(self):
        """Отказ гейта неослабления по тексту — прогона исходов нет.

        Сценарий: проект `junit-xml` с двумя тестами в файле `tests/`;
        правка ветки удаляет один тест из файла без мандата. `advance`
        записывает «переход отклонён: гейт неослабления тестов»;
        `acceptance.full_suite` не звался, записей гейта исходов нет.

        Ловит мутацию: гейт исходов поставлен до гейта по тексту — полный
        набор прогнан, и отказ — «гейт неослабления по исходам» (исчезнувший
        тест), а не отказ по тексту.
        """
        rel, keep, gone = self.py_rel(), self.py_name(), self.py_name()
        project = self.junit_project({rel: [keep, gone]})
        t = self.task(project)
        rows, output = self.developer_advance(t, {rel: py_source([keep])})
        self.assertTrue(self.details(rows, TEXT_GATE_ACTION), self.explain(rows, output))
        self.assertEqual(self.suite_calls, [], self.explain(rows, output))
        self.assertEqual(self.gate_rows(rows), [], self.explain(rows, output))

    def test_ac2_outcome_refusal_stops_before_review_rework_gate(self):
        """Отказ гейта исходов — гейт переделки ревью не исполняется; при пройденном гейте исходов тот же REVIEW.md даёт отказ переделки.

        Сценарий (подслучай — свежая задача): после коммита кода задача
        проходит `in_dev -> review -> in_dev`, в ссылку документов ложится
        REVIEW.md `changes_requested` автокоммитом шага reviewer, шага
        developer после него нет. (а) Тест базы на ветке
        красен все три раза — отказ «… — сломан правкой», записи «переход
        отклонён: замечания ревью не отработаны» нет. (б) Все тесты зелены
        — гейт исходов пройден, отказ переделки ревью есть.

        Ловит мутацию: гейт исходов поставлен после гейта переделки ревью —
        в (а) отказ переделки ревью вместо отказа гейта исходов.
        """
        for label in ("сломан", "зелёный"):
            with self.subTest(case=label, seed=self.seed):
                rel, name = self.py_rel(), self.py_name()
                project = self.junit_project({rel: [name]})
                t = self.task(project)
                if label == "сломан":
                    self.cases[(rel, name)] = {"base": ["passed"],
                                               "head": ["failed"]}

                def review():
                    store.set_state(self.conn, t.id, "review", "fsm",
                                    expected_state="in_dev",
                                    detail="сценарий: на ревью")
                    t.docs.mkdir(parents=True, exist_ok=True)
                    (t.docs / "REVIEW.md").write_text(
                        REVIEW_CHANGES.format(task=t.id, word=self.word()),
                        encoding="utf-8")
                    store.journal(self.conn, t.id, "reviewer",
                                  "agent run started", "шаг сценария")
                    checkpoint.commit_step_artifacts(self.conn, t.id, "reviewer")
                    store.set_state(self.conn, t.id, "in_dev", "fsm",
                                    expected_state="review",
                                    detail="сценарий: замечания ревью")
                rows, output = self.developer_advance(t, before=review)
                if label == "сломан":
                    self.refusal(rows, output, BROKEN_ACTION)
                    self.assertEqual(self.details(rows, REWORK_ACTION), [],
                                     self.explain(rows, output))
                else:
                    self.no_gate_refusal(rows, output)
                    self.assertTrue(self.details(rows, REWORK_ACTION),
                                    self.explain(rows, output))


# ---------------------------------------------------------------- AC-3

class Ac3RunsTest(OutcomeGateSandbox):

    def test_ac3_full_suite_on_base_and_head_checkouts_fresh(self):
        """Полный набор компонента — дважды, `fresh=True`, на отдельных выписках базы и головы; сторона — по метке дерева.

        Сценарий: проект `junit-xml` с двумя-тремя файлами тестов, все
        зелёные на обеих сторонах. `acceptance.full_suite` позван ровно
        дважды, оба раза с `fresh=True` и профилем компонента; корни — два
        разных каталога, ни один не рабочая копия задачи; метка одного
        корня — база, другого — голова; раннер компонента запущен полным
        набором по разу на каждой стороне; гейт пройден, отказа нет.

        Ловит мутацию: голова гоняется в рабочей копии задачи — корень
        совпадает с рабочей копией; база гоняется на дереве головы (одна
        выписка дважды) — обе метки «head»; `fresh` не передан — `False`
        в вызове.
        """
        tests = {self.py_rel(): [self.py_name() for _ in range(2)]
                 for _ in range(self.rng.randint(2, 3))}
        project = self.junit_project(tests)
        t = self.task(project)
        rows, output = self.developer_advance(t)
        self.no_gate_refusal(rows, output)
        calls = self.suite_calls
        self.assertEqual(len(calls), 2, self.explain(rows, output))
        self.assertTrue(all(c["fresh"] is True for c in calls), self.explain(rows, output))
        self.assertEqual(sorted(c["side"] for c in calls), ["base", "head"],
                         self.explain(rows, output))
        roots = {os.path.realpath(c["root"]) for c in calls}
        self.assertEqual(len(roots), 2, self.explain(rows, output))
        self.assertNotIn(os.path.realpath(t.wt), roots, self.explain(rows, output))
        for c in calls:
            self.assertEqual(getattr(c["command"], "component", None),
                             project.comp, self.explain(rows, output))
        sides = sorted(r["side"] for r in self.full_runs())
        self.assertEqual(sides, ["base", "head"], self.explain(rows, output))


# ---------------------------------------------------------------- AC-4

class Ac4PrepareTest(OutcomeGateSandbox):

    def prepared(self, git_fail=None, timeout_when=None, no_report_when=None):
        rel, name = self.py_rel(), self.py_name()
        project = self.junit_project({rel: [name]})
        t = self.task(project)
        self.cases[(rel, name)] = {"base": ["passed"], "head": ["failed"]}
        clone = t.project.clone
        base = self.git("-C", str(clone), "merge-base",
                        f"origin/{config.MAIN_BRANCH}", t.branch).strip()
        self.git_fail = git_fail(t, base) if git_fail else None
        self.timeout_when = timeout_when
        self.no_report_when = no_report_when
        return t

    def assert_prepare(self, t, rows, output, side_words=()) -> str:
        detail = self.refusal(rows, output, PREPARE_ACTION)
        self.assertTrue(detail.strip(), self.explain(rows, output))
        self.assertEqual(self.subset_runs(), [], self.explain(rows, output))
        self.assertNotEqual(self.state(t), "verifying", self.explain(rows, output))
        if side_words:
            low = detail.lower()
            self.assertTrue(any(w in low for w in side_words),
                            self.explain(rows, output))
        return detail

    def test_ac4_git_preparation_failures_refuse(self):
        """Сбой подготовки git — отказ «… — подготовка» с причиной, без сравнения и без перепрогонов.

        Сценарий (подслучай — свежая задача, тест базы на ветке красен):
        git отказывает только вызовам из модуля гейта — (а) `merge-base`
        (база `diff_base` не определена); (б) любое чтение кодовой ветки,
        кроме `merge-base` (голова не прочитана); (в) выписка с sha базы;
        (г) выписка с sha головы (или по имени ветки). В каждом —
        отказ «переход отклонён: гейт неослабления по исходам —
        подготовка» с непустой деталью, ни «… — сломан правкой», ни общего
        отказа, перепрогонов нет, задача не в `verifying`.

        Ловит мутацию: `None` от `diff_base` или пустая голова — гейт
        пропущен (задача уходит дальше без отказа); сбой выписки
        проглочен — сравнение по одной стороне даёт «сломан правкой» или
        проход.

        Метод исполняет подслучай (а) «база не определена» (`cases[0]`):
        ветки и помощники всех подслучаев — в теле, исполняется одна
        ветка; (б)–(г) — методы `test_ac4_git_head_not_read_refuses`,
        `test_ac4_git_base_checkout_failure_refuses`,
        `test_ac4_git_head_checkout_failure_refuses`.
        """
        def merge_base(t, base):
            return lambda args: "merge-base" in args

        def head_read(t, base):
            return lambda args: "merge-base" not in args and any(
                t.branch in a for a in args)

        def checkout(side):
            def rule(t, base):
                head = self.git("-C", str(t.project.clone), "rev-parse",
                                t.branch).strip()
                wanted = base if side == "base" else head

                def fail(args):
                    making = ("worktree" in args and "add" in args) or \
                        "clone" in args or "archive" in args
                    return making and any(
                        wanted in a or (side == "head" and t.branch in a)
                        for a in args)
                return fail
            return rule

        cases = (("база не определена", merge_base),
                 ("голова не прочитана", head_read),
                 ("выписка базы", checkout("base")),
                 ("выписка головы", checkout("head")))
        label, rule = cases[0]  # «база не определена»
        with self.subTest(case=label, seed=self.seed):
            t = self.prepared(git_fail=rule)
            rows, output = self.developer_advance(t)
            self.git_fail = None
            self.assert_prepare(t, rows, output)

    def test_ac4_git_head_not_read_refuses(self):
        """Сбой чтения кодовой ветки (кроме `merge-base`) — отказ «… — подготовка» с причиной, без сравнения и перепрогонов.

        Сценарий (подслучай (б) `test_ac4_git_preparation_failures_refuse`
        — свежая задача, тест базы на ветке красен): git отказывает только
        вызовам из модуля гейта, читающим кодовую ветку, кроме
        `merge-base` (голова не прочитана). Отказ «переход отклонён: гейт
        неослабления по исходам — подготовка» с непустой деталью, ни «… —
        сломан правкой», ни общего отказа, перепрогонов нет, задача не в
        `verifying`.

        Ловит мутацию: пустая голова — гейт пропущен (задача уходит
        дальше без отказа).
        """
        def merge_base(t, base):
            return lambda args: "merge-base" in args

        def head_read(t, base):
            return lambda args: "merge-base" not in args and any(
                t.branch in a for a in args)

        def checkout(side):
            def rule(t, base):
                head = self.git("-C", str(t.project.clone), "rev-parse",
                                t.branch).strip()
                wanted = base if side == "base" else head

                def fail(args):
                    making = ("worktree" in args and "add" in args) or \
                        "clone" in args or "archive" in args
                    return making and any(
                        wanted in a or (side == "head" and t.branch in a)
                        for a in args)
                return fail
            return rule

        cases = (("база не определена", merge_base),
                 ("голова не прочитана", head_read),
                 ("выписка базы", checkout("base")),
                 ("выписка головы", checkout("head")))
        label, rule = cases[1]  # «голова не прочитана»
        with self.subTest(case=label, seed=self.seed):
            t = self.prepared(git_fail=rule)
            rows, output = self.developer_advance(t)
            self.git_fail = None
            self.assert_prepare(t, rows, output)

    def test_ac4_git_base_checkout_failure_refuses(self):
        """Сбой выписки дерева с sha базы — отказ «… — подготовка» с причиной, без сравнения и перепрогонов.

        Сценарий (подслучай (в) `test_ac4_git_preparation_failures_refuse`
        — свежая задача, тест базы на ветке красен): git отказывает только
        выписке (`worktree add`, `clone`, `archive`) модуля гейта с sha
        базы. Отказ «переход отклонён: гейт неослабления по исходам —
        подготовка» с непустой деталью, ни «… — сломан правкой», ни
        общего отказа, перепрогонов нет, задача не в `verifying`.

        Ловит мутацию: сбой выписки проглочен — сравнение по одной
        стороне даёт «сломан правкой» или проход.
        """
        def merge_base(t, base):
            return lambda args: "merge-base" in args

        def head_read(t, base):
            return lambda args: "merge-base" not in args and any(
                t.branch in a for a in args)

        def checkout(side):
            def rule(t, base):
                head = self.git("-C", str(t.project.clone), "rev-parse",
                                t.branch).strip()
                wanted = base if side == "base" else head

                def fail(args):
                    making = ("worktree" in args and "add" in args) or \
                        "clone" in args or "archive" in args
                    return making and any(
                        wanted in a or (side == "head" and t.branch in a)
                        for a in args)
                return fail
            return rule

        cases = (("база не определена", merge_base),
                 ("голова не прочитана", head_read),
                 ("выписка базы", checkout("base")),
                 ("выписка головы", checkout("head")))
        label, rule = cases[2]  # «выписка базы»
        with self.subTest(case=label, seed=self.seed):
            t = self.prepared(git_fail=rule)
            rows, output = self.developer_advance(t)
            self.git_fail = None
            self.assert_prepare(t, rows, output)

    def test_ac4_git_head_checkout_failure_refuses(self):
        """Сбой выписки дерева головы — отказ «… — подготовка» с причиной, без сравнения и перепрогонов.

        Сценарий (подслучай (г) `test_ac4_git_preparation_failures_refuse`
        — свежая задача, тест базы на ветке красен): git отказывает только
        выписке модуля гейта с sha головы или по имени ветки. Отказ
        «переход отклонён: гейт неослабления по исходам — подготовка» с
        непустой деталью, ни «… — сломан правкой», ни общего отказа,
        перепрогонов нет, задача не в `verifying`.

        Ловит мутацию: сбой выписки проглочен — сравнение по одной
        стороне даёт «сломан правкой» или проход.
        """
        def merge_base(t, base):
            return lambda args: "merge-base" in args

        def head_read(t, base):
            return lambda args: "merge-base" not in args and any(
                t.branch in a for a in args)

        def checkout(side):
            def rule(t, base):
                head = self.git("-C", str(t.project.clone), "rev-parse",
                                t.branch).strip()
                wanted = base if side == "base" else head

                def fail(args):
                    making = ("worktree" in args and "add" in args) or \
                        "clone" in args or "archive" in args
                    return making and any(
                        wanted in a or (side == "head" and t.branch in a)
                        for a in args)
                return fail
            return rule

        cases = (("база не определена", merge_base),
                 ("голова не прочитана", head_read),
                 ("выписка базы", checkout("base")),
                 ("выписка головы", checkout("head")))
        label, rule = cases[3]  # «выписка головы»
        with self.subTest(case=label, seed=self.seed):
            t = self.prepared(git_fail=rule)
            rows, output = self.developer_advance(t)
            self.git_fail = None
            self.assert_prepare(t, rows, output)

    def test_ac4_side_not_started_or_timeout_refuses_naming_side(self):
        """Исход стороны «неизвестно/не начат» или таймаут на базе либо на ветке — отказ подготовки, названа сторона.

        Сценарий (подслучай — свежая задача, тест базы на ветке красен):
        (а) раннер полного набора на базе не пишет отчёт (исход
        «неизвестно»); (б) то же на голове; (в) полный прогон базы
        превышает предел; (г) то же на голове. Отказ «… — подготовка»,
        деталь называет сторону («баз…» либо «ветк…»/«голов…»),
        перепрогонов нет, отказа «… — сломан правкой» нет.

        Ловит мутацию: «неизвестно» на базе принят за пустой отчёт — набор
        `PASS_TO_PASS` пуст, гейт пройден; таймаут головы принят за
        красный прогон — находки «сломан правкой» вместо отказа подготовки;
        сторона в отказе не названа.

        Метод исполняет подслучай (а) «неизвестно база» (`cases[0]`);
        (б)–(г) — методы `test_ac4_side_head_unknown_refuses_naming_head`,
        `test_ac4_side_base_timeout_refuses_naming_base`,
        `test_ac4_side_head_timeout_refuses_naming_head`.
        """
        base_words, head_words = ("баз",), ("ветк", "голов")
        cases = (("неизвестно база", "base", "report", base_words),
                 ("неизвестно голова", "head", "report", head_words),
                 ("таймаут база", "base", "timeout", base_words),
                 ("таймаут голова", "head", "timeout", head_words))
        label, side, kind, words = cases[0]  # «неизвестно база»
        with self.subTest(case=label, seed=self.seed):
            def pick(run, side=side):
                return run["full"] and not run["plank"] and run["side"] == side
            t = self.prepared(timeout_when=pick if kind == "timeout" else None,
                              no_report_when=pick if kind == "report" else None)
            rows, output = self.developer_advance(t)
            self.timeout_when = self.no_report_when = None
            self.assert_prepare(t, rows, output, words)

    def test_ac4_side_head_unknown_refuses_naming_head(self):
        """Исход «неизвестно» полного прогона на голове — отказ подготовки, названа ветка.

        Сценарий (подслучай (б)
        `test_ac4_side_not_started_or_timeout_refuses_naming_side` —
        свежая задача, тест базы на ветке красен): раннер полного набора
        на голове не пишет отчёт. Отказ «… — подготовка», деталь называет
        сторону («ветк…»/«голов…»), перепрогонов нет, отказа «… — сломан
        правкой» нет.

        Ловит мутацию: «неизвестно» на голове принят за красный прогон
        или пустой отчёт — находки «сломан правкой» или проход вместо
        отказа подготовки; сторона в отказе не названа.
        """
        base_words, head_words = ("баз",), ("ветк", "голов")
        cases = (("неизвестно база", "base", "report", base_words),
                 ("неизвестно голова", "head", "report", head_words),
                 ("таймаут база", "base", "timeout", base_words),
                 ("таймаут голова", "head", "timeout", head_words))
        label, side, kind, words = cases[1]  # «неизвестно голова»
        with self.subTest(case=label, seed=self.seed):
            def pick(run, side=side):
                return run["full"] and not run["plank"] and run["side"] == side
            t = self.prepared(timeout_when=pick if kind == "timeout" else None,
                              no_report_when=pick if kind == "report" else None)
            rows, output = self.developer_advance(t)
            self.timeout_when = self.no_report_when = None
            self.assert_prepare(t, rows, output, words)

    def test_ac4_side_base_timeout_refuses_naming_base(self):
        """Таймаут полного прогона базы — отказ подготовки, названа база.

        Сценарий (подслучай (в)
        `test_ac4_side_not_started_or_timeout_refuses_naming_side` —
        свежая задача, тест базы на ветке красен): полный прогон базы
        превышает предел. Отказ «… — подготовка», деталь называет сторону
        («баз…»), перепрогонов нет, отказа «… — сломан правкой» нет.

        Ловит мутацию: таймаут базы принят за пустой отчёт — набор
        `PASS_TO_PASS` пуст, гейт пройден; сторона в отказе не названа.
        """
        base_words, head_words = ("баз",), ("ветк", "голов")
        cases = (("неизвестно база", "base", "report", base_words),
                 ("неизвестно голова", "head", "report", head_words),
                 ("таймаут база", "base", "timeout", base_words),
                 ("таймаут голова", "head", "timeout", head_words))
        label, side, kind, words = cases[2]  # «таймаут база»
        with self.subTest(case=label, seed=self.seed):
            def pick(run, side=side):
                return run["full"] and not run["plank"] and run["side"] == side
            t = self.prepared(timeout_when=pick if kind == "timeout" else None,
                              no_report_when=pick if kind == "report" else None)
            rows, output = self.developer_advance(t)
            self.timeout_when = self.no_report_when = None
            self.assert_prepare(t, rows, output, words)

    def test_ac4_side_head_timeout_refuses_naming_head(self):
        """Таймаут полного прогона головы — отказ подготовки, названа ветка.

        Сценарий (подслучай (г)
        `test_ac4_side_not_started_or_timeout_refuses_naming_side` —
        свежая задача, тест базы на ветке красен): полный прогон головы
        превышает предел. Отказ «… — подготовка», деталь называет сторону
        («ветк…»/«голов…»), перепрогонов нет, отказа «… — сломан правкой»
        нет.

        Ловит мутацию: таймаут головы принят за красный прогон — находки
        «сломан правкой» вместо отказа подготовки; сторона в отказе не
        названа.
        """
        base_words, head_words = ("баз",), ("ветк", "голов")
        cases = (("неизвестно база", "base", "report", base_words),
                 ("неизвестно голова", "head", "report", head_words),
                 ("таймаут база", "base", "timeout", base_words),
                 ("таймаут голова", "head", "timeout", head_words))
        label, side, kind, words = cases[3]  # «таймаут голова»
        with self.subTest(case=label, seed=self.seed):
            def pick(run, side=side):
                return run["full"] and not run["plank"] and run["side"] == side
            t = self.prepared(timeout_when=pick if kind == "timeout" else None,
                              no_report_when=pick if kind == "report" else None)
            rows, output = self.developer_advance(t)
            self.timeout_when = self.no_report_when = None
            self.assert_prepare(t, rows, output, words)


# ---------------------------------------------------------------- AC-5

class Ac5PassToPassTest(OutcomeGateSandbox):

    def test_ac5_retried_on_base_not_in_pass_to_pass(self):
        """Тест, прошедший на базе с повтором, — вне `PASS_TO_PASS`: красный на ветке не находка и не перепрогоняется (`pult-vitest` и `junit-xml`).

        Сценарий (подслучай): (а) `pult-vitest`: на базе тест `pass` с
        `retry_count: 1`, на ветке — `fail`; соседний тест зелён везде.
        Отказов гейта исходов нет, перепрогонов нет. (б) Контроль — тот же
        тест без повтора на базе: отказ «… — сломан правкой».

        Ловит мутацию: в набор берётся любой `passed` базы без сверки
        `retries == 0` — в (а) тест перепрогоняется и даёт «сломан
        правкой».
        """
        for retried in (True, False):
            with self.subTest(retried=retried, seed=self.seed):
                rel, name, other = self.js_rel(), self.js_name(), self.js_name()
                project = self.vitest_project({rel: [name, other]})
                t = self.task(project)
                self.cases[(rel, name)] = {
                    "base": ["retried" if retried else "passed", "passed"],
                    "head": ["failed"]}
                rows, output = self.developer_advance(t)
                if retried:
                    self.no_gate_refusal(rows, output)
                    self.assertEqual(self.subset_runs(), [], self.explain(rows, output))
                else:
                    detail = self.refusal(rows, output, BROKEN_ACTION)
                    self.assertIn(self.case_id(project, rel, name), detail,
                                  self.explain(rows, output))

    def test_ac5_no_tests_on_base_empty_pass_to_pass(self):
        """«Нет тестов» на базе — `PASS_TO_PASS` пуст: новый красный тест ветки не находка.

        Сценарий: проект `junit-xml` без каталога `tests/` на базе; ветка
        добавляет файл `tests/` с тестом, который на ветке падает. Полный
        набор прогнан на обеих сторонах, отказа гейта исходов нет,
        перепрогонов нет.

        Ловит мутацию: «нет тестов» базы принят за отказ подготовки или за
        «все тесты исчезли» — отказ гейта исходов на ветке без единой
        находки по `PASS_TO_PASS`.
        """
        project = self.junit_project({})
        t = self.task(project)
        rel, name = self.py_rel(), self.py_name()
        self.cases[(rel, name)] = {"head": ["failed"]}
        rows, output = self.developer_advance(t, {rel: py_source([name])})
        self.no_gate_refusal(rows, output)
        self.assertEqual(len(self.suite_calls), 2, self.explain(rows, output))
        self.assertEqual(self.subset_runs(), [], self.explain(rows, output))


# ---------------------------------------------------------------- AC-6

class Ac6RerunTest(OutcomeGateSandbox):

    def test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit(self):
        """Красный на ветке (`failed`, `error`, `passed` с повтором) — по два перепрогона на ветке и на базе только по своему файлу, с пределом компонента.

        Сценарий (подслучай — свежая задача): у компонента
        `full_suite_timeout_sec` из `random`; два-три файла тестов, тест
        первого файла на ветке — (а) `failed` (`junit-xml`); (б) `error`
        (`junit-xml`); (в) `passed` с `retry_count: 1` (`pult-vitest`);
        перепрогоны зелёные на обеих сторонах. Перепрогонов ветки — два,
        базы — два; каждый передаёт раннеру только файл красного теста;
        предел каждого — `full_suite_timeout_sec` компонента.

        Ловит мутацию: перепрогон по всем файлам набора — в запуске файлы
        других тестов; перепрогон базы пропущен — перепрогонов базы ноль;
        предел — `config.FULL_SUITE_TIMEOUT_SEC` либо предел приёмки — не
        тот предел в запуске; `passed` с повтором не считается красным —
        перепрогонов нет.
        """
        for kind in ("failed", "error", "retried"):
            with self.subTest(kind=kind, seed=self.seed):
                limit = self.rng.randint(300, 900)
                vitest = kind == "retried"
                rel_of = self.js_rel if vitest else self.py_rel
                name_of = self.js_name if vitest else self.py_name
                tests = {rel_of(): [name_of()] for _ in range(self.rng.randint(2, 3))}
                (rel, (name,)), = list(tests.items())[:1]
                project = (self.vitest_project(tests, limit=limit) if vitest
                           else self.junit_project(tests, limit=limit))
                t = self.task(project)
                self.cases[(rel, name)] = {"base": ["passed"],
                                           "head": [kind, "passed"]}
                rows, output = self.developer_advance(t)
                for side in ("head", "base"):
                    runs = self.subset_runs(side)
                    self.assertEqual(len(runs), 2, self.explain(rows, output))
                    for run in runs:
                        self.assertEqual(run["files"], [rel], self.explain(rows, output))
                        self.assertEqual(run["timeout"], limit, self.explain(rows, output))

    def test_ac6_skipped_on_branch_not_rerun(self):
        """Тест `PASS_TO_PASS`, ставший на ветке `skipped`, не перепрогоняется.

        Сценарий: проект `junit-xml`; тест базы зелён, на ветке — пропуск.
        Перепрогонов нет ни на одной стороне (находка «стал пропуском» —
        предмет AC-9).

        Ловит мутацию: `skipped` на ветке считается красным — тест
        перепрогоняется дважды на каждой стороне.
        """
        rel, name, other = self.py_rel(), self.py_name(), self.py_name()
        project = self.junit_project({rel: [name, other]})
        t = self.task(project)
        self.cases[(rel, name)] = {"base": ["passed"], "head": ["skipped"]}
        rows, output = self.developer_advance(t)
        self.assertEqual(self.subset_runs(), [], self.explain(rows, output))


# ---------------------------------------------------------------- AC-7

class Ac7RerunPrepareTest(OutcomeGateSandbox):

    def test_ac7_rerun_preparation_refusals(self):
        """Отказ подготовки перепрогона: `pult-vitest` без `select`, исход перепрогона не «зелёный» и не «красный», пропуск или нет записи на перепрогоне базы.

        Сценарий (подслучай — свежая задача, тест базы на ветке красен):
        (а) компонент `pult-vitest`, с записи которого после выхода из
        `tests_writing` снят `select`; (б) перепрогон ветки без
        отчёта (исход «неизвестно»); (в) перепрогон ветки превышает предел;
        (г) на перепрогоне базы запись теста `skipped`; (д) на перепрогоне
        базы записи теста нет. В каждом — отказ «переход отклонён: гейт
        неослабления по исходам — подготовка», находки «сломан правкой»
        нет.

        Ловит мутацию: без `select` перепрогон идёт полным набором — отказа
        подготовки нет; «неизвестно»/предел перепрогона принят за красный —
        отказ «сломан правкой»; пропуск или отсутствие записи на базе
        принят за красный базы — «нестабилен и на базе», гейт пройден.

        Метод исполняет подслучай (а) «без select» (`cases[0]`); (б)–(д) —
        методы `test_ac7_rerun_unknown_outcome_refuses`,
        `test_ac7_rerun_timeout_refuses`,
        `test_ac7_rerun_base_skipped_refuses`,
        `test_ac7_rerun_base_record_missing_refuses`.
        """
        def rerun_head(run):
            return not run["full"] and not run["plank"] and run["side"] == "head"

        cases = ("без select", "неизвестно", "таймаут", "база пропуск",
                 "база нет записи")
        label = cases[0]  # «без select»
        with self.subTest(case=label, seed=self.seed):
            vitest = label == "без select"
            rel = self.js_rel() if vitest else self.py_rel()
            name = self.js_name() if vitest else self.py_name()
            project = (self.vitest_project({rel: [name]}) if vitest
                       else self.junit_project({rel: [name]}))
            t = self.task(project)
            if vitest:
                # Выход из `tests_writing` гоняет планку подмножеством —
                # `select` снимается с записи после него.
                self.drop_select()
            base = {"база пропуск": ["passed", "skipped"],
                    "база нет записи": ["passed", "missing"]}.get(
                        label, ["passed"])
            self.cases[(rel, name)] = {"base": base, "head": ["failed"]}
            self.no_report_when = rerun_head if label == "неизвестно" else None
            self.timeout_when = rerun_head if label == "таймаут" else None
            rows, output = self.developer_advance(t)
            self.no_report_when = self.timeout_when = None
            self.refusal(rows, output, PREPARE_ACTION)

    def test_ac7_rerun_unknown_outcome_refuses(self):
        """Перепрогон ветки без отчёта (исход «неизвестно») — отказ подготовки перепрогона.

        Сценарий (подслучай (б) `test_ac7_rerun_preparation_refusals` —
        свежая задача, тест базы на ветке красен): компонент `junit-xml`,
        перепрогон ветки не пишет отчёт. Отказ «переход отклонён: гейт
        неослабления по исходам — подготовка», находки «сломан правкой»
        нет.

        Ловит мутацию: «неизвестно» перепрогона принят за красный — отказ
        «сломан правкой».
        """
        def rerun_head(run):
            return not run["full"] and not run["plank"] and run["side"] == "head"

        cases = ("без select", "неизвестно", "таймаут", "база пропуск",
                 "база нет записи")
        label = cases[1]  # «неизвестно»
        with self.subTest(case=label, seed=self.seed):
            vitest = label == "без select"
            rel = self.js_rel() if vitest else self.py_rel()
            name = self.js_name() if vitest else self.py_name()
            project = (self.vitest_project({rel: [name]}) if vitest
                       else self.junit_project({rel: [name]}))
            t = self.task(project)
            if vitest:
                # Выход из `tests_writing` гоняет планку подмножеством —
                # `select` снимается с записи после него.
                self.drop_select()
            base = {"база пропуск": ["passed", "skipped"],
                    "база нет записи": ["passed", "missing"]}.get(
                        label, ["passed"])
            self.cases[(rel, name)] = {"base": base, "head": ["failed"]}
            self.no_report_when = rerun_head if label == "неизвестно" else None
            self.timeout_when = rerun_head if label == "таймаут" else None
            rows, output = self.developer_advance(t)
            self.no_report_when = self.timeout_when = None
            self.refusal(rows, output, PREPARE_ACTION)

    def test_ac7_rerun_timeout_refuses(self):
        """Перепрогон ветки превышает предел — отказ подготовки перепрогона.

        Сценарий (подслучай (в) `test_ac7_rerun_preparation_refusals` —
        свежая задача, тест базы на ветке красен): компонент `junit-xml`,
        перепрогон ветки превышает предел. Отказ «переход отклонён: гейт
        неослабления по исходам — подготовка», находки «сломан правкой»
        нет.

        Ловит мутацию: предел перепрогона принят за красный — отказ
        «сломан правкой».
        """
        def rerun_head(run):
            return not run["full"] and not run["plank"] and run["side"] == "head"

        cases = ("без select", "неизвестно", "таймаут", "база пропуск",
                 "база нет записи")
        label = cases[2]  # «таймаут»
        with self.subTest(case=label, seed=self.seed):
            vitest = label == "без select"
            rel = self.js_rel() if vitest else self.py_rel()
            name = self.js_name() if vitest else self.py_name()
            project = (self.vitest_project({rel: [name]}) if vitest
                       else self.junit_project({rel: [name]}))
            t = self.task(project)
            if vitest:
                # Выход из `tests_writing` гоняет планку подмножеством —
                # `select` снимается с записи после него.
                self.drop_select()
            base = {"база пропуск": ["passed", "skipped"],
                    "база нет записи": ["passed", "missing"]}.get(
                        label, ["passed"])
            self.cases[(rel, name)] = {"base": base, "head": ["failed"]}
            self.no_report_when = rerun_head if label == "неизвестно" else None
            self.timeout_when = rerun_head if label == "таймаут" else None
            rows, output = self.developer_advance(t)
            self.no_report_when = self.timeout_when = None
            self.refusal(rows, output, PREPARE_ACTION)

    def test_ac7_rerun_base_skipped_refuses(self):
        """Запись теста `skipped` на перепрогоне базы — отказ подготовки перепрогона.

        Сценарий (подслучай (г) `test_ac7_rerun_preparation_refusals` —
        свежая задача, тест базы на ветке красен): компонент `junit-xml`,
        на перепрогоне базы запись теста `skipped`. Отказ «переход
        отклонён: гейт неослабления по исходам — подготовка», находки
        «сломан правкой» нет.

        Ловит мутацию: пропуск на базе принят за красный базы —
        «нестабилен и на базе», гейт пройден.
        """
        def rerun_head(run):
            return not run["full"] and not run["plank"] and run["side"] == "head"

        cases = ("без select", "неизвестно", "таймаут", "база пропуск",
                 "база нет записи")
        label = cases[3]  # «база пропуск»
        with self.subTest(case=label, seed=self.seed):
            vitest = label == "без select"
            rel = self.js_rel() if vitest else self.py_rel()
            name = self.js_name() if vitest else self.py_name()
            project = (self.vitest_project({rel: [name]}) if vitest
                       else self.junit_project({rel: [name]}))
            t = self.task(project)
            if vitest:
                # Выход из `tests_writing` гоняет планку подмножеством —
                # `select` снимается с записи после него.
                self.drop_select()
            base = {"база пропуск": ["passed", "skipped"],
                    "база нет записи": ["passed", "missing"]}.get(
                        label, ["passed"])
            self.cases[(rel, name)] = {"base": base, "head": ["failed"]}
            self.no_report_when = rerun_head if label == "неизвестно" else None
            self.timeout_when = rerun_head if label == "таймаут" else None
            rows, output = self.developer_advance(t)
            self.no_report_when = self.timeout_when = None
            self.refusal(rows, output, PREPARE_ACTION)

    def test_ac7_rerun_base_record_missing_refuses(self):
        """Нет записи теста на перепрогоне базы — отказ подготовки перепрогона.

        Сценарий (подслучай (д) `test_ac7_rerun_preparation_refusals` —
        свежая задача, тест базы на ветке красен): компонент `junit-xml`,
        на перепрогоне базы записи теста нет. Отказ «переход отклонён:
        гейт неослабления по исходам — подготовка», находки «сломан
        правкой» нет.

        Ловит мутацию: отсутствие записи на базе принято за красный базы
        — «нестабилен и на базе», гейт пройден.
        """
        def rerun_head(run):
            return not run["full"] and not run["plank"] and run["side"] == "head"

        cases = ("без select", "неизвестно", "таймаут", "база пропуск",
                 "база нет записи")
        label = cases[4]  # «база нет записи»
        with self.subTest(case=label, seed=self.seed):
            vitest = label == "без select"
            rel = self.js_rel() if vitest else self.py_rel()
            name = self.js_name() if vitest else self.py_name()
            project = (self.vitest_project({rel: [name]}) if vitest
                       else self.junit_project({rel: [name]}))
            t = self.task(project)
            if vitest:
                # Выход из `tests_writing` гоняет планку подмножеством —
                # `select` снимается с записи после него.
                self.drop_select()
            base = {"база пропуск": ["passed", "skipped"],
                    "база нет записи": ["passed", "missing"]}.get(
                        label, ["passed"])
            self.cases[(rel, name)] = {"base": base, "head": ["failed"]}
            self.no_report_when = rerun_head if label == "неизвестно" else None
            self.timeout_when = rerun_head if label == "таймаут" else None
            rows, output = self.developer_advance(t)
            self.no_report_when = self.timeout_when = None
            self.refusal(rows, output, PREPARE_ACTION)

    def test_ac7_branch_rerun_red_kinds(self):
        """На перепрогоне ветки `failed`, `error`, `passed` с повтором, `skipped` или нет записи — красный этого прогона: трижды красный — «сломан правкой».

        Сценарий (подслучай — свежая задача): тест базы зелён на базе
        трижды, на ветке полный прогон — `failed`, оба перепрогона ветки —
        (а) `failed`, (б) `error`, (в) `skipped`, (г) нет записи (`junit-
        xml`), (д) `passed` с `retry_count: 1` (`pult-vitest`). Отказ «… —
        сломан правкой» с идентификатором теста.

        Ловит мутацию: `skipped` или отсутствие записи на перепрогоне ветки
        — зелёный либо отказ подготовки; `passed` с повтором — зелёный;
        итог — «нестабилен после правки» (общий отказ) вместо «сломан
        правкой».

        Метод исполняет подслучай (а) `failed`; (б)–(д) — методы
        `test_ac7_branch_rerun_error_is_red`,
        `test_ac7_branch_rerun_skipped_is_red`,
        `test_ac7_branch_rerun_missing_is_red`,
        `test_ac7_branch_rerun_retried_is_red`.
        """
        kind = "failed"
        with self.subTest(kind=kind, seed=self.seed):
            vitest = kind == "retried"
            rel = self.js_rel() if vitest else self.py_rel()
            name = self.js_name() if vitest else self.py_name()
            project = (self.vitest_project({rel: [name]}) if vitest
                       else self.junit_project({rel: [name]}))
            t = self.task(project)
            self.cases[(rel, name)] = {"base": ["passed"],
                                       "head": ["failed", kind]}
            rows, output = self.developer_advance(t)
            detail = self.refusal(rows, output, BROKEN_ACTION)
            self.assertIn(self.case_id(project, rel, name), detail,
                          self.explain(rows, output))

    def test_ac7_branch_rerun_error_is_red(self):
        """`error` на обоих перепрогонах ветки — красный прогона: трижды красный — «сломан правкой».

        Сценарий (подслучай (б) `test_ac7_branch_rerun_red_kinds` —
        свежая задача, `junit-xml`): тест базы зелён на базе трижды, на
        ветке полный прогон — `failed`, оба перепрогона ветки — `error`.
        Отказ «… — сломан правкой» с идентификатором теста.

        Ловит мутацию: `error` перепрогона не считается красным — зелёный
        либо итог «нестабилен после правки» (общий отказ) вместо «сломан
        правкой».
        """
        kind = "error"
        with self.subTest(kind=kind, seed=self.seed):
            vitest = kind == "retried"
            rel = self.js_rel() if vitest else self.py_rel()
            name = self.js_name() if vitest else self.py_name()
            project = (self.vitest_project({rel: [name]}) if vitest
                       else self.junit_project({rel: [name]}))
            t = self.task(project)
            self.cases[(rel, name)] = {"base": ["passed"],
                                       "head": ["failed", kind]}
            rows, output = self.developer_advance(t)
            detail = self.refusal(rows, output, BROKEN_ACTION)
            self.assertIn(self.case_id(project, rel, name), detail,
                          self.explain(rows, output))

    def test_ac7_branch_rerun_skipped_is_red(self):
        """`skipped` на обоих перепрогонах ветки — красный прогона: трижды красный — «сломан правкой».

        Сценарий (подслучай (в) `test_ac7_branch_rerun_red_kinds` —
        свежая задача, `junit-xml`): тест базы зелён на базе трижды, на
        ветке полный прогон — `failed`, оба перепрогона ветки — `skipped`.
        Отказ «… — сломан правкой» с идентификатором теста.

        Ловит мутацию: `skipped` на перепрогоне ветки — зелёный либо
        отказ подготовки.
        """
        kind = "skipped"
        with self.subTest(kind=kind, seed=self.seed):
            vitest = kind == "retried"
            rel = self.js_rel() if vitest else self.py_rel()
            name = self.js_name() if vitest else self.py_name()
            project = (self.vitest_project({rel: [name]}) if vitest
                       else self.junit_project({rel: [name]}))
            t = self.task(project)
            self.cases[(rel, name)] = {"base": ["passed"],
                                       "head": ["failed", kind]}
            rows, output = self.developer_advance(t)
            detail = self.refusal(rows, output, BROKEN_ACTION)
            self.assertIn(self.case_id(project, rel, name), detail,
                          self.explain(rows, output))

    def test_ac7_branch_rerun_missing_is_red(self):
        """Нет записи теста на обоих перепрогонах ветки — красный прогона: трижды красный — «сломан правкой».

        Сценарий (подслучай (г) `test_ac7_branch_rerun_red_kinds` —
        свежая задача, `junit-xml`): тест базы зелён на базе трижды, на
        ветке полный прогон — `failed`, на обоих перепрогонах ветки записи
        теста нет. Отказ «… — сломан правкой» с идентификатором теста.

        Ловит мутацию: отсутствие записи на перепрогоне ветки — зелёный
        либо отказ подготовки.
        """
        kind = "missing"
        with self.subTest(kind=kind, seed=self.seed):
            vitest = kind == "retried"
            rel = self.js_rel() if vitest else self.py_rel()
            name = self.js_name() if vitest else self.py_name()
            project = (self.vitest_project({rel: [name]}) if vitest
                       else self.junit_project({rel: [name]}))
            t = self.task(project)
            self.cases[(rel, name)] = {"base": ["passed"],
                                       "head": ["failed", kind]}
            rows, output = self.developer_advance(t)
            detail = self.refusal(rows, output, BROKEN_ACTION)
            self.assertIn(self.case_id(project, rel, name), detail,
                          self.explain(rows, output))

    def test_ac7_branch_rerun_retried_is_red(self):
        """`passed` с повтором на обоих перепрогонах ветки — красный прогона: трижды красный — «сломан правкой».

        Сценарий (подслучай (д) `test_ac7_branch_rerun_red_kinds` —
        свежая задача, `pult-vitest`): тест базы зелён на базе трижды, на
        ветке полный прогон — `failed`, оба перепрогона ветки — `passed` с
        `retry_count: 1`. Отказ «… — сломан правкой» с идентификатором
        теста.

        Ловит мутацию: `passed` с повтором — зелёный; итог — «нестабилен
        после правки» (общий отказ) вместо «сломан правкой».
        """
        kind = "retried"
        with self.subTest(kind=kind, seed=self.seed):
            vitest = kind == "retried"
            rel = self.js_rel() if vitest else self.py_rel()
            name = self.js_name() if vitest else self.py_name()
            project = (self.vitest_project({rel: [name]}) if vitest
                       else self.junit_project({rel: [name]}))
            t = self.task(project)
            self.cases[(rel, name)] = {"base": ["passed"],
                                       "head": ["failed", kind]}
            rows, output = self.developer_advance(t)
            detail = self.refusal(rows, output, BROKEN_ACTION)
            self.assertIn(self.case_id(project, rel, name), detail,
                          self.explain(rows, output))


# ---------------------------------------------------------------- AC-8

class Ac8VerdictByRecordTest(OutcomeGateSandbox):

    def test_ac8_broken_unstable_and_flaky_on_base(self):
        """«Сломан правкой», «нестабилен после правки» и «нестабилен и на базе» по исходам трёх прогонов.

        Сценарий (подслучай — свежая задача, проект `junit-xml`): (а) на
        ветке красный трижды, база зелёна трижды — отказ «… — сломан
        правкой» с идентификатором; (б) на ветке красный, затем зелёный
        (порядок из `random`) — общий отказ «переход отклонён: гейт
        неослабления по исходам» с идентификатором; (в) на ветке трижды
        красный, база красна на одном из перепрогонов (`failed` или
        `error`) — отказа гейта исходов нет, в журнале строка «нестабилен и
        на базе: <идентификатор>».

        Ловит мутацию: «нестабилен» не отличается от «сломан» — в (б)
        действие «… — сломан правкой»; красная база перепрогона не читается
        — в (в) отказ «сломан правкой»; строка о базе не пишется — её нет
        в журнале.

        Метод исполняет подслучай (а) «сломан»: ветки и помощники всех
        подслучаев — в теле, исполняется одна ветка; (б) и (в) — методы
        `test_ac8_unstable_after_change_general_refusal`,
        `test_ac8_flaky_on_base_no_refusal`.
        """
        label = "сломан"
        with self.subTest(case=label, seed=self.seed):
            rel, name = self.py_rel(), self.py_name()
            project = self.junit_project({rel: [name, self.py_name()]})
            t = self.task(project)
            tid = self.case_id(project, rel, name)
            head = ["failed", "failed", "failed"]
            base = ["passed", "passed", "passed"]
            if label == "нестабилен":
                head[self.rng.choice((1, 2))] = "passed"
            if label == "база":
                base[self.rng.choice((1, 2))] = self.rng.choice(("failed", "error"))
            self.cases[(rel, name)] = {"base": base, "head": head}
            rows, output = self.developer_advance(t)
            if label == "сломан":
                self.assertIn(tid, self.refusal(rows, output, BROKEN_ACTION),
                              self.explain(rows, output))
            elif label == "нестабилен":
                self.assertIn(tid, self.refusal(rows, output, OUTCOME_ACTION),
                              self.explain(rows, output))
            else:
                self.no_gate_refusal(rows, output)
                texts = [f"{r['action']} {r['detail'] or ''}" for r in rows]
                self.assertTrue(any(FLAKY_ON_BASE + tid in x for x in texts),
                                self.explain(rows, output))

    def test_ac8_unstable_after_change_general_refusal(self):
        """«Нестабилен после правки»: на ветке красный, затем зелёный — общий отказ гейта исходов.

        Сценарий (подслучай (б) `test_ac8_broken_unstable_and_flaky_on_base`
        — свежая задача, проект `junit-xml`): на ветке красный, затем
        зелёный (порядок из `random`), база зелёна трижды — общий отказ
        «переход отклонён: гейт неослабления по исходам» с
        идентификатором.

        Ловит мутацию: «нестабилен» не отличается от «сломан» — действие
        «… — сломан правкой».
        """
        label = "нестабилен"
        with self.subTest(case=label, seed=self.seed):
            rel, name = self.py_rel(), self.py_name()
            project = self.junit_project({rel: [name, self.py_name()]})
            t = self.task(project)
            tid = self.case_id(project, rel, name)
            head = ["failed", "failed", "failed"]
            base = ["passed", "passed", "passed"]
            if label == "нестабилен":
                head[self.rng.choice((1, 2))] = "passed"
            if label == "база":
                base[self.rng.choice((1, 2))] = self.rng.choice(("failed", "error"))
            self.cases[(rel, name)] = {"base": base, "head": head}
            rows, output = self.developer_advance(t)
            if label == "сломан":
                self.assertIn(tid, self.refusal(rows, output, BROKEN_ACTION),
                              self.explain(rows, output))
            elif label == "нестабилен":
                self.assertIn(tid, self.refusal(rows, output, OUTCOME_ACTION),
                              self.explain(rows, output))
            else:
                self.no_gate_refusal(rows, output)
                texts = [f"{r['action']} {r['detail'] or ''}" for r in rows]
                self.assertTrue(any(FLAKY_ON_BASE + tid in x for x in texts),
                                self.explain(rows, output))

    def test_ac8_flaky_on_base_no_refusal(self):
        """«Нестабилен и на базе»: база красна на одном из перепрогонов — отказа нет, строка о базе в журнале.

        Сценарий (подслучай (в) `test_ac8_broken_unstable_and_flaky_on_base`
        — свежая задача, проект `junit-xml`): на ветке трижды красный,
        база красна на одном из перепрогонов (`failed` или `error`) —
        отказа гейта исходов нет, в журнале строка «нестабилен и на базе:
        <идентификатор>».

        Ловит мутацию: красная база перепрогона не читается — отказ
        «сломан правкой»; строка о базе не пишется — её нет в журнале.
        """
        label = "база"
        with self.subTest(case=label, seed=self.seed):
            rel, name = self.py_rel(), self.py_name()
            project = self.junit_project({rel: [name, self.py_name()]})
            t = self.task(project)
            tid = self.case_id(project, rel, name)
            head = ["failed", "failed", "failed"]
            base = ["passed", "passed", "passed"]
            if label == "нестабилен":
                head[self.rng.choice((1, 2))] = "passed"
            if label == "база":
                base[self.rng.choice((1, 2))] = self.rng.choice(("failed", "error"))
            self.cases[(rel, name)] = {"base": base, "head": head}
            rows, output = self.developer_advance(t)
            if label == "сломан":
                self.assertIn(tid, self.refusal(rows, output, BROKEN_ACTION),
                              self.explain(rows, output))
            elif label == "нестабилен":
                self.assertIn(tid, self.refusal(rows, output, OUTCOME_ACTION),
                              self.explain(rows, output))
            else:
                self.no_gate_refusal(rows, output)
                texts = [f"{r['action']} {r['detail'] or ''}" for r in rows]
                self.assertTrue(any(FLAKY_ON_BASE + tid in x for x in texts),
                                self.explain(rows, output))

    def test_ac8_neighbour_red_in_same_file_does_not_redden_rerun(self):
        """Итог перепрогона — по записи теста: красный сосед в том же файле не делает зелёную запись красной.

        Сценарий: в одном файле тест A (`PASS_TO_PASS`) и сосед B, красный
        на базе и на ветке во всех прогонах. A на ветке: полный прогон —
        `failed`, оба перепрогона — `passed`; на базе A зелён. Итог A —
        «нестабилен после правки»: общий отказ с идентификатором A, не
        «… — сломан правкой» и не «нестабилен и на базе».

        Ловит мутацию: итог перепрогона по вердикту прогона (красный из-за
        B) — A красен трижды на ветке и база красна — отказа гейта нет или
        отказ «сломан правкой».
        """
        rel, a, b = self.py_rel(), self.py_name(), self.py_name()
        project = self.junit_project({rel: [a, b]})
        t = self.task(project)
        self.cases[(rel, a)] = {"base": ["passed"], "head": ["failed", "passed"]}
        self.cases[(rel, b)] = {"base": ["failed"], "head": ["failed"]}
        rows, output = self.developer_advance(t)
        detail = self.refusal(rows, output, OUTCOME_ACTION)
        self.assertIn(self.case_id(project, rel, a), detail, self.explain(rows, output))
        self.assertNotIn(self.case_id(project, rel, b), detail, self.explain(rows, output))


# ---------------------------------------------------------------- AC-9

class Ac9CompareTest(OutcomeGateSandbox):

    def test_ac9_vitest_records_findings_and_non_findings(self):
        """Сравнение записей `pult-vitest`: исчезнувший, ставший пропуском, `todo`/`fails` появились, новый пропуск/`todo`/`fails` — находки; неизменные `todo`/`fails` — нет.

        Сценарий: один проект `pult-vitest`, один отказ. База: `gone`
        (`pass`, на ветке файла нет теста), `s_pass`/`s_fail`/`s_err`
        (`pass`/`fail AssertionError`/`fail TypeError`, на ветке `skip`),
        `to_todo` (`pass`, на ветке `todo`), `to_fails` (`pass`, на ветке
        `pass` с `fails`), `keep_todo` (`todo` на обеих сторонах),
        `keep_fails` (`pass` с `fails` на обеих), `quiet` (зелёный везде).
        Ветка добавляет `new_skip`, `new_todo`, `new_fails`, `new_pass`.
        Общий отказ «… по исходам»: идентификаторы всех находок — в детали,
        каждый ровно одной строкой; `keep_todo`, `keep_fails`, `quiet`,
        `new_pass` в детали нет. Деталь несёт итоговую строку о росте
        пропусков без идентификатора теста.

        Ловит мутацию: «стал пропуском» только у `passed` базы — у `s_fail`/
        `s_err` нет находки; `todo`/`fails` — находка без сверки с базой —
        `keep_todo`/`keep_fails` в отказе; новый идентификатор не
        проверяется — `new_*` нет в детали; у `to_todo` две находки (пропуск
        и `todo`) — две строки; рост пропусков — отдельные строки по
        тестам без итоговой.
        """
        rel, gone_rel = self.js_rel(), self.js_rel()
        n = {k: self.js_name() for k in (
            "gone", "s_pass", "s_fail", "s_err", "to_todo", "to_fails",
            "keep_todo", "keep_fails", "quiet", "new_skip", "new_todo",
            "new_fails", "new_pass")}
        base_names = [n[k] for k in ("s_pass", "s_fail", "s_err", "to_todo",
                                     "to_fails", "keep_todo", "keep_fails",
                                     "quiet")]
        project = self.vitest_project({rel: base_names, gone_rel: [n["gone"]]})
        t = self.task(project)
        plan = {"s_pass": ("passed", "skipped"), "s_fail": ("failed", "skipped"),
                "s_err": ("error", "skipped"), "to_todo": ("passed", "todo"),
                "to_fails": ("passed", "fails"), "keep_todo": ("todo", "todo"),
                "keep_fails": ("fails", "fails"),
                "new_skip": ("passed", "skipped"), "new_todo": ("passed", "todo"),
                "new_fails": ("passed", "fails")}
        for key, (base, head) in plan.items():
            self.cases[(rel, n[key])] = {"base": [base], "head": [head]}
        head_names = base_names + [n[k] for k in ("new_skip", "new_todo",
                                                  "new_fails", "new_pass")]
        rows, output = self.developer_advance(t, {rel: js_source(head_names),
                                                  gone_rel: js_source([])})
        detail = self.refusal(rows, output, OUTCOME_ACTION)
        found = ("s_pass", "s_fail", "s_err", "to_todo", "to_fails",
                 "new_skip", "new_todo", "new_fails")
        for key in found:
            cid = self.case_id(project, rel, n[key])
            self.assertEqual(len(self.lines_with(detail, cid)), 1,
                             self.explain(rows, output) + f"\n{key}: {cid}")
        gone = self.case_id(project, gone_rel, n["gone"])
        self.assertEqual(len(self.lines_with(detail, gone)), 1, self.explain(rows, output))
        for key in ("keep_todo", "keep_fails", "quiet", "new_pass"):
            self.assertNotIn(self.case_id(project, rel, n[key]), detail,
                             self.explain(rows, output) + f"\n{key}")
        ids = [self.case_id(project, rel, x) for x in n.values()] + [gone]
        summary = [line for line in detail.splitlines() if "пропуск" in line.lower()
                   and not any(cid in line for cid in ids)]
        self.assertTrue(summary, self.explain(rows, output))

    def test_ac9_junit_records_findings(self):
        """Сравнение записей `junit-xml`: исчезнувший тест и тест базы `passed`/`failed`/`error`, ставший пропуском, — находки; новый пропуск — находка.

        Сценарий: проект `junit-xml`; тест `gone` исчез из отчёта ветки
        (записи нет, текст файла не менялся), `s_pass`/`s_fail`/`s_err` на
        ветке `skipped`, новый тест ветки `new_skip` — пропуск, новый
        `new_pass` — зелёный. Общий отказ: идентификаторы `gone`, `s_*`,
        `new_skip` — каждый одной строкой; `new_pass` в детали нет.

        Ловит мутацию: исчезновение ищется только по тексту файлов
        (гейт по тексту), а не по отчёту — `gone` без находки; «стал
        пропуском» только у `passed` — `s_fail`/`s_err` без находки.
        """
        rel = self.py_rel()
        n = {k: self.py_name() for k in ("gone", "s_pass", "s_fail", "s_err",
                                         "new_skip", "new_pass")}
        base_names = [n[k] for k in ("gone", "s_pass", "s_fail", "s_err")]
        project = self.junit_project({rel: base_names})
        t = self.task(project)
        plan = {"gone": ("passed", "missing"), "s_pass": ("passed", "skipped"),
                "s_fail": ("failed", "skipped"), "s_err": ("error", "skipped")}
        for key, (base, head) in plan.items():
            self.cases[(rel, n[key])] = {"base": [base], "head": [head]}
        new_rel = self.py_rel()
        self.cases[(new_rel, n["new_skip"])] = {"head": ["skipped"]}
        rows, output = self.developer_advance(
            t, {new_rel: py_source([n["new_skip"], n["new_pass"]])})
        detail = self.refusal(rows, output, OUTCOME_ACTION)
        for key in ("gone", "s_pass", "s_fail", "s_err"):
            cid = self.case_id(project, rel, n[key])
            self.assertEqual(len(self.lines_with(detail, cid)), 1,
                             self.explain(rows, output) + f"\n{key}")
        self.assertEqual(len(self.lines_with(
            detail, self.case_id(project, new_rel, n["new_skip"]))), 1,
            self.explain(rows, output))
        self.assertNotIn(self.case_id(project, new_rel, n["new_pass"]), detail,
                         self.explain(rows, output))

    def test_ac9_one_finding_per_id_senior_kind(self):
        """Один идентификатор — одна находка, старшая: красный трижды тест, у которого появилось `fails`, — только «сломан правкой».

        Сценарий: `pult-vitest`; тест базы `pass` без `fails`; на ветке
        все три прогона — `fail` с `fails: true`. Отказ — действие «… —
        сломан правкой» (непокрытые находки только этого вида),
        идентификатор теста — ровно в одной строке детали.

        Ловит мутацию: находка сравнения («появилось `fails`») добавляется
        к находке «сломан правкой» — две находки, действие общего отказа и
        две строки с идентификатором.
        """
        rel, name = self.js_rel(), self.js_name()
        project = self.vitest_project({rel: [name, self.js_name()]})
        t = self.task(project)
        self.cases[(rel, name)] = {"base": ["passed"], "head": ["failed"]}
        with mock.patch.dict(VITEST_KIND, {"failed": {
                "state": "fail", "error_name": "AssertionError", "fails": True}}):
            rows, output = self.developer_advance(t)
        detail = self.refusal(rows, output, BROKEN_ACTION)
        self.assertEqual(len(self.lines_with(detail, self.case_id(project, rel, name))),
                         1, self.explain(rows, output))


# --------------------------------------------------------------- AC-10

class Ac10OrderTest(OutcomeGateSandbox):

    def test_ac10_findings_order_and_one_line_each(self):
        """Порядок находок одного отказа: исчезнувшие → «сломан правкой» → «нестабилен после правки» → прочие; внутри вида — по идентификатору.

        Сценарий: проект `junit-xml`; по два теста каждого вида в
        случайных файлах: исчезнувшие из отчёта ветки, трижды красные на
        ветке, красные один раз из трёх, ставшие пропуском. Общий отказ;
        строки с идентификаторами идут видами в указанном порядке, внутри
        вида — по возрастанию идентификатора; у каждой находки своя
        строка, не несущая идентификатора другой находки.

        Ловит мутацию: находки в порядке отчёта или в порядке сравнения
        (прочие раньше красных) — порядок строк другой; внутри вида без
        сортировки — пары идут в порядке файлов; все находки одной
        строкой.
        """
        kinds = ("gone", "broken", "unstable", "skip")
        names = {k: [(self.py_rel(), self.py_name()) for _ in range(2)]
                 for k in kinds}
        tests: dict = {}
        for items in names.values():
            for rel, name in items:
                tests.setdefault(rel, []).append(name)
        project = self.junit_project(tests)
        t = self.task(project)
        plan = {"gone": {"base": ["passed"], "head": ["missing"]},
                "broken": {"base": ["passed"], "head": ["failed"]},
                "unstable": {"base": ["passed"], "head": ["failed", "passed"]},
                "skip": {"base": ["passed"], "head": ["skipped"]}}
        for kind, items in names.items():
            for rel, name in items:
                self.cases[(rel, name)] = plan[kind]
        rows, output = self.developer_advance(t)
        detail = self.refusal(rows, output, OUTCOME_ACTION)
        lines = detail.splitlines()
        ids = {k: sorted(self.case_id(project, r, n) for r, n in items)
               for k, items in names.items()}
        expected = [cid for k in kinds for cid in ids[k]]
        every = set(expected)
        position = []
        for cid in expected:
            found = [i for i, line in enumerate(lines) if cid in line]
            self.assertEqual(len(found), 1, self.explain(rows, output) + f"\n{cid}")
            others = [o for o in every if o != cid and o in lines[found[0]]]
            self.assertEqual(others, [], self.explain(rows, output))
            position.append(found[0])
        self.assertEqual(position, sorted(position), self.explain(rows, output))


# --------------------------------------------------------------- AC-11

class Ac11MandateTest(OutcomeGateSandbox):

    def broken_task(self, names):
        """Проект `junit-xml` с классами тестов в одном файле; тесты
        `names` — трижды красные на ветке."""
        rel = self.py_rel()
        project = self.junit_project({rel: names + [self.py_name()]})
        t = self.task(project)
        for name in names:
            self.cases[(rel, name)] = {"base": ["passed"], "head": ["failed"]}
        return project, t, rel

    def test_ac11_file_and_prefix_mandate_cover_findings(self):
        """Мандат Оператора на путь файла и на префикс `путь::Класс`/`путь::Класс::метод` снимает находки этого файла; мандат на другой файл — нет.

        Сценарий (подслучай — свежая задача, тесты класса `K` трижды
        красные на ветке): ANSWER Оператора с маркером «Ослабление тестов
        разрешено:» (а) на путь файла; (б) на `путь::K`; (в) на
        `путь::K::test_x` при единственном красном `K::test_x[a]`/`[b]`
        (варианты); (г) на путь другого файла. В (а)–(в) отказа гейта
        исходов нет; в (г) — отказ «… — сломан правкой».

        Ловит мутацию: мандат сверяется точным равенством с
        идентификатором — префикс класса и метод с вариантами не покрывают;
        покрытие по имени файла без пути — мандат другого файла покрывает.

        Метод исполняет подслучай (а) «файл»: ветки всех подслучаев — в
        теле, исполняется одна; (б)–(г) — методы
        `test_ac11_class_prefix_mandate_covers`,
        `test_ac11_method_prefix_mandate_covers_variants`,
        `test_ac11_other_file_mandate_does_not_cover`.
        """
        label = "файл"
        with self.subTest(case=label, seed=self.seed):
            klass = "K" + self.word().capitalize()
            method = self.py_name()
            if label == "метод":
                names = [f"{klass}{SEP}{method}[a]", f"{klass}{SEP}{method}[b]"]
            else:
                names = [f"{klass}{SEP}{self.py_name()}" for _ in range(2)]
            project, t, rel = self.broken_task(names)
            element = {"файл": rel, "класс": f"{rel}{SEP}{klass}",
                       "метод": f"{rel}{SEP}{klass}{SEP}{method}",
                       "другой файл": self.py_rel()}[label]
            self.operator_mandate(t, [element])
            rows, output = self.developer_advance(t, finished=True)
            if label == "другой файл":
                self.refusal(rows, output, BROKEN_ACTION)
            else:
                self.no_gate_refusal(rows, output)

    def test_ac11_class_prefix_mandate_covers(self):
        """Мандат Оператора на префикс `путь::Класс` снимает находки класса.

        Сценарий (подслучай (б)
        `test_ac11_file_and_prefix_mandate_cover_findings` — свежая
        задача, тесты класса `K` трижды красные на ветке): ANSWER
        Оператора с маркером «Ослабление тестов разрешено:» на `путь::K`.
        Отказа гейта исходов нет.

        Ловит мутацию: мандат сверяется точным равенством с
        идентификатором — префикс класса не покрывает.
        """
        label = "класс"
        with self.subTest(case=label, seed=self.seed):
            klass = "K" + self.word().capitalize()
            method = self.py_name()
            if label == "метод":
                names = [f"{klass}{SEP}{method}[a]", f"{klass}{SEP}{method}[b]"]
            else:
                names = [f"{klass}{SEP}{self.py_name()}" for _ in range(2)]
            project, t, rel = self.broken_task(names)
            element = {"файл": rel, "класс": f"{rel}{SEP}{klass}",
                       "метод": f"{rel}{SEP}{klass}{SEP}{method}",
                       "другой файл": self.py_rel()}[label]
            self.operator_mandate(t, [element])
            rows, output = self.developer_advance(t, finished=True)
            if label == "другой файл":
                self.refusal(rows, output, BROKEN_ACTION)
            else:
                self.no_gate_refusal(rows, output)

    def test_ac11_method_prefix_mandate_covers_variants(self):
        """Мандат Оператора на `путь::Класс::метод` снимает находки его вариантов.

        Сценарий (подслучай (в)
        `test_ac11_file_and_prefix_mandate_cover_findings` — свежая
        задача): единственный красный метод `K::test_x[a]`/`[b]`
        (варианты), ANSWER Оператора с маркером «Ослабление тестов
        разрешено:» на `путь::K::test_x`. Отказа гейта исходов нет.

        Ловит мутацию: мандат сверяется точным равенством с
        идентификатором — метод с вариантами не покрывается.
        """
        label = "метод"
        with self.subTest(case=label, seed=self.seed):
            klass = "K" + self.word().capitalize()
            method = self.py_name()
            if label == "метод":
                names = [f"{klass}{SEP}{method}[a]", f"{klass}{SEP}{method}[b]"]
            else:
                names = [f"{klass}{SEP}{self.py_name()}" for _ in range(2)]
            project, t, rel = self.broken_task(names)
            element = {"файл": rel, "класс": f"{rel}{SEP}{klass}",
                       "метод": f"{rel}{SEP}{klass}{SEP}{method}",
                       "другой файл": self.py_rel()}[label]
            self.operator_mandate(t, [element])
            rows, output = self.developer_advance(t, finished=True)
            if label == "другой файл":
                self.refusal(rows, output, BROKEN_ACTION)
            else:
                self.no_gate_refusal(rows, output)

    def test_ac11_other_file_mandate_does_not_cover(self):
        """Мандат Оператора на путь другого файла находки не снимает.

        Сценарий (подслучай (г)
        `test_ac11_file_and_prefix_mandate_cover_findings` — свежая
        задача, тесты класса `K` трижды красные на ветке): ANSWER
        Оператора с маркером «Ослабление тестов разрешено:» на путь
        другого файла. Отказ «… — сломан правкой».

        Ловит мутацию: покрытие по имени файла без пути — мандат другого
        файла покрывает.
        """
        label = "другой файл"
        with self.subTest(case=label, seed=self.seed):
            klass = "K" + self.word().capitalize()
            method = self.py_name()
            if label == "метод":
                names = [f"{klass}{SEP}{method}[a]", f"{klass}{SEP}{method}[b]"]
            else:
                names = [f"{klass}{SEP}{self.py_name()}" for _ in range(2)]
            project, t, rel = self.broken_task(names)
            element = {"файл": rel, "класс": f"{rel}{SEP}{klass}",
                       "метод": f"{rel}{SEP}{klass}{SEP}{method}",
                       "другой файл": self.py_rel()}[label]
            self.operator_mandate(t, [element])
            rows, output = self.developer_advance(t, finished=True)
            if label == "другой файл":
                self.refusal(rows, output, BROKEN_ACTION)
            else:
                self.no_gate_refusal(rows, output)

    def test_ac11_prefix_needs_separator_after_it(self):
        """Префикс `путь::Класс` не покрывает `путь::КлассДругой::метод`: за префиксом иной символ.

        Сценарий: в файле тесты классов `K<слово>` и `K<слово>Other`, оба
        трижды красные на ветке; мандат Оператора — `путь::K<слово>`. Отказ
        «… — сломан правкой»; деталь несёт идентификатор теста класса
        `K<слово>Other` и не несёт идентификатора теста класса `K<слово>`.

        Ловит мутацию: покрытие — `startswith` без сверки следующего
        символа — `K<слово>Other` покрыт, отказа нет.
        """
        klass = "K" + self.word().capitalize()
        own, other = f"{klass}{SEP}{self.py_name()}", f"{klass}Other{SEP}{self.py_name()}"
        project, t, rel = self.broken_task([own, other])
        self.operator_mandate(t, [f"{rel}{SEP}{klass}"])
        rows, output = self.developer_advance(t, finished=True)
        detail = self.refusal(rows, output, BROKEN_ACTION)
        self.assertIn(self.case_id(project, rel, other), detail, self.explain(rows, output))
        self.assertNotIn(self.case_id(project, rel, own), detail, self.explain(rows, output))

    def test_ac11_role_autocommitted_answer_does_not_cover(self):
        """ANSWER с маркером мандата, унесённый автокоммитом шага developer, находку не снимает.

        Сценарий: тест трижды красный на ветке; ANSWER-1.md с маркером
        «Ослабление тестов разрешено: <путь файла>» кладётся в каталог
        документов и уходит в ссылку автокоммитом шага developer. Отказ
        «… — сломан правкой» с идентификатором теста.

        Ловит мутацию: мандат собран без отбраковки автокоммита роли —
        находка покрыта, отказа нет.
        """
        name = self.py_name()
        project, t, rel = self.broken_task([name])
        rows, output = self.developer_advance(t, before=self.role_mandate(t, [rel]))
        self.assertIn(self.case_id(project, rel, name),
                      self.refusal(rows, output, BROKEN_ACTION),
                      self.explain(rows, output))


# --------------------------------------------------------------- AC-13

class Ac13PassedRecordTest(OutcomeGateSandbox):

    def test_ac13_passed_gate_journal_counts(self):
        """Пройденный гейт пишет запись с числом тестов базы и ветки, числом прошедших перепрогон, числом прогонов файлов и числом покрытых мандатом находок.

        Сценарий: проект `junit-xml`; на базе `nb` тестов (из `random`), из
        них `m` исчезают на ветке в файле под мандатом Оператора, ветка
        добавляет `k` новых зелёных; один тест трижды красен на ветке и
        красен на одном перепрогоне базы («нестабилен и на базе»). Гейт
        пройден; среди новых записей журнала есть запись, несущая отдельными
        числами `nb`, число тестов ветки, 1 (тестов прошедших перепрогон),
        4 (прогонов файлов) и `m` (покрытых находок).

        Ловит мутацию: запись пройденного гейта не пишется — записи с
        числами нет; число покрытых мандатом находок не указано — нет
        числа `m`; прогоны файлов не посчитаны — нет числа 4.
        """
        nb = self.rng.randint(11, 19)
        m = self.rng.randint(2, 3)
        k = self.rng.randint(21, 29)
        covered = self.py_rel()
        gone = [self.py_name() for _ in range(m)]
        flaky_rel, flaky = self.py_rel(), self.py_name()
        rest_rel = self.py_rel()
        rest = [self.py_name() for _ in range(nb - m - 1)]
        tests = {covered: gone, flaky_rel: [flaky], rest_rel: rest}
        project = self.junit_project(tests)
        t = self.task(project)
        self.cases[(flaky_rel, flaky)] = {"base": ["passed", "failed", "passed"],
                                          "head": ["failed"]}
        new_rel = self.py_rel()
        added = [self.py_name() for _ in range(k)]
        self.operator_mandate(t, [covered])
        rows, output = self.developer_advance(
            t, {covered: None, new_rel: py_source(added)}, finished=True)
        self.no_gate_refusal(rows, output)
        nh = nb - m + k
        wanted = (nb, nh, 1, 4, m)

        def numbers(row) -> set:
            text = f"{row['action']} {row['detail'] or ''}"
            return {int(x) for x in re.findall(r"(?<![\w.:-])\d+(?![\w.:-])", text)}
        self.assertTrue(any(set(wanted) <= numbers(r) for r in rows),
                        self.explain(rows, output) + f"\nожидались числа {wanted}")


if __name__ == "__main__":
    unittest.main()
