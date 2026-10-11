"""Приёмочный тест T094 — AC-16 (tasks/T094/SPEC.md, «Критерии приёмки»),
переформулирован ANSWER-1 (tasks/T094/ANSWER-1.md, решение Оператора
01.09, прочтение (а)).

AC-16 исходно: «Полное удаление локального кэша ретро-корпуса в .artel/
не теряет данных — кэш пересобирается fetch'ем refs/artifacts/*
целевых.» ANSWER-1 разводит объёмы: в M1 кэш ЕСТЬ и пересобирается
ПРОХОДОМ ПО ЛОКАЛЬНЫМ refs/artifacts/* (git for-each-ref + чтение RETRO
из снапшотов) — без сети; сетевой fetch чужих refs — M2 (вне охвата
этой задачи). Тест пишется под локальную пересборку — прямое указание
ANSWER-1.

Придуманный минимум контракта (SPEC/PLAN интерфейс не называют — этот
критерий целиком про НОВУЮ подсистему, для которой на момент написания
теста нет вообще никакого кода; тот же приём, что AC-1 придумывает
минимум для ещё не существующего PLAN.md): модуль `orchestrator.
retro_corpus` несёт `CACHE_PATH` (путь кэша под `.artel/`, идиома
`config.ROOT / ".artel" / <имя>` — `orchestrator/config.py`) и функцию
`rebuild_cache() -> list[dict]`, которая проходит `refs/artifacts/*`
ПО ВСЕМ целевым, объявленным `targets.yaml` (`orchestrator.targets.
load()`), в их ЛОКАЛЬНЫХ клонах (`config.PROJECTS/<target>/workspace`
— тот же адрес, что уже использует `orchestrator.runner.role_env`),
извлекает из каждого снапшота файл с frontmatter RETRO (`operator`/
`model`/`artel_sha`, `yamlmini.frontmatter` — тот же парсер, что уже
использует `test_ac13_ac14_snapshot_on_close.py`) и пишет строки
кэша в CACHE_PATH.

Ref `refs/artifacts/<task_id>` кладётся тестом НАПРЯМУЮ git-плотницей
(`hash-object`/`update-index`/`write-tree`/`commit-tree`/`update-ref`)
в ЛОКАЛЬНЫЙ клон целевого (`self.target_workspace`), а НЕ через
`cleanup.cmd_kill` (AC-13/AC-15, красные до реализации сами по себе —
зависеть от них здесь означало бы одолжить чужую красноту): AC-16
проверяет пересборку кэша ИЗ уже существующих локальных refs, не
механизм их публикации. Bare-репозиторий `self.target_origin`
(имитирует форндж, сеть не участвует вовсе — `_sandbox.
ExternalTargetGitSandbox`) ref не получает НИКОГДА в этом тесте: если
`rebuild_cache()` всё равно находит данные, это и есть доказательство
локальности пересборки (без fetch/push к форнджу).

Красен до реализации: модуля `orchestrator/retro_corpus.py` не
существует вовсе (grep по `orchestrator/*.py` на «retro_corpus» —
пусто) — `import` уронит тест `ModuleNotFoundError` до первого assert.
"""
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import ExternalTargetGitSandbox  # noqa: E402

TASK_ID = "01J9ZXCRETROCORPUSAAAAAAA"
OPERATOR = "al.sidorenko"
MODEL = "claude-sonnet-5"
ARTEL_SHA = "deadbeefcafef00d000000000000000deadbee"


