"""Юнит-тесты долгоживущих приёмочных тестов в `tests/` кодовой ветки
(SPEC 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ; ADR-0020, задача 2): правило имени Р1 и
формат перечня Р2 (`scripts/guard.py`), мандат test_author на чекпоинте
(`orchestrator/checkpoint.py`), общий узел сверки перечня
(`orchestrator/advance_gates/acceptance.py::_long_lived_manifest_refuses`),
лок на гейте мержа (`orchestrator/fsm_merge_gate.py`), единый прогон и
итог двух групп (`orchestrator/acceptance.py`), задание ролей
(`orchestrator/role_prompt.py`).

Сквозные сценарии переходов — планка задачи; здесь — сами узлы, на
настоящем git (`tests/test_timeout_checkpoint.py::_WorktreeCheckpointTest`:
пульт с артефактной веткой, bare origin и worktree кодовой ветки).
"""
import hashlib
import random
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (acceptance, artifact_branch, brief, checkpoint,  # noqa: E402
                          config, fsm_merge_gate, gitcmd, idgen, role_prompt,
                          store)
from orchestrator.advance_gates import acceptance as acceptance_gates  # noqa: E402
from scripts import guard  # noqa: E402
from tests.test_timeout_checkpoint import _WorktreeCheckpointTest  # noqa: E402

LONG_LIVED_SOURCE = '''"""Долгоживущий файл фикстуры.

Группа: долгоживущий
"""
import unittest


class FixtureTest(unittest.TestCase):

    def test_ac1_fixture(self):
        """Ловит мутацию: фикстура — {tag}."""
        self.assertEqual(1 + 1, {right})
'''


def long_lived_source(tag: str = "", right: int = 2) -> str:
    return LONG_LIVED_SOURCE.format(tag=tag, right=right)


class LongLivedPathRuleTest(unittest.TestCase):

    def test_only_full_lowercase_task_id_prefix_is_accepted(self):
        """Для свежих id: имя с полным id в нижнем регистре — своё; с
        первыми 10 знаками, с id в исходном регистре, с пустым или
        недопустимым `<имя>`, во вложенном каталоге — нет.

        Ловит мутацию: префикс укорочен до метки времени ULID
        (`task_id[:10]`) или не приводится к нижнему регистру — короткий
        или заглавный префикс признаётся своим.
        """
        seed = random.randrange(1 << 30)
        rnd = random.Random(seed)
        for _ in range(5):
            task_id = idgen.new_task_id()
            name = "".join(rnd.choice("abc019_") for _ in range(rnd.randint(1, 12)))
            lower = task_id.lower()
            msg = f"зерно: {seed}, id {task_id}, имя {name!r}"
            self.assertTrue(guard.is_long_lived_test_path(
                task_id, f"tests/test_{lower}_{name}.py"), msg)
            for rel in (f"tests/test_{lower[:10]}_{name}.py",
                        f"tests/test_{task_id}_{name}.py",
                        f"tests/test_{lower}_.py",
                        f"tests/test_{lower}_{name}-x.py",
                        f"tests/sub/test_{lower}_{name}.py",
                        f"tests/test_{lower}_{name}.txt"):
                self.assertFalse(guard.is_long_lived_test_path(task_id, rel),
                                 f"{msg}: {rel}")


