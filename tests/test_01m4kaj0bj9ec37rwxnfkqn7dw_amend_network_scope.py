"""`amend-tests` применяет признак сетевых адресов к долгоживущим файлам только у артели.

Группа: долгоживущий
Красен до реализации: `amend-tests` зовёт узел проверки долгоживущих файлов без признака проекта (умолчание — адреса ловятся всегда), поэтому чужой проект получает отказ по инварианту 35 (AC-2) и AC-3 видит в отказе ошибку адреса; AC-1 (артель по-прежнему получает отказ) и AC-4 (мутация «вызов без признака» даёт отказ по адресу) держат поведение, которое правка обязана сохранить, и зелёные.

Сценарий на настоящем git (тот же каркас, что у
`tests/test_01m4jd36367e5cg3gxdv429xte_amend_pult.py`): пульт — `self.root`;
задача артели заводится `catalog.cmd_new`; в её кодовой ветке закоммичен
долгоживущий файл, планка лока в ссылке документов несёт SPEC.md с одним
критерием, файл `test_*.py` и перечень суммы долгоживущего файла;
`tests_locked_sha` стоит на коммите планки. Оператор правит долгоживущий
файл в рабочей копии кода — вписывает строку с адресом по DNS-имени — и
зовёт `amend.cmd_amend_tests`.

Чужой проект — та же задача под подменой признака проекта
`repo_context.is_artel` (никто не артель), как допускает критерий AC-2.
Отправка головы кодовой ветки в origin (`github_adapter.
ensure_head_in_origin`) подменена успехом: она вне предмета, а настоящая
зовёт `gh`. Адрес собран по частям (`SEP`) — сам этот файл лежит в
`tests/` и обязан проходить инвариант 35. Положение строки адреса, прочие
ошибки долгоживущего файла и текст правки — из `random`, зерно печатается
и входит в текст провала.
"""
import contextlib
import hashlib
import io
import os
import random
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (amend, catalog, config, github_adapter, projects,
                          repo_context, store, workspace)
from scripts import guard
from tests.sandbox import GitignoreCommittedRealGitSandbox

SEP = ":" + "//"
ADDRESS = f"https{SEP}example.test/x"
INVARIANT = "инвариант 35"
REF_PREFIX = "refs/artifacts/"
PLANK = "test_plank.py"

SPEC_TEMPLATE = """---
task: TASK_ID
type: spec
author_role: analyst
status: ready
schema_version: 5
---

# SPEC: <название задачи>

## Контекст

## Требования

## Критерии приёмки

AC-1. Фикстурный критерий песочницы.

## Не входит
"""

PLANK_TEXT = '''"""Фикстура разового файла планки.

Группа: разовый
Зелёный с рождения: фикстура песочницы.
"""
import unittest


class FixturePlankTest(unittest.TestCase):

    def test_ac1_fixture_plank(self):
        """Фикстурный метод планки."""
        self.assertEqual(2 + 2, 4)
'''

LONG_LIVED_HEAD = '''"""Фикстура долгоживущего файла песочницы.

Группа: долгоживущий
"""
import random
import unittest
'''

LONG_LIVED_BODY = '''

class FixtureLongLivedTest(unittest.TestCase):

    def test_ac1_long_fixture(self):
        """Фикстурный метод долгоживущего файла.
CLAIM
        """
        seed = random.randrange(1 << 30)
        self.assertEqual(1 + 1, 2, f"зерно: {seed}")
'''

CLAIM_LINE = "\n        Ловит мутацию: фикстура песочницы — сумма перестаёт совпадать.\n"

# Прочие ошибки проверки долгоживущих файлов (AC-3): каждая — своя правка
# фикстуры и подстрока, по которой отказ её называет.
OTHER_ERRORS = {
    "метод без «Ловит мутацию»": ({"claim": False}, "Ловит мутацию"),
    "литерал каталога задач": ({"extra": 'DATA_DIR = "tasks" "/"\n'},
                               "tasks"),
}

TITLES = ("Правка долгоживущего файла", "Адрес в тестах", "Фиксация правки")


def long_lived_text(address_at: int = -1, claim: bool = True,
                    extra: str = "", tag: str = "") -> str:
    """Текст долгоживущего файла фикстуры; `address_at` ≥ 0 — строка с
    адресом после стольких строк-комментариев за импортами."""
    head = LONG_LIVED_HEAD
    if address_at >= 0:
        head += "".join(f"# строка-заполнитель {i}\n" for i in range(address_at))
        head += f'ADDRESS = "{ADDRESS}"\n'
    head += extra
    body = LONG_LIVED_BODY.replace("CLAIM", CLAIM_LINE if claim else "")
    return head + body + (f"# {tag}\n" if tag else "")


