"""`amend-tests` проверяет правку линтом детерминизма, не отказывая за методы, залоченные до правки.

Группа: долгоживущий
Красен до реализации: `amend-tests` линта не зовёт — добавленный правкой метод с `time.sleep(1)` и изменённый залоченный метод со сном проходят без отказа на обоих путях (рабочая копия и `--from-branch`), для долгоживущего файла и файла планки; на `--from-branch` нет и отказа за метод первого из двух коммитов правки и за методы файла без ревизии с суммой лока. Случаи «правка другого метода — отказа нет» держат поведение, которое правка обязана сохранить, и зелёные.

Стенд — настоящий git (`tests/sandbox.py::GitignoreCommittedRealGitSandbox`,
тот же каркас, что `amend-tests` в
`tests/test_01m5633wz3y3a0p4kkbzdb3ker_long_lived_imports.py`): задача
артели заводится в БД пульта (`store.insert_task`) в `in_dev`, рабочая
копия кода — `workspace.ensure`. Лок: долгоживущий файл (если есть)
закоммичен в кодовую ветку, планка (и перечень сумм долгоживущего файла)
записана в каталог документов и перенесена в ссылку документов штатным
чекпоинтом шага, `tests_locked_sha` — голова ссылки.

Правка на пути рабочей копии — файлы в рабочей копии кода (планка — в
каталоге задачи рабочей копии, как её правит Оператор), затем
`amend.cmd_amend_tests`. Правка на пути `--from-branch` — коммит в
кодовую ветку (долгоживущий файл) или в ссылку документов (планка), затем
`amend.cmd_amend_tests(..., from_branch=True)`.

Нарушение — `time.sleep(1)` во вспомогательном методе класса (не `test_*`):
прогон планки и долгоживущих файлов его не исполняет. Имена файлов,
классов, методов и положение методов — от `random`; зерно печатается и
входит в текст провала. Отправка головы в origin подменена успехом (она
зовёт `gh`).
"""
import contextlib
import hashlib
import io
import keyword
import os
import random
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from orchestrator import (amend, checkpoint, config, github_adapter, store,
                          workspace)
from scripts import guard
from tests.sandbox import GitignoreCommittedRealGitSandbox

ULID_LETTERS = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LETTERS = "abcdefghijklmnopqrstuvwxyz"
DOCS_DIR = "tasks"
PLANK_DIR = "acceptance_tests"
DOCS_REF_PREFIX = "refs/artifacts/"
SLEEP_HIT = "time.sleep с ненулевой паузой"
SLEEP = "        time.sleep(1)"
CLEAN = "        return 1"


def ulid(rng: random.Random) -> str:
    return "01" + "".join(rng.choice(ULID_LETTERS) for _ in range(24))


def word(rng: random.Random, size: int = 7) -> str:
    while True:
        value = "".join(rng.choice(LETTERS) for _ in range(size))
        if not keyword.iskeyword(value) and value not in sys.stdlib_module_names:
            return value


def spec_text(task_id: str) -> str:
    return ("---\ntask: " + task_id + "\ntype: spec\nauthor_role: analyst\n"
            "status: ready\nschema_version: 5\n---\n\n"
            "# SPEC: фикстура линта в amend-tests\n\n## Контекст\n\n"
            "## Требования\n\n## Критерии приёмки\n\n"
            "AC-1. Критерий фикстуры.\n\n## Не входит\n")


class Fixture:
    """Файл фикстуры: класс с тестом `test_ac1_…` (заявка мутации есть) и
    вспомогательными методами `helpers` (имя -> тело)."""

    def __init__(self, rng: random.Random, group: str | None, helpers: dict):
        self.cls = "Fixture" + word(rng, 6).capitalize() + "Test"
        self.test = "test_ac1_" + word(rng, 6)
        self.group = group
        self.helpers = dict(helpers)

    def text(self) -> str:
        head = ['"""Фикстура линта в amend-tests.', ""]
        if self.group is not None:
            head += ["Группа: " + self.group]
        head += ["Зелёный " + "с рождения: фикстура песочницы.", '"""',
                 "import random", "import time", "import unittest", "", "",
                 f"class {self.cls}(unittest.TestCase):", "",
                 f"    def {self.test}(self):",
                 '        """Фикстурный метод.', "",
                 "        Ловит " + "мутацию: фикстура — сумма перестаёт совпадать.",
                 '        """',
                 "        seed = random.randrange(1 << 30)",
                 '        self.assertEqual(seed + 1, 1 + seed, f"зерно: {seed}")']
        for name, body in self.helpers.items():
            head += ["", f"    def {name}(self):", body]
        return "\n".join(head) + "\n"

    def line(self, method: str) -> int:
        """Строка нарушения метода `method` — первый вызов сна после его `def`."""
        lines = self.text().splitlines()
        start = next(i for i, line in enumerate(lines, 1)
                     if line.strip().startswith(f"def {method}("))
        return next(i for i, line in enumerate(lines, 1)
                    if i > start and "time.sleep(" in line)

    def address(self, label: str, method: str) -> str:
        return f"{label}::{self.cls}::{method}: строка {self.line(method)}"