class ManifestFormatTest(unittest.TestCase):

    def test_render_is_sorted_and_parses_back(self):
        """Случайный набор путей: каждая строка — `<sha256>␣␣<путь>\\n`,
        строки по пути, разбор возвращает тот же словарь; пустой набор —
        пустой текст и пустой словарь.

        Ловит мутацию: перечень пишется в порядке словаря, а не по пути,
        или разделитель — один пробел (несовместимо с `sha256sum -c`) —
        строки не отсортированы / разбор не совпадает.
        """
        seed = random.randrange(1 << 30)
        rnd = random.Random(seed)
        digests = {f"tests/test_x_{rnd.randrange(10 ** 6)}.py":
                   hashlib.sha256(str(rnd.random()).encode()).hexdigest()
                   for _ in range(rnd.randint(1, 6))}
        text = guard.render_long_lived_manifest(digests)
        lines = text.splitlines()
        self.assertTrue(text.endswith("\n"), f"зерно: {seed}")
        self.assertEqual([line.split("  ", 1)[1] for line in lines],
                         sorted(digests), f"зерно: {seed}")
        self.assertEqual(guard.parse_long_lived_manifest(text), (digests, ""),
                         f"зерно: {seed}")
        self.assertEqual(guard.render_long_lived_manifest({}), "")
        self.assertEqual(guard.parse_long_lived_manifest(""), ({}, ""))

    def test_malformed_line_is_rejected(self):
        """Строка с одним пробелом, комментарий, короткая сумма — разбор
        отказывает (`None` и причина).

        Ловит мутацию: разбор пропускает строки не по формату — порча
        перечня читается как «записей меньше», и сверка молча слабеет.
        """
        digest = "a" * 64
        for text in (f"{digest} tests/test_x.py\n", "# комментарий\n",
                     "abc  tests/test_x.py\n"):
            with self.subTest(text=text):
                parsed, reason = guard.parse_long_lived_manifest(text)
                self.assertIsNone(parsed)
                self.assertTrue(reason)


class PlankLongLivedErrorTest(unittest.TestCase):

    def test_long_lived_file_in_plank_named_with_tests_hint(self):
        """Долгоживущий файл планки — ошибка с его меткой и подсказкой
        `tests/test_<префикс>_<имя>.py`; разовый — без ошибки.

        Ловит мутацию: проверка смотрит на любую строку группы (или на
        «разовый») — разовый файл получает ошибку либо долгоживущий
        проходит.
        """
        task_id = idgen.new_task_id()
        once = long_lived_source().replace("Группа: долгоживущий", "Группа: разовый")
        errors = guard.long_lived_plank_errors(
            [("acceptance_tests/test_a.py", long_lived_source()),
             ("acceptance_tests/test_b.py", once)], task_id)
        self.assertEqual(len(errors), 1)
        self.assertIn("acceptance_tests/test_a.py", errors[0])
        self.assertIn(f"tests/test_{task_id.lower()}_", errors[0])


class _LongLivedGitTest(_WorktreeCheckpointTest):

    def setUp(self):
        super().setUp()
        self.branch = store.get_task(store.db(), self.TASK)["branch"]
        self.own = f"tests/test_{self.TASK.lower()}_alpha.py"

    def set_row(self, **fields) -> None:
        store.update_task(store.db(), self.TASK, **fields)

    def branch_text(self, rel: str) -> str | None:
        text, _ = gitcmd.show(self.branch, rel)
        return text

    def journal_text(self) -> str:
        return "\n".join(f"{r['action']} {r['detail'] or ''}"
                         for r in store.task_steps(store.db(), self.TASK))


class TestAuthorCheckpointMandateTest(_LongLivedGitTest):

    def test_own_file_committed_and_base_edit_rolled_back(self):
        """test_author в `tests_writing`: свой новый файл и правка `CLAUDE.md`
        базы. После WIP-чекпоинта таймаута свой файл в голове кодовой
        ветки, `CLAUDE.md` откачен, журнал называет его.

        Ловит мутацию: test_author идёт общей веткой отката ролей без
        мандата кода (`_wip_checkpoint`, `else`) — свой файл удалён с
        диска и не закоммичен.
        """
        self.set_row(state="tests_writing")
        text = long_lived_source(tag=str(random.randrange(1 << 30)))
        self.write_code_file(self.own, text)
        claude_md = self.wt / "CLAUDE.md"
        original = claude_md.read_text(encoding="utf-8")
        claude_md.write_text(original + "правка test_author\n", encoding="utf-8")

        checkpoint.commit_timeout_checkpoint(store.db(), self.TASK, "test_author")

        self.assertEqual(self.branch_text(self.own), text)
        self.assertEqual(claude_md.read_text(encoding="utf-8"), original)
        self.assertIn("CLAUDE.md", self.journal_text())

    def test_own_file_is_rolled_back_outside_tests_writing(self):
        """Та же правка своего файла, но задача уже в `in_dev`: файл
        откачен, в кодовую ветку не попал.

        Ловит мутацию: проверка состояния `tests_writing` снята — test_author
        коммитит в кодовую ветку и после лока, в обход перечня.
        """
        self.set_row(state="in_dev")
        self.write_code_file(self.own, long_lived_source())

        checkpoint.commit_success_checkpoint(store.db(), self.TASK, "test_author")

        self.assertIsNone(self.branch_text(self.own))
        self.assertFalse((self.wt / self.own).exists())


