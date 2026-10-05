"""`doctor --fix` досылает в origin коммит закрытия, которого нет в клоне,
из git главной копии пульта; не нашедший его нигде — говорит об этом
строкой `[FIX]`.

Группа: разовый

Почему разовый: критерии AC-6/AC-7 называют закрытую функцию
`doctor._fix_unsent_closed_refs`, а долгоживущий файл `tests/` закрытых
имён `orchestrator` касаться не вправе (skills/test-authoring.md);
постоянные тесты этого свойства в `tests/` пишет разработчик
(требование 5 SPEC), AC-9 сторожит их заявки.

Песочница — настоящий git (`tests.sandbox.RealGitSandbox`,
`ARTEL_CLONE_IS_ROOT = False`): главная копия пульта (`config.ROOT`), bare
`origin` рядом и отдельный клон артели, заведённый из него
(`clone_artel_from_origin`). Коммит закрытия создаётся в git главной копии
(`git commit-tree` вне истории `main`, ссылка документов главной копии
указывает на него) уже после заведения клона — в клоне его объекта нет.
Запись о коммите закрытия — строка журнала `snapshot.CLOSING_ACTION` того
же вида, что пишет `snapshot.commit_closing`; её разбор
`snapshot.closing_sha` проверяется предусловием.

Красен до реализации: `_fix_unsent_closed_refs` пропускает закрытую задачу,
у которой в клоне нет локальной ссылки, молча — в origin ничего не
досылается (AC-6) и строки `[FIX]` нет (AC-6 отказ, AC-7). Провалидирован
временным стабом (удалён, не закоммичен): объект из главной копии
подтягивается в клон `git fetch <ROOT> <sha>`, локальная ссылка ставится
на него, `artifact_branch.push` без force; объекта нет нигде — строка
`[FIX]` с id и sha.
"""
import random
import re
import shutil
import unittest

from _plank import git  # noqa: F401  (кладёт корень рабочей копии в sys.path)

from orchestrator import artifact_branch, config, doctor, snapshot, store
from tests.sandbox import RealGitSandbox, capture, clone_artel_from_origin

