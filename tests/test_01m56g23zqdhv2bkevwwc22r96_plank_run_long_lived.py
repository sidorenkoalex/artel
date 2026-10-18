"""`plank-run <id> <путь>` принимает путь долгоживущего файла своей задачи.

Группа: долгоживущий
Красен до реализации: `plank_run.cmd_plank_run` ищет `[файл]` только в планке — путь долгоживущего файла отклоняется «нет в планке», а при пустой планке — «планки нет», pytest не запускается (AC-5, AC-11); путь без файла получает тот же отказ вместо «файла нет в рабочей копии кода» (AC-10); AC-6 держит прежний исход и зелён с рождения.

Песочница — настоящий git (`tests.sandbox.RealGitSandbox`): клон артели —
сам репозиторий песочницы с bare `origin`, клон учебного внешнего проекта —
`tests.sandbox.make_project_repo` со своим `origin`. Профиль тестов артели —
`pult-pytest` с каталогом `tests`; профиль внешнего проекта — `runner:
pytest-own` со случайными `workdir` (не корень дерева) и `long_lived_dir`
под ним, своей командой (`python3 -m pytest` и случайный флаг `-o`).
Рабочая копия кода задачи — `workspace.ensure`; документы задачи —
каталог документов (каталог `<id>` под каталогом задач проекта в
`config.PROJECTS`), переносимый в
ссылку документов `checkpoint.commit_step_artifacts`.

Команда зовётся через `artel.main()`. Вызов pytest наблюдается подменой
`subprocess.run`/`subprocess.Popen`: argv, рабочий каталог и ответ
кодом выхода от зерна; прочие вызовы (git) идут настоящим `subprocess`.
Цель прогона распознаётся разрешением аргумента argv от рабочего
каталога вызова — представление пути (абсолютный или от `workdir`) не
предмет теста. Идентификаторы, имена и коды выхода — из `random`, зерно
печатается и входит в текст каждого провала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
путь, проходящий `Profile.is_long_lived` задачи, отбирается до отказа
«планки нет», без файла — отказ о рабочей копии кода, с файлом — после
тех же проверок документов и расхождения прогоняется `run_plank` с
профилем; все методы зелёные.
"""
import io
import os
import random
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from orchestrator import (artel, checkpoint, config, idgen, project_profile,
                          store, workspace)
from tests.sandbox import RealGitSandbox, artel_target_entry, make_project_repo

REAL_RUN = subprocess.run
REAL_POPEN = subprocess.Popen
ALPHABET = "abcdefghijklmnopqrstuvwxyz"
ARTEL = config.DEFAULT_TARGET
NOT_IN_PLANK = "нет в планке"
NO_PLANK = "планки нет"
NO_FILE_PLACE = "рабочей копии кода"
# Опции pytest и интерпретатора, чьё значение — следующий аргумент argv.
OPTIONS_WITH_VALUE = ("-m", "-p", "-o", "-c", "-k", "--rootdir", "--junitxml")

EXT_ENTRY = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
    test_profile:
      command: [python3, -m, pytest, -o, {flag}]
      long_lived_dir: {lld}
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [{lld}/**/*.py]
      mutation_claim_scope: [{lld}/test_*.py]
      report: junit-xml
      install: []
      runner: pytest-own
      workdir: {workdir}