def nobody_is_artel(*args, **kwargs) -> bool:
    """Подмена признака проекта: задача — чужого проекта."""
    return False


class AmendNetworkScopeSandbox(GitignoreCommittedRealGitSandbox):
    """Задача артели с долгоживущим файлом в кодовой ветке и планкой лока
    с его перечнем; правку долгоживущего файла кладёт сам тест."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

        config.TARGETS.write_text(
            "targets:\n" + _artel_entry(), encoding="utf-8")
        self.run_cmd(projects.cmd_target_init, config.DEFAULT_TARGET)
        self.run_cmd(catalog.cmd_init)
        self.use_role_map()
        templates = self.root / ".artel" / "templates-fixture"
        templates.mkdir(parents=True, exist_ok=True)
        (templates / "SPEC.md").write_text(SPEC_TEMPLATE, encoding="utf-8")
        for patcher in (
                mock.patch.object(config, "TEMPLATES", templates),
                mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}),
                mock.patch("orchestrator.doctor.preflight_checks",
                           lambda *args, **kwargs: []),
                mock.patch.object(github_adapter, "ensure_head_in_origin",
                                  lambda *args, **kwargs: (True, ""))):
            patcher.start()
            self.addCleanup(patcher.stop)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.task_id = catalog.cmd_new(self.rng.choice(TITLES),
                                           target=config.DEFAULT_TARGET)
        self.branch = store.get_task(store.db(), self.task_id)["branch"]
        self.git("branch", self.branch, config.MAIN_BRANCH)
        self.wt, error = workspace.ensure(self.task_id, self.branch)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        self.long_rel = f"tests/test_{self.task_id.lower()}_fixture.py"
        self.lock_plank()

    # --- обвязка -------------------------------------------------------

    def note(self, text: str) -> str:
        return f"{text} (зерно {self.seed})"

    def run_cmd(self, fn, *args, **kwargs) -> tuple[str, bool]:
        """(вывод вместе с текстом отказа, был ли ненулевой `SystemExit`)."""
        buf = io.StringIO()
        refused = False
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fn(*args, **kwargs)
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    refused = True
                    buf.write(f"\n{exc.code}")
        return buf.getvalue(), refused

    def ref(self) -> str:
        return REF_PREFIX + self.task_id

    def head(self) -> str:
        return self.git("for-each-ref", "--format=%(objectname)",
                        self.ref()).strip()

    def locked(self) -> str:
        return store.get_task(store.db(), self.task_id)["tests_locked_sha"]

    def commit_docs(self, files: dict, message: str) -> None:
        """Коммит `files` (путь внутри каталога задачи -> текст) в ссылку
        документов: отдельная рабочая копия на её голове и `update-ref`."""
        old = self.head()
        self.assertTrue(old, self.note(f"ссылки {self.ref()} нет"))
        scratch = Path(tempfile.mkdtemp(prefix="artel-docs-copy-"))
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        copy = scratch / "copy"
        self.git("worktree", "add", "-q", "--detach", str(copy), old)
        try:
            for rel, text in files.items():
                path = copy.joinpath("tasks", self.task_id, rel)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            self.git("-C", str(copy), "add", "-A")
            self.git("-C", str(copy), "commit", "-q", "-m",
                     f"{self.task_id}: {message}")
            new = self.git("-C", str(copy), "rev-parse", "HEAD").strip()
        finally:
            self.git("worktree", "remove", "--force", str(copy))
        self.git("update-ref", self.ref(), new, old)

    def lock_plank(self) -> None:
        """Долгоживущий файл без адреса в кодовой ветке, планка с его
        перечнем в ссылке документов, лок на её коммите."""
        path = self.wt / self.long_rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(long_lived_text(), encoding="utf-8")
        self.git("-C", str(self.wt), "add", "--", self.long_rel)
        self.git("-C", str(self.wt), "commit", "-q", "-m", "долгоживущий файл")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.commit_docs({
            "SPEC.md": SPEC_TEMPLATE.replace("TASK_ID", self.task_id),
            "acceptance_tests/" + PLANK: PLANK_TEXT,
            "acceptance_tests/" + guard.LONG_LIVED_MANIFEST_NAME:
                guard.render_long_lived_manifest({self.long_rel: digest}),
        }, "планка")
        store.update_task(store.db(), self.task_id,
                          tests_locked_sha=self.head())
        store.record_fixation(store.db(), self.task_id)
        self.locked_before = self.locked()
        self.head_before = self.head()

    def edit_long_lived(self, **kwargs) -> int:
        """Правка Оператора: долгоживущий файл с адресом в рабочей копии;
        возвращает номер строки адреса."""
        text = long_lived_text(address_at=self.rng.randrange(0, 6),
                               tag=f"правка {self.rng.randrange(1 << 20)}",
                               **kwargs)
        (self.wt / self.long_rel).write_text(text, encoding="utf-8")
        return next(i for i, line in enumerate(text.splitlines(), 1)
                    if ADDRESS in line)

    def amend(self) -> tuple[str, bool]:
        return self.run_cmd(amend.cmd_amend_tests, self.task_id,
                            f"правка долгоживущего файла {self.seed}")

    def amend_events(self) -> int:
        return sum(1 for s in store.task_steps(store.db(), self.task_id)
                   if amend.AMEND_ACTION in s["action"])

    def foreign(self):
        return mock.patch.object(repo_context, "is_artel", nobody_is_artel)

    def assert_refused_untouched(self, out: str, refused: bool, what: str) -> None:
        self.assertTrue(refused, self.note(f"{what}: правка принята:\n{out}"))
        self.assertEqual(self.locked(), self.locked_before, self.note(
            f"{what}: лок сдвинут"))
        self.assertEqual(self.head(), self.head_before, self.note(
            f"{what}: ссылка документов изменена:\n{out}"))
        self.assertEqual(self.amend_events(), 0, self.note(
            f"{what}: событие правки планки записано"))

    def assert_no_address_error(self, out: str, what: str) -> None:
        self.assertNotIn(INVARIANT, out, self.note(
            f"{what}: ошибка признака сетевых адресов у чужого проекта:\n{out}"))
        self.assertNotIn(ADDRESS, out, self.note(
            f"{what}: адрес назван в выводе:\n{out}"))


def _artel_entry() -> str:
    """Запись артели с профилем тестов (долгоживущие файлы — `tests/`)."""
    return (f"  {config.DEFAULT_TARGET}:\n"
            f"    forge: github\n"
            f"    url: file:///nonexistent/{config.DEFAULT_TARGET}\n"
            f"    base: {config.MAIN_BRANCH}\n"
            f"    token_slot: {config.DEFAULT_TARGET}-token\n"
            f"    no_paths: []\n"
            f"    project_skills: []\n"
            f"    merge_gate: operator\n"
            f"    test_profile:\n"
            f"      command: [python3, -m, pytest]\n"
            f"      long_lived_dir: tests\n"
            f"      long_lived_name: test_<id>_<name>.py\n"
            f"      weakening_scope: [tests/**/*.py]\n"
            f"      mutation_claim_scope: [tests/test_*.py]\n"
            f"      report: junit-xml\n"
            f"      install: []\n")


class ArtelAddressRefusedTest(AmendNetworkScopeSandbox):

    def test_ac1_artel_long_lived_address_refused_with_file_line(self):
        """Артель: правка долгоживущего файла с адресом по DNS-имени — отказ с файлом, строкой и инвариантом 35.

        Сценарий: признак проекта не подменён (задача артели). Оператор
        вписывает в долгоживущий файл строку с адресом (её номер — из
        `random`). `amend-tests` отказывает ненулевым кодом; текст отказа
        несёт `<путь файла>:<номер строки адреса>` и «инвариант 35»; лок и
        голова ссылки документов прежние, события правки планки нет.

        Ловит мутацию: `amend-tests` передаёт узлу `network_addresses=False`
        всегда (или признак проекта перевёрнут) — у артели правка с адресом
        проходит, лок сдвигается.
        """
        line = self.edit_long_lived()

        out, refused = self.amend()

        self.assert_refused_untouched(out, refused, "артель, адрес")
        self.assertIn(INVARIANT, out, self.note(
            f"отказ не ссылается на инвариант 35:\n{out}"))
        self.assertIn(f"{self.long_rel}:{line}", out, self.note(
            f"отказ не называет файл и строку {line}:\n{out}"))


class ForeignAddressAllowedTest(AmendNetworkScopeSandbox):

    def test_ac2_foreign_long_lived_address_not_refused(self):
        """Чужой проект: та же правка с адресом проходит без ошибки признака адресов.

        Сценарий: тот же долгоживущий файл с адресом, но признак проекта
        подменён — задача чужого проекта. `amend-tests` завершается без
        отказа; в выводе нет ни «инвариант 35», ни самого адреса; лок
        сдвинут на новую голову ссылки документов, событие правки планки
        записано ровно одно.

        Ловит мутацию: `amend-tests` зовёт узел проверки долгоживущих
        файлов без признака проекта (умолчание `True`) — чужой проект
        получает отказ «… сетевой адрес … (инвариант 35)», лок не сдвинут.
        """
        self.edit_long_lived()

        with self.foreign():
            out, refused = self.amend()

        self.assert_no_address_error(out, "чужой проект")
        self.assertFalse(refused, self.note(f"правка отклонена:\n{out}"))
        self.assertNotEqual(self.locked(), self.locked_before, self.note(
            f"лок не сдвинут:\n{out}"))
        self.assertEqual(self.locked(), self.head(), self.note(
            "лок не на голове ссылки документов"))
        self.assertEqual(self.amend_events(), 1, self.note(
            "событие правки планки не одно"))


class ForeignOtherErrorsKeptTest(AmendNetworkScopeSandbox):

    def test_ac3_foreign_other_long_lived_errors_still_refused(self):
        """Чужой проект: прочие ошибки долгоживущего файла с адресом по-прежнему дают отказ.

        Сценарий: признак проекта подменён (чужой проект); долгоживущий
        файл несёт адрес и ещё одну ошибку проверки долгоживущих файлов —
        метод без «Ловит мутацию» или литерал каталога задач (каждый
        вариант — отдельный подтест). `amend-tests` отказывает ненулевым
        кодом, текст отказа называет файл и эту ошибку и не несёт
        «инвариант 35»; лок и ссылка документов прежние.

        Ловит мутацию: для чужого проекта снят не один признак адресов, а
        вся проверка долгоживущих файлов (узел не зовётся, либо его ошибки
        отброшены) — правка с прочей ошибкой проходит, лок сдвигается.
        """
        for label, (kwargs, needle) in OTHER_ERRORS.items():
            with self.subTest(ошибка=label):
                self.edit_long_lived(**kwargs)

                with self.foreign():
                    out, refused = self.amend()

                self.assert_refused_untouched(out, refused, label)
                self.assertIn(self.long_rel, out, self.note(
                    f"{label}: отказ не называет файл:\n{out}"))
                self.assertIn(needle, out, self.note(
                    f"{label}: отказ не называет ошибку:\n{out}"))
                self.assertNotIn(INVARIANT, out, self.note(
                    f"{label}: ошибка признака адресов у чужого проекта:\n{out}"))


class MutationWithoutFlagCaughtTest(AmendNetworkScopeSandbox):

    def test_ac4_call_without_project_flag_reddens_ac2(self):
        """Мутация «вызов узла без признака проекта» даёт у чужого проекта отказ по адресу — наблюдение AC-2 краснеет.

        Сценарий: сценарий AC-2 (чужой проект, долгоживущий файл с адресом),
        но узел `guard.long_lived_errors_from_files` подменён обёрткой,
        которая отбрасывает `network_addresses` и зовёт настоящий узел с
        умолчанием `True`, — ровно мутация критерия. Обёртка позвана;
        `amend-tests` отказывает, текст отказа несёт «инвариант 35» и
        `<путь файла>:<строка адреса>`, лок прежний — то есть проверки AC-2
        («нет ошибки признака», «лок сдвинут») на этой мутации падают.

        Ловит мутацию: признак адресов у чужого проекта снят мимо узла
        (ошибки адреса вырезаются из его вывода всегда, либо узел не
        зовётся вовсе) — вызов без признака больше не даёт отказа, и
        мутация критерия проходит незамеченной.
        """
        line = self.edit_long_lived()
        real = guard.long_lived_errors_from_files
        calls = []

        def without_flag(files, task_id, **kwargs):
            calls.append(kwargs)
            return real(files, task_id)

        with self.foreign(), mock.patch.object(
                guard, "long_lived_errors_from_files", without_flag):
            out, refused = self.amend()

        self.assertTrue(calls, self.note(
            "amend-tests не позвал узел проверки долгоживущих файлов"))
        self.assert_refused_untouched(out, refused, "мутация без признака")
        self.assertIn(INVARIANT, out, self.note(
            f"мутация без признака не дала отказа по адресу:\n{out}"))
        self.assertIn(f"{self.long_rel}:{line}", out, self.note(
            f"отказ мутации не называет файл и строку {line}:\n{out}"))


if __name__ == "__main__":
    unittest.main()
