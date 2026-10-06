"""Проверки тестов по профилю проекта на настоящем git клона проекта
(SPEC «Критерии приёмки», AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9,
AC-11, AC-12).

Группа: разовый

Почему разовый, хотя предмет — поведение гейтов: сценариям нужна
настоящая ветка задачи в клоне проекта (удалённый метод теста, добавленный
файл без заявки, долгоживущий файл, лок в ссылке документов), а правила
долгоживущего файла запрещают ему и импорт `gitcmd`, и git-вызовы. Те же
свойства без git (отказы артели без профиля и неразрешённого контекста) —
в долгоживущем `tests/test_<задача>_profile_refusals.py`.

Песочница — `_profile_git.ProfileGitSandbox`: клон проекта
`config.PROJECTS/<имя>/repo` с bare `origin`, ветка задачи, рабочая копия
задачи — `git worktree` на ветке в `workspace.path`; документы задачи — на
диске, а для сценариев лока и `amend-tests` — настоящая ссылка документов в
клоне. pytest не исполняется: вызов и его `cwd` запоминаются. Имена
каталогов профиля, флаги команды и имена файлов выбираются случайно; зерно
печатается и входит в текст провала.

Красен до реализации: профиля тестов нет — у внешнего проекта гейты
неослабления, заявки мутации, строк группы, долгоживущих файлов, лока и
перечня не включаются и не пишут записей журнала о пропуске, команда
прогона — зашитая команда пульта без флагов профиля; у артели области и
каталог зашиты (`tests/test_*.py`, `tests/**/*.py`, `tests/`) — профиль из
её записи `targets.yaml` не читается; `amend-tests` артели без профиля
проходит, задачи неразрешённого контекста — отказывает не той причиной.
Зелёные с рождения методы прежнего поведения артели: `test_ac3_*`
(команда, области, префикс по значениям профиля артели) и `test_ac12_*`
(канарейка); они держат это поведение после перевода на профиль.

Планка провалидирована временным стабом реализации (удалён, не
закоммичен; тот же, что у долгоживущего файла отказов): под ним зелены все
23 метода файла.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import amend, review, stack, store  # noqa: E402
from scripts import guard  # noqa: E402

from _profile_git import (ARTEL, ARTEL_PROFILE, SPEC,  # noqa: E402
                          ProfileGitSandbox, long_lived_text, plank_text,
                          fixture_test_class)

INTEGRITY = "гейт неослабления тестов"
MUTATION = "гейт заявки мутации"
LONG_LIVED = "долгоживущие файлы"
GROUPS = "группы приёмочных тестов"
LOCK = "лок приёмочных тестов"
MANIFEST = "перечень долгоживущих тестов"

TWO_METHODS = fixture_test_class()
ONE_METHOD = fixture_test_class(methods=("test_one",))


def refusals(rows: list, gate: str) -> list:
    return [r for r in rows
            if r["action"].startswith("переход отклонён") and gate in r["action"]]


class _Base(ProfileGitSandbox):

    def profile(self, **overrides) -> dict:
        return dict(ARTEL_PROFILE, **overrides)

    def external(self, profile, base_files=None):
        self.ext = self.rng.choice(["sled", "kedr", "vega"])
        return self.make_project(self.ext, profile, base_files)

    def skip_entries(self, rows: list) -> list:
        """Записи журнала о пропуске проверки: называют `test_profile` и
        проект задачи."""
        return [r for r in rows if "test_profile" in f"{r['action']} {r['detail']}"
                and self.target in f"{r['action']} {r['detail']}"]

    def pytest_call(self, kind: str):
        """Последний вызов pytest: `collect` — сухой сбор, `run` — прогон."""
        calls = [(w, cwd) for w, cwd in self.pytest_calls
                 if ("--collect-only" in w) == (kind == "collect")]
        self.assertTrue(calls, self.msg(f"pytest ({kind}) не вызывался: "
                                        f"{self.pytest_calls}"))
        return calls[-1]

    def assert_profile_command(self, words, extra=()):
        self.assertEqual(words[:3], [stack.pytest_python_executable(), "-m",
                                     "pytest"], self.msg(str(words)))
        joined = " ".join(words)
        for piece in ("-p no:cacheprovider", "-p timeout",
                      f"-o timeout={stack.PER_TEST_TIMEOUT_SEC}", *extra):
            self.assertIn(piece, joined, self.msg(joined))


class ProfileSourceTest(_Base):

    def test_ac2_external_profile_command_comes_from_targets(self):
        """Внешний проект с `test_profile`, чья команда несёт свой флаг:
        сухой сбор планки на выходе из `tests_writing` идёт командой профиля
        (интерпретатор venv пульта вместо `python3`, флаг профиля, флаги
        пульта) в рабочей копии задачи.

        Ловит мутацию: команда прогона по-прежнему собирается зашитым
        `_pytest_command` без чтения профиля — флага профиля в вызове нет.
        """
        flag = self.rng.choice(["--strict-markers", "-x", "--maxfail=3", "-rA"])
        self.external(self.profile(command=["python3", "-m", "pytest", flag]))
        wt = self.set_branch({})
        text, _rows = self.advance_from("tests_writing")
        self.assertEqual(self.state(), "in_dev", self.msg(text))
        words, cwd = self.pytest_call("collect")
        self.assert_profile_command(words, extra=(flag,))
        self.assertEqual(Path(cwd).resolve(), wt.resolve(), self.msg(text))

    def test_ac2_artel_profile_read_from_its_targets_entry(self):
        """Артель с профилем, чья область заявки мутации — другой каталог:
        файл без заявки в этом каталоге отклоняет `in_dev -> verifying`,
        такой же файл в `tests/` — нет.

        Ловит мутацию: для артели область заявки мутации остаётся зашитой
        `tests/test_*.py` (профиль артели не читается из её записи) — отказ
        приходит на `tests/`, а не на каталог профиля.
        """
        folder = self.rng.choice(["checks", "probe", "spec"])
        self.make_project(ARTEL, self.profile(
            mutation_claim_scope=[f"{folder}/test_*.py"]))
        inside = f"{folder}/test_q{self.rng.randrange(100)}.py"
        self.set_branch({inside: fixture_test_class(claim=False)})
        text, rows = self.advance_from("in_dev")
        found = refusals(rows, MUTATION)
        self.assertTrue(found and inside in found[0]["detail"], self.msg(text))
        self.set_branch({"tests/test_q.py": fixture_test_class(claim=False)})
        text, rows = self.advance_from("in_dev")
        self.assertEqual(refusals(rows, MUTATION), [], self.msg(text))

    def test_ac2_no_profile_and_unreadable_profile_are_distinguished(self):
        """Профиля нет (внешний проект без поля) — переход проходит, в
        журнале запись о пропуске с именем проекта и `test_profile`;
        профиль не прочитан (у артели поле не разбирается) — отказ с
        причиной про `targets.yaml` и `test_profile`.

        Ловит мутацию: ответ профиля не различает «нет» и «не прочитан» —
        неразборчивый профиль артели читается как отсутствующий (или
        наоборот, отсутствующий у внешнего проекта — как сбой).
        """
        self.external(None)
        self.set_branch({})
        text, rows = self.advance_from("in_dev")
        self.assertEqual(self.state(), "verifying", self.msg(text))
        self.assertTrue(self.skip_entries(rows), self.msg(text))

        self.profiles[ARTEL] = self.profile(report="tap")
        self.make_project(ARTEL, self.profiles[ARTEL])
        self.set_row(target=ARTEL)
        self.set_branch({})
        text, _rows = self.advance_from("in_dev")
        self.assertEqual(self.state(), "in_dev", self.msg(text))
        self.assertIn("targets.yaml", text, self.msg(text))
        self.assertIn("test_profile", text, self.msg(text))


class ArtelProfileKeepsBehaviourTest(_Base):

    def setUp(self):
        super().setUp()
        self.base = {"tests/a.py": TWO_METHODS,
                     "tests/x/y/test_b.py": TWO_METHODS,
                     "tests/data.json": TWO_METHODS,
                     "orchestrator/a.py": TWO_METHODS}
        self.make_project(ARTEL, ARTEL_PROFILE, self.base)

    def test_ac3_plank_command_unchanged(self):
        """Профиль артели: сухой сбор на выходе из `tests_writing` —
        `stack.pytest_python_executable() -m pytest`, без кеша, с
        `pytest-timeout` и прежним таймаутом, в рабочей копии задачи.

        Ловит мутацию: первый элемент `python3` профиля не заменяется
        интерпретатором venv пульта (или теряются флаги пульта) — вызов
        расходится с прежней командой.
        """
        wt = self.set_branch({})
        text, _rows = self.advance_from("tests_writing")
        words, cwd = self.pytest_call("collect")
        self.assert_profile_command(words)
        self.assertEqual(Path(cwd).resolve(), wt.resolve(), self.msg(text))

    def test_ac3_weakening_scope_unchanged(self):
        """Профиль артели: удалённый метод теста в `tests/a.py` и
        `tests/x/y/test_b.py` отклоняет `in_dev -> verifying`, тот же дифф в
        `tests/data.json` и `orchestrator/a.py` — нет.

        Ловит мутацию: маска `**` сопоставляется только с одним сегментом
        (не входит `tests/x/y/test_b.py`) либо суффикс `.py` маски не
        сверяется (входит `tests/data.json`).
        """
        paths = list(self.base)
        self.rng.shuffle(paths)
        inside = {"tests/a.py", "tests/x/y/test_b.py"}
        for path in paths:
            with self.subTest(seed=self.seed, path=path):
                self.set_branch({path: ONE_METHOD})
                text, rows = self.advance_from("in_dev")
                found = refusals(rows, INTEGRITY)
                if path in inside:
                    self.assertTrue(found and path in found[0]["detail"],
                                    self.msg(text))
                else:
                    self.assertEqual(found, [], self.msg(text))

    def test_ac3_mutation_scope_unchanged(self):
        """Профиль артели: новый `tests/test_a.py` без заявки отклоняет
        переход, `tests/sub/test_a.py` и `tests/helper.py` — нет.

        Ловит мутацию: `*` маски сопоставляется через `/` (входит
        `tests/sub/test_a.py`) либо префикс `test_` маски не сверяется
        (входит `tests/helper.py`).
        """
        cases = [("tests/test_a.py", True), ("tests/sub/test_a.py", False),
                 ("tests/helper.py", False)]
        self.rng.shuffle(cases)
        for path, refused in cases:
            with self.subTest(seed=self.seed, path=path):
                self.set_branch({path: fixture_test_class(claim=False)})
                text, rows = self.advance_from("in_dev")
                found = refusals(rows, MUTATION)
                if refused:
                    self.assertTrue(found and path in found[0]["detail"],
                                    self.msg(text))
                else:
                    self.assertEqual(found, [], self.msg(text))

    def test_ac3_long_lived_prefix_unchanged(self):
        """Профиль артели: долгоживущий файл `tests/test_<id в нижнем
        регистре>_<имя>.py` проходит выход из `tests_writing`, файл с
        другим префиксом — отказ гейта долгоживущих файлов с его путём.

        Ловит мутацию: префикс собирается из шаблона без подстановки
        `<id>` в нижнем регистре (или без каталога) — законный файл
        отклоняется либо файл без префикса задачи проходит.
        """
        name = self.rng.choice(["alpha", "beta2", "gamma_x"])
        good = f"tests/test_{self.TASK.lower()}_{name}.py"
        bad = f"tests/test_{self.TASK[:6].lower()}_{name}.py"
        self.set_branch({bad: long_lived_text()})
        text, rows = self.advance_from("tests_writing")
        found = refusals(rows, LONG_LIVED)
        self.assertTrue(found and bad in found[0]["detail"], self.msg(text))
        self.set_branch({good: long_lived_text()})
        text, rows = self.advance_from("tests_writing")
        self.assertEqual(refusals(rows, LONG_LIVED), [], self.msg(text))
        self.assertEqual(self.state(), "in_dev", self.msg(text))


class ExternalWithoutProfileTest(_Base):

    def setUp(self):
        super().setUp()
        self.external(None, {"tests/test_old.py": TWO_METHODS,
                             "tests/test_v.py": TWO_METHODS})

    def test_ac5_tests_writing_skips_with_journal_and_pult_command(self):
        """Внешний проект без профиля, планка без строки группы: выход из
        `tests_writing` проходит, в журнале запись о пропуске проверки с
        именем проекта и `test_profile`; сухой сбор — командой пульта в
        рабочей копии задачи.

        Ловит мутацию: проверка строк группы и долгоживущих файлов у
        проекта без профиля отключается молча — записи журнала нет.
        """
        self.write_plank(plank_text(group=None))
        wt = self.set_branch({})
        text, rows = self.advance_from("tests_writing")
        self.assertEqual(self.state(), "in_dev", self.msg(text))
        self.assertEqual(refusals(rows, GROUPS), [], self.msg(text))
        self.assertTrue(self.skip_entries(rows), self.msg(text))
        words, cwd = self.pytest_call("collect")
        self.assert_profile_command(words)
        self.assertEqual(Path(cwd).resolve(), wt.resolve(), self.msg(text))

    def test_ac5_in_dev_skips_with_journal_and_runs_plank_in_work_copy(self):
        """Тот же проект: ветка удаляет метод теста и добавляет тест без
        заявки — `in_dev -> verifying` проходит, в журнале записи о
        пропуске, планка прогоняется командой пульта в рабочей копии.

        Ловит мутацию: пропуск неослабления и заявки мутации без записи в
        журнал — записей с `test_profile` нет.
        """
        wt = self.set_branch({"tests/test_old.py": ONE_METHOD,
                              "tests/test_new.py": fixture_test_class(claim=False)})
        text, rows = self.advance_from("in_dev")
        self.assertEqual(self.state(), "verifying", self.msg(text))
        self.assertEqual(refusals(rows, INTEGRITY) + refusals(rows, MUTATION),
                         [], self.msg(text))
        self.assertTrue(self.skip_entries(rows), self.msg(text))
        words, cwd = self.pytest_call("run")
        self.assert_profile_command(words)
        self.assertEqual(Path(cwd).resolve(), wt.resolve(), self.msg(text))

    def test_ac5_review_package_without_section_with_journal(self):
        """Тот же проект с изменённым утверждением теста: пакет ревью без
        раздела изменённых утверждений, в журнале запись о пропуске.

        Ловит мутацию: раздел у проекта без профиля пропускается молча —
        записи журнала с `test_profile` нет.
        """
        self.set_branch({"tests/test_v.py": fixture_test_class(
            assertion="self.assertTrue(True)")})
        package, rows = self.package()
        self.assertNotIn(review.CHANGED_ASSERTIONS_SECTION, package["text"])
        self.assertTrue(self.skip_entries(rows), self.msg(str(rows)))


class ExternalWithProfileTest(_Base):

    def setUp(self):
        super().setUp()
        self.folder = self.rng.choice(["checks", "spec", "probe"])
        self.ll_dir = self.rng.choice(["longlived", "keep"])
        f = self.folder
        self.external(self.profile(
            long_lived_dir=self.ll_dir,
            long_lived_name="check_<id>_<name>.py",
            weakening_scope=[f"{f}/**/*.py"],
            mutation_claim_scope=[f"{f}/test_*.py"]),
            {f"{f}/sub/test_w.py": TWO_METHODS, "other/test_w.py": TWO_METHODS,
             f"{f}/test_v.py": fixture_test_class(
                 assertion="self.assertEqual(len('ab'), 2)")})

    def good_long_lived(self) -> str:
        return f"{self.ll_dir}/check_{self.TASK.lower()}_alpha.py"

    def test_ac6_weakening_in_profile_scope_refused_outside_not(self):
        """Удалённый метод теста в области `weakening_scope` профиля
        отклоняет `in_dev -> verifying`, тот же дифф вне области — нет.

        Ловит мутацию: у внешнего проекта гейт неослабления по-прежнему
        отключён (или смотрит в зашитую `tests/**/*.py`) — удаление в
        каталоге профиля проходит.
        """
        inside = f"{self.folder}/sub/test_w.py"
        self.set_branch({inside: ONE_METHOD})
        text, rows = self.advance_from("in_dev")
        found = refusals(rows, INTEGRITY)
        self.assertTrue(found and inside in found[0]["detail"], self.msg(text))
        self.set_branch({"other/test_w.py": ONE_METHOD})
        text, rows = self.advance_from("in_dev")
        self.assertEqual(refusals(rows, INTEGRITY), [], self.msg(text))

    def test_ac6_review_package_has_changed_assertions_section(self):
        """Изменённое утверждение метода в области профиля — пакет ревью
        несёт раздел изменённых утверждений с путём файла.

        Ловит мутацию: раздел собирается только для артели — у внешнего
        проекта с профилем его нет.
        """
        path = f"{self.folder}/test_v.py"
        self.set_branch({path: fixture_test_class(assertion="self.assertTrue(True)")})
        package, _rows = self.package()
        self.assertIn(review.CHANGED_ASSERTIONS_SECTION, package["text"])
        section = package["text"].split(review.CHANGED_ASSERTIONS_SECTION, 1)[1]
        self.assertIn(path, section, self.msg(section[:2000]))

    def test_ac6_merge_gate_weakening_step_runs_in_project_clone(self):
        """Удалённый метод теста в области профиля — `approve` гейта мержа
        останавливается шагом неослабления до ожидания CI, причина
        называет файл.

        Ловит мутацию: шаг неослабления гейта мержа включён только для
        артели (`is_artel`) — `approve` внешнего проекта доходит до
        ожидания CI.
        """
        inside = f"{self.folder}/sub/test_w.py"
        self.set_branch({inside: ONE_METHOD})
        text, _rows, finished = self.approve_merge()
        self.assertFalse(finished, self.msg(text))
        self.assertIn(inside, text, self.msg(text))

    def test_ac7_mutation_claim_in_profile_scope(self):
        """Новый тест без заявки в области `mutation_claim_scope` профиля
        отклоняет `in_dev -> verifying`, такой же файл вне области — нет.

        Ловит мутацию: гейт заявки мутации у внешнего проекта отключён
        либо смотрит в зашитую `tests/test_*.py` — отказ не приходит или
        приходит на `tests/`.
        """
        inside = f"{self.folder}/test_q.py"
        self.set_branch({inside: fixture_test_class(claim=False)})
        text, rows = self.advance_from("in_dev")
        found = refusals(rows, MUTATION)
        self.assertTrue(found and inside in found[0]["detail"], self.msg(text))
        self.set_branch({"tests/test_q.py": fixture_test_class(claim=False)})
        text, rows = self.advance_from("in_dev")
        self.assertEqual(refusals(rows, MUTATION), [], self.msg(text))

    def test_ac8_long_lived_by_profile_dir_and_name(self):
        """Долгоживущий файл по каталогу и шаблону профиля проходит выход
        из `tests_writing` и попадает в записанный перечень; файл в каталоге
        без префикса задачи — отказ гейта долгоживущих файлов.

        Ловит мутацию: у внешнего проекта долгоживущие файлы не
        проверяются (или префикс зашит `tests/test_<id>_`) — файл без
        префикса проходит, перечень не пишется.
        """
        bad = f"{self.ll_dir}/check_alpha.py"
        self.set_branch({bad: long_lived_text()})
        text, rows = self.advance_from("tests_writing")
        found = refusals(rows, LONG_LIVED)
        self.assertTrue(found and bad in found[0]["detail"], self.msg(text))
        self.set_branch({self.good_long_lived(): long_lived_text()})
        text, rows = self.advance_from("tests_writing")
        self.assertEqual(self.state(), "in_dev", self.msg(text))
        written = [r for r in rows if r["action"].startswith(MANIFEST)
                   and "записан" in r["action"]]
        self.assertTrue(written, self.msg(text))

    def test_ac8_plank_group_lines_checked(self):
        """Планка без строки группы у внешнего проекта с профилем — отказ
        выхода из `tests_writing` гейтом групп.

        Ловит мутацию: гейт строк группы включён только для артели — планка
        без строки группы проходит.
        """
        self.write_plank(plank_text(group=None))
        self.set_branch({})
        text, rows = self.advance_from("tests_writing")
        self.assertEqual(self.state(), "tests_writing", self.msg(text))
        self.assertTrue(refusals(rows, GROUPS), self.msg(text))

    def lock_docs(self, head_plank: str, manifest: dict | None = None) -> tuple:
        files = {"SPEC.md": SPEC.format(task=self.TASK),
                 "acceptance_tests/test_ac.py": plank_text()}
        if manifest is not None:
            files[f"acceptance_tests/{guard.LONG_LIVED_MANIFEST_NAME}"] = \
                guard.render_long_lived_manifest(manifest)
        locked = self.docs_commit(files)
        head = locked
        if head_plank != plank_text():
            head = self.docs_commit(dict(files, **{
                "acceptance_tests/test_ac.py": head_plank}), parent=locked)
        self.set_row(tests_locked_sha=locked)
        self.use_real_docs_ref(head)
        return locked, head

    def test_ac8_merge_approve_checks_plank_lock(self):
        """Планка в ссылке документов изменена после лока — `approve`
        гейта мержа отказывает сверкой лока до ожидания CI.

        Ловит мутацию: сверка лока на гейте мержа включена только для
        артели — `approve` доходит до ожидания CI.
        """
        self.set_branch({})
        self.lock_docs(plank_text(note=" Правка после лока."))
        text, rows, finished = self.approve_merge()
        self.assertFalse(finished, self.msg(text))
        self.assertTrue(refusals(rows, LOCK), self.msg(text))

    def test_ac8_merge_approve_checks_long_lived_manifest(self):
        """Долгоживущий файл ветки расходится с суммой в перечне лока —
        `approve` гейта мержа отказывает сверкой перечня до ожидания CI.

        Ловит мутацию: перечень у внешнего проекта не сверяется (или ищет
        файлы в зашитом `tests/`) — `approve` доходит до ожидания CI.
        """
        path = self.good_long_lived()
        self.set_branch({path: long_lived_text(note=" Голова ветки.")})
        self.lock_docs(plank_text(), manifest={path: "0" * 64})
        text, rows, finished = self.approve_merge()
        self.assertFalse(finished, self.msg(text))
        self.assertTrue(refusals(rows, MANIFEST) or MANIFEST in text,
                        self.msg(text))
        self.assertIn(path, text, self.msg(text))

    def test_ac8_amend_tests_checks_group_lines(self):
        """`amend-tests --from-branch`: правка планки снимает строку группы —
        отказ с именем файла, лок не сдвигается.

        Ловит мутацию: проверка строк группы в `amend-tests` включена
        только для артели — правка внешнего проекта принимается, лок
        сдвигается на голову ссылки.
        """
        self.set_branch({})
        locked, _head = self.lock_docs(plank_text(group=None))
        text, _rows, _finished = self.outcome(
            amend.cmd_amend_tests, self.TASK, "основание сценария", None, True)
        self.assertEqual(store.get_task(store.db(), self.TASK)["tests_locked_sha"],
                         locked, self.msg(text))
        self.assertIn("test_ac.py", text, self.msg(text))


class AmendRefusalTest(_Base):

    def prepare_amend(self) -> str:
        self.set_branch({})
        files = {"SPEC.md": SPEC.format(task=self.TASK),
                 "acceptance_tests/test_ac.py": plank_text()}
        locked = self.docs_commit(files)
        head = self.docs_commit(dict(files, **{
            "acceptance_tests/test_ac.py": plank_text(note=" Правка.")}),
            parent=locked)
        self.set_row(tests_locked_sha=locked)
        self.use_real_docs_ref(head)
        return locked

    def amend(self) -> str:
        text, _rows, _finished = self.outcome(
            amend.cmd_amend_tests, self.TASK, "основание сценария", None, True)
        return text

    def test_ac4_amend_tests_refused_for_artel_without_profile(self):
        """Артель без `test_profile`, законная правка планки — `amend-tests`
        отказывает с причиной про `targets.yaml` и поле, лок не сдвигается.

        Ловит мутацию: `amend-tests` без профиля артели пропускает проверку
        строк группы и принимает правку.
        """
        self.make_project(ARTEL, None)
        locked = self.prepare_amend()
        text = self.amend()
        self.assertEqual(store.get_task(store.db(), self.TASK)["tests_locked_sha"],
                         locked, self.msg(text))
        self.assertIn("targets.yaml", text, self.msg(text))
        self.assertIn("test_profile", text, self.msg(text))

    def test_ac9_amend_tests_refused_context_unresolved(self):
        """Проект задачи исчез из `targets.yaml` — `amend-tests` отказывает
        причиной «контекст проекта … не разрешён», лок не сдвигается.

        Ловит мутацию: неразрешённый контекст в `amend-tests` читается как
        «нет профиля» — правка принимается с записью о пропуске.
        """
        self.external(self.profile())
        locked = self.prepare_amend()
        del self.profiles[self.ext]
        self.write_targets()
        text = self.amend()
        self.assertEqual(store.get_task(store.db(), self.TASK)["tests_locked_sha"],
                         locked, self.msg(text))
        self.assertRegex(text, r"контекст проекта[^\n]*не разрешён", self.msg(text))


class ArtelRunInWorkCopyTest(_Base):

    def test_ac11_runs_in_task_work_copy_with_profile_command(self):
        """Артель с профилем, чья команда несёт свой флаг, рабочая копия на
        ветке задачи: сухой сбор и прогон приёмки идут в ней командой
        профиля.

        Ловит мутацию: прогон артели собирается зашитой командой пульта
        (флага профиля нет) либо идёт с `cwd` главной копии.
        """
        flag = self.rng.choice(["-x", "--strict-markers", "-rA"])
        self.make_project(ARTEL, self.profile(
            command=["python3", "-m", "pytest", flag]))
        wt = self.set_branch({})
        text, _rows = self.advance_from("tests_writing")
        words, cwd = self.pytest_call("collect")
        self.assert_profile_command(words, extra=(flag,))
        self.assertEqual(Path(cwd).resolve(), wt.resolve(), self.msg(text))
        text, _rows = self.advance_from("in_dev")
        words, cwd = self.pytest_call("run")
        self.assert_profile_command(words, extra=(flag,))
        self.assertEqual(Path(cwd).resolve(), wt.resolve(), self.msg(text))


class CanaryTest(_Base):

    def test_ac12_canary_artel_skips_weakening_mutation_and_section(self):
        """Канареечная задача артели с профилем: удалённый метод теста,
        тест без заявки и изменённое утверждение — ни отказа неослабления,
        ни отказа заявки мутации на `in_dev -> verifying`, раздела
        изменённых утверждений в пакете ревью нет.

        Ловит мутацию: снятие развилки по проекту сняло и отбор канарейки
        (`is_canary`) — канарейка получает отказ неослабления или заявки.
        """
        self.make_project(ARTEL, ARTEL_PROFILE, {"tests/test_old.py": TWO_METHODS,
                                                 "tests/test_v.py": TWO_METHODS})
        self.set_row(is_canary=1)
        self.set_branch({"tests/test_old.py": ONE_METHOD,
                         "tests/test_new.py": fixture_test_class(claim=False),
                         "tests/test_v.py": fixture_test_class(
                             assertion="self.assertTrue(True)")})
        text, rows = self.advance_from("in_dev")
        self.assertEqual(refusals(rows, INTEGRITY) + refusals(rows, MUTATION),
                         [], self.msg(text))
        package, _rows = self.package()
        self.assertNotIn(review.CHANGED_ASSERTIONS_SECTION, package["text"])


if __name__ == "__main__":
    unittest.main()
