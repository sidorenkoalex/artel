"""AC-1…AC-5: прогон планки после подтяжки main исполняет долгоживущую группу.

Группа: разовый
Красен до реализации: `orchestrator/pull.py::_materialize_and_run_plank` зовёт `acceptance.run(tdir, cwd=wt_path)` без `extra` — планка из одного перечня даёт pytest «collected 0 items» (AC-1 эскалирует, AC-2 не видит долгоживущего файла в тексте эскалации), сбой перечня не замечается вовсе (AC-3 — зелёный прогон разовой группы), перечень в выбор файлов не попадает (AC-5); AC-4 зелен с рождения — держит прежнее поведение задачи без перечня.

Почему «разовый»: постоянное покрытие тех же сценариев SPEC возлагает на
разработчика (требование 5, `tests/test_pull_long_lived_plank.py`), а
сценарий здесь требует подмены `gitcmd` (свежесть, merge, чтение
перечня из дерева лока) — долгоживущему файлу она запрещена.

Песочница — приём `tests/test_pull.py::PullEvaluateTest`: `TmpRootTest`,
дисковые `gitcmd.show`/`gitcmd.ls_tree_files` (`tests/sandbox.py`),
поддельный `gitcmd.in_repo` (merge «проходит»), `workspace.ensure` —
временный каталог `wt`. Вход — `fsm._pull_main_or_escalate` (тот же узел,
которым пульт подтягивает main): так тест не зависит от того, как
разработчик доставит перечень в `pull.evaluate`. Сам pytest-прогон
планки и долгоживущего файла — настоящий (`acceptance.run`).
"""
import hashlib
import inspect
import io
import subprocess
import unittest
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from unittest import mock

from orchestrator import (acceptance, config, fsm, gitcmd, pull, store,
                          workspace)
from orchestrator.advance_gates import acceptance as acceptance_gates
from scripts import guard
from tests.sandbox import (TmpRootTest, disk_backed_ls_tree_files,
                           disk_backed_show)

SPEC_FIXTURE = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
---

# SPEC: песочница планки после подтяжки

## Критерии приёмки

AC-1. Фикстура.
"""

ONE_OFF_GREEN = '''"""Разовый файл фикстуры.

Группа: разовый
"""
import unittest


class OneOffFixtureTest(unittest.TestCase):

    def test_ac1_one_off_fixture(self):
        """Фикстурный метод."""
        self.assertEqual(1 + 1, 2)
'''

LONG_LIVED_FIXTURE = '''"""Долгоживущий файл фикстуры.