class AmendLintSandbox(GitignoreCommittedRealGitSandbox):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop(config.ARTEL_ROLE_ENV, None)
        push = mock.patch.object(github_adapter, "ensure_head_in_origin",
                                 lambda *args, **kwargs: (True, ""))
        push.start()
        self.addCleanup(push.stop)
        self.add_synced_origin()
        self.conn = store.db()

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    # --- задача и лок -------------------------------------------------

    def new_task(self):
        tid = ulid(self.rng)
        branch = f"task/{tid.lower()}-amend-lint"
        store.insert_task(self.conn, tid, "Фикстура линта в amend-tests",
                          "in_dev", branch, config.DEFAULT_TARGET, 25.0)
        wt, error = workspace.ensure(tid, branch)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        t = SimpleNamespace(id=tid, branch=branch, wt=Path(wt))
        t.docs = config.PROJECTS / config.DEFAULT_TARGET / DOCS_DIR / tid
        t.plank = t.docs / PLANK_DIR
        t.plank.mkdir(parents=True, exist_ok=True)
        (t.docs / "SPEC.md").write_text(spec_text(tid), encoding="utf-8")
        t.plank_name = f"test_{word(self.rng, 6)}.py"
        t.plank_label = f"{PLANK_DIR}/{t.plank_name}"
        t.long_rel = "/".join(("tests", f"test_{tid.lower()}_{word(self.rng, 6)}.py"))
        return t

    def docs_head(self, t) -> str:
        return self.git("for-each-ref", "--format=%(objectname)",
                        DOCS_REF_PREFIX + t.id).strip()

    def commit_code(self, t, text: str, message: str) -> None:
        path = t.wt / t.long_rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self.git("-C", str(t.wt), "add", "--", t.long_rel)
        self.git("-C", str(t.wt), "commit", "-q", "-m", message)

    def commit_docs(self, t, files: dict) -> None:
        for name, text in files.items():
            (t.plank / name).write_text(text, encoding="utf-8")
        checkpoint.commit_step_artifacts(self.conn, t.id, "developer")

    def lock(self, t, plank, long_lived=None, manifest_text=None) -> None:
        """Лок: `long_lived` (Fixture) — в кодовой ветке, планка `plank`
        (Fixture) с перечнем суммы долгоживущего файла — в ссылке
        документов; `manifest_text` — текст, чью сумму пишет перечень
        (по умолчанию — закоммиченный файл)."""
        files = {t.plank_name: plank.text()}
        if long_lived is not None:
            self.commit_code(t, long_lived.text(), "долгоживущий файл")
            data = (manifest_text if manifest_text is not None
                    else long_lived.text()).encode("utf-8")
            files[guard.LONG_LIVED_MANIFEST_NAME] = guard.render_long_lived_manifest(
                {t.long_rel: hashlib.sha256(data).hexdigest()})
        self.commit_docs(t, files)
        head = self.docs_head(t)
        self.assertTrue(head, self.note("ссылки документов нет"))
        store.update_task(self.conn, t.id, tests_locked_sha=head)
        store.record_fixation(self.conn, t.id)
        t.locked = head

    # --- правки -------------------------------------------------------

    def edit_worktree_plank(self, t, plank) -> None:
        """Правка Оператора в каталоге задачи рабочей копии кода."""
        target = t.wt / DOCS_DIR / t.id / PLANK_DIR
        target.mkdir(parents=True, exist_ok=True)
        (target / t.plank_name).write_text(plank.text(), encoding="utf-8")

    def commit_docs_ref(self, t, plank) -> None:
        """Правка планки коммитом в ссылку документов мимо пульта:
        отдельная рабочая копия на её голове и `update-ref`."""
        old = self.docs_head(t)
        scratch = Path(tempfile.mkdtemp(prefix="artel-docs-copy-"))
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        copy = scratch / "copy"
        self.git("worktree", "add", "-q", "--detach", str(copy), old)
        try:
            path = copy.joinpath(DOCS_DIR, t.id, PLANK_DIR, t.plank_name)
            path.write_text(plank.text(), encoding="utf-8")
            self.git("-C", str(copy), "add", "-A")
            self.git("-C", str(copy), "commit", "-q", "-m", f"{t.id}: правка планки")
            new = self.git("-C", str(copy), "rev-parse", "HEAD").strip()
        finally:
            self.git("worktree", "remove", "--force", str(copy))
        self.git("update-ref", DOCS_REF_PREFIX + t.id, new, old)
        # Автокоммит шага пульт фиксирует сам — сверка фиксации его признаёт.
        store.record_fixation(self.conn, t.id)

    def edit_worktree_long_lived(self, t, long_lived) -> None:
        (t.wt / t.long_rel).write_text(long_lived.text(), encoding="utf-8")

    def amend(self, t, from_branch: bool = False) -> tuple:
        """(вывод вместе с текстом отказа, был ли ненулевой `SystemExit`)."""
        buf = io.StringIO()
        refused = False
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                amend.cmd_amend_tests(t.id, f"правка {self.seed}",
                                      from_branch=from_branch)
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    refused = True
                    buf.write(f"\n{exc.code}")
        return buf.getvalue(), refused

    # --- утверждения --------------------------------------------------

    def locked_now(self, t) -> str:
        return store.get_task(self.conn, t.id)["tests_locked_sha"]

    def assert_refused_at(self, t, out: str, refused: bool, address: str,
                          what: str) -> None:
        self.assertTrue(refused, self.note(f"{what}: правка принята:\n{out}"))
        self.assertIn(address, out, self.note(
            f"{what}: отказ не называет «{address}»:\n{out}"))
        self.assertEqual(self.locked_now(t), t.locked, self.note(
            f"{what}: лок сдвинут"))

    def assert_no_lint_refusal(self, t, out: str, refused: bool, what: str) -> None:
        self.assertNotIn(SLEEP_HIT, out, self.note(
            f"{what}: отказ линта за метод, залоченный до правки:\n{out}"))
        self.assertFalse(refused, self.note(f"{what}: правка отклонена:\n{out}"))
        self.assertNotEqual(self.locked_now(t), t.locked, self.note(
            f"{what}: лок не сдвинут:\n{out}"))

    def assert_plank_address_form(self, t, out: str, what: str) -> None:
        wrong = "/".join((DOCS_DIR, t.id, t.plank_label)) + "::"
        self.assertNotIn(wrong, out, self.note(
            f"{what}: адрес нарушения планки — метка снимка «{wrong}»:\n{out}"))

    # --- фикстуры -----------------------------------------------------

    def locked_pair(self, group: str | None):
        """Фикстура с залоченным методом со сном и чистым методом."""
        settle, other = word(self.rng, 6), word(self.rng, 6)
        return Fixture(self.rng, group, {settle: SLEEP, other: CLEAN}), settle, other

    def clean_plank(self):
        return Fixture(self.rng, guard.GROUP_ONE_OFF, {word(self.rng, 6): CLEAN})