"""

PLANK_TEXT = '''"""Фикстура планки песочницы."""
import unittest


class FixturePlankTest(unittest.TestCase):

    def test_ac1_fixture_{word}(self):
        self.assertEqual(1 + 1, 2)
'''

LONG_LIVED_TEXT = '''"""Фикстура долгоживущего файла песочницы."""
import unittest


class FixtureLongLivedTest(unittest.TestCase):

    def test_{word}(self):
        self.assertEqual(2 + 2, 4)

    def test_other_{word}(self):
        self.assertEqual(3 + 3, 6)
'''

SPEC_TEXT = "---\ntask: {task}\ntype: spec\n---\n# SPEC фикстуры\n"


def is_pytest(argv) -> bool:
    parts = [str(a) for a in argv] if isinstance(argv, (list, tuple)) else []
    return any(Path(p).name in ("pytest", "py.test") for p in parts) or any(
        a == "-m" and b == "pytest" for a, b in zip(parts, parts[1:]))


class SpyProc:
    """Процесс подменённого pytest: код выхода и вывод сценария."""
    pid = 2_000_000_000
    stdin = stdout = stderr = None

    def __init__(self, argv, code, text):
        self.args = argv
        self.returncode = code
        self.text = text

    def communicate(self, input=None, timeout=None):
        return self.text, ""

    def wait(self, timeout=None):
        return self.returncode

    def poll(self):
        return self.returncode

    def kill(self):
        pass

    terminate = kill

    def send_signal(self, sig):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class PlankLongLivedSandbox(RealGitSandbox):
    """Артель и учебный внешний проект с профилем `pytest-own`; задачи
    обоих проектов с рабочей копией кода."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.ext = f"sled{self.word()}"
        self.workdir = f"wd{self.word()}"
        self.ext_lld = f"{self.workdir}/t{self.word()}"
        self.flag = f"console_output_style={self.rng.choice(['classic', 'count'])}"
        self.add_synced_origin()
        config.TARGETS.write_text(
            "targets:\n" + artel_target_entry() + EXT_ENTRY.format(
                name=self.ext, base=config.MAIN_BRANCH, flag=self.flag,
                lld=self.ext_lld, workdir=self.workdir), encoding="utf-8")
        self.ext_clone = make_project_repo(self.ext)
        self.commit_to_main(self.ext_clone, {
            f"{self.ext_lld}/test_base_{self.word()}.py": "A = 1\n"})
        self.commit_to_main(self.root, {f"tests/test_base_{self.word()}.py":
                                        "A = 1\n"})
        self.calls: list = []
        self.code = 0
        self.fail_ls_tree = False

        def spy_run(argv, *args, **kwargs):
            if is_pytest(argv):
                self.record(argv, kwargs)
                return subprocess.CompletedProcess(
                    argv, self.code, self.pytest_output(), "")
            if self.fail_ls_tree and isinstance(argv, (list, tuple)) \
                    and "ls-tree" in [str(a) for a in argv]:
                text = kwargs.get("text") or kwargs.get("universal_newlines") \
                    or kwargs.get("encoding")
                empty = "" if text else b""
                err = "fatal: сбой чтения (песочница)"
                return subprocess.CompletedProcess(
                    argv, 128, empty, err if text else err.encode("utf-8"))
            return REAL_RUN(argv, *args, **kwargs)

        def spy_popen(argv, *args, **kwargs):
            if is_pytest(argv):
                self.record(argv, kwargs)
                return SpyProc(argv, self.code, self.pytest_output())
            return REAL_POPEN(argv, *args, **kwargs)

        for patcher in (mock.patch.object(subprocess, "run", spy_run),
                        mock.patch.object(subprocess, "Popen", spy_popen),
                        mock.patch.dict(os.environ,
                                        {config.ARTEL_ROLE_ENV: ""})):
            patcher.start()
            self.addCleanup(patcher.stop)

    # ------------------------------------------------------------ входы

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(ALPHABET) for _ in range(size))

    def exit_code(self) -> int:
        return self.rng.randrange(61, 100)

    def pytest_output(self) -> str:
        return f"1 passed in 0.01s (зерно {self.seed})\n"

    def record(self, argv, kwargs) -> None:
        cwd = kwargs.get("cwd")
        self.calls.append({"argv": [str(a) for a in argv],
                           "cwd": os.path.realpath(cwd if cwd is not None
                                                   else os.getcwd())})

    def commit_to_main(self, clone: Path, files: dict) -> None:
        for rel, text in files.items():
            path = clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("-C", str(clone), "add", "-A")
        self.git("-C", str(clone), "commit", "-q", "-m", "файлы проекта")
        self.git("-C", str(clone), "push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")

    def profile(self, target: str):
        profile = project_profile.decide(target).profile
        self.assertIsNotNone(profile, self.note(f"профиля {target} нет"))
        return profile

    def new_task(self, target: str, state: str) -> str:
        task_id = idgen.new_task_id()
        branch = f"task/{task_id.lower()}-{self.word()}"
        store.insert_task(self.conn, task_id, f"Фикстура {self.word()}", state,
                          branch, target, config.DEFAULT_BUDGET_USD)
        _wt, error = workspace.ensure(task_id, branch)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        self.commit_docs(task_id, {"SPEC.md": SPEC_TEXT.format(task=task_id)})
        return task_id

    def docs_dir(self, task_id: str) -> Path:
        return (config.PROJECTS / store.task_target(self.conn, task_id)
                / "tasks" / task_id)

    def wt(self, task_id: str) -> Path:
        return workspace.path(task_id, store.task_target(self.conn, task_id))

    def own_dir(self, task_id: str) -> Path:
        return self.wt(task_id) / "tasks" / task_id

    def write_docs(self, task_id: str, files: dict) -> None:
        for rel, text in files.items():
            path = self.docs_dir(task_id) / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def commit_docs(self, task_id: str, files: dict) -> None:
        """Файлы в каталог документов и в ссылку документов задачи."""
        self.write_docs(task_id, files)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            checkpoint.commit_step_artifacts(self.conn, task_id, "test_author")
        store.record_fixation(self.conn, task_id)

    def plank_name(self) -> str:
        return f"test_ac1_{self.word()}.py"

    def with_plank(self, task_id: str) -> str:
        """Планка из одного файла в источнике планки состояния задачи:
        черновик в `tests_writing`, ссылка документов — в прочих."""
        name = self.plank_name()
        files = {f"acceptance_tests/{name}": PLANK_TEXT.format(word=self.word())}
        if store.get_task(self.conn, task_id)["state"] == "tests_writing":
            self.write_docs(task_id, files)
        else:
            self.commit_docs(task_id, files)
        return name

    def own_long_lived(self, task_id: str, create: bool = True) -> tuple:
        """(путь от корня рабочей копии, имя теста в файле) долгоживущего
        файла своей задачи по префиксу профиля её проекта."""
        target = store.task_target(self.conn, task_id)
        rel = f"{self.profile(target).long_lived_prefix(task_id)}{self.word()}.py"
        self.assertTrue(self.profile(target).is_long_lived(task_id, rel),
                        self.note(f"{rel} — не долгоживущий файл задачи"))
        word = self.word()
        if create:
            path = self.wt(task_id) / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(LONG_LIVED_TEXT.format(word=word), encoding="utf-8")
        return rel, f"test_{word}"

    def put_in_code_copy(self, task_id: str, rel: str) -> None:
        path = self.wt(task_id) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(LONG_LIVED_TEXT.format(word=self.word()),
                        encoding="utf-8")

    # ------------------------------------------------------------ прогон

    def plank_run(self, task_id: str, *extra: str) -> tuple:
        """(код выхода, текст отказа или пусто, весь вывод) `artel.py
        plank-run <id> [путь]`; вызовы pytest — в `self.calls`."""
        self.calls = []
        argv = ["artel.py", "plank-run", task_id, *extra]
        out, err = io.StringIO(), io.StringIO()
        code = None
        with mock.patch.object(sys, "argv", argv), redirect_stdout(out), \
                redirect_stderr(err):
            try:
                artel.main()
            except SystemExit as exc:
                code = exc.code
        message = "" if code is None or isinstance(code, int) else str(code)
        status = code if isinstance(code, int) else (0 if code is None else 1)
        return status, message, "\n".join((out.getvalue(), err.getvalue(),
                                           message))

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def explain(self, output: str) -> str:
        calls = "\n".join(f"{c['argv']} @ {c['cwd']}" for c in self.calls)
        return self.note(f"вывод plank-run:\n{output[-3000:]}\n"
                         f"вызовы pytest:\n{calls}")

    def targets_of(self, call: dict) -> list:
        """(абсолютный путь, узел) аргументов-путей вызова pytest,
        разрешённых от его рабочего каталога."""
        found = []
        argv = call["argv"]
        for prev, arg in zip(argv, argv[1:]):
            if arg.startswith("-") or prev in OPTIONS_WITH_VALUE:
                continue
            path, _sep, node = arg.partition("::")
            found.append((os.path.realpath(os.path.join(call["cwd"], path)),
                          node))
        return found

    def assert_runs_file(self, task_id: str, rel: str, node: str,
                         output: str) -> None:
        """Ровно один вызов pytest, целью — файл `rel` рабочей копии
        (с узлом `node`, если он назван), планка задачи целью не служит."""
        self.assertEqual(len(self.calls), 1, self.explain(output))
        expected = os.path.realpath(self.wt(task_id) / rel)
        targets = self.targets_of(self.calls[0])
        self.assertIn((expected, node), targets,
                      self.explain(f"цель {rel}::{node} не прогонялась\n{output}"))
        plank = os.path.realpath(self.own_dir(task_id) / "acceptance_tests")
        layout = os.path.realpath(
            self.wt(task_id)
            / self.profile(store.task_target(self.conn, task_id)).long_lived_dir
            / ".artel-plank" / task_id)
        self.assertFalse(any(path == p or path.startswith(p + os.sep)
                             for path, _node in targets for p in (plank, layout)),
                         self.explain(f"прогонялась планка\n{output}"))

    def assert_refused_without_run(self, status, output: str, text: str) -> None:
        self.assertNotEqual(status, 0, self.explain(output))
        self.assertIn(text, output, self.explain(output))
        self.assertEqual(self.calls, [], self.explain(output))