Группа: долгоживущий
"""
import unittest


class LongLivedFixtureTest(unittest.TestCase):

    def test_ac1_long_lived_fixture(self):
        """Фикстурный метод."""
        self.assertTrue({green}, "МАРКЕР-ДОЛГОЖИВУЩИЙ-КРАСНЫЙ")
'''


class _PullPlankSandbox(TmpRootTest):

    TASK = "01PULLLONGLIVEDPLANKACC"
    BRANCH = f"task/{TASK.lower()}-x"
    LOCKED = "1111111111111111111111111111111111111111"

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        store.insert_task(store.db(), self.TASK, "Планка после подтяжки",
                          "in_dev", self.BRANCH, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        store.update_task(store.db(), self.TASK, tests_locked_sha=self.LOCKED)
        self.wt = self.root / "wt"
        (self.wt / "tests").mkdir(parents=True, exist_ok=True)
        self.tdir = config.TASKS / self.TASK
        self.plank = self.tdir / "acceptance_tests"
        self.plank.mkdir(parents=True, exist_ok=True)
        (self.tdir / "SPEC.md").write_text(SPEC_FIXTURE.format(task=self.TASK),
                                           encoding="utf-8")
        self.own = f"tests/test_{self.TASK.lower()}_alpha.py"
        self.manifest_rel = (f"tasks/{self.TASK}/acceptance_tests/"
                             f"{guard.LONG_LIVED_MANIFEST_NAME}")
        self.show = disk_backed_show
        self.ls_tree = disk_backed_ls_tree_files

    # ------------------------------------------------------------ фикстуры

    def write_long_lived(self, rel: str, green: bool = True) -> str:
        data = LONG_LIVED_FIXTURE.format(green=green).encode("utf-8")
        path = self.wt / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return hashlib.sha256(data).hexdigest()

    def write_manifest(self, entries: dict) -> None:
        text = "".join(f"{digest}  {rel}\n" for rel, digest in sorted(entries.items()))
        (self.plank / guard.LONG_LIVED_MANIFEST_NAME).write_text(
            text, encoding="utf-8")

    def write_one_off(self) -> None:
        (self.plank / "test_ac1_one_off.py").write_text(ONE_OFF_GREEN,
                                                         encoding="utf-8")

    # -------------------------------------------------------------- прогон

    @staticmethod
    def _ok(repo, *args) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(("git", "-C", str(repo), *args),
                                           0, "", "")

    def pull_main(self, *extra_patches):
        """Подтяжка через `fsm._pull_main_or_escalate`: (исход, текст
        журнала задачи + печать, spy `acceptance.run`)."""
        real_run = acceptance.run
        spy = mock.Mock(side_effect=lambda *a, **k: real_run(*a, **k))
        buf = io.StringIO()
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(
                gitcmd, "show", side_effect=lambda b, r: self.show(b, r)))
            stack.enter_context(mock.patch.object(
                gitcmd, "ls_tree_files",
                side_effect=lambda b, r: self.ls_tree(b, r)))
            stack.enter_context(mock.patch.object(
                workspace, "ensure", lambda task_id, branch: (self.wt, None)))
            stack.enter_context(mock.patch.object(gitcmd, "commits_behind",
                                                  return_value=3))
            stack.enter_context(mock.patch.object(gitcmd, "in_repo",
                                                  side_effect=self._ok))
            stack.enter_context(mock.patch.object(
                fsm, "_origin_main_source",
                return_value=("origin", config.MAIN_BRANCH)))
            stack.enter_context(mock.patch.object(
                fsm, "_origin_main_sha", return_value="deadbeefcafefeed"))
            stack.enter_context(mock.patch.object(acceptance, "run", spy))
            for patcher in extra_patches:
                stack.enter_context(patcher)
            conn = store.db()
            with redirect_stdout(buf):
                outcome = fsm._pull_main_or_escalate(
                    conn, self.TASK, store.get_task(conn, self.TASK), "in_dev")
        steps = "\n".join(f"{r['action']} {r['detail'] or ''}"
                          for r in store.task_steps(store.db(), self.TASK))
        return outcome, steps + "\n" + buf.getvalue(), spy

    def state(self) -> str:
        return store.get_task(store.db(), self.TASK)["state"]

    @staticmethod
    def extra_of(call) -> list:
        if "extra" in call.kwargs:
            return list(call.kwargs["extra"] or [])
        return list(call.args[2]) if len(call.args) > 2 else []


class PullLongLivedPlankTest(_PullPlankSandbox):

    def test_ac1_long_lived_only_plank_green_stays_in_dev(self):
        """Планка — один перечень, долгоживущий файл зелёный: подтяжка проходит.

        В `acceptance_tests/` лежит только `long_lived.sha256.txt` с
        суммой своего файла `tests/`; файл в рабочей копии зелёный. Исход
        подтяжки — `pulled`, задача остаётся в `in_dev`, эскалации в
        журнале нет.

        Ловит мутацию: прогон после подтяжки снова берёт только каталог
        acceptance_tests/ — pytest «collected 0 items», задача уходит в
        `escalated`, исход `escalated`.
        """
        digest = self.write_long_lived(self.own, green=True)
        self.write_manifest({self.own: digest})
        outcome, text, _spy = self.pull_main()
        self.assertEqual(outcome, "pulled", text)
        self.assertEqual(self.state(), "in_dev", text)

    def test_ac2_long_lived_red_escalates(self):
        """Тот же случай с красным долгоживущим файлом: задача в `escalated`.

        Перечень называет свой файл `tests/`, файл падает. Исход подтяжки —
        `escalated`, задача в `escalated`, а текст эскалации называет
        упавший долгоживущий файл — красноту дал именно он, не пустой сбор.

        Ловит мутацию: долгоживущая группа передана, но её исход не
        учитывается — подтяжка `pulled`, задача в `in_dev`; а прогон без
        группы (пустой сбор) не назовёт файл в тексте эскалации.
        """
        digest = self.write_long_lived(self.own, green=False)
        self.write_manifest({self.own: digest})
        outcome, text, _spy = self.pull_main()
        self.assertEqual(outcome, "escalated", text)
        self.assertEqual(self.state(), "escalated", text)
        self.assertIn(Path(self.own).name, text,
                      "эскалация не называет упавший долгоживущий файл")

    def test_ac3_manifest_read_failure_is_named_refusal(self):
        """Перечень не читается при подтяжке: именованный отказ, не зелёный прогон.

        Планка несёт зелёный разовый файл и перечень со своим зелёным
        долгоживущим файлом. Два сбоя чтения перечня из дерева лока: git не
        ответил на `ls-tree` пути перечня; `show` перечня не отдал текст.
        В обоих исход подтяжки — не `pulled`/`fresh`, а текст отказа
        (журнал/печать) называет перечень.

        Ловит мутацию: сбой перечня молча сводится к пустой группе —
        прогон одной разовой группы зелёный, исход `pulled`.
        """
        digest = self.write_long_lived(self.own, green=True)
        self.write_manifest({self.own: digest})
        self.write_one_off()
        manifest_rel = self.manifest_rel

        def ls_tree_fails(branch, rel):
            if rel == manifest_rel:
                return None
            return disk_backed_ls_tree_files(branch, rel)

        def show_fails(branch, rel):
            if rel == manifest_rel and branch == self.LOCKED:
                return None, "МАРКЕР-СБОЙ-ЧТЕНИЯ"
            return disk_backed_show(branch, rel)

        for label, ls_tree, show in (("ls-tree перечня", ls_tree_fails,
                                      disk_backed_show),
                                     ("show перечня", disk_backed_ls_tree_files,
                                      show_fails)):
            with self.subTest(сбой=label):
                store.update_task(store.db(), self.TASK, state="in_dev")
                self.ls_tree, self.show = ls_tree, show
                outcome, text, _spy = self.pull_main()
                self.assertNotIn(outcome, ("pulled", "fresh"), text)
                self.assertIn("переч", text.lower(),
                              "отказ не называет сбой чтения перечня")

    def test_ac4_task_without_manifest_pulls_as_before(self):
        """Задача без перечня: прогоняется только каталог планки, исход прежний.

        Два вида «без перечня»: лок есть, но перечня в дереве лока нет
        (задача залочена до ADR-0020); лока нет вовсе. Планка — зелёный
        разовый файл. Исход — `pulled`, задача в `in_dev`, `acceptance.run`
        вызван один раз без долгоживущих файлов.

        Зелёный с рождения: держит поведение задач без перечня, которое
        правка не должна менять.
        """
        self.write_one_off()
        for label, locked in (("лок без перечня", self.LOCKED),
                              ("без лока", None)):
            with self.subTest(вид=label):
                store.update_task(store.db(), self.TASK, state="in_dev",
                                  tests_locked_sha=locked)
                outcome, text, spy = self.pull_main()
                self.assertEqual(outcome, "pulled", text)
                self.assertEqual(self.state(), "in_dev", text)
                self.assertEqual(spy.call_count, 1, text)
                self.assertEqual(self.extra_of(spy.call_args), [], text)

    def test_ac5_long_lived_group_comes_from_long_lived_manifest(self):
        """Долгоживущая группа берётся из `long_lived_manifest`, не из своего правила.

        `long_lived_manifest` подменён: он называет файл с именем вне
        соглашения о префиксе задачи (`tests/test_custom_selected_q.py`),
        а на диске перечня нет. Прогон после подтяжки обязан передать
        именно этот путь в `acceptance.run(…, extra=…)`. Отдельно —
        `orchestrator/pull.py` не читает и не разбирает перечень сам
        (ни имени файла перечня, ни его разбора, ни выбора по префиксу).

        Ловит мутацию: `pull.py` выбирает долгоживущие файлы собственным
        правилом (глоб `tests/test_<id>_*.py` или свой разбор перечня с
        диска) — подменённый путь не попадает в `extra`.
        """
        custom = "tests/test_custom_selected_q.py"
        digest = self.write_long_lived(custom, green=True)
        # Перечень ветки называет другой файл: свой разбор перечня с диска
        # передал бы в `extra` его, а не путь из `long_lived_manifest`.
        self.write_manifest({self.own: self.write_long_lived(self.own)})
        fake = mock.Mock(return_value=({custom: digest}, ""))
        patches = [mock.patch.object(acceptance_gates, "long_lived_manifest", fake)]
        if hasattr(pull, "long_lived_manifest"):
            patches.append(mock.patch.object(pull, "long_lived_manifest", fake))
        outcome, text, spy = self.pull_main(*patches)
        self.assertTrue(fake.called, "long_lived_manifest не вызван при подтяжке")
        self.assertEqual(outcome, "pulled", text)
        self.assertTrue(spy.called, text)
        extra = [str(p) for p in self.extra_of(spy.call_args)]
        self.assertTrue(any(p.replace("\\", "/").endswith(custom) for p in extra),
                        f"extra не несёт путь из long_lived_manifest: {extra}")
        source = inspect.getsource(pull)
        for own_rule in ("LONG_LIVED_MANIFEST_NAME", "parse_long_lived_manifest",
                         "sha256.txt", "long_lived_manifest_rel"):
            self.assertNotIn(own_rule, source,
                             f"pull.py несёт собственное правило: {own_rule}")


if __name__ == "__main__":
    unittest.main()
