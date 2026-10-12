"""Временная имитация требований 1-4 (аналитик, замер требования 7) — удалить."""


def pytest_configure(config):
    from orchestrator import brief
    table = {"analyst": ["SPEC.md", "QUESTIONS.md"],
             "developer": ["PLAN.md"],
             "spec_auditor": ["SPEC-AUDIT.md"]}

    def templates(conn, task_id, role, render):
        out = []
        run_id = brief.new_run_id()
        for name in table[role]:
            rel = f"templates/{name}"
            text, reason = brief.gitcmd.show(brief.config.MAIN_BRANCH, rel,
                                             repo=brief.config.ROOT)
            if text is None:
                brief.store.journal(conn, task_id, role,
                                    "бриф: шаблон не прочитан",
                                    f"{rel}: {reason}")
                out.append(f"шаблон {rel} не прочитан: {reason} — "
                           f"прочитай его сам\n")
            else:
                out.append(render(conn, task_id, role, rel, text, run_id))
        return "\n".join(out)

    orig_dev = brief.developer_brief
    orig_aud = brief.spec_auditor_brief
    orig_an = brief.analyst_map_component

    def developer_brief(conn, task_id):
        text = orig_dev(conn, task_id)
        return text + "\n" + templates(conn, task_id, "developer",
                                       brief._manifest_component)

    def spec_auditor_brief(conn, task_id):
        text = orig_aud(conn, task_id)
        return text + "\n" + templates(conn, task_id, "spec_auditor",
                                       brief._manifest_component)

    def analyst_map_component(conn, task_id):
        text = orig_an(conn, task_id)
        return text + "\n" + templates(conn, task_id, "analyst",
                                       brief._journal_component)

    brief.developer_brief = developer_brief
    brief.spec_auditor_brief = spec_auditor_brief
    brief.analyst_map_component = analyst_map_component