class ManifestCheckNodeTest(_LongLivedGitTest):

    def lock_with(self, text: str) -> None:
        """Свой файл в кодовой ветке, перечень с его суммой в ветке
        документов, лок — голова ветки документов; задача в `in_dev`."""
        self.write_code_file(self.own, text)
        self.worktree_git("add", self.own)
        self.worktree_git("-c", "user.name=t", "-c", "user.email=t@example.invalid",
                          "commit", "-q", "-m", "долгоживущий файл")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        sha = artifact_branch.commit_files(
            self.TASK, {acceptance_gates.long_lived_manifest_rel(self.TASK):
                        guard.render_long_lived_manifest({self.own: digest})},
            "перечень")
        self.assertTrue(sha)
        self.set_row(state="in_dev", tests_locked_sha=sha)

    def refuses(self) -> bool:
        return acceptance_gates._long_lived_manifest_refuses(store.db(), self.TASK)

    def test_matching_file_passes_changed_and_deleted_refuse(self):
        """Файл совпадает с перечнем — узел пропускает; изменён после лока —
        отказ с путём и подсказкой; удалён — отказ с путём.

        Ловит мутацию: сверка сравнивает только наличие путей (не суммы)
        либо перебирает файлы головы вместо путей перечня — правленый или
        удалённый файл проходит.
        """
        self.lock_with(long_lived_source(tag=str(random.randrange(1 << 30))))
        self.assertFalse(self.refuses())

        self.write_code_file(self.own, long_lived_source(tag="правка после лока"))
        self.worktree_git("-c", "user.name=t", "-c", "user.email=t@example.invalid",
                          "commit", "-q", "-am", "правка")
        self.assertTrue(self.refuses())
        journal = self.journal_text()
        self.assertIn(f"{self.own} изменён", journal)
        self.assertIn(acceptance_gates.LONG_LIVED_MANIFEST_HINT, journal)

        self.worktree_git("rm", "-q", self.own)
        self.worktree_git("-c", "user.name=t", "-c", "user.email=t@example.invalid",
                          "commit", "-q", "-m", "удаление")
        self.assertTrue(self.refuses())
        self.assertIn(f"{self.own} удалён", self.journal_text())

    def test_unreadable_head_refuses(self):
        """Ref кодовой ветки удалён — отказ, не пропуск.

        Ловит мутацию: пустая голова трактуется как «сверять не с чем» —
        узел возвращает `False`.
        """
        self.lock_with(long_lived_source())
        self.git("update-ref", "-d", f"refs/heads/{self.branch}")
        self.assertTrue(self.refuses())

    def test_out_of_scope_tasks_pass(self):
        """Внешний target, задача без лока (`skip_tests`) и лок без перечня
        в дереве (снят до внедрения) — узел пропускает, даже при удалённом
        ref кодовой ветки.

        Ловит мутацию: область не проверяется — отсутствие перечня или
        головы у задачи вне правила даёт отказ.
        """
        self.lock_with(long_lived_source())
        locked = store.get_task(store.db(), self.TASK)["tests_locked_sha"]
        self.git("update-ref", "-d", f"refs/heads/{self.branch}")
        self.set_row(target="sled")
        self.assertFalse(self.refuses())
        self.set_row(target=config.DEFAULT_TARGET, tests_locked_sha=None)
        self.assertFalse(self.refuses())
        parent = self.git("rev-parse", f"{locked}^").strip()
        self.set_row(tests_locked_sha=parent)
        self.assertFalse(self.refuses())


