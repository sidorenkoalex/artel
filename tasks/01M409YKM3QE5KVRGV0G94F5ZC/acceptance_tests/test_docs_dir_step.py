"""Документы задачи на шаге роли: выкладка в каталог документов из ссылки,
отсутствие документов в рабочей копии кода, автокоммит правки роли в
ссылку.

Группа: разовый

Красен до реализации: `runner.role_cwd` выкладывает `tasks/<id>/` из ссылки внутрь рабочей копии кода (`.artel/worktrees/<id>`), а каталога `.artel/projects/<проект>/tasks/<id>/` пульт не заводит и не читает — на старте шага каталога документов нет (AC-1), а документы лежат в рабочей копии кода (AC-2); правку роли в каталоге документов автокоммит не видит, ссылка не двигается (AC-3).

Группа «разовый», хотя свойство живёт в коде: сценарий читает ссылку
документов (`artifact_branch.read_tree`/`ref_head`) и сверяет историю git
(`merge-base --is-ancestor`), а долгоживущему файлу то и другое запрещено
статической проверкой выхода из `tests_writing`. Постоянных сторожей тех
же свойств в `tests/` пишет разработчик (SPEC, требование 7).

Сценарий общий (`_sandbox.DocsStepSandbox`): задача артели (`target` по
умолчанию — `config.DEFAULT_TARGET`) в `tests_writing` на настоящем git,
шаг test_author штатным `runner.cmd_run`; «роль» — функция, исполняемая в
момент запуска агента, то есть после всей подготовки шага пультом. Имена и
содержимое файлов документов выбираются случайно; зерно печатается и
входит в текст провала.
"""
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import artifact_branch, config  # noqa: E402

from _sandbox import DocsStepSandbox, disk_tree, docs_dir, ref_tree  # noqa: E402

# AC-10: escalate — какой сценарий значит «отказ от сверки фиксации» для правки роли в каталоге документов? Правку, сделанную ролью во время шага, автокоммит переносит в ссылку и сразу перефиксирует (`store.record_fixation`), поэтому ни `fixation.check_integrity`, ни `fsm.confirm_fixation` её не отклоняют — ни сегодня (правка в рабочей копии кода), ни после выноса; лок `acceptance_tests/` и перечень сумм проверяемы однозначно. Варианты: (а) роль сама двигает `refs/artifacts/<id>` мимо автокоммита (`git update-ref`/`commit-tree` из шага) — следующий старт шага отказывает инцидентом целостности; (б) после шага каталог документов расходится с зафиксированным коммитом ссылки (файл, который автокоммит не перенёс) — переход отклоняется как «рабочая копия артефактов грязная»; (в) убрать «сверку фиксации» из AC-10, оставить лок `acceptance_tests/` и перечень сумм долгоживущих тестов. Дефолт при молчании — (в).


class DocsDirMirrorsRefBeforeStepTest(DocsStepSandbox):

    def test_ac1_docs_dir_equals_ref_head_tree_at_step_start(self):
        """На старте шага каталог документов — зеркало головы ссылки.

        Сценарий: в ссылку `refs/artifacts/<id>` задачи артели дописаны
        случайные файлы (в корне `tasks/<id>/` и во вложенном каталоге);
        в каталоге документов до шага лежит мусор — файл, которого в
        ссылке нет, и (случайно) устаревшая версия одного из файлов
        ссылки. В момент запуска агента файлы
        `.artel/projects/<проект>/tasks/<id>/` (пути и байты) в точности
        равны дереву `tasks/<id>/` головы ссылки.

        Ловит мутацию: документы выкладываются не в каталог документов
        (в рабочую копию кода, как до задачи) — каталог пуст; выкладка
        только дописывает файлы и не убирает лишние — мусорный файл
        остаётся; выкладка не перезаписывает существующие — устаревшая
        версия остаётся; выкладка берёт не голову ссылки."""
        files = {f"{self.word()}.md": f"документ {self.word()}\n",
                 f"{self.word()}/{self.word()}.txt": f"вложенный {self.word()}\n"}
        for _ in range(self.rnd.randint(0, 2)):
            files[f"{self.word()}.txt"] = f"ещё {self.word()}\n"
        self.commit_docs(files, "документы песочницы")
        target_dir = docs_dir(self.TASK)
        stale = target_dir / f"{self.word()}-stale.md"
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_text("мусор прошлого шага\n", encoding="utf-8")
        if self.rnd.random() < 0.5:
            old = target_dir / next(iter(files))
            old.parent.mkdir(parents=True, exist_ok=True)
            old.write_text("устаревшая версия\n", encoding="utf-8")
        seen = {}

        def role(cmd, kwargs):
            seen["disk"] = disk_tree(target_dir)
            seen["ref"] = ref_tree(self.TASK)

        step = self.run_step(role)

        self.assertTrue(step["calls"], self.note(
            f"агент не запущен: {step['refusal']}\n{step['output']}"))
        self.assertIn(f"{next(iter(files))}", seen["ref"],
                      self.note("фикстура: файл не попал в ссылку"))
        self.assertEqual(sorted(seen["disk"]), sorted(seen["ref"]), self.note(
            f"состав каталога документов {target_dir} на старте шага не "
            f"равен дереву ссылки"))
        self.assertEqual(seen["disk"], seen["ref"], self.note(
            "содержимое каталога документов не равно дереву ссылки"))