class WorktreeLongLivedTest(AmendLintSandbox):

    def setUp(self):
        super().setUp()
        self.t = self.new_task()
        self.f, self.settle, self.other = self.locked_pair(guard.GROUP_LONG_LIVED)
        self.lock(self.t, self.clean_plank(), self.f)

    def test_ac6_worktree_long_lived_other_method_edit_passes(self):
        """Рабочая копия: долгоживущий файл залочен с методом со сном; правка другого метода — отказа линта нет, лок сдвинут.

        Сценарий: в рабочей копии кода тело чистого вспомогательного метода
        переписано (иное значение возврата), залоченный метод со сном не
        тронут, строки выше него не сдвинуты. `amend-tests` принимает
        правку: текста линта в выводе нет, `tests_locked_sha` сдвинут.

        Ловит мутацию: `amend-tests` не передаёт `lint_base` (или передаёт
        не голову кодовой ветки до правки) — залоченный метод со сном даёт
        отказ «time.sleep с ненулевой паузой».
        """
        self.f.helpers[self.other] = "        return 2"
        self.edit_worktree_long_lived(self.t, self.f)

        out, refused = self.amend(self.t)

        self.assert_no_lint_refusal(self.t, out, refused, "правка другого метода")

    def test_ac6_worktree_long_lived_added_sleep_method_refused(self):
        """Рабочая копия: правка добавляет в долгоживущий файл метод с `time.sleep(1)` — отказ с адресом этого метода.

        Сценарий: к залоченному файлу правкой дописан новый
        вспомогательный метод со сном. `amend-tests` отказывает ненулевым
        кодом; отказ называет «<файл>::<Класс>::<новый метод>: строка N»;
        лок прежний.

        Ловит мутацию: линт не подключён к пути рабочей копии `amend-tests`
        либо гасит нарушения всех методов файла, который есть в базе, —
        правка принята, лок сдвинут.
        """
        added = word(self.rng, 6)
        self.f.helpers[added] = SLEEP
        self.edit_worktree_long_lived(self.t, self.f)

        out, refused = self.amend(self.t)

        self.assert_refused_at(self.t, out, refused,
                               self.f.address(self.t.long_rel, added),
                               "добавленный метод со сном")

    def test_ac6_worktree_long_lived_changed_locked_method_refused(self):
        """Рабочая копия: залоченный метод со сном изменён правкой и всё ещё спит — отказ с адресом этого метода.

        Сценарий: тело залоченного метода переписано (пауза из переменной,
        вызов сна остался). `amend-tests` отказывает; отказ называет
        «<файл>::<Класс>::<метод>: строка N» этого метода; лок прежний.

        Ловит мутацию: гашение по одному имени «Класс::метод» без сравнения
        `ast.dump` узла — изменённый метод молчит, правка принята.
        """
        self.f.helpers[self.settle] = "        pause = 1\n        time.sleep(pause)"
        self.edit_worktree_long_lived(self.t, self.f)

        out, refused = self.amend(self.t)

        self.assert_refused_at(self.t, out, refused,
                               self.f.address(self.t.long_rel, self.settle),
                               "изменённый залоченный метод")