class MergeGateLocksTest(_LongLivedGitTest):

    def test_lock_git_failure_stops_artel_task_only(self):
        """Недостижимый `tests_locked_sha`: у задачи `artel` сверка на гейте
        мержа отказывает, у внешнего target — не сверяет (поведение прежнее).

        Ловит мутацию: `_acceptance_locks_refuse` трактует сбой git сверки
        лока как «расхождений нет» либо не ограничена target `artel`.
        """
        self.set_row(state="merge_gate", tests_locked_sha="0" * 40)
        self.assertTrue(fsm_merge_gate._acceptance_locks_refuse(store.db(), self.TASK))
        self.set_row(target="sled")
        self.assertFalse(fsm_merge_gate._acceptance_locks_refuse(store.db(), self.TASK))


class OneRunTest(unittest.TestCase):

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / "tests").mkdir()

    def test_long_lived_files_run_without_plank_and_redden_the_run(self):
        """Планки нет, долгоживущий файл падает — прогон красный и называет
        файл; зелёный файл — прогон зелёный.

        Ловит мутацию: `run` возвращает «приёмочные тесты не заведены» при
        отсутствии каталога планки, не глядя на `extra`, — долгоживущие
        файлы не исполняются.
        """
        red, ok = "tests/test_fixture_red.py", "tests/test_fixture_green.py"
        (self.root / red).write_text(long_lived_source(right=3), encoding="utf-8")
        (self.root / ok).write_text(long_lived_source(), encoding="utf-8")
        green, tail = acceptance.run(self.root / "нет", cwd=self.root, extra=[red])
        self.assertFalse(green)
        self.assertIn("test_fixture_red.py", tail)
        green, tail = acceptance.run(self.root / "нет", cwd=self.root, extra=[ok])
        self.assertTrue(green, tail)

    def test_summary_names_both_group_counts(self):
        """Итог с долгоживущими файлами называет число тестов обеих групп.

        Ловит мутацию: `summary` игнорирует `long_lived` — числа
        долгоживущей группы в итоге нет.
        """
        count = random.randint(1, 5)
        methods = "".join(f"\n    def test_ac1_m{i}(self):\n        pass\n"
                          for i in range(count))
        path = self.root / "tests" / "test_fixture.py"
        path.write_text(f"import unittest\n\n\nclass T(unittest.TestCase):\n{methods}",
                        encoding="utf-8")
        card = acceptance.summary(self.root / "нет", long_lived=[path])
        self.assertIn("разовая группа — 0 тест(ов)", card)
        self.assertIn(f"долгоживущая группа — {count} тест(ов)", card,
                      f"число методов: {count}")


class RolePromptTest(unittest.TestCase):

    def test_test_author_and_developer_missions_name_own_prefix(self):
        """Задание test_author и developer несёт префикс имени СВОЕЙ задачи
        (полный id в нижнем регистре).

        Ловит мутацию: в задание подставлен шаблон `<префикс>` или id в
        исходном регистре — конкретного префикса в тексте нет.
        """
        task_id = idgen.new_task_id()
        t = {"branch": f"task/{task_id.lower()}-x", "reviewed_iter": 0,
             "title": "x"}
        for role in ("test_author", "developer"):
            with self.subTest(role=role), \
                    mock.patch.object(brief, "test_author_answer_component",
                                      return_value=""), \
                    mock.patch.object(brief, "developer_brief", return_value=""):
                mission, _b, _p = role_prompt.mission_brief_package(
                    None, task_id, t, role, Path("/нет"))
                self.assertIn(f"tests/test_{task_id.lower()}_", mission)


if __name__ == "__main__":
    unittest.main()