class NoDocsInCodeCopyTest(DocsStepSandbox):

    def test_ac2_code_copy_has_no_docs_before_and_after_step(self):
        """В рабочей копии кода задачи нет документов ни до шага, ни после.

        Сценарий: в ссылке задачи артели — SPEC и случайные файлы
        документов (в корне и во вложенном каталоге); шаг test_author,
        «роль» пишет в каталог документов новый файл планки. В момент
        запуска агента и после шага в `.artel/worktrees/<id>` (без `.git`)
        нет каталога `tasks/<id>/` и нет ни одного файла со случайным
        именем документа задачи.

        Ловит мутацию: выкладка документов перед шагом по-прежнему идёт в
        рабочую копию кода (рядом с каталогом документов или вместо него);
        уборка `acceptance_tests/`/документов из рабочей копии забыта на
        пути шага."""
        files = {f"{self.word()}.md": f"документ {self.word()}\n",
                 f"{self.word()}/{self.word()}.txt": f"вложенный {self.word()}\n"}
        self.commit_docs(files, "документы песочницы")
        # Имена — только случайные: у кода есть свои `SPEC.md`/`PLAN.md`
        # (`templates/`), совпадение с ними документом задачи не является.
        names = {rel.rsplit("/", 1)[-1] for rel in files}
        new_test = f"test_{self.word()}.py"
        names.add(new_test)
        seen = {}

        def role(cmd, kwargs):
            seen["before"] = self.code_copy_doc_hits(names)
            plank = docs_dir(self.TASK) / "acceptance_tests"
            plank.mkdir(parents=True, exist_ok=True)
            (plank / new_test).write_text("# планка роли\n", encoding="utf-8")

        step = self.run_step(role)

        self.assertTrue(step["calls"], self.note(
            f"агент не запущен: {step['refusal']}\n{step['output']}"))
        self.assertTrue(self.wt.is_dir(), self.note(
            f"рабочая копия кода {self.wt} не заведена"))
        self.assertEqual(seen["before"], [], self.note(
            "перед шагом роли документы в рабочей копии кода"))
        self.assertEqual(self.code_copy_doc_hits(names), [], self.note(
            "после шага роли документы в рабочей копии кода"))


class RoleEditReachesRefTest(DocsStepSandbox):

    def test_ac3_role_edit_and_new_file_in_docs_dir_reach_ref(self):
        """Правка и новый файл роли в каталоге документов уходят в ссылку.

        Сценарий: в ссылке — файл планки `acceptance_tests/test_<x>.py`;
        «роль» (test_author в `tests_writing`) в каталоге документов
        переписывает его случайным текстом и создаёт новый
        `acceptance_tests/test_<y>.py`. После шага голова
        `refs/artifacts/<id>` — новый коммит, потомок прежней головы, а
        её дерево несёт оба файла ровно с текстом роли.

        Ловит мутацию: автокоммит шага читает рабочую копию кода, а не
        каталог документов — ссылка не двигается; автокоммит пишет коммит
        без родителя или от другой базы (не потомок прежней головы);
        переносит только новые файлы, а правку существующего теряет."""
        existing = f"acceptance_tests/test_{self.word()}.py"
        self.commit_docs({existing: "# исходная планка\n"}, "планка песочницы")
        before = artifact_branch.ref_head(self.TASK)
        created = f"acceptance_tests/test_{self.word()}.py"
        edited_text = f"# правка роли {self.word()}\n"
        created_text = f"# новый файл роли {self.word()}\n"

        def role(cmd, kwargs):
            target_dir = docs_dir(self.TASK)
            (target_dir / existing).parent.mkdir(parents=True, exist_ok=True)
            (target_dir / existing).write_text(edited_text, encoding="utf-8")
            (target_dir / created).write_text(created_text, encoding="utf-8")

        step = self.run_step(role)

        self.assertTrue(step["calls"], self.note(
            f"агент не запущен: {step['refusal']}\n{step['output']}"))
        after = artifact_branch.ref_head(self.TASK)
        self.assertTrue(after and after != before, self.note(
            f"голова ссылки не сдвинулась: {before}\n{step['output']}"))
        ancestry = subprocess.run(
            ["git", "merge-base", "--is-ancestor", before, after],
            cwd=config.ROOT, capture_output=True, text=True)
        self.assertEqual(ancestry.returncode, 0, self.note(
            f"новая голова {after} не потомок прежней {before}"))
        tree = ref_tree(self.TASK)
        self.assertEqual(tree.get(existing), edited_text.encode("utf-8"),
                         self.note(f"правка {existing} не в ссылке"))
        self.assertEqual(tree.get(created), created_text.encode("utf-8"),
                         self.note(f"новый {created} не в ссылке"))


if __name__ == "__main__":
    unittest.main()