class Ac5OwnProfileLongLivedRunTest(PlankLongLivedSandbox):

    def test_ac5_long_lived_path_runs_by_own_profile(self):
        """Путь долгоживущего файла своей задачи внешнего проекта прогоняется командой и в `workdir` профиля `pytest-own`.

        Сценарий: задача учебного проекта с `runner: pytest-own` (случайные
        `workdir`, каталог долгоживущих файлов под ним, своя команда с
        флагом `-o`) в трёх состояниях источника планки: `tests_writing`
        без черновика, `in_dev` без планки в ссылке документов и
        `tests_writing` с черновиком из одного `test_*.py`. Свой
        долгоживущий файл лежит в рабочей копии кода. `plank-run <id>
        <путь>` запускает pytest ровно раз: голова argv — команда профиля,
        рабочий каталог — `workdir` рабочей копии, цель — этот файл, планка
        целью не служит; код выхода команды — код прогона (от зерна). Тот
        же вызов с `<путь>::<тест>` прогоняет узел этого файла.

        Ловит мутацию: `[файл]` ищется только в планке — отказ «нет в
        планке» либо «планки нет», pytest не вызывался; путь прогоняется
        раннером пульта без профиля — голова argv — интерпретатор пульта,
        рабочий каталог — корень рабочей копии; узел `::тест` от пути
        переводится в `workdir` без своей части пути либо отбрасывается —
        цели `<файл>::<тест>` в разрешённых аргументах нет; код прогона
        не возвращается — статус 0 вместо кода от зерна.
        """
        profile = self.profile(self.ext)
        for state, plank in (("tests_writing", False), ("in_dev", False),
                             ("tests_writing", True)):
            with self.subTest(state=state, plank=plank, seed=self.seed):
                task_id = self.new_task(self.ext, state)
                if plank:
                    self.with_plank(task_id)
                rel, test_name = self.own_long_lived(task_id)
                for node in ("", test_name):
                    self.code = self.exit_code()
                    arg = f"{rel}::{node}" if node else rel
                    status, _message, output = self.plank_run(task_id, arg)
                    self.assertNotIn(NO_PLANK, output, self.explain(output))
                    self.assert_runs_file(task_id, rel, node, output)
                    call = self.calls[0]
                    self.assertEqual(call["argv"][:len(profile.command)],
                                     list(profile.command),
                                     self.explain(f"не команда профиля\n{output}"))
                    self.assertEqual(
                        call["cwd"],
                        os.path.realpath(self.wt(task_id) / self.workdir),
                        self.explain(f"не workdir профиля\n{output}"))
                    self.assertEqual(status, self.code, self.explain(output))


