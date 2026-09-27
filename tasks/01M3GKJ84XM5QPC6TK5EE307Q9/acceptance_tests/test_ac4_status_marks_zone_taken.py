"""AC-4 — 01M3GKJ84XM5QPC6TK5EE307Q9: `status` помечает «зона занята:
<id>» строки задач до `in_dev`, чья зона занята задачей из
`zone_lock.BLOCKING_STATES`.

Источник — SPEC.md, «Критерии приёмки»:

AC-4. `status` печатает добавку «зона занята: <id>» в строке задачи в
`spec_writing`, `spec_gate` или `tests_writing`, чья зона пересекается с
зоной задачи в `zone_lock.BLOCKING_STATES`; пересечение только по общим
зонам добавки не даёт.

Держатель заводится БЕЗ маркера «занимает зону»: SPEC требование 3
повторяет условие требования 1 — `zone_lock._occupies` к этой сверке не
применяется, членства в состоянии довольно.

Красен до реализации: `catalog.cmd_status` собирает строку из
`_lease_holder_suffix`/`_zone_wait_suffix`/`_wave_breaker_suffix`/
`_division_suffix`/`merge_queue.wait_suffix`, и ни один из них добавки
«зона занята: …» не печатает — `assertIn` падает на каждом из трёх
дозаводских состояний.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402

HOLDER = "T840"
SHARED_ZONE = "orchestrator/catalog.py"


class StatusMarksZoneTakenTest(_sandbox.ZoneOverlapSandbox):

    def test_ac4_pre_dev_rows_carry_the_zone_taken_mark(self):
        """Держатель в `in_dev` и по задаче в каждом из трёх
        дозаводских состояний с той же зоной: строка каждой из трёх
        несёт «зона занята: T840».

        Ловит мутацию: добавка подключена только к `tests_writing`
        (ближайшему к `in_dev` состоянию) — строки `spec_writing` и
        `spec_gate` останутся без пометки, и ассерт назовёт их поимённо.
        """
        self.seed_task(HOLDER, "in_dev", SHARED_ZONE)
        waiters = {}
        for index, state in enumerate(_sandbox.PRE_DEV_STATES):
            waiters[f"T84{index + 1}"] = state
        for task_id, state in waiters.items():
            self.seed_task(task_id, state, SHARED_ZONE)

        lines = self.status_lines()

        expected = f"{_sandbox.ZONE_TAKEN_PREFIX}{HOLDER}"
        missed = [f"{task_id} ({state})" for task_id, state in waiters.items()
                  if expected not in lines.get(task_id, "")]
        self.assertEqual(
            [], missed,
            f"строки без добавки «{expected}»: " + ", ".join(missed)
            + "\n" + "\n".join(lines.get(t, "") for t in waiters))

    def test_ac4_common_zone_only_overlap_gets_no_mark(self):
        """Держатель в `in_dev` и задача в `tests_writing` делят только
        общую зону — добавки нет.

        Ловит мутацию: сверка `status` написана отдельно от сверки `new`
        и забыла отсев `config.COMMON_ZONES` — каждая задача пульта
        получила бы пометку «зона занята» по `tests/`.
        """
        self.seed_task("T845", "in_dev",
                       f"{_sandbox.COMMON_FILE_ZONE}, {_sandbox.COMMON_DIR_ZONE}")
        self.seed_task("T846", "tests_writing",
                       f"{_sandbox.COMMON_FILE_ZONE}, "
                       f"{_sandbox.COMMON_DIR_ZONE}test_obschaya.py")

        lines = self.status_lines()

        self.assertNotIn(
            _sandbox.ZONE_TAKEN_PREFIX, lines.get("T846", ""),
            f"пересечение только по общим зонам не должно давать "
            f"добавки: {lines.get('T846', '')!r}")

    def test_ac4_holder_must_be_in_a_blocking_state(self):
        """Единственная задача с той же зоной сидит в `done` —
        дозаводская строка пометки не получает.

        Ловит мутацию: держателем считается любая задача с
        пересекающейся зоной, без сверки состояния с
        `zone_lock.BLOCKING_STATES` — закрытая задача «занимала» бы зону
        вечно.
        """
        zone = "orchestrator/zakrytyy_derzhatel.py"
        self.seed_task("T847", "done", zone)
        self.seed_task("T848", "spec_writing", zone)

        lines = self.status_lines()

        self.assertNotIn(_sandbox.ZONE_TAKEN_PREFIX, lines.get("T848", ""),
                         f"задача в done зону не держит: "
                         f"{lines.get('T848', '')!r}")


if __name__ == "__main__":
    unittest.main()
