"""Юнит-тесты перечня защищённых путей проекта в местах сверки, которые не
закрывают долгоживущие файлы задачи (SPEC 01M45FK56DWMNBRKA1VWM12H19,
требования 1-3): неразрешённый контекст на `new` и на гейте SPEC, зоны
SPEC внешнего проекта по его `no_paths`, гейт применимости приложений при
неразрешённом контексте и PLAN без приложений.

`config.TARGETS` — временный файл с записью артели и внешнего проекта
`vnesh`; строка задачи не нужна — `store.task_target` подменён.
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import catalog, config, fsm, repo_context, store
from orchestrator.advance_gates import plan_appendix
from scripts import guard

ENTRY = """  {name}:
    forge: github
    url: http://localhost/{name}
    base: main
    token_slot: {name}-token
    no_paths: [{no_paths}]
    project_skills: []
    merge_gate: operator
"""

PLAN_WITH_APPENDIX = """---
task: T1
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN

## Приложение 1: правка

```diff
diff --git a/zz/a.cfg b/zz/a.cfg
new file mode 100644
--- /dev/null
+++ b/zz/a.cfg
@@ -0,0 +1 @@
+строка
```
"""

PLAN_WITHOUT_APPENDIX = """---
task: T1
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN

## Подход
Без приложений.
"""


class ProjectPerimeterTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="artel-targets-")
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "targets.yaml"
        path.write_text(
            "targets:\n"
            + ENTRY.format(name=config.DEFAULT_TARGET,
                           no_paths=", ".join(config.PROTECTED_PATHS))
            + ENTRY.format(name="vnesh", no_paths="zz/"), encoding="utf-8")
        patcher = mock.patch.object(config, "TARGETS", path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_external_perimeter_is_its_no_paths(self):
        """Перечень внешнего проекта — его `no_paths`, у артели —
        `config.PROTECTED_PATHS`.

        Ловит мутацию: `protected_paths` отдаёт `config.PROTECTED_PATHS`
        любому проекту — у `vnesh` в перечне `skills/` вместо `zz/`."""
        self.assertEqual(repo_context.protected_paths(
            repo_context.resolve("vnesh")), ("zz/",))
        self.assertEqual(repo_context.protected_paths(
            repo_context.resolve(config.DEFAULT_TARGET)),
            tuple(config.PROTECTED_PATHS))

    def test_tz_zones_refusal_names_unresolved_project(self):
        """`new` с ТЗ для проекта без записи в `targets.yaml` — отказ,
        называющий проект и неразрешённый контекст.

        Ловит мутацию: неразрешённый контекст молча сверяется по перечню
        пульта (`protected=None`) — зона вне `config.PROTECTED_PATHS`
        проходит, отказа нет."""
        tz = "Требуется: правка.\n\nЗоны: src/.\n"
        refusal = catalog._tz_path_refusal("TZ.md", tz, "nosuch")
        self.assertIsNotNone(refusal)
        self.assertIn("nosuch", refusal)
        self.assertIn("не разрешён", refusal)
        self.assertIsNone(catalog._tz_path_refusal("TZ.md", tz, "vnesh"))

    def test_spec_gate_zones_by_project_perimeter(self):
        """Зоны SPEC внешнего проекта сверяются с его `no_paths`;
        проект без записи — отказ, называющий проект.

        Ловит мутацию: гейт SPEC сверяет зоны с `config.PROTECTED_PATHS` —
        назван `skills/x/`, а `zz/a/` нет; неразрешённый контекст молча
        пропускается — пустая причина."""
        meta = {"zones": "zz/a/, skills/x/, src/"}
        with mock.patch.object(store, "task_target", return_value="vnesh"):
            reason = fsm._spec_protected_zones_refusal(None, "T1", meta)
        self.assertIn("zz/a/", reason)
        self.assertNotIn("skills/x/", reason)
        self.assertIn(guard.PROTECTED_ZONE_REFUSAL, reason)
        with mock.patch.object(store, "task_target", return_value="nosuch"):
            reason = fsm._spec_protected_zones_refusal(None, "T1", meta)
        self.assertIn("nosuch", reason)
        self.assertIn("не разрешён", reason)

    def test_appendix_gate_unresolved_context_refuses_only_with_appendices(self):
        """Неразрешённый контекст: PLAN с приложением — отказ гейта
        приложений, называющий проект; PLAN без приложений — гейт не
        держит (проверять нечего), git не зовётся ни в одном случае.

        Ловит мутацию: неразрешённый контекст отказывает и PLAN без
        приложений — задача без механики приложений стоит на сломанной
        записи чужого проекта; приложение при неразрешённом контексте
        пропускается молча."""
        t = {"branch": "task/t1-x"}

        def boom(*args, **kwargs):
            raise AssertionError("git не нужен без контекста проекта")

        with mock.patch.object(store, "task_target", return_value="nosuch"), \
                mock.patch.object(plan_appendix.gitcmd, "diff_base", boom):
            refusal = plan_appendix._plan_appendix_gate(
                None, "T1", t, PLAN_WITH_APPENDIX)
            passed = plan_appendix._plan_appendix_gate(
                None, "T1", t, PLAN_WITHOUT_APPENDIX)
        self.assertIsNotNone(refusal)
        self.assertEqual(refusal.action,
                         plan_appendix.PLAN_APPENDIX_GATE_FAILURE_ACTION)
        self.assertIn("nosuch", refusal.detail)
        self.assertIsNone(passed)


if __name__ == "__main__":
    unittest.main()
