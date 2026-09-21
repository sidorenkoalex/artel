"""Юнит-тесты orchestrator/retro_corpus.py: поля записи кэша ретро-корпуса
(SPEC 01M31ZHWJWRSACYMRWTCPBC0DM, требование 6).

Провайдер собирается НЕОБЯЗАТЕЛЬНЫМ полем: перенос его в `RETRO_FIELDS`
(обязательная тройка, по которой снапшот опознаётся как ретро) молча
вычистил бы из кэша весь исторический корпус — все RETRO, закрытые до
появления поля. Приёмочная планка задачи это стережёт, но в CI входит
только `tests/` (`.github/workflows/ci.yml`), поэтому регресс держится
здесь (REVIEW.md итерации 1, R1-F3).

Git здесь подменён на уровне `gitcmd.in_repo`: предмет теста — какие поля
`_retro_entry` кладёт в запись, а не умение git отдать снапшот (последнее
проверяет планка задачи на настоящем репозитории).
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import retro_corpus  # noqa: E402

TARGET = "podopytnyi"
REF = "refs/artifacts/T001"
SNAPSHOT_FILE = "tasks/T001/RETRO.md"

OPERATOR = "оператор"
MODEL = "alfa-model-x"
ARTEL_SHA = "abcdef01" * 5
PROVIDER = "alfa-cli"


def _frontmatter(provider: str = None) -> str:
    fields = [f"operator: {OPERATOR}", f"model: {MODEL}",
              f"artel_sha: {ARTEL_SHA}"]
    if provider is not None:
        fields.append(f"provider: {provider}")
    return "---\n" + "\n".join(fields) + "\n---\n\n# RETRO: T001\n"


def _ok(stdout: str):
    return subprocess.CompletedProcess(args=(), returncode=0, stdout=stdout)


class RetroEntryFieldsTest(unittest.TestCase):
    """Запись кэша из снапшота: обязательная тройка полей плюс
    необязательные, если frontmatter их несёт."""

    def entry(self, provider: str = None) -> dict:
        def in_repo(_workspace, *args):
            if args[0] == "ls-tree":
                return _ok(f"{SNAPSHOT_FILE}\n")
            return _ok(_frontmatter(provider))

        with mock.patch.object(retro_corpus.gitcmd, "in_repo", in_repo):
            return retro_corpus._retro_entry(TARGET, REF)

    def test_snapshot_with_a_provider_carries_it_into_the_entry(self):
        """Провайдер frontmatter попадает в запись кэша своим полем
        рядом с прежней тройкой.

        Ловит мутацию: `OPTIONAL_RETRO_FIELDS` перестали собираться в
        запись (собирающий словарь снова строится по одной `RETRO_
        FIELDS`) — разрез расхода по провайдерам корпусу не достанется,
        и `assertEqual` на значении поля покраснеет.
        """
        entry = self.entry(provider=PROVIDER)

        self.assertEqual(PROVIDER, entry["provider"])
        self.assertEqual(MODEL, entry["model"])

    def test_snapshot_without_a_provider_still_lands_on_the_old_fields(self):
        """Снапшот без провайдера (любой RETRO, закрытый до этой задачи)
        собирается по-прежнему: запись есть, тройка полей на месте, и
        ключа провайдера в ней нет вовсе.

        Ловит мутацию: `provider` перенесён в `RETRO_FIELDS` —
        `all(field in meta ...)` перестаёт выполняться, `_retro_entry`
        отдаёт `None`, и весь исторический корпус молча исчезает из
        кэша; встречная мутация — провайдер кладётся в запись значением
        `None`, неотличимым от честного «провайдер неизвестен».
        """
        entry = self.entry()

        self.assertIsNotNone(entry, "снапшот без провайдера выпал из корпуса")
        self.assertEqual(
            {"task_id": "T001", "target": TARGET, "operator": OPERATOR,
             "model": MODEL, "artel_sha": ARTEL_SHA},
            entry)

    def test_required_fields_stay_the_historical_triple(self):
        """`RETRO_FIELDS` — ровно те три поля, по которым снапшот
        опознаётся как ретро.

        Ловит мутацию: в обязательные добавлено новое поле — снапшоты,
        закрытые до его появления, перестают опознаваться, а сборка
        кэша молча возвращает меньше записей.
        """
        self.assertEqual(("operator", "model", "artel_sha"),
                         retro_corpus.RETRO_FIELDS)


if __name__ == "__main__":
    unittest.main()
