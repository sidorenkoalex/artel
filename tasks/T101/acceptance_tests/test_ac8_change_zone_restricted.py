"""AC-8 (SPEC T101) — изменения задачи не выходят за разрешённую зону:
`orchestrator/runner.py`, `orchestrator/acceptance.py`,
`orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`,
(при необходимости) `orchestrator/agent_log.py`; схема `store.db`,
`store.py` сверх вызова существующего журнального API, `catalog.py`,
`brief.py`, `fixation.py`, `doctor.py`, `cleanup.py`, `prune.py`,
`config.py` не затронуты.

Реальный git, не заглушка (сверяется настоящий диапазон коммитов ветки
задачи, заглушкой `gitcmd.git` этого не изобразить — тот же приём, что
`LockTest` в `tests/test_acceptance_tests_flow.py`).

Сравнение — с точкой РАСХОЖДЕНИЯ ветки (`git merge-base main HEAD`), не
с текущим кончиком `main`: `main` двигается вперёд независимо от этой
задачи (пример из практики этой самой сессии написания тестов —
`orchestrator/config.py` был правлен Оператором на main уже ПОСЛЕ того,
как ветка T101 от него ответвилась; прямой `git diff main HEAD` ложно
показал бы `config.py` изменённым со стороны T101, хотя случилось
обратное — сдвинулся main). `docs/codebase-map.md` разрешён отдельно:
это не зона SPEC, а обязательная регенерация карты при правке `*.py`
под `orchestrator/`/`scripts/`/`tests/` (скил conventions-core) —
законное следствие правки разрешённых файлов, не нарушение зоны.

Зелёный с рождения: на момент написания этого теста ветка задачи несёт
только `tasks/T101/*` (SPEC/TZ/приёмочные тесты test_author) — вне зоны
ничего не тронуто, проверка проходит уже сейчас и покраснеет, если
разработчик впоследствии заденет запрещённый файл.
"""
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

ALLOWED_EXACT = {
    "orchestrator/runner.py",
    "orchestrator/acceptance.py",
    "orchestrator/fsm_advance.py",
    "orchestrator/fsm_autogate.py",
    "orchestrator/agent_log.py",
    "docs/codebase-map.md",
}
FORBIDDEN_EXACT = {
    "orchestrator/store.py",
    "orchestrator/catalog.py",
    "orchestrator/brief.py",
    "orchestrator/fixation.py",
    "orchestrator/doctor.py",
    "orchestrator/cleanup.py",
    "orchestrator/prune.py",
    "orchestrator/config.py",
}
# Собственные артефакты задачи и (по требованию 7/AC-9) тесты разработчика
# в `tests/` — SPEC не запрещает их прямо, в отличие от перечня выше.
ALLOWED_PREFIXES = ("tasks/T101/", "tests/")


class ZoneRestrictionTest(unittest.TestCase):

    def _git(self, *args: str) -> str:
        res = subprocess.run(["git", *args], cwd=REPO_ROOT,
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"git {' '.join(args)}: {res.stderr}")
        return res.stdout

    def test_ac8_changed_files_stay_within_allowed_zone(self):
        base = self._git("merge-base", "main", "HEAD").strip()
        changed = [line for line in
                  self._git("diff", "--name-only", base, "HEAD").splitlines()
                  if line]

        outside_task_artifacts = [f for f in changed
                                  if not f.startswith(ALLOWED_PREFIXES)]
        violations = [f for f in outside_task_artifacts
                     if f in FORBIDDEN_EXACT or f not in ALLOWED_EXACT]

        self.assertEqual(
            violations, [],
            f"изменения вышли за зону SPEC T101 (AC-8): {violations} "
            f"(полный список изменений с {base}: {changed})")


if __name__ == "__main__":
    unittest.main()
