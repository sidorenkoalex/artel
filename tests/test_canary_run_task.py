"""Разбор внутренней подкоманды `canary run-task` (SPEC
01M5FZ9G7ME2F1T5TYEWSVNA1R, требование 1): значения флагов доходят до
`canary.cmd_canary_run_task` при любом порядке флагов.

Песочница — `tests.sandbox.TmpRootTest`; сама подкоманда подменена, реестр
и БД не трогаются.
"""
import itertools
import random
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import artel, canary
from tests.sandbox import TmpRootTest


class RunTaskArgumentOrderTest(TmpRootTest):
    def test_flags_in_any_order_reach_subcommand(self):
        """Пять флагов во всех перестановках; значения порождены от зерна.

        Наблюдение: подкоманда вызвана один раз с run_stamp, путём шаблона,
        sha, набором и сводкой из своих флагов, независимо от порядка.

        Ловит мутацию: разбор берёт значения по позиции (`rest[1]` — всегда
        `--stamp` и т. д.) либо путает значения соседних флагов — при
        перестановке подкоманда получает чужое значение.
        """
        seed = random.randrange(1 << 30)
        rng = random.Random(seed)
        values = {"--stamp": f"2031{rng.randrange(10, 12)}01T0{rng.randrange(10)}0000Z",
                  "--template": f"/pul/uchebnaya-{rng.randrange(10 ** 6)}.md",
                  "--sha": "".join(rng.choice("0123456789abcdef") for _ in range(40)),
                  "--set": f"nabor-{rng.randrange(10 ** 6)}",
                  "--summary": f"developer → model-{rng.randrange(10 ** 6)}"}
        for order in itertools.permutations(artel._RUN_TASK_FLAGS):
            argv = [item for flag in order for item in (flag, values[flag])]
            with self.subTest(зерно=seed, порядок=order), mock.patch.object(
                    canary, "cmd_canary_run_task") as run_task:
                artel._cmd_canary(["run-task", *argv])
                run_task.assert_called_once_with(
                    run_stamp=values["--stamp"],
                    template_path=Path(values["--template"]),
                    target_sha=values["--sha"], set_name=values["--set"],
                    summary=values["--summary"])


if __name__ == "__main__":
    unittest.main()