ID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class UnsentClosingSandbox(RealGitSandbox):

    ARTEL_CLONE_IS_ROOT = False

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(2 ** 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.origin = self.root.parent / f"{self.root.name}-origin.git"
        self.git("clone", "-q", "--bare", str(self.root), str(self.origin))
        self.addCleanup(shutil.rmtree, self.origin, True)
        self.clone = clone_artel_from_origin(self.origin)
        self.conn = store.db()

    def msg(self, text: str) -> str:
        return f"{text} (зерно: {self.seed})"

    def task_id(self) -> str:
        return "01" + "".join(self.rng.choice(ID_ALPHABET) for _ in range(24))

    def main_commit(self) -> str:
        """Коммит в git главной копии вне истории `main`."""
        tree = self.git("rev-parse", "HEAD^{tree}").strip()
        return self.git("commit-tree", tree, "-p", "HEAD", "-m",
                        f"документы {self.rng.randrange(10 ** 9)}").strip()

    def closed_task(self, closing: str) -> str:
        task_id = self.task_id()
        state = self.rng.choice(("done", "killed"))
        store.insert_task(self.conn, task_id, "Задача", state,
                          f"task/{task_id.lower()}-x", config.DEFAULT_TARGET,
                          25.0)
        ref = artifact_branch.branch_name(task_id)
        store.journal(self.conn, task_id, "orchestrator",
                      snapshot.CLOSING_ACTION, f"{ref} <- {closing} ({state})")
        self.assertEqual(snapshot.closing_sha(self.conn, task_id), closing,
                         "предусловие: запись о коммите закрытия разбирается")
        return task_id

    def has_object(self, repo, sha: str) -> bool:
        res = git("-C", str(repo), "cat-file", "-e", f"{sha}^{{commit}}")
        return res.returncode == 0

    def origin_head(self, task_id: str) -> str:
        res = git("-C", str(self.origin), "for-each-ref",
                  "--format=%(objectname)", artifact_branch.branch_name(task_id))
        return res.stdout.strip()

    def push_origin(self, task_id: str, sha: str) -> None:
        self.git("push", "-q", "--force", str(self.origin),
                 f"{sha}:{artifact_branch.branch_name(task_id)}")

    def fix_lines(self, out: str, *needles: str) -> list:
        return [line for line in out.splitlines()
                if "[FIX]" in line and all(n in line for n in needles)]


class ResendFromMainCopyTest(UnsentClosingSandbox):

    def closing_only_in_main_copy(self) -> tuple[str, str]:
        closing = self.main_commit()
        task_id = self.closed_task(closing)
        self.git("update-ref", artifact_branch.branch_name(task_id), closing)
        self.assertFalse(self.has_object(self.clone, closing),
                         "предусловие: объекта коммита закрытия в клоне нет")
        self.assertTrue(self.has_object(self.root, closing))
        return task_id, closing

    def test_ac6_closing_commit_from_main_copy_lands_in_origin(self):
        """Коммит закрытия, которого нет ни в origin, ни в клоне, но есть в главной копии, досылается в origin.

        Сценарий: закрытая задача артели; в origin ссылки
        `refs/artifacts/<id>` нет, в клоне нет ни ссылки, ни объекта
        коммита закрытия, в git главной копии он есть. После
        `_fix_unsent_closed_refs` ссылка в origin равна коммиту закрытия.

        Ловит мутацию: досылка по-прежнему требует локальную голову в
        клоне и пропускает задачу без неё — ссылки в origin нет; поиск
        объекта идёт только в клоне, без главной копии — то же.
        """
        task_id, closing = self.closing_only_in_main_copy()
        self.assertEqual(self.origin_head(task_id), "")

        capture(doctor._fix_unsent_closed_refs, self.conn)

        self.assertEqual(self.origin_head(task_id), closing, self.msg(
            "коммит закрытия из главной копии не дослан в origin"))

    def test_ac6_non_fast_forward_is_refused_and_reported(self):
        """Непродвигающее обновление ссылки в origin не проходит: origin не меняется, строка `[FIX]` о недосланном коммите.

        Сценарий: как выше, но в origin (уже после заведения клона)
        лежит другая ссылка задачи — коммит, не предок коммита закрытия.
        После `_fix_unsent_closed_refs` ссылка в origin прежняя, а в выводе
        есть строка `[FIX]` с id задачи о том, что коммит не дослан.

        Ловит мутацию: досылка идёт с `--force` (или `+<sha>:<ссылка>`) —
        ссылка в origin перезаписана коммитом закрытия; отказ origin
        глотается молча — строки `[FIX]` с id задачи нет.
        """
        task_id, closing = self.closing_only_in_main_copy()
        diverged = self.main_commit()
        self.push_origin(task_id, diverged)
        self.assertNotEqual(diverged, closing)

        out = capture(doctor._fix_unsent_closed_refs, self.conn)

        self.assertEqual(self.origin_head(task_id), diverged, self.msg(
            "непродвигающая досылка изменила ссылку в origin"))
        lines = self.fix_lines(out, task_id)
        self.assertTrue(lines, self.msg(f"нет строки [FIX] с id задачи: {out!r}"))
        self.assertTrue(any(re.search(r"не\s*дослан", line) for line in lines),
                        self.msg(f"строка [FIX] не говорит о недосланном "
                                 f"коммите: {lines}"))


class ClosingCommitNowhereTest(UnsentClosingSandbox):

    def test_ac7_missing_closing_commit_is_reported(self):
        """Коммит закрытия, которого нет ни в клоне, ни в главной копии, — строка `[FIX]` с id и sha, не молчание.

        Сценарий: закрытая задача артели, запись о коммите закрытия
        называет sha, которого нет ни в одном репозитории; ссылка в origin
        либо отсутствует, либо указывает на другой коммит (вид —
        случайно). `_fix_unsent_closed_refs` печатает строку `[FIX]`,
        содержащую id задачи и этот sha.

        Ловит мутацию: задача без локальной головы пропускается молча
        (прежнее поведение) — строки нет; строка печатается без sha
        коммита закрытия — нужной строки нет.
        """
        closing = "".join(self.rng.choice("0123456789abcdef")
                          for _ in range(40))
        task_id = self.closed_task(closing)
        if self.rng.random() < 0.5:
            self.push_origin(task_id, self.main_commit())
        self.assertFalse(self.has_object(self.root, closing))
        self.assertFalse(self.has_object(self.clone, closing))

        out = capture(doctor._fix_unsent_closed_refs, self.conn)

        self.assertTrue(self.fix_lines(out, task_id, closing), self.msg(
            f"нет строки [FIX] с id задачи и коммитом закрытия: {out!r}"))


if __name__ == "__main__":
    unittest.main()