class Ac6PreviousOutcomeTest(PlankLongLivedSandbox):

    def foreign_paths(self, task_id: str) -> list:
        """Пути, не входящие ни в планку, ни в шаблон долгоживущего файла
        своей задачи: долгоживущий файл другой задачи, путь вне каталога
        `long_lived_dir`, имя вне шаблона."""
        target = store.task_target(self.conn, task_id)
        profile = self.profile(target)
        other = idgen.new_task_id()
        own_prefix = profile.long_lived_prefix(task_id)
        own_name = own_prefix[len(profile.long_lived_dir) + 1:]
        paths = [
            ("файл другой задачи",
             f"{profile.long_lived_prefix(other)}{self.word()}.py"),
            ("вне каталога",
             f"o{self.word()}/{own_name}{self.word()}.py"),
            ("имя вне шаблона",
             f"{profile.long_lived_dir}/check_{task_id.lower()}_{self.word()}.py"),
        ]
        for label, rel in paths:
            self.assertFalse(profile.is_long_lived(task_id, rel),
                             self.note(f"{label}: {rel} проходит шаблон"))
        return paths

    def test_ac6_foreign_paths_and_plain_calls_keep_previous_outcome(self):
        """Чужой путь — прежний отказ без прогона; вызов без аргумента и с файлом планки — прежний набор целей и код выхода.

        Сценарий для задачи артели и задачи учебного проекта с
        `pytest-own`: пути «долгоживущий файл другой задачи», «вне
        `long_lived_dir`», «имя вне шаблона» лежат в рабочей копии кода.
        При планке из одного файла каждый такой путь отклоняется «нет в
        планке», при пустом источнике планки — «планки нет»; pytest не
        запускается. Вызов без аргумента прогоняет каталог планки и не
        прогоняет свой долгоживущий файл, лежащий в рабочей копии; вызов с
        именем файла планки прогоняет этот файл; код выхода команды — код
        прогона (от зерна). Без планки вызов без аргумента — «планки нет».

        Ловит мутацию: шаблон долгоживущего файла сверяется без номера
        задачи или без каталога — чужой путь уходит в pytest, отказа нет;
        вызов без аргумента начинает гнать и долгоживущие файлы задачи —
        свой файл среди целей прогона; отказ «планки нет» снят для всех
        вызовов — пустая планка без аргумента запускает pytest.
        """
        for target in (ARTEL, self.ext):
            with self.subTest(target=target, seed=self.seed):
                empty = self.new_task(target, "tests_writing")
                status, _m, output = self.plank_run(empty)
                self.assert_refused_without_run(status, output, NO_PLANK)
                for label, rel in self.foreign_paths(empty):
                    self.put_in_code_copy(empty, rel)
                    status, _m, output = self.plank_run(empty, rel)
                    self.assert_refused_without_run(status, output, NO_PLANK)

                task_id = self.new_task(target, "in_dev")
                name = self.with_plank(task_id)
                own_rel, _test = self.own_long_lived(task_id)
                for label, rel in self.foreign_paths(task_id):
                    self.put_in_code_copy(task_id, rel)
                    status, _m, output = self.plank_run(task_id, rel)
                    self.assert_refused_without_run(status, output, NOT_IN_PLANK)

                self.code = self.exit_code()
                status, _m, output = self.plank_run(task_id)
                self.assertEqual(len(self.calls), 1, self.explain(output))
                targets = [p for p, _n in self.targets_of(self.calls[0])]
                plank = os.path.realpath(self.own_dir(task_id) / "acceptance_tests")
                if target == self.ext:
                    plank = os.path.realpath(
                        self.wt(task_id) / self.profile(target).long_lived_dir
                        / ".artel-plank" / task_id / "acceptance_tests")
                self.assertEqual(targets, [plank], self.explain(output))
                self.assertNotIn(os.path.realpath(self.wt(task_id) / own_rel),
                                 targets, self.explain(output))
                self.assertEqual(status, self.code, self.explain(output))

                self.code = self.exit_code()
                status, _m, output = self.plank_run(task_id, name)
                self.assertEqual(len(self.calls), 1, self.explain(output))
                targets = [p for p, _n in self.targets_of(self.calls[0])]
                self.assertEqual(targets, [os.path.join(plank, name)],
                                 self.explain(output))
                self.assertEqual(status, self.code, self.explain(output))


