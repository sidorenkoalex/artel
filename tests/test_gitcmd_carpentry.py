"""Юнит-тесты `gitcmd.carpentry` (SPEC 01M1KVGD18P9H5WR7VM8TGPV1T, требования
2-3): единая точка `subprocess.run` для плотницкой записи артефактной ветки
(`artifact_branch.write_commit`/`commit_files`) — раньше `artifact_branch.py`
звал `subprocess.run` напрямую, в обход `gitcmd` и любой его подмены, и
утекал в НАСТОЯЩИЙ репозиторий пульта из тестов, подменявших только
`gitcmd.git` (SPEC «Контекст»).

Реальный git (не заглушка): предмет проверки — что `carpentry` фактически
передаёт `repo`/`env`/`input`/`text` в `subprocess.run` так, как ожидает
`write_commit` (собственное окружение `GIT_INDEX_FILE`, бинарный stdin/
stdout `hash-object`, произвольный `repo`, не только `config.ROOT`).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import gitcmd  # noqa: E402


class CarpentryTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.repo,
                       check=True)
        self.env = {**os.environ, "GIT_INDEX_FILE": str(self.repo / "custom-index")}

    def test_runs_git_in_the_given_repo_independent_of_cwd(self):
        """`repo` — явный параметр, не текущая рабочая директория процесса:
        плотницкая запись `write_commit` идёт и в клон целевого (`snapshot.
        publish_and_cleanup`), не только в `config.ROOT`.

        Ловит мутацию: `carpentry` зовёт `subprocess.run` с `cwd=None`
        (или игнорирует `repo`) — тогда git исполнился бы в текущей
        рабочей директории процесса тестов, не в переданном временном
        репозитории, и `git rev-parse --git-dir` увидел бы чужой `.git`.
        """
        res = gitcmd.carpentry(self.repo, ["rev-parse", "--git-dir"], self.env)

        self.assertEqual(res.returncode, 0)
        self.assertEqual((self.repo / res.stdout.strip()).resolve(),
                         (self.repo / ".git").resolve())

    def test_env_reaches_the_git_process(self):
        """`GIT_INDEX_FILE` — то, ради чего `write_commit` держит собственное
        окружение: плотницкая запись не трогает индекс основной рабочей
        копии.

        Ловит мутацию: `carpentry` зовёт `subprocess.run` без `env=env`
        (или с `env=None`) — тогда git взял бы окружение процесса тестов
        со своим `GIT_INDEX_FILE`/без него, `custom-index` не появился бы
        на диске, и `write_commit` тайно попортил бы индекс основной
        рабочей копии вместо изолированного плотницкого.
        """
        blob = gitcmd.carpentry(self.repo, ["hash-object", "-w", "--stdin"],
                                self.env, input=b"content", text=False)
        upd = gitcmd.carpentry(
            self.repo, ["update-index", "--add", "--cacheinfo",
                       f"100644,{blob.stdout.decode().strip()},marker.txt"],
            self.env)

        self.assertEqual(blob.returncode, 0)
        self.assertEqual(upd.returncode, 0)
        self.assertTrue((self.repo / "custom-index").exists(),
                        "GIT_INDEX_FILE не дошёл до git")

    def test_text_false_returns_bytes_stdout(self):
        """`hash-object` бинарных артефактов (REVIEW.md T094 итерация 2,
        замечание 1): `text=False` — вызывающий код сам решает, декодировать
        ли ответ.

        Ловит мутацию: `carpentry` игнорирует переданный `text=False` (или
        всегда передаёт `text=True` дальше в `subprocess.run`) — тогда
        `blob.stdout` пришёл бы `str`, и `write_commit` упал бы на
        бинарных артефактах, которые `str` не декодирует байт-в-байт.
        """
        blob = gitcmd.carpentry(self.repo, ["hash-object", "-w", "--stdin"],
                                self.env, input=b"binary\x00data", text=False)

        self.assertEqual(blob.returncode, 0)
        self.assertIsInstance(blob.stdout, bytes)

    def test_text_true_is_the_default(self):
        """Вызывающий код (`write_commit`) не передаёт `text=` явно на
        большинстве плотницких шагов — сигнатура `carpentry` обязана сама
        подставлять `text=True` по умолчанию.

        Ловит мутацию: значение по умолчанию параметра `text` меняется на
        `False` (или убирается вовсе, откатываясь к байтам `subprocess.
        run` по умолчанию) — тогда `res.stdout` пришёл бы `bytes`, и
        вызывающий код, ожидающий `str` (`.strip()` без `.decode()`),
        упал бы `TypeError`.
        """
        res = gitcmd.carpentry(self.repo, ["rev-parse", "--git-dir"], self.env)

        self.assertIsInstance(res.stdout, str)

    def test_failure_is_reported_by_return_code_not_exception(self):
        """Несуществующая плотницкая команда — обычный ненулевой код
        возврата: вызывающий код (`write_commit`) сам решает, что делать
        (`return ""`), без try/except вокруг `carpentry`.

        Ловит мутацию: `carpentry` добавляет `check=True` (или иначе
        поднимает исключение на ненулевом коде возврата) — тогда
        `write_commit` без try/except вокруг `carpentry` падал бы
        трейсбеком на первой же неудачной плотницкой команде вместо
        штатного `return ""`.
        """
        res = gitcmd.carpentry(self.repo, ["cat-file", "-p", "deadbeef"],
                               self.env)

        self.assertNotEqual(res.returncode, 0)


if __name__ == "__main__":
    unittest.main()
