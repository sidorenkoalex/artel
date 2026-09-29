"""Юнит-тесты `amend-tests` для долгоживущих файлов задачи в `tests/`
(SPEC 01M3NSZ4YWZW9SD5Y6H62ATGRV, требования 1-4; ADR-0020, задача 3):
правка из worktree — проверки до записей, записи (а) коммит кодовой ветки
-> (б) перечень по новой голове в ветке документов -> (в) сдвиг лока;
границы правки; правило удаления; сбой между записями и восстановление
`--from-branch`; одно событие `AMEND_ACTION` на успешный вызов. Плюс
свойства вне приёмочных критериев: допуск красной планки рядом с зелёным
долгоживущим файлом, отказ при непрочитанном перечне лока, перечень в
обход команды без иной правки, незакоммиченная правка worktree при
`--from-branch`.

Планка задачи целиком разовая и после мержа не исполняется — эти тесты
держат ядро команды вместо неё (R1-F1 REVIEW.md итерации 1).

Песочница — `_TransitionSandbox` задачи 2 (настоящий git: пульт с веткой
документов, bare `origin`, worktree кодовой ветки); задача залочена
настоящим выходом из `tests_writing` с непустым перечнем.
"""
import contextlib
import hashlib
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import amend, artifact_branch, gitcmd, store  # noqa: E402
from orchestrator.advance_gates import acceptance as acceptance_gates  # noqa: E402
from scripts import guard  # noqa: E402
from tests.test_long_lived_transitions import (  # noqa: E402
    _TransitionSandbox, capture_call, long_lived_source, plank_source)

MANIFEST_NAME = guard.LONG_LIVED_MANIFEST_NAME

RED_MARKED_PLANK = '''"""Фикстура разового файла планки, ещё без кода под собой.

Группа: разовый
Красен до реализации: фикстура песочницы — кода ещё нет.
"""
import unittest


class FixturePlankTest(unittest.TestCase):

    def test_ac1_plank_fixture(self):
        """Фикстурный метод."""
        self.assertEqual(1 + 1, 3)
'''

# Правка Оператора: каждый параметр ломает ровно одну проверку требования 1.
EDIT_TEMPLATE = '''"""Правка долгоживущего файла песочницы.

{group_line}
"""
import random
import unittest


class FixtureLongLivedTest(unittest.TestCase):

    def {method}(self):
        """Фикстурный метод.
{claim}
        """
        seed = random.randrange(1 << 30)
        self.assertEqual(1 + 1, {rhs}, f"зерно: {{seed}}")
{tail}'''

CLAIM = "\n        Ловит мутацию: фикстура песочницы — сумма перестаёт совпадать.\n"


def edited_source(method: str = "test_ac1_long_fixture", *,
                  group: str | None = "долгоживущий", claim: bool = True,
                  rhs: str = "2", tail: str = "# правка Оператора\n") -> str:
    return EDIT_TEMPLATE.format(
        group_line=f"Группа: {group}" if group else "Без строки группы.",
        method=method, claim=CLAIM if claim else "", rhs=rhs, tail=tail)