class Ac10MissingLongLivedFileTest(PlankLongLivedSandbox):

    def test_ac10_own_path_without_file_refused_by_name(self):
        """Путь долгоживущего файла своей задачи без файла в рабочей копии — именованный отказ «файла нет» без прогона.

        Сценарий для задачи артели и задачи учебного проекта, при пустом
        источнике планки и при планке из одного файла: путь проходит
        `Profile.is_long_lived` задачи, файла по нему в рабочей копии кода
        нет. `plank-run <id> <путь>` завершается ненулевым кодом, текст
        называет этот путь и рабочую копию кода, не говорит «нет в планке»
        и «планки нет»; pytest не вызывался.

        Ловит мутацию: наличие файла не проверяется — pytest запускается на
        несуществующем пути (вызов в `self.calls`); путь без файла уходит в
        прежнюю ветку планки — отказ «нет в планке»/«планки нет» вместо
        отказа о рабочей копии кода.
        """
        for target in (ARTEL, self.ext):
            for plank in (False, True):
                with self.subTest(target=target, plank=plank, seed=self.seed):
                    task_id = self.new_task(target, "tests_writing")
                    if plank:
                        self.with_plank(task_id)
                    rel, _test = self.own_long_lived(task_id, create=False)
                    status, _m, output = self.plank_run(task_id, rel)
                    self.assert_refused_without_run(status, output, rel)
                    self.assertIn(NO_FILE_PLACE, output, self.explain(output))
                    self.assertNotIn(NOT_IN_PLANK, output, self.explain(output))
                    self.assertNotIn(NO_PLANK, output, self.explain(output))