class WorktreePlankTest(AmendLintSandbox):

    def lock_plank(self, group):
        self.t = self.new_task()
        self.f, self.settle, self.other = self.locked_pair(group)
        self.lock(self.t, self.f)

    def test_ac6_worktree_plank_other_method_edit_passes(self):
        """Рабочая копия: файл планки артели залочен с методом со сном; правка другого метода — отказа линта нет, лок сдвинут.

        Сценарий: в каталоге задачи рабочей копии файл планки переписан —
        изменено тело чистого вспомогательного метода, метод со сном не
        тронут. `amend-tests` принимает правку: текста линта нет, лок
        сдвинут.

        Ловит мутацию: метки базы (`<каталог задачи>/acceptance_tests/…` снимка)
        и проверяемых файлов (`acceptance_tests/…`) не приведены к одной
        форме — база не находится, залоченный метод со сном даёт отказ.
        """
        self.lock_plank(guard.GROUP_ONE_OFF)
        self.f.helpers[self.other] = "        return 2"
        self.edit_worktree_plank(self.t, self.f)

        out, refused = self.amend(self.t)

        self.assert_no_lint_refusal(self.t, out, refused, "правка другого метода планки")

    def test_ac6_worktree_plank_added_sleep_method_refused(self):
        """Рабочая копия: правка планки добавляет метод с `time.sleep(1)` — отказ с адресом `acceptance_tests/…` этого метода.

        Сценарий: в файл планки (группа «разовый», лок со строками группы)
        дописан новый вспомогательный метод со сном. `amend-tests`
        отказывает; отказ называет «acceptance_tests/<файл>::<Класс>::<метод>:
        строка N» и не несёт метки `<каталог задачи>/acceptance_tests/<файл>::`;
        лок прежний.

        Ловит мутацию: линт файлов планки на пути рабочей копии не
        подключён (только долгоживущие файлы) — правка принята; адрес
        собран из метки снимка — подстроки `acceptance_tests/…` в начале
        адреса нет.
        """
        self.lock_plank(guard.GROUP_ONE_OFF)
        added = word(self.rng, 6)
        self.f.helpers[added] = SLEEP
        self.edit_worktree_plank(self.t, self.f)

        out, refused = self.amend(self.t)

        self.assert_refused_at(self.t, out, refused,
                               self.f.address(self.t.plank_label, added),
                               "добавленный метод планки")
        self.assert_plank_address_form(self.t, out, "добавленный метод планки")

    def test_ac6_worktree_plank_without_group_lines_still_linted(self):
        """Рабочая копия: планка без строк группы (ранний выход проверки групп) — добавленный метод со сном всё равно даёт отказ.

        Сценарий: залоченная планка и её правка не несут строки «Группа:»
        (проверка строк группы `amend-tests` выходит рано, планка «до
        правила»); правка дописывает вспомогательный метод со сном.
        `amend-tests` отказывает с адресом
        «acceptance_tests/<файл>::<Класс>::<метод>: строка N»; лок прежний.

        Ловит мутацию: ошибки линта планки считаются внутри проверки строк
        группы после её раннего выхода — у планки без строк группы линт не
        исполняется, правка принята.
        """
        self.lock_plank(None)
        added = word(self.rng, 6)
        self.f.helpers[added] = SLEEP
        self.edit_worktree_plank(self.t, self.f)

        out, refused = self.amend(self.t)

        self.assert_refused_at(self.t, out, refused,
                               self.f.address(self.t.plank_label, added),
                               "планка без строк группы")