def _publish_local_artifact_ref(workspace: Path, task_id: str) -> None:
    """Кладёт refs/artifacts/<task_id> НАПРЯМУЮ в локальный клон целевого
    (без push, без сети) — плотницкая сборка commit-а, минуя рабочее
    дерево/индекс основной ветки клона, чтобы не тревожить checkout
    `self.target_workspace` (он используется и другими тестами)."""
    text = (
        "---\n"
        f"operator: {OPERATOR}\n"
        f"model: {MODEL}\n"
        f"artel_sha: {ARTEL_SHA}\n"
        "---\n"
        f"# RETRO: {task_id}\n"
        "Итог: killed — тестовая заглушка снапшота AC-16.\n"
    )
    blob = subprocess.run(
        ["git", "hash-object", "-w", "--stdin"], cwd=workspace,
        input=text, capture_output=True, text=True, check=True,
    ).stdout.strip()

    index_file = workspace / f".git-index-ac16-{task_id}"
    env = {**os.environ, "GIT_INDEX_FILE": str(index_file)}
    subprocess.run(
        ["git", "update-index", "--add", "--cacheinfo",
         f"100644,{blob},tasks/{task_id}/RETRO.md"],
        cwd=workspace, env=env, check=True)
    tree = subprocess.run(
        ["git", "write-tree"], cwd=workspace, env=env,
        capture_output=True, text=True, check=True).stdout.strip()
    commit = subprocess.run(
        ["git", "commit-tree", tree, "-m", f"snapshot {task_id}"],
        cwd=workspace, capture_output=True, text=True, check=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "update-ref", f"refs/artifacts/{task_id}", commit],
        cwd=workspace, check=True)
    index_file.unlink(missing_ok=True)


def _ref_exists(repo: Path, ref: str) -> bool:
    res = subprocess.run(
        ["git", "-C", str(repo), "show-ref", "--verify", "--quiet", ref],
        capture_output=True, text=True)
    return res.returncode == 0


class Ac16RetroCorpusLocalRebuildTest(ExternalTargetGitSandbox):

    def setUp(self):
        super().setUp()
        _publish_local_artifact_ref(self.target_workspace, TASK_ID)

    def test_ac16_cache_survives_full_deletion_via_local_rebuild(self):
        from orchestrator import retro_corpus

        self.assertFalse(
            _ref_exists(self.target_origin, f"refs/artifacts/{TASK_ID}"),
            f"тест положил refs/artifacts/{TASK_ID} только в локальный "
            f"клон целевого — если он уже виден в bare-origin, сценарий "
            f"сломан (проверка AC-16 требует локальности, не сети)")

        rows = retro_corpus.rebuild_cache()
        self.assertTrue(
            retro_corpus.CACHE_PATH.exists(),
            f"rebuild_cache() не создал файл кэша {retro_corpus.CACHE_PATH} "
            f"под .artel/ (AC-16)")

        def _find(rows_):
            for row in rows_:
                if row.get("task_id") == TASK_ID:
                    return row
            return None

        entry = _find(rows)
        self.assertIsNotNone(
            entry,
            f"rebuild_cache() не нашёл {TASK_ID} по локальному "
            f"refs/artifacts/* клона целевого (AC-16): {rows}")
        self.assertEqual(entry.get("operator"), OPERATOR)
        self.assertEqual(entry.get("model"), MODEL)
        self.assertEqual(entry.get("artel_sha"), ARTEL_SHA)

        self.assertFalse(
            _ref_exists(self.target_origin, f"refs/artifacts/{TASK_ID}"),
            f"rebuild_cache() не имеет права трогать сеть/origin — "
            f"refs/artifacts/{TASK_ID} по-прежнему не должен появиться "
            f"в bare-origin целевого после пересборки (AC-16, ANSWER-1: "
            f"без сети)")

        retro_corpus.CACHE_PATH.unlink()
        self.assertFalse(
            retro_corpus.CACHE_PATH.exists(),
            "файл кэша не удалился — сценарий «полное удаление кэша» "
            "не воспроизведён")

        rows_after = retro_corpus.rebuild_cache()
        entry_after = _find(rows_after)
        self.assertIsNotNone(
            entry_after,
            f"после ПОЛНОГО удаления файла кэша rebuild_cache() не "
            f"восстановил запись {TASK_ID} — данные потеряны, AC-16 "
            f"нарушен: {rows_after}")
        self.assertEqual(
            entry_after, entry,
            "пересобранная с нуля запись отличается от исходной — "
            "AC-16 требует, чтобы полное удаление кэша не теряло данных")


if __name__ == "__main__":
    import unittest
    unittest.main()