class Ac11RefusalsBeforeLayoutTest(PlankLongLivedSandbox):

    def compare_with_plain(self, task_id: str, rel: str, keep: Path) -> None:
        """Вызов с путём долгоживущего файла и без аргумента в одном
        состоянии: оба отказывают одним текстом без прогона, файл `keep`
        на месте с прежним содержимым."""
        before = keep.read_bytes() if keep is not None else None
        status, message, output = self.plank_run(task_id, rel)
        self.assertNotEqual(status, 0, self.explain(output))
        self.assertTrue(message, self.explain(f"нет текста отказа\n{output}"))
        self.assertEqual(self.calls, [], self.explain(output))
        if keep is not None:
            self.assertEqual(keep.read_bytes(), before,
                             self.explain(f"{keep} изменён\n{output}"))
        plain_status, plain_message, plain_output = self.plank_run(task_id)
        self.assertEqual(self.calls, [], self.explain(plain_output))
        self.assertEqual((status, message), (plain_status, plain_message),
                         self.explain(f"отказ не тот, что без аргумента:\n"
                                      f"{output}\n--- без аргумента:\n"
                                      f"{plain_output}"))
        if keep is not None:
            self.assertEqual(keep.read_bytes(), before,
                             self.explain(f"{keep} изменён\n{plain_output}"))

    def test_ac11_long_lived_path_passes_refusals_before_layout(self):
        """Вызов с путём своего долгоживущего файла проходит отказы до выкладки планки — тем же текстом, что без аргумента, без прогона.

        Сценарий для задачи артели и задачи учебного проекта, свой
        долгоживущий файл в рабочей копии кода, планка из одного файла:
        (а) в каталоге задачи под `tasks` рабочей копии кода лежит
        документ; (б) файл каталога `acceptance_tests` там же расходится с
        зафиксированной планкой ссылки документов; (в) чтение ссылки
        документов отказывает (`git ls-tree` подменённого git — код 128),
        а в каталоге планки рабочей копии лежит файл. Каждый раз вызов с
        путём — ненулевой код, pytest не запускался, документ или файл
        планки на месте с прежним содержимым, а текст отказа и код — те
        же, что у вызова без аргумента в том же состоянии.

        Ловит мутацию: ветка долгоживущего пути выходит на прогон раньше
        проверок документов, расхождения и чтения ссылки — pytest
        вызывается, выкладка и уборка стирают документ или правку планки;
        ветка несёт свою копию проверки с другим текстом — отказ отличается
        от отказа вызова без аргумента.
        """
        for target in (ARTEL, self.ext):
            with self.subTest(target=target, case="а", seed=self.seed):
                task_id = self.new_task(target, "in_dev")
                self.with_plank(task_id)
                rel, _test = self.own_long_lived(task_id)
                doc = self.own_dir(task_id) / "PLAN.md"
                doc.parent.mkdir(parents=True, exist_ok=True)
                doc.write_text(f"план {self.seed}\n", encoding="utf-8")
                self.compare_with_plain(task_id, rel, doc)

            with self.subTest(target=target, case="б", seed=self.seed):
                task_id = self.new_task(target, "in_dev")
                name = self.with_plank(task_id)
                rel, _test = self.own_long_lived(task_id)
                drift = self.own_dir(task_id) / "acceptance_tests" / name
                drift.parent.mkdir(parents=True, exist_ok=True)
                drift.write_text(PLANK_TEXT.format(word=self.word())
                                 + f"# правка {self.seed}\n", encoding="utf-8")
                self.compare_with_plain(task_id, rel, drift)

            with self.subTest(target=target, case="в", seed=self.seed):
                task_id = self.new_task(target, "tests_writing")
                name = self.with_plank(task_id)
                rel, _test = self.own_long_lived(task_id)
                disk = self.own_dir(task_id) / "acceptance_tests" / name
                disk.parent.mkdir(parents=True, exist_ok=True)
                disk.write_text(PLANK_TEXT.format(word=self.word()),
                                encoding="utf-8")
                self.fail_ls_tree = True
                try:
                    self.compare_with_plain(task_id, rel, disk)
                finally:
                    self.fail_ls_tree = False