class FromBranchPlankTest(AmendLintSandbox):

    def setUp(self):
        super().setUp()
        self.t = self.new_task()
        self.f, self.settle, self.other = self.locked_pair(guard.GROUP_ONE_OFF)
        self.lock(self.t, self.f)

    def test_ac6_from_branch_plank_added_sleep_method_refused(self):
        """`--from-branch`: на голове ссылки документов в файл планки добавлен метод со сном — отказ с адресом `acceptance_tests/…`.

        Сценарий: файл планки, залоченный с методом со сном, правлен
        коммитом в ссылку документов — дописан новый вспомогательный
        метод со сном. `amend-tests --from-branch` отказывает; отказ
        называет «acceptance_tests/<файл>::<Класс>::<метод>: строка N» и не
        несёт `<каталог задачи>/acceptance_tests/<файл>::`; лок прежний.

        Ловит мутацию: на пути `--from-branch` линт планки не подключён —
        лок сдвинут на голову; адрес нарушения — метка снимка
        `<каталог задачи>/acceptance_tests/…`.
        """
        added = word(self.rng, 6)
        self.f.helpers[added] = SLEEP
        self.commit_docs_ref(self.t, self.f)

        out, refused = self.amend(self.t, from_branch=True)

        self.assert_refused_at(self.t, out, refused,
                               self.f.address(self.t.plank_label, added),
                               "--from-branch, метод планки")
        self.assert_plank_address_form(self.t, out, "--from-branch, метод планки")

    def test_ac6_from_branch_plank_other_method_edit_passes(self):
        """`--from-branch`: на голове ссылки документов правлен другой метод залоченного файла планки — отказа линта нет.

        Сценарий: коммитом в ссылку документов изменено тело чистого
        вспомогательного метода, метод со сном не тронут.
        `amend-tests --from-branch` принимает правку: текста линта нет, лок
        сдвинут на голову ссылки.

        Ловит мутацию: на пути `--from-branch` база не передаётся (или её
        метки `<каталог задачи>/acceptance_tests/…` не приведены к меткам файлов)
        — залоченный метод со сном даёт отказ.
        """
        self.f.helpers[self.other] = "        return 2"
        self.commit_docs_ref(self.t, self.f)

        out, refused = self.amend(self.t, from_branch=True)

        self.assert_no_lint_refusal(self.t, out, refused,
                                    "--from-branch, другой метод планки")


