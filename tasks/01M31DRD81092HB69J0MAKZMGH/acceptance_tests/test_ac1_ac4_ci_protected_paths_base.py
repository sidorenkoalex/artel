"""Приёмочные тесты AC-1..AC-4: джоб `protected-paths` сверяет изменённые
веткой файлы со списком `PROTECTED_PATHS` из ТЕКСТА `orchestrator/config.py`
БАЗЫ сравнения PR, а не из кода ветки (SPEC, требования 1-4).

Контракт вызова взят из SPEC дословно и повторяет образец
`scripts/ci_push_class.py` (требование 2, ADR-0016): логика живёт
python-модулем `scripts/ci_protected_paths.py` на stdlib, запускается БЕЗ
аргументов командной строки в каталоге чекаута PR, базу получает
переменной окружения `BASE_SHA` (тем же именем, каким её несёт
`.github/workflows/ci.yml` сегодня), и отвечает кодом возврата: 0 —
нарушений нет, ненулевой — нарушение либо нечитаемая база.

Песочница каждого сценария — СВОЙ временный git-репозиторий (`self.tdir`)
с двумя коммитами: база и «ветка PR». Артефакты задачи с диска здесь не
читаются — читается только сам скрипт репозитория.

Красен до реализации: модуля scripts/ci_protected_paths.py ещё нет — setUp
объявляет отсутствие файла, поэтому ни один тест не зеленеет случайно на
коде возврата 2 от несуществующего пути.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from orchestrator import config

REPO_ROOT = Path(config.__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "ci_protected_paths.py"

CONFIG_REL = "orchestrator/config.py"

# Маркеры «сообщение назвало источник списка» (AC-4): отказ обязан назвать
# то, чего не смог прочитать, а не ограничиться пустым ненулевым кодом.
REASON_MARKERS = (CONFIG_REL, "PROTECTED_PATHS", "BASE_SHA")

# Текст `orchestrator/config.py` базы, в котором значения `PROTECTED_PATHS`
# нет вовсе — «значение не разбирается» (SPEC, требование 3).
CONFIG_WITHOUT_LIST = ('# Защищённые пути переехали.\n'
                       'MAIN_BRANCH = "main"\n')


def protected_paths_source(paths) -> str:
    """Фрагмент `orchestrator/config.py` со списком защищённых путей — в
    той же многострочной форме, в какой список записан в настоящем
    `orchestrator/config.py` (перенос кортежа на вторую строку)."""
    quoted = [f'"{p}"' for p in paths]
    head = ", ".join(quoted[:2])
    tail = ", ".join(quoted[2:])
    body = f"({head},\n                   {tail})" if tail else f"({head},)"
    return ("# Защищённые пути — зона Оператора.\n"
            f"PROTECTED_PATHS = {body}\n"
            'MAIN_BRANCH = "main"\n')


class ProtectedPathsFromBaseTest(unittest.TestCase):
    """Сверка изменённых файлов со списком защищённых путей БАЗЫ PR."""

    def setUp(self):
        self.assertTrue(
            SCRIPT.is_file(),
            f"логика джоба обязана жить модулем scripts/{SCRIPT.name} "
            f"(SPEC, требование 2) — файла нет")
        self._fresh_repo()

    # --- песочница ---------------------------------------------------

    def _fresh_repo(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tdir = Path(tmp.name)
        self.env = {**os.environ, "HOME": str(self.tdir),
                    "GIT_CONFIG_NOSYSTEM": "1"}
        self._git("init", "-q")
        self._git("config", "user.email", "plank@example.invalid")
        self._git("config", "user.name", "plank")
        self._git("config", "commit.gpgsign", "false")

    def _git(self, *args) -> subprocess.CompletedProcess:
        res = subprocess.run(["git", *args], cwd=self.tdir, env=self.env,
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(res.returncode, 0,
                         f"git {' '.join(args)}: {res.stderr}")
        return res

    def _commit(self, files: dict, message: str) -> str:
        for rel, text in files.items():
            path = self.tdir / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", message)
        return self._git("rev-parse", "HEAD").stdout.strip()

    def _run_job(self, base_sha: str) -> tuple:
        """(код возврата, stdout+stderr) прогона логики джоба в чекауте."""
        res = subprocess.run([sys.executable, str(SCRIPT)], cwd=self.tdir,
                             env={**self.env, "BASE_SHA": base_sha},
                             capture_output=True, text=True, timeout=120)
        return res.returncode, res.stdout + res.stderr

    def _scenario(self, base_config, branch_config, changed: dict) -> tuple:
        """База с текстом `orchestrator/config.py` `base_config` -> ветка с
        текстом `branch_config` и правками `changed`. `None` любого из
        текстов — файла в этом коммите нет."""
        self._fresh_repo()
        base_files = {"README.md": "база\n"}
        if base_config is not None:
            base_files[CONFIG_REL] = base_config
        base_sha = self._commit(base_files, "база")

        branch_files = dict(changed)
        if branch_config is not None:
            branch_files[CONFIG_REL] = branch_config
        self._commit(branch_files, "ветка PR")
        return self._run_job(base_sha)

    def _assert_failed_with_reason(self, rc: int, out: str, case: str) -> None:
        self.assertNotEqual(
            rc, 0, f"{case}: зелёного исхода на нечитаемой базе нет:\n{out}")
        self.assertTrue(
            any(marker in out for marker in REASON_MARKERS),
            f"{case}: отказ обязан назвать причину (один из {REASON_MARKERS}), "
            f"вывод:\n{out}")

    # --- критерии ----------------------------------------------------

    def test_ac1_path_absent_in_the_base_list_is_not_a_violation(self):
        """Ветка впервые создаёт `models.yaml` и тем же изменением вносит
        его в `PROTECTED_PATHS`; в базе пути в списке ещё нет.

        Джоб обязан остаться зелёным: именно этот сценарий сегодня не
        проводится ни веткой, ни приложением к PLAN (SPEC, контекст,
        источник трения 1).

        Ловит мутацию: список взят из кода ВЕТКИ (сегодняшний однострочник
        `from orchestrator import config`) — путь в нём уже есть, и
        собственный PR ветки краснеет.
        """
        base = ("gates.yaml", "roles.yaml", "skills/")
        rc, out = self._scenario(
            base_config=protected_paths_source(base),
            branch_config=protected_paths_source(base + ("models.yaml",)),
            changed={"models.yaml": "tiers: {}\n"})

        self.assertEqual(rc, 0, f"нарушений быть не должно, вывод:\n{out}")

    def test_ac2_path_protected_in_the_base_is_named_and_fails(self):
        """Ветка правит `skills/spec-authoring.md`, уже защищённый в базе.

        Джоб обязан покраснеть и перечислить путь-нарушитель — как красит
        сегодня (SPEC, требование 4, второе предложение).

        Ловит мутацию: сверка ослаблена до точного равенства пути элементу
        списка, и префикс каталога `skills/` перестаёт ловить файл внутри
        него.
        """
        listing = protected_paths_source(("gates.yaml", "roles.yaml", "skills/"))
        rc, out = self._scenario(
            base_config=listing, branch_config=listing,
            changed={"skills/spec-authoring.md": "правка роли\n"})

        self.assertNotEqual(rc, 0, f"нарушение обязано красить джоб:\n{out}")
        self.assertIn("skills/spec-authoring.md", out,
                      f"отказ обязан назвать путь-нарушитель:\n{out}")

    def test_ac3_verdict_follows_the_base_list_not_the_branch_list(self):
        """Список ветки отличается от списка базы в ОБЕ стороны при одном и
        том же изменённом файле `skills/x.md`.

        Ответ обязан совпасть с ответом по списку БАЗЫ: путь защищён в базе
        и снят в ветке — красим; путь снят в базе и объявлен в ветке — не
        красим. Подмена списка в ветке на результат не влияет (SPEC,
        требование 2, последнее предложение).

        Ловит мутацию: список читается из базы, но при непрочитанном или
        пустом ответе тихо подменяется импортом `orchestrator.config`
        ветки — половины этого теста разъезжаются.
        """
        rc_protected, out_protected = self._scenario(
            base_config=protected_paths_source(("skills/",)),
            branch_config=protected_paths_source(("docs/",)),
            changed={"skills/x.md": "правка\n"})
        self.assertNotEqual(
            rc_protected, 0,
            f"путь защищён в базе — джоб красный, даже если ветка снимает "
            f"его из своего списка:\n{out_protected}")
        self.assertIn("skills/x.md", out_protected)

        rc_free, out_free = self._scenario(
            base_config=protected_paths_source(("docs/",)),
            branch_config=protected_paths_source(("skills/",)),
            changed={"skills/x.md": "правка\n"})
        self.assertEqual(
            rc_free, 0,
            f"путь НЕ защищён в базе — джоб зелёный, даже если ветка "
            f"объявляет его защищённым:\n{out_free}")

    def test_ac4_unreadable_base_list_fails_closed_with_the_reason(self):
        """Три способа не получить список базы: файла в базе нет; git не
        отвечает на саму базу; текст базы есть, а значения в нём нет.

        Каждый — ненулевой код возврата и названная причина: молчаливо
        зелёного исхода на нечитаемой базе нет (SPEC, требование 3,
        fail-closed ADR-0002).

        Ловит мутацию: неудачное чтение базы сведено к пустому списку
        защищённых путей — нарушений «не находится», и джоб зеленеет, так
        и не проверив ничего.
        """
        rc_no_file, out_no_file = self._scenario(
            base_config=None,
            branch_config=protected_paths_source(("skills/",)),
            changed={"skills/x.md": "правка\n"})
        self._assert_failed_with_reason(rc_no_file, out_no_file,
                                        "в базе нет orchestrator/config.py")

        self._fresh_repo()
        self._commit({CONFIG_REL: protected_paths_source(("skills/",))}, "база")
        self._commit({"skills/x.md": "правка\n"}, "ветка PR")
        rc_bad_sha, out_bad_sha = self._run_job("0" * 40)
        self._assert_failed_with_reason(rc_bad_sha, out_bad_sha,
                                        "git не отвечает на базу")

        rc_unparsed, out_unparsed = self._scenario(
            base_config=CONFIG_WITHOUT_LIST,
            branch_config=protected_paths_source(("skills/",)),
            changed={"skills/x.md": "правка\n"})
        self._assert_failed_with_reason(rc_unparsed, out_unparsed,
                                        "значение в базе не разбирается")


if __name__ == "__main__":
    unittest.main()
