"""Песочница гейта SPEC для планки 01M2XJKQNFTWHYAY4KBBQ1NVY7 —
надстройка над `tests.sandbox.LightTransitionSandbox` (skills/
test-authoring.md: лёгкая песочница переходов импортируется, не
копируется).

Своих `disk_backed_*`/`advance_from_in_dev`/патчей `gitcmd` здесь нет:
добавляется только сев упоминаемых SPEC путей во временный `config.ROOT`,
подготовка задачи к approve на `spec_gate` и метка-часовой в
`tasks.zones`, по которой видно, переписал ли approve колонку до отказа.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402

sys.path.insert(0, str(_util.REPO_ROOT))

from orchestrator import fsm, store  # noqa: E402
from tests import sandbox  # noqa: E402


class SpecGateSandbox(sandbox.LightTransitionSandbox):
    """Задача эталона, доведённая до `spec_gate` с подготовленным SPEC.md
    на диске (его читает `disk_backed_show` эталона через
    `artifact_source.resolve`)."""

    # Значение `tasks.zones` ДО approve: не равно ни одному `zones:`
    # фикстур, поэтому «колонка не переписана значением этого SPEC»
    # проверяется сравнением с этой меткой, а не косвенно.
    ZONES_SENTINEL = "зоны-до-гейта/часовой.py"

    def setUp(self):
        super().setUp()
        _util.seed_paths(self.root)
        self.tdir.mkdir(parents=True, exist_ok=True)

    def arrange_gate(self, **spec_fields) -> None:
        """Кладёт SPEC.md фикстуры, ставит метку-часового в `tasks.zones`
        и переводит задачу на `spec_gate`."""
        (self.tdir / "SPEC.md").write_text(
            _util.spec_text(self.TASK, **spec_fields), encoding="utf-8")
        conn = store.db()
        conn.execute("UPDATE tasks SET zones=? WHERE id=?",
                     (self.ZONES_SENTINEL, self.TASK))
        conn.commit()
        self.set_state("spec_gate")

    def run_approve(self) -> str:
        """Весь вывод `approve`. Прошёл гейт или отказал — видно по
        состоянию задачи, не по форме отказа: `_approve_spec_gate`
        отказывает мягким `return` после печати, без `SystemExit`."""
        return _util.run_command(fsm.cmd_approve, self.TASK)

    def zones_column(self):
        return self.task_row()["zones"]
