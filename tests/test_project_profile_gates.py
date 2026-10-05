"""Гейты тестов у внешнего проекта: запись о пропуске проверки без профиля
и значения неартельного профиля на гейтах (SPEC 01M45FJVGQT1K0P8HDEXZX6HS7,
требования 3 и 5; REVIEW.md итерации 1, R1-F1).

Песочница — `TaskIdSchemaConnTmpRootTest` с задачей внешнего проекта в БД и
его записью в `config.TARGETS` песочницы; git гейтов подменён примитивами
`gitcmd`, как в `tests/test_mutation_claim_gate.py` и
`tests/test_test_integrity_gate.py`. Журнал — настоящий `store.journal`.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (config, fsm_advance, gitcmd,  # noqa: E402
                          project_profile, review, store)
from orchestrator.advance_gates import acceptance as acceptance_gates  # noqa: E402
from orchestrator.advance_gates import tests_writing  # noqa: E402
from tests.sandbox import TaskIdSchemaConnTmpRootTest, declare_target  # noqa: E402

TARGET = "sled"
CODE_BRANCH = "task/t001-x"
ARTIFACT_BRANCH = "artifact/t001"
BASE = "basesha"

# Профиль, отличный от артельного во всех подполях, которые читают гейты.
FOREIGN_PROFILE = """    test_profile:
      command: [python3, -m, pytest]
      long_lived_dir: checks
      long_lived_name: check_<id>_<name>.py
      weakening_scope: [checks/**/*.py]
      mutation_claim_scope: [checks/**/test_*.py]
      report: junit-xml
      install: []