class _LockedSandbox(_TransitionSandbox):

    def own_source(self) -> str:
        """Текст долгоживущего файла перечня на момент лока."""
        return long_lived_source()

    def setUp(self):
        super().setUp()
        self.lock_with_own(self.own_source())
        self.docs_branch = artifact_branch.branch_name(self.TASK)
        self.plank_rel = f"tasks/{self.TASK}/acceptance_tests/test_ac1_plank.py"
        self.plank_dir = self.wt / "tasks" / self.TASK / "acceptance_tests"
        self.new_path = f"tests/test_{self.TASK.lower()}_beta.py"

    def heads(self) -> tuple:
        return (gitcmd.branch_head_sha(self.branch),
                gitcmd.branch_head_sha(self.docs_branch),
                self.row()["tests_locked_sha"])

    def amend_events(self) -> int:
        return sum(1 for s in store.task_steps(store.db(), self.TASK)
                   if amend.AMEND_ACTION in s["action"])

    def write_wt(self, rel: str, text: str) -> None:
        path = self.wt / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def amend(self, **kwargs) -> str:
        return capture_call(amend.cmd_amend_tests, self.TASK, "правка",
                            **kwargs)

    def manifest_at(self, rev: str) -> str | None:
        text, _reason = gitcmd.show(
            rev, acceptance_gates.long_lived_manifest_rel(self.TASK))
        return text

    def long_lived_paths_at(self, rev: str) -> list[str]:
        return sorted(p for p in gitcmd.ls_tree_files(rev, "tests") or []
                      if guard.is_long_lived_test_path(self.TASK, p))

    def expected_manifest(self, code_head: str) -> str:
        """Перечень по байтам долгоживущих файлов головы кодовой ветки."""
        return guard.render_long_lived_manifest(
            {p: acceptance_gates.blob_sha256(code_head, p)
             for p in self.long_lived_paths_at(code_head)})

    def changed_paths(self, old: str, new: str) -> set[str]:
        return set(gitcmd.git("diff", "--name-only", old, new).stdout.split())

    def manifest_check_refuses(self) -> tuple[bool, str]:
        """Сверка сумм — тот же узел, что на переходах и на гейте мержа."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            refused = acceptance_gates._long_lived_manifest_refuses(
                store.db(), self.TASK)
        return refused, buf.getvalue()

    def materialize_plank(self) -> None:
        prefix = f"tasks/{self.TASK}/acceptance_tests/"
        for rel, text in artifact_branch.read_tree(self.TASK).items():
            if rel.startswith(prefix):
                self.write_wt(rel, text)

    def restore_wt(self) -> None:
        """Worktree — к голове кодовой ветки, планка на диске — к голове
        ветки документов: исходная точка очередного сценария."""
        self.wt_git("checkout", "-q", "--", "tests")
        self.wt_git("clean", "-q", "-fd", "--", "tests", "docs")
        if self.plank_dir.is_dir():
            for f in sorted(self.plank_dir.rglob("*"), reverse=True):
                if f.is_file():
                    f.unlink()
        self.materialize_plank()

    @contextlib.contextmanager
    def docs_branch_write_fails(self):
        """Запись под `tasks/<id>/` плотницким коммитом (путь ветки
        документов) не удаётся; прочие записи идут настоящим git."""
        real = artifact_branch.write_commit
        prefix = f"tasks/{self.TASK}/"

        def failing(repo, files, *args, **kwargs):
            touched = list(files) + list(kwargs.get("remove") or [])
            if any(str(rel).startswith(prefix) for rel in touched):
                return ""
            return real(repo, files, *args, **kwargs)

        with mock.patch.object(artifact_branch, "write_commit", failing):
            yield

    def assert_relocked(self, before: tuple, paths: set[str], out: str) -> None:
        """Записи (а)-(в) прошли: коммит кодовой ветки ровно с `paths`,
        перечень лока — суммы новой головы, сверка сумм проходит, одно
        событие правки планки."""
        self.assertNotIn("SystemExit", out)
        code_old, docs_old, _lock_old = before
        code_new, docs_new, lock_new = self.heads()
        self.assertEqual(self.changed_paths(code_old, code_new), paths, out)
        self.assertNotEqual(docs_new, docs_old, out)
        self.assertEqual(lock_new, docs_new)
        self.assertEqual(self.manifest_at(lock_new),
                         self.expected_manifest(code_new))
        refused, text = self.manifest_check_refuses()
        self.assertFalse(refused, text)
        self.assertEqual(self.amend_events(), 1)

    def assert_refused_untouched(self, before: tuple, out: str,
                                 *needles: str) -> None:
        self.assertIn("SystemExit", out)
        for needle in needles:
            self.assertIn(needle, out)
        self.assertEqual(self.heads(), before, out)
        self.assertEqual(self.amend_events(), 0, out)


class WorktreeModeTest(_LockedSandbox):

    def test_green_long_lived_next_to_red_marked_plank_passes(self):
        """Оператор правит долгоживущий файл (зелёный, без маркера
        красноты) и одновременно кладёт в планку файл «Красен до
        реализации», который падает: правка проходит, лок сдвинут.

        Ловит мутацию: маркер красноты требуется от каждого долгоживущего
        файла красного прогона, а не только от упавшего — зелёный
        долгоживущий файл без маркера отклоняет правку.
        """
        before = self.heads()
        self.write_wt(self.plank_rel, RED_MARKED_PLANK)
        self.write_wt(self.own, long_lived_source(tag="правка Оператора"))

        out = self.amend()

        self.assertNotIn("SystemExit", out)
        self.assertNotEqual(self.heads()[2], before[2], out)
        self.assertEqual(self.amend_events(), 1)

    def test_unreadable_manifest_refuses_long_lived_edit(self):
        """Перечень в дереве лока испорчен; Оператор правит долгоживущий
        файл — отказ, называющий непрочитанный перечень, без записей и без
        события правки планки.

        Ловит мутацию: ветка «перечень не прочитан» снята — непрочитанный
        перечень трактуется как «долгоживущих файлов нет», и отказ
        приходит как «изменения за пределами», не называя причину.
        """
        artifact_branch.commit_files(
            self.TASK, {acceptance_gates.long_lived_manifest_rel(self.TASK):
                        "мусор\n"}, "испорченный перечень")
        self.set_row(tests_locked_sha=gitcmd.branch_head_sha(self.docs_branch))
        before = self.heads()
        self.write_wt(self.own, long_lived_source(tag="правка Оператора"))

        out = self.amend()

        self.assertIn("SystemExit", out)
        self.assertIn("перечень долгоживущих файлов лока не прочитан", out)
        self.assertEqual(self.heads(), before)
        self.assertEqual(self.amend_events(), 0)

    def test_modified_and_added_long_lived_relocked(self):
        """Оператор правит файл перечня и добавляет новый
        `tests/test_<id>_beta.py`: коммит кодовой ветки меняет ровно эти
        два пути, перечень лока — суммы новой головы (новый файл в нём),
        лок на голове ветки документов, сверка сумм проходит, одно событие
        правки планки.

        Ловит мутацию: перечень пересчитан по старой голове кодовой ветки
        (или только по путям старого перечня) — перечень лока расходится
        с файлами головы, и сверка сумм отказывает.
        """
        before = self.heads()
        self.write_wt(self.own, edited_source())
        self.write_wt(self.new_path, edited_source("test_ac1_second_fixture"))

        out = self.amend()

        self.assert_relocked(before, {self.own, self.new_path}, out)
        self.assertIn(self.new_path, self.manifest_at(self.heads()[2]))

    def test_failed_check_refused_before_any_write(self):
        """Правка долгоживущего файла, нарушающая одну проверку требования 1
        (строка группы, статический признак `tasks/`, «Ловит мутацию»,
        сухой сбор, непромаркированное падение), — отказ с именем файла;
        головы обеих веток и лок прежние, события правки нет.

        Ловит мутацию: проверки идут после записи (а) или сняты — голова
        кодовой ветки сдвигается при отказе либо правка проходит.
        """
        scenarios = {
            "разовая строка группы в tests/": edited_source(group="разовый"),
            "чтение tasks/": edited_source(tail='DATA_DIR = "tasks/"\n'),
            "метод без «Ловит мутацию»": edited_source(claim=False),
            "файл не собирается": edited_source(tail="def broken(:\n    pass\n"),
            "непромаркированное падение": edited_source(rhs="3"),
        }
        name = self.own.rsplit("/", 1)[-1]
        for label, text in scenarios.items():
            with self.subTest(scenario=label):
                self.restore_wt()
                before = self.heads()
                self.write_wt(self.own, text)

                out = self.amend()

                self.assert_refused_untouched(before, out, name)

    def test_out_of_bounds_and_hand_manifest_refused(self):
        """Рядом с годной правкой долгоживущего файла — правка
        `tests/test_existing.py` (без префикса задачи), новый
        `tests/test_noprefix.py`, файл вне `tests/`, либо ручная правка
        `long_lived.sha256.txt` в worktree (даже с верной суммой) — отказ с
        путём нарушителя, без записей.

        Ловит мутацию: граница правки расширена на весь `tests/` (или
        ручной перечень принят, раз его суммы сходятся) — чужой файл или
        перечень в обход команды уходит в ветку и лок.
        """
        manifest_rel = f"tasks/{self.TASK}/acceptance_tests/{MANIFEST_NAME}"
        existing = (self.wt / self.EXISTING).read_text(encoding="utf-8")
        scenarios = {
            "tests/ без префикса": (self.EXISTING, lambda: existing + "# правка\n"),
            "новый tests/ без префикса": ("tests/test_noprefix.py",
                                          lambda: edited_source()),
            "вне tests/": ("docs/extra.md", lambda: "постороннее\n"),
            "ручной перечень": (manifest_rel, lambda: (
                hashlib.sha256((self.wt / self.own).read_bytes()).hexdigest()
                + f"  {self.own}\n")),
        }
        for label, (rel, make) in scenarios.items():
            with self.subTest(scenario=label):
                self.restore_wt()
                before = self.heads()
                self.write_wt(self.own, edited_source())
                self.write_wt(rel, make())

                out = self.amend()

                self.assert_refused_untouched(before, out,
                                              rel.rsplit("/", 1)[-1])

    def test_docs_write_failure_names_recovery_then_from_branch_relocks(self):
        """Запись в ветку документов не удалась после коммита кодовой
        ветки: ненулевой код, сообщение называет `amend-tests <id>
        --from-branch`, лок прежний, сверка сумм отказывает, события правки
        нет. Затем `--from-branch` сдвигает лок на перечень по голове
        кодовой ветки — ровно одно событие правки за оба вызова.

        Ловит мутацию: `--from-branch` видит только расхождение
        `acceptance_tests/` — после сбоя он отвечает «нет расхождения», и
        задача застревает на отказе сверки сумм.
        """
        code_before, _docs_before, lock_before = self.heads()
        self.write_wt(self.own, edited_source())

        with self.docs_branch_write_fails():
            out = self.amend()

        self.assertIn("SystemExit", out)
        self.assertIn(f"amend-tests {self.TASK} --from-branch", out)
        code_head, _docs, lock = self.heads()
        self.assertNotEqual(code_head, code_before, "предпосылка: (а) прошла")
        self.assertEqual(lock, lock_before)
        self.assertTrue(self.manifest_check_refuses()[0])
        self.assertEqual(self.amend_events(), 0)

        out = self.amend(from_branch=True)

        self.assertNotIn("SystemExit", out)
        code_head, docs_head, lock = self.heads()
        self.assertEqual(lock, docs_head)
        self.assertEqual(self.manifest_at(lock), self.expected_manifest(code_head))
        refused, text = self.manifest_check_refuses()
        self.assertFalse(refused, text)
        self.assertEqual(self.amend_events(), 1)


class DeletionRuleTest(_LockedSandbox):

    def test_moved_to_plank_passes_and_drops_from_manifest(self):
        """Файл перечня удалён из worktree, его метод перенесён в
        `acceptance_tests/` разовым файлом: правка проходит, пути нет ни на
        голове кодовой ветки, ни в перечне лока.

        Ловит мутацию: удаление пути `tests/` считается изменением «за
        пределами» (или новый перечень — старый плюс изменённые пути) —
        перенос отклонён либо удалённый путь остаётся в перечне.
        """
        self.materialize_plank()
        before = self.heads()
        (self.wt / self.own).unlink()
        self.write_wt(f"tasks/{self.TASK}/acceptance_tests/test_moved.py",
                      plank_source("test_ac1_long_fixture"))

        out = self.amend()

        self.assert_relocked(before, {self.own}, out)
        self.assertNotIn(self.own, self.manifest_at(self.heads()[2]))

    def test_lost_method_refused_naming_file_and_method(self):
        """Файл перечня удалён, его метод не перенесён никуда — отказ с
        именем файла и метода `test_ac1_long_fixture`, без записей.

        Ловит мутацию: правило удаления не сверяет методы удаляемого файла
        с итоговой планкой — тест снят правкой планки в обход ADR-0020 п.8.
        """
        before = self.heads()
        (self.wt / self.own).unlink()

        out = self.amend()

        self.assert_refused_untouched(before, out, self.own.rsplit("/", 1)[-1],
                                      "test_ac1_long_fixture")


class FromBranchModeTest(_LockedSandbox):

    def test_bypass_manifest_alone_is_no_divergence(self):
        """В ветку документов в обход команды закоммичен перечень с чужой
        суммой, а кодовая ветка и планка не менялись: `--from-branch` —
        отказ «нет расхождения», лок прежний, события правки нет.

        Ловит мутацию: файл перечня входит в сравнение планки лока и
        головы ветки документов — перечень в обход команды сам по себе
        засчитывается правкой, и лок сдвигается с событием правки планки.
        """
        artifact_branch.commit_files(
            self.TASK, {acceptance_gates.long_lived_manifest_rel(self.TASK):
                        guard.render_long_lived_manifest({self.own: "0" * 64})},
            "перечень в обход команды")
        before = self.heads()

        out = self.amend(from_branch=True)

        self.assertIn("нет расхождения", out)
        self.assertEqual(self.heads(), before)
        self.assertEqual(self.amend_events(), 0)

    def test_dirty_worktree_long_lived_refused(self):
        """Кодовая ветка несёт закоммиченную годную правку долгоживущего
        файла, а в worktree поверх неё — ещё одна, незакоммиченная:
        `--from-branch` — отказ с путём файла, лок прежний.

        Ловит мутацию: проверка незакоммиченной правки снята — прогон
        `--from-branch` исполняет файл с диска worktree вместо головы
        кодовой ветки, и лок сдвигается по непроверенному содержимому.
        """
        self.wt_commit({self.own: long_lived_source(tag="годная правка")})
        self.write_wt(self.own, long_lived_source(tag="незакоммиченная правка"))
        before = self.heads()

        out = self.amend(from_branch=True)

        self.assertIn("SystemExit", out)
        self.assertIn(self.own, out)
        self.assertEqual(self.heads(), before)
        self.assertEqual(self.amend_events(), 0)

    def test_violating_code_head_refused_without_writes(self):
        """На голове кодовой ветки — закоммиченный долгоживущий файл без
        строки группы: `--from-branch` — отказ, головы и лок прежние.

        Ловит мутацию: при расхождении долгоживущих путей `--from-branch`
        пересчитывает перечень и сдвигает лок, не применив проверок
        требования 1.
        """
        self.wt_commit({self.own: edited_source(group=None)})
        before = self.heads()

        out = self.amend(from_branch=True)

        self.assert_refused_untouched(before, out)

    def test_bypass_manifest_replaced_by_recomputed(self):
        """Кодовая ветка несёт годную правку, а в ветку документов в обход
        команды закоммичен перечень с чужой суммой: `--from-branch`
        проходит, и в лок попадает перечень, пересчитанный по голове
        кодовой ветки, а не закоммиченный в обход.

        Ловит мутацию: `--from-branch` сдвигает лок на голову ветки
        документов как есть — в лок уезжает перечень с чужой суммой, и
        сверка сумм отказывает.
        """
        self.wt_commit({self.own: edited_source()})
        bypass = guard.render_long_lived_manifest({self.own: "0" * 64})
        artifact_branch.commit_files(
            self.TASK, {acceptance_gates.long_lived_manifest_rel(self.TASK):
                        bypass}, "перечень в обход команды")

        out = self.amend(from_branch=True)

        self.assertNotIn("SystemExit", out)
        code_head, docs_head, lock = self.heads()
        self.assertEqual(lock, docs_head)
        self.assertEqual(self.manifest_at(lock), self.expected_manifest(code_head))
        self.assertFalse(self.manifest_check_refuses()[0])
        self.assertEqual(self.amend_events(), 1)


if __name__ == "__main__":
    unittest.main()