class FromBranchLongLivedTest(AmendLintSandbox):

    def lock_long_lived(self, manifest_text=None):
        self.t = self.new_task()
        self.f, self.settle, self.other = self.locked_pair(guard.GROUP_LONG_LIVED)
        self.lock(self.t, self.clean_plank(), self.f, manifest_text=manifest_text)

    def test_ac6_from_branch_long_lived_added_sleep_method_refused(self):
        """`--from-branch`: на голове кодовой ветки в долгоживущий файл добавлен метод со сном — отказ с адресом этого метода.

        Сценарий: долгоживущий файл залочен с методом со сном; коммитом в
        кодовую ветку дописан новый вспомогательный метод со сном.
        `amend-tests --from-branch` отказывает; отказ называет
        «<файл>::<Класс>::<метод>: строка N»; лок прежний.

        Ловит мутацию: линт долгоживущих файлов не подключён к пути
        `--from-branch` — лок сдвинут.
        """
        self.lock_long_lived()
        added = word(self.rng, 6)
        self.f.helpers[added] = SLEEP
        self.commit_code(self.t, self.f.text(), "правка: метод со сном")

        out, refused = self.amend(self.t, from_branch=True)

        self.assert_refused_at(self.t, out, refused,
                               self.f.address(self.t.long_rel, added),
                               "--from-branch, долгоживущий файл")

    def test_ac6_from_branch_long_lived_other_method_edit_passes(self):
        """`--from-branch`: на голове кодовой ветки правлен другой метод залоченного долгоживущего файла — отказа линта нет.

        Сценарий: коммитом в кодовую ветку изменено тело чистого
        вспомогательного метода, метод со сном не тронут.
        `amend-tests --from-branch` принимает правку: текста линта нет, лок
        сдвинут.

        Ловит мутацию: на пути `--from-branch` база долгоживущего файла не
        передаётся (голова кодовой ветки уже несёт правку) — залоченный
        метод со сном даёт отказ.
        """
        self.lock_long_lived()
        self.f.helpers[self.other] = "        return 2"
        self.commit_code(self.t, self.f.text(), "правка другого метода")

        out, refused = self.amend(self.t, from_branch=True)

        self.assert_no_lint_refusal(self.t, out, refused,
                                    "--from-branch, другой метод")

    def test_ac6_from_branch_two_commits_first_added_method_refused(self):
        """`--from-branch`: правка двумя коммитами после лока — метод со сном из первого коммита даёт отказ с адресом.

        Сценарий: первый коммит кодовой ветки после лока дописывает
        вспомогательный метод со сном, второй — меняет тело чистого
        метода. База — ревизия с суммой blob из перечня лока (коммит
        лока), поэтому `amend-tests --from-branch` отказывает и называет
        «<файл>::<Класс>::<метод первого коммита>: строка N»; лок прежний.

        Ловит мутацию: базой взят родитель головы (ревизия первого
        коммита), а не ревизия с суммой из перечня лока — метод первого
        коммита там уже есть с тем же узлом, нарушение гасится, лок сдвинут.
        """
        self.lock_long_lived()
        added = word(self.rng, 6)
        self.f.helpers[added] = SLEEP
        self.commit_code(self.t, self.f.text(), "правка 1: метод со сном")
        self.f.helpers[self.other] = "        return 2"
        self.commit_code(self.t, self.f.text(), "правка 2: другой метод")

        out, refused = self.amend(self.t, from_branch=True)

        self.assert_refused_at(self.t, out, refused,
                               self.f.address(self.t.long_rel, added),
                               "--from-branch, два коммита")

    def test_ac6_from_branch_no_locked_revision_checks_all_methods(self):
        """`--from-branch`: в истории кодовой ветки нет ревизии файла с суммой перечня лока — нарушения отдаются для всех методов.

        Сценарий: перечень лока несёт сумму текста, которого в истории
        кодовой ветки нет (закоммичен файл без последней строки
        перечневого текста); голова — тот же закоммиченный файл с
        залоченным методом со сном. `amend-tests --from-branch`
        отказывает и называет «<файл>::<Класс>::<метод со сном>: строка N»;
        лок прежний.

        Ловит мутацию: без ревизии с суммой лока базой служит иная ревизия
        (родитель головы, любая ревизия, где файл был) — метод со сном
        гасится, лок сдвинут.
        """
        self.t = self.new_task()
        self.f, self.settle, self.other = self.locked_pair(guard.GROUP_LONG_LIVED)
        self.lock(self.t, self.clean_plank(), self.f,
                  manifest_text=self.f.text() + f"# не в истории {self.seed}\n")

        out, refused = self.amend(self.t, from_branch=True)

        self.assert_refused_at(self.t, out, refused,
                               self.f.address(self.t.long_rel, self.settle),
                               "--from-branch, ревизии с суммой нет")


if __name__ == "__main__":
    unittest.main()
