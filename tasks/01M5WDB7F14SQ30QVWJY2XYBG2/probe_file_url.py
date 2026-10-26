"""Разовая проба ревьювера: обход белого списка отправкой по file:// URL."""
from pathlib import Path
from unittest import mock

from orchestrator import config, gitcmd, targets

root = Path(config.ROOT)
clone = config.PROJECTS / "qhuman" / "repo"
entry = {"merge_gate": "target-human", "url": "https://localhost/team/qhuman",
         "base": "main"}


def fake_refuse(plan, project, related, env, task_id, why):
    plan.refusal = f"{project}: {why}"
    return plan


for broken in (False, True):
    load = (mock.patch.object(targets, "load", side_effect=targets.TargetsError("x"))
            if broken else mock.patch.object(targets, "load", return_value={"qhuman": entry}))
    with load, mock.patch.object(gitcmd, "_project_tasks", return_value=[]), \
            mock.patch.object(gitcmd, "_refuse", side_effect=fake_refuse):
        for dest in (str(clone), "file://" + str(clone)):
            plan = gitcmd._push_plan(["push", dest, "main"], root, {}, None)
            print("broken" if broken else "ok", dest[:8], "->",
                  plan.refusal if plan else None)
