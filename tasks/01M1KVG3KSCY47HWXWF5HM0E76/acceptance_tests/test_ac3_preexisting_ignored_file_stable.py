"""AC-3 (SPEC): «Игнорируемый файл, уже находящийся в артефактной ветке,
при последующих автокоммитах не порождает удаления записи, если файл
отсутствует в рабочем каталоге задачи, и не порождает добавления
записи, если файл присутствует в рабочем каталоге задачи».

Сценарий — ровно тот, что легализован ADR-0013 «вариант A» (SPEC
«Контекст»): `.pyc`, занесённый ДО этой задачи (когда автокоммит ещё не
фильтровал `.gitignore`), уже лежит в артефактной ветке; последующие шаги
той же роли не обязаны ни убирать его, ни трогать его содержимое —
трактуется как файл вне учёта автокоммита вовсе, симметрично в обе
стороны.

Красен до реализации: файл целиком красен из-за второго теста ниже —
но краснота смешанная, по методу, не по файлу равномерно (оба метода
вместе проверяют требование 2 симметрично, но живут на разных путях
сегодняшнего кода). Первый тест ниже уже ЗЕЛЁН сегодня, но СЛУЧАЙНО, не
по проектному замыслу — `checkpoint._commit_external_step_artifacts`
не делает ни одного исключения для игнорируемых путей по `.gitignore`
вовсе; кандидат на удаление (`removed`) находит путь по «последний
коммит — автокоммит этой же роли» (совпадает — сообщение seed-коммита
нарочно повторяет формат автокоммита) И по frontmatter `type` в
`_DELETABLE_ARTIFACT_TYPES`, а `yamlmini.frontmatter` на бинарном
содержимом `.pyc` фронтматтер не находит (`meta is None`) — .pyc
выживает благодаря этому совпадению, не благодаря фильтрации, которую
проверяет требование 2. Второй тест ниже красен по-настоящему: `files`
сегодня собираются безусловным `task_dir.rglob("*")` (никакого фильтра
по игнорируемым путям), `.pyc` из рабочего каталога перезапишет запись
в артефактной ветке новым содержимым NEW — `assertEqual` на старое
значение OLD упадёт.
"""
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import artifact_branch, checkpoint, store  # noqa: E402
from _sandbox import GitignoreExternalTargetSandbox  # noqa: E402

PYC_REL = "acceptance_tests/__pycache__/test_ac.cpython-311.pyc"


class PreexistingIgnoredFileStableTest(GitignoreExternalTargetSandbox):

    def seed_preexisting_pyc(self, content: bytes = b"\x00OLD\xff") -> None:
        """Кладёт `.pyc` в артефактную ветку НАПРЯМУЮ (`artifact_branch.
        commit_files`, в обход автокоммита) — имитация файла, занесённого
        ДО этой задачи (инцидент 03.09), а не файла, который сейчас
        коммитит проверяемый код."""
        sha = artifact_branch.commit_files(
            self.TASK,
            {f"tasks/{self.TASK}/{PYC_REL}": content,
             f"tasks/{self.TASK}/PLAN.md": "план разработчика\n"},
            f"{self.TASK}: артефакты шага developer (автокоммит оркестратора)")
        self.assertTrue(sha, "seed-коммит артефактной ветки обязан пройти")

    def test_ac3_absent_from_workdir_does_not_delete_preexisting_ignored_file(self):
        """`.pyc` уже в артефактной ветке; на текущем шаге роль пишет
        только `REVIEW.md`, `.pyc` в `task_dir` не появляется вовсе (его
        там и не может быть — файл игнорируемый, роль его не создаёт).
        Автокоммит не имеет права счесть его отсутствие в `task_dir`
        удалением.

        Ловит мутацию: включение игнорируемых путей в сравнение
        `existing - files` без исключения — `.pyc`, отсутствующий в
        `files` (он никогда не читается с диска, раз его там нет), будет
        сочтён кандидатом на удаление тем же путём, что и обычный файл
        роли (что «последний коммит — автокоммит developer» совпадает) —
        `assertIn` на `.pyc` после шага упадёт.
        """
        self.seed_preexisting_pyc()
        self.write("REVIEW.md", "ревью")

        checkpoint.commit_step_artifacts(store.db(), self.TASK, "developer")

        files = self.artifact_branch_files()
        self.assertIn(f"tasks/{self.TASK}/{PYC_REL}", files,
                      "игнорируемый файл не должен исчезать из-за своего "
                      "отсутствия в рабочем каталоге")
        self.assertIn(f"tasks/{self.TASK}/REVIEW.md", files)

    def test_ac3_present_in_workdir_does_not_update_preexisting_ignored_file(self):
        """`.pyc` уже в артефактной ветке с содержимым OLD; на этом шаге
        тот же путь СЛУЧАЙНО оказался и в `task_dir` (например, роль
        повторно прогнала тесты локально) с ДРУГИМ содержимым NEW.
        Автокоммит не имеет права считать это добавлением/обновлением
        записи — запись в артефактной ветке обязана остаться прежней.

        Ловит мутацию: включение игнорируемых путей в `files` (обычное
        чтение `task_dir.rglob("*")` без исключения) — `.pyc` перепишется
        новым содержимым NEW, `assertEqual` на старое содержимое упадёт.
        """
        self.seed_preexisting_pyc(content=b"OLD")
        self.write(PYC_REL, b"NEW")
        self.write("REVIEW.md", "ревью")

        checkpoint.commit_step_artifacts(store.db(), self.TASK, "developer")

        text = self.artifact_branch_text(f"tasks/{self.TASK}/{PYC_REL}")
        self.assertEqual(text, "OLD",
                         "присутствие игнорируемого файла в рабочем "
                         "каталоге не должно порождать запись/перезапись")


if __name__ == "__main__":
    unittest.main()
