"""Регенерация стухшей карты кодовой базы при сборке брифа при подложном `python3` первым в PATH.

Группа: долгоживущий
Красен до реализации: регенерация карты в `brief` зовёт голый `python3`, подложный `python3` первым в PATH падает кодом 1 — бриф получает прежнюю карту с пометкой «КАРТА НЕАКТУАЛЬНА».

Сценарий — публичная `brief.fresh_map_text` (карта для брифа) в настоящем
git-репозитории песочницы (`tests/sandbox.py::RealGitSandbox`): связка
«сверка свежести карты по git — регенерация — откат правки» держится
только настоящим git. Карта закоммичена с `built_at_sha` коммита, после
которого изменён `orchestrator/*.py`, — карта стухла, бриф обязан её
регенерировать. Регенератор — заглушка `scripts/codebase_map.py`,
пишущая карту со случайной меткой.

Число правленых модулей, метка карты и текст подложного `python3` — от
зерна; зерно печатается и входит в текст каждого провала.

Валидировано временным стабом реализации (регенерация под
`sys.executable`): тест зелёный, стаб удалён.
"""
import os
import random
import shutil
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import brief, config, store
from tests.sandbox import RealGitSandbox

MAP_REL = "docs/codebase-map.md"
STALE_NOTE = "КАРТА НЕАКТУАЛЬНА"
STUB_OK = (
    "import pathlib\n"
    "path = pathlib.Path('docs') / 'codebase-map.md'\n"
    "path.parent.mkdir(parents=True, exist_ok=True)\n"
    "path.write_text({text!r}, encoding='utf-8')\n")


class BriefStaleMapSandbox(RealGitSandbox):
    """Главная копия пульта — репозиторий песочницы: регенератор-заглушка,
    карта с `built_at_sha` его коммита и правка модулей пульта после."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.marker = f"регенерировано для брифа {self.rng.randrange(10**9)}"
        (self.root / "scripts").mkdir(parents=True, exist_ok=True)
        (self.root / "scripts" / "codebase_map.py").write_text(
            STUB_OK.format(text=f"---\nbuilt_at_sha: x\n---\n\n{self.marker}\n"),
            encoding="utf-8")
        self.git("add", "scripts/codebase_map.py")
        self.git("commit", "-q", "-m", "регенератор-заглушка")
        base_sha = self.git("rev-parse", "HEAD").strip()
        self.committed_map = (f"---\nbuilt_at_sha: {base_sha}\n---\n\n"
                              f"прежняя карта\n")
        (self.root / "docs").mkdir(parents=True, exist_ok=True)
        (self.root / MAP_REL).write_text(self.committed_map, encoding="utf-8")
        self.git("add", MAP_REL)
        self.git("commit", "-q", "-m", "карта")
        (self.root / "orchestrator").mkdir(parents=True, exist_ok=True)
        for number in range(self.rng.randint(1, 3)):
            (self.root / "orchestrator" / f"m{number}.py").write_text(
                f"VALUE = {self.rng.randrange(10**6)}\n", encoding="utf-8")
        self.git("add", "orchestrator")
        self.git("commit", "-q", "-m", "правка модулей пульта после карты")

        self.task = "T001"
        store.insert_task(store.db(), self.task, "Задача брифа", "in_dev",
                          "task/t001-x", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

    def note(self, text: str) -> str:
        return f"{text} (зерно {self.seed})"

    def put_fake_python3_first(self) -> None:
        """Подложный `python3` первым в PATH: завершается кодом 1."""
        bindir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, bindir, ignore_errors=True)
        fake = bindir / "python3"
        fake.write_text(
            "#!/bin/sh\n"
            f"echo 'подложный python3 {self.rng.randrange(10**6)}' >&2\n"
            "exit 1\n", encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP
                   | stat.S_IXOTH)
        patcher = mock.patch.dict(
            os.environ, {"PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}"})
        patcher.start()
        self.addCleanup(patcher.stop)


class BriefMapInterpreterTest(BriefStaleMapSandbox):

    def test_ac3_brief_gets_regenerated_map_with_fake_python3(self):
        """Бриф получает регенерированную карту при подложном `python3` первым в PATH.

        Сценарий: карта стухла (после её `built_at_sha` изменён модуль
        `orchestrator/`), первым в PATH стоит `python3`, завершающийся
        кодом 1. `brief.fresh_map_text` возвращает текст регенератора со
        случайной меткой без пометки «КАРТА НЕАКТУАЛЬНА»; закоммиченная
        карта в рабочем дереве восстановлена.

        Ловит мутацию: регенерация в `brief` снова зовёт голый `python3` —
        подложный интерпретатор падает, бриф получает прежнюю карту с
        пометкой «КАРТА НЕАКТУАЛЬНА» и без метки регенератора.
        """
        self.put_fake_python3_first()

        text = brief.fresh_map_text(store.db(), self.task)

        context = self.note(f"карта брифа:\n{text}")
        self.assertIn(self.marker, text, context)
        self.assertNotIn(STALE_NOTE, text, context)
        self.assertEqual((self.root / MAP_REL).read_text(encoding="utf-8"),
                         self.committed_map, context)


if __name__ == "__main__":
    unittest.main()
