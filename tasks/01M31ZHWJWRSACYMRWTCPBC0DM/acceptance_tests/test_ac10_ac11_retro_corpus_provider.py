"""AC-10, AC-11 — 01M31ZHWJWRSACYMRWTCPBC0DM: RETRO с провайдером попадает
в кэш ретро-корпуса с полем провайдера, RETRO без провайдера — по-прежнему
на прежних полях и без отказа сборки.

Источник — SPEC.md, «Критерии приёмки»:

AC-10. RETRO, несущий провайдера, попадает в кэш ретро-корпуса с полем
провайдера среди собираемых полей.

AC-11. RETRO без провайдера по-прежнему попадает в кэш ретро-корпуса на
прежних полях (`operator`, `model`, `artel_sha`), без отказа сборки.

Песочница здесь — НАСТОЯЩИЙ git-репозиторий во временном каталоге, а не
`tests.sandbox.TmpRootTest`: та подменяет `subprocess.run` спаем, который
фейкует `update-ref` пустым успехом, и `refs/artifacts/*` в ней завести
нечем (прецедент T051: мок душил git и красил планку мимо предмета).
Патчатся ровно три адреса — каталог клонов целевых, `targets.yaml` и путь
файла кэша, чтобы пересборка не трогала `.artel/` настоящего пульта.

Красен до реализации: `retro_corpus.RETRO_FIELDS` — `("operator",
"model", "artel_sha")`, и `_retro_entry` собирает запись кэша ровно по
ним (`orchestrator/retro_corpus.py:22,57-59`): провайдер снапшота в кэш
не попадает ни под каким именем. AC-11 сегодня зелёный — это регресс
существующего поведения, который наивное добавление провайдера в
`RETRO_FIELDS` (всё поле обязательно, `all(field in meta ...)`) как раз
и ломает.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _tokens  # noqa: E402
from orchestrator import config, retro_corpus  # noqa: E402

TARGET = "podopytnyi"

OPERATOR = "оператор планки"
MODEL = "alfa-model-x"
ARTEL_SHA = "abcdef01" * 5
PROVIDER = "alfa-cli"

TARGETS_TEXT = f"""targets:
  {TARGET}:
    forge: github
    url: https://example.invalid/{TARGET}
    base: main
    token_slot: artel-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

RETRO_BODY = f"""
# RETRO: задача планки {_tokens.TASK_ID}

Итог: done, sha {ARTEL_SHA}
"""


class RetroCorpusProviderTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()

        self.workspace = self.root / "projects" / TARGET / "workspace"
        self.workspace.mkdir(parents=True)
        targets_path = self.root / "targets.yaml"
        targets_path.write_text(TARGETS_TEXT, encoding="utf-8")

        self.patch(config, "PROJECTS", self.root / "projects")
        self.patch(config, "TARGETS", targets_path)
        self.patch(retro_corpus, "CACHE_PATH", self.root / "corpus-cache.json")

        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "artel@example.invalid")
        self.git("config", "user.name", "artel plank")

    def patch(self, module, attr: str, value) -> None:
        patcher = mock.patch.object(module, attr, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def git(self, *args: str) -> None:
        # Переменные git текущего процесса (плотницкая запись пульта
        # выставляет GIT_INDEX_FILE и компанию) увели бы команды планки в
        # чужой индекс — временный репозиторий обязан быть сам по себе.
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("GIT_DIR", "GIT_WORK_TREE",
                                    "GIT_INDEX_FILE"))}
        result = subprocess.run(["git", *args], cwd=self.workspace, env=env,
                                capture_output=True, text=True)
        self.assertEqual(0, result.returncode,
                         f"git {' '.join(args)}: {result.stderr}")

    def seed_snapshot(self, task_id: str, *, provider: str | None) -> None:
        """Снапшот закрытия задачи в `refs/artifacts/<id>` локального клона
        целевого — тем же адресом и той же формой (frontmatter + тело
        RETRO), какую публикует `orchestrator/snapshot.py`."""
        fields = [f"operator: {OPERATOR}", f"model: {MODEL}",
                  f"artel_sha: {ARTEL_SHA}"]
        if provider is not None:
            fields.append(f"provider: {provider}")
        text = "---\n" + "\n".join(fields) + "\n---\n" + RETRO_BODY

        snapshot = self.workspace / "tasks" / task_id / "RETRO.md"
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_text(text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", f"снапшот {task_id}")
        self.git("update-ref", f"refs/artifacts/{task_id}", "HEAD")

    def entry(self) -> dict:
        rows = retro_corpus.rebuild_cache()
        self.assertEqual(1, len(rows),
                         f"в кэше ретро-корпуса ожидалась одна запись, "
                         f"получено: {rows}")
        # Кэш на диске обязан нести то же, что и возврат: читатель корпуса
        # (`read_cache`) берёт именно файл.
        self.assertEqual(rows, json.loads(
            retro_corpus.CACHE_PATH.read_text(encoding="utf-8")))
        return rows[0]

    def test_ac10_snapshot_with_a_provider_lands_in_the_cache_with_it(self):
        """Снапшот, чей frontmatter несёт провайдера, попадает в кэш, и в
        записи кэша есть поле, названное провайдером, со значением
        снапшота.

        Ловит мутацию: провайдер прочитан из frontmatter, но в запись
        кэша не положен (собирающий словарь по-прежнему собирается по
        прежней тройке полей) — значение `alfa-cli` в записи не найдётся,
        и разрез расхода по провайдерам корпусу так и не достанется.
        """
        self.seed_snapshot(_tokens.TASK_ID, provider=PROVIDER)

        entry = self.entry()

        carrying = [key for key, value in entry.items() if value == PROVIDER]
        self.assertTrue(
            carrying,
            f"значения провайдера {PROVIDER!r} нет в записи кэша: {entry}")
        self.assertTrue(
            any("provider" in key for key in carrying),
            f"провайдер лежит в записи кэша не под полем провайдера, а под "
            f"{carrying} — читателю корпуса его не найти: {entry}")

    def test_ac11_snapshot_without_a_provider_still_lands_on_old_fields(self):
        """Снапшот без поля провайдера (любой RETRO, закрытый до этой
        задачи) собирается в кэш по-прежнему: запись есть, три прежних
        поля на месте, сборка не отказывает.

        Ловит мутацию: провайдер добавлен в `RETRO_FIELDS` как
        обязательное поле — условие `all(field in meta for field in
        RETRO_FIELDS)` перестаёт выполняться, `_retro_entry` отдаёт
        `None`, и ВЕСЬ исторический корпус молча исчезает из кэша:
        `self.entry()` покраснеет на пустом списке записей.
        """
        self.seed_snapshot(_tokens.TASK_ID, provider=None)

        entry = self.entry()

        self.assertEqual(OPERATOR, entry.get("operator"), entry)
        self.assertEqual(MODEL, entry.get("model"), entry)
        self.assertEqual(ARTEL_SHA, entry.get("artel_sha"), entry)


if __name__ == "__main__":
    unittest.main()
