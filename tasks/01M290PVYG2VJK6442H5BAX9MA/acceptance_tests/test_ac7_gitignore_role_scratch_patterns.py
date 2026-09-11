"""AC-7 (tasks/01M290PVYG2VJK6442H5BAX9MA/SPEC.md): `.gitignore` пульта
несёт шаблоны `.git-commit-msg*.txt` и рабочие файлы ролей первого
уровня репозитория (`_*.txt`, `_*.md`) — такие файлы не подхватывает ни
один `git add -A`, включая запускаемый самой ролью до чекпоинта.

Красен до реализации (первые два теста): `.gitignore` репозитория
сегодня не несёт ни `.git-commit-msg*.txt`, ни `_*.txt`/`_*.md` в
корне — `.git-commit-msg-T001.txt`/`_head_map.md`/`_notes.txt` реально
попадают под `git add -A`. Третий тест (привязка шаблона к корню, не
на любую глубину) зелёный с рождения: сегодняшний `.gitignore` вообще
не содержит `_*.md` ни в каком виде, поэтому вложенный `_notes.md`
и так не игнорируется — тест фиксирует границу, которую обязана
удержать будущая реализация (не расширять `_*.md`/`_*.txt` глубже
корня), а не наблюдает регрессию прямо сейчас.

Проверка — реальным git во временном репозитории, скопировавшем ТЕКУЩИЙ
`.gitignore` дерева (не копия правил текстом): семантика `.gitignore`
(привязка к корню, приоритет правил) проверяется исполнением `git add`/
`git status`, не regex по содержимому файла.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

REPO_ROOT = Path(__file__).resolve().parents[3]


class GitignoreRoleScratchPatternsTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "artel-tests@example.invalid")
        self.git("config", "user.name", "artel tests")
        shutil.copy(REPO_ROOT / ".gitignore", self.root / ".gitignore")
        (self.root / "marker.txt").write_text("main\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

    def git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        res = subprocess.run(["git", *args], cwd=self.root,
                             capture_output=True, text=True)
        if check:
            self.assertEqual(res.returncode, 0,
                             f"git {' '.join(args)}: {res.stderr}")
        return res

    def test_ac7_commit_msg_scratch_file_is_ignored_by_git_add(self):
        """`.git-commit-msg-T001.txt» (скил coding-standards: сообщение
        коммита через `-m`/`-F` из временного каталога сессии) — не
        подхватывается `git add -A` роли.

        Ловит мутацию: шаблон `.git-commit-msg*.txt` не добавлен в
        `.gitignore` (или добавлен с опечаткой в расширении/маске) —
        файл реально застейджится, `assertNotIn` ниже покраснеет."""
        (self.root / ".git-commit-msg-T001.txt").write_text(
            "сообщение коммита роли\n", encoding="utf-8")

        self.git("add", "-A")

        status = self.git("status", "--porcelain").stdout
        self.assertNotIn(".git-commit-msg-T001.txt", status)

    def test_ac7_role_scratch_file_at_repo_root_is_ignored_by_git_add(self):
        """`_*.md`/`_*.txt» первого уровня репозитория — рабочие файлы
        ролей (черновик карты кодовой базы и подобное, инцидент 11.09
        01M28NX43E) — не подхватываются `git add -A`.

        Ловит мутацию: шаблон `_*.md`/`_*.txt` не добавлен в `.gitignore`
        корня — `_head_map.md`/`_notes.txt` реально попадут под `git add
        -A`, `assertNotIn` ниже покраснеет."""
        (self.root / "_head_map.md").write_text("черновик карты\n",
                                                 encoding="utf-8")
        (self.root / "_notes.txt").write_text("черновик заметок\n",
                                               encoding="utf-8")

        self.git("add", "-A")

        status = self.git("status", "--porcelain").stdout
        self.assertNotIn("_head_map.md", status)
        self.assertNotIn("_notes.txt", status)

    def test_ac7_role_scratch_pattern_does_not_reach_into_subdirectories(self):
        """Шаблон касается ТОЛЬКО корня репозитория (SPEC, требование 5:
        «в корне репозитория») — одноимённый файл внутри обычного
        каталога (например `tasks/<id>/acceptance_tests/_notes.md`,
        легитимный вспомогательный файл планки приёмки, скил
        test-authoring) не обязан пострадать от того же шаблона по
        недосмотру диапазона.

        Ловит мутацию: шаблон `.gitignore` написан без привязки к корню
        (без ведущего `/` перед `_*.md`) — совпадает на любой глубине,
        нетронутый `_notes.md` внутри каталога задачи тоже игнорируется,
        и `assertIn` ниже (файл ОБЯЗАН попасть под `add`) покраснеет."""
        nested = self.root / "tasks" / "T001" / "acceptance_tests"
        nested.mkdir(parents=True)
        (nested / "_notes.md").write_text("легитимный файл планки\n",
                                          encoding="utf-8")

        self.git("add", "-A")

        status = self.git("status", "--porcelain").stdout
        self.assertIn("_notes.md", status)


if __name__ == "__main__":
    unittest.main()