"""

ALPHA = '''import unittest


class AlphaTest(unittest.TestCase):

    def test_one(self):
        pass
'''

NO_CLAIM = "def test_new():\n    assert True\n"


class _ExternalTaskTest(TaskIdSchemaConnTmpRootTest):
    """Задача проекта `sled`; `PROFILE` — хвост его записи в
    `targets.yaml` (пусто — профиля нет)."""

    PROFILE = ""

    def setUp(self):
        super().setUp()
        declare_target(TARGET)
        if self.PROFILE:
            # Запись проекта — последняя в файле: профиль дописывается к ней.
            text = config.TARGETS.read_text(encoding="utf-8")
            config.TARGETS.write_text(text.rstrip("\n") + "\n" + self.PROFILE,
                                      encoding="utf-8")
        store.insert_task(self.conn, self.task_id, "Задача", "in_dev",
                          CODE_BRANCH, TARGET, 25.0)
        self.t = {"branch": CODE_BRANCH, "target": TARGET, "is_canary": False}

    def journal(self):
        return [(row["action"], row["detail"]) for row in self.conn.execute(
            "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
            (self.task_id,))]

    def assert_skip_recorded(self, check):
        action = f"{project_profile.SKIP_ACTION}: {check}"
        details = [detail for act, detail in self.journal() if act == action]
        self.assertEqual(1, len(details), self.journal())
        self.assertIn(f"«{TARGET}»", details[0])
        self.assertIn("нет test_profile", details[0])


def _no_git(*args, **kwargs):
    raise AssertionError("проекту без профиля гейт не читает git")


class SkipIsJournaledTest(_ExternalTaskTest):
    """Проект без профиля: каждая пропущенная проверка — запись в журнале
    задачи с названием проверки и причиной (требование 3)."""

    def test_mutation_claim_gate_journals_skip(self):
        """Ловит мутацию: `journal_skip` не пишет запись (тело — `return`)
        или гейт заявки мутации пропускает проверку без вызова — пропуск у
        проекта без профиля становится молчаливым."""
        with mock.patch.object(gitcmd, "diff_base", _no_git):
            self.assertIsNone(fsm_advance._mutation_claim_gate(
                self.conn, self.task_id, self.t, CODE_BRANCH))
        self.assert_skip_recorded(project_profile.CHECK_MUTATION)

    def test_weakening_gate_journals_skip(self):
        """Ловит мутацию: гейт неослабления на переходе возвращает `None`
        у проекта без профиля, не записав пропуск в журнал."""
        with mock.patch.object(gitcmd, "diff_base", _no_git):
            self.assertIsNone(fsm_advance._test_integrity_gate(
                self.conn, self.task_id, self.t, ARTIFACT_BRANCH))
        self.assert_skip_recorded(project_profile.CHECK_WEAKENING)

    def test_manifest_check_journals_skip(self):
        """Ловит мутацию: сверка перечня долгоживущих файлов у залоченной
        задачи проекта без профиля пропускается без записи в журнал."""
        store.update_task(self.conn, self.task_id, tests_locked_sha="locksha")
        with mock.patch.object(gitcmd, "ls_tree_files", _no_git), \
                mock.patch.object(gitcmd, "branch_head_sha", _no_git):
            self.assertFalse(acceptance_gates._long_lived_manifest_refuses(
                self.conn, self.task_id))
        self.assert_skip_recorded(project_profile.CHECK_MANIFEST)

    def test_review_package_section_journals_skip(self):
        """Ловит мутацию: раздел изменённых утверждений пакета ревью у
        проекта без профиля заменяется пометкой без записи в журнал, либо
        пометка о пропуске пропадает из пакета."""
        part = review._changed_assertions_part(
            self.conn, self.task_id, CODE_BRANCH, ARTIFACT_BRANCH, TARGET,
            "run")
        self.assertIsNotNone(part)
        self.assertIn("нет test_profile", part)
        self.assert_skip_recorded(project_profile.CHECK_ASSERTIONS_SECTION)


class ForeignProfileMutationClaimTest(_ExternalTaskTest):
    """Область заявки мутации — `mutation_claim_scope` профиля проекта, а
    не зашитое `tests/test_*.py` артели (требование 5)."""

    PROFILE = FOREIGN_PROFILE

    def refusal(self, files):
        def fake_show(ref, path, repo=None):
            if ref == BASE:
                return None, "новый файл"
            return NO_CLAIM, ""

        with mock.patch.object(gitcmd, "diff_base", return_value=BASE), \
                mock.patch.object(gitcmd, "diff_names", return_value=files), \
                mock.patch.object(gitcmd, "show", fake_show):
            return fsm_advance._mutation_claim_gate(
                self.conn, self.task_id, self.t, CODE_BRANCH)

    def test_file_in_profile_scope_needs_claim(self):
        """Ловит мутацию: гейт отбирает файлы зашитым фильтром
        `tests/test_*.py` вместо `profile.in_mutation_claim_scope` — тест
        без заявки в `checks/unit/` проекта проходит переход."""
        refusal = self.refusal(["checks/unit/test_a.py"])
        self.assertIsNotNone(refusal)
        self.assertIn("checks/unit/test_a.py: test_new", refusal.detail)

    def test_artel_path_outside_profile_scope_needs_no_claim(self):
        """Ловит мутацию: к области профиля добавлена артельная
        `tests/test_*.py` (или фильтр зашит) — файл вне области заявки
        проекта требует заявки."""
        self.assertIsNone(self.refusal(["tests/test_x.py"]))


class ForeignProfileWeakeningTest(_ExternalTaskTest):
    """Область гейта неослабления — `weakening_scope` профиля проекта
    (требование 5, AC-6): тот же дифф вне области отказа не даёт."""

    PROFILE = FOREIGN_PROFILE

    def refusal(self, path):
        sources = {(BASE, path): ALPHA}

        def fake_show(ref, rel, repo=None):
            if (ref, rel) in sources:
                return sources[(ref, rel)], ""
            return None, "файла нет в этой ветке"

        def fake_git(*args):
            return subprocess.CompletedProcess(args, 0, "\n", "")

        with mock.patch.object(gitcmd, "diff_base", return_value=BASE), \
                mock.patch.object(gitcmd, "diff_name_status",
                                  return_value=[("D", path, None)]), \
                mock.patch.object(gitcmd, "show", fake_show), \
                mock.patch.object(gitcmd, "ls_tree_files", return_value=[]), \
                mock.patch.object(gitcmd, "git", fake_git):
            return fsm_advance._test_integrity_gate(
                self.conn, self.task_id, self.t, ARTIFACT_BRANCH)

    def test_deletion_in_profile_scope_refuses(self):
        """Ловит мутацию: гейт зовёт узел без `scope=` профиля (область по
        умолчанию `tests/**/*.py` артели) — удаление тестов в `checks/`
        проекта проходит переход."""
        refusal = self.refusal("checks/test_alpha.py")
        self.assertIsNotNone(refusal)
        self.assertIn("checks/test_alpha.py: удалён", refusal.detail)

    def test_same_deletion_outside_profile_scope_passes(self):
        """Ловит мутацию: область гейта — объединение профиля с артельной
        `tests/**/*.py` — тот же дифф вне области профиля даёт отказ."""
        self.assertIsNone(self.refusal("tests/test_alpha.py"))


class ForeignProfileLongLivedPathTest(unittest.TestCase):
    """Каталог и шаблон имени долгоживущего файла на выходе
    `tests_writing` — из профиля проекта (требование 5, AC-8)."""

    TASK = "01M45FJVGQT1K0P8HDEXZX6HS7"

    def setUp(self):
        self.profile = project_profile.Profile(
            command=("python3", "-m", "pytest"), long_lived_dir="checks",
            long_lived_name="check_<id>_<name>.py",
            weakening_scope=("checks/**/*.py",),
            mutation_claim_scope=("checks/**/test_*.py",))
        self.lower = self.TASK.lower()

    def error(self, path):
        return tests_writing._diff_entry_error(self.TASK, "A", path, None,
                                               self.profile)

    def test_path_by_profile_template_is_legal(self):
        """Ловит мутацию: `_diff_entry_error` сверяет каталог с зашитым
        `tests/` либо признак долгоживущего файла (`Profile.is_long_lived`)
        берёт артельные каталог и шаблон — законный долгоживущий файл
        проекта отклоняется."""
        self.assertIsNone(self.error(f"checks/check_{self.lower}_gates.py"))

    def test_artel_directory_is_outside_profile_directory(self):
        """Ловит мутацию: каталог долгоживущих файлов зашит как `tests/` —
        файл артельного вида вне каталога профиля проходит выход."""
        error = self.error(f"tests/test_{self.lower}_gates.py")
        self.assertIsNotNone(error)
        self.assertIn("вне checks/", error)

    def test_artel_name_in_profile_directory_has_no_task_prefix(self):
        """Ловит мутацию: сверка имени по шаблону профиля пропущена для
        файла в каталоге профиля (или каталог зашит как `tests/`) — файл
        `checks/` с именем не по шаблону проекта проходит выход, а подсказка
        не называет шаблон профиля."""
        error = self.error(f"checks/test_{self.lower}_gates.py")
        self.assertIsNotNone(error)
        self.assertIn(f"checks/check_{self.lower}_<имя>.py", error)


if __name__ == "__main__":
    unittest.main()
