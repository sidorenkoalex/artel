"""AC-12 — неразрешённый контекст внешнего проекта на выходе из `in_dev`:
гейт зон и гейт применимости приложений PLAN отказывают с причиной,
называющей проект и неразрешённый контекст; гейт ёмкости диффа переход не
держит.

Обёртки гейтов зовутся напрямую (`fsm_advance._zones_gate_refuses`,
`_plan_appendix_gate_refuses`, `_capacity_gate_refuses`) — решение
Оператора (ANSWER-1, п.2): через `advance` эти гейты при неразрешённом
контексте недостижимы, раньше них переход отклоняет чтение PLAN.md из
ссылки документов. Поэтому файл разовый: имена обёрток — закрытые имена
пульта, долгоживущему тесту их звать нельзя.

Песочница — `tests.sandbox.RealGitSandbox` (временный корень, своя БД,
`config.TARGETS` песочницы). Задача внешнего проекта в `in_dev` с
заявленными зонами заводится прямо в БД; PLAN — текст с одним приложением
(новый файл). Неразрешённый контекст — два варианта: имени проекта задачи
нет в `targets.yaml`; запись проекта есть, но без обязательного поля `base`
(`targets.yaml` не проходит проверку). Имена проекта и путей случайны,
зерно печатается и входит в текст провала.

Группа: разовый
Красен до реализации: гейт зон и гейт применимости приложений PLAN для проекта, отличного от артели, сегодня возвращают «не проверяется» до всякого разрешения контекста — обёртки отвечают False, отказа с причиной «контекст не разрешён» нет; часть про гейт ёмкости держит сегодняшнее поведение.
"""
import contextlib
import io
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pult import CODE_ROOT  # noqa: E402

if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from orchestrator import config, fsm_advance, idgen, store  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

ALPHABET = "abcdefghijklmnopqrstuvwxyz"

ENTRY = """  {name}:
    forge: github
    url: {url}
{base}    token_slot: {name}-token
    no_paths: [{no_paths}]
    project_skills: []
    merge_gate: operator
"""

ARTEL_PROFILE = """    test_profile:
      command: [python3, -m, pytest]
      long_lived_dir: tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
"""

PLAN_TEXT = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: фикстура неразрешённого контекста

## Подход
Фикстура.

## Приложение 1: {heading}

```diff
diff --git a/{rel} b/{rel}
new file mode 100644
--- /dev/null
+++ b/{rel}
@@ -0,0 +1 @@
+строка {word}
```
"""


class UnresolvedContextGatesTest(RealGitSandbox):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(ALPHABET) for _ in range(size))

    def write_targets(self, project: str, variant: str) -> None:
        """`targets.yaml`: запись артели; у варианта `без base` — ещё
        запись `project` без поля `base`; у `нет записи` — записи нет."""
        text = "targets:\n" + ENTRY.format(
            name=config.DEFAULT_TARGET, url="http://localhost/artel",
            base=f"    base: {config.MAIN_BRANCH}\n",
            no_paths=", ".join(config.PROTECTED_PATHS)) + ARTEL_PROFILE
        if variant == "без base":
            text += ENTRY.format(name=project, url=f"file:///nonexistent/{project}",
                                 base="", no_paths=f"zn{self.word()}/")
        config.TARGETS.write_text(text, encoding="utf-8")

    def new_task(self, project: str) -> tuple[str, dict, str]:
        """(id задачи в `in_dev` с зонами, её строка БД, текст PLAN)."""
        task_id = idgen.new_task_id()
        branch = f"task/{task_id.lower()}-ctx"
        store.insert_task(self.conn, task_id, f"Фикстура {self.word()}",
                          "in_dev", branch, project, config.DEFAULT_BUDGET_USD)
        store.update_task(self.conn, task_id, zones=f"pk{self.word()}/")
        plan = PLAN_TEXT.format(task=task_id, heading=self.word(),
                                rel=f"zn{self.word()}/{self.word()}.cfg",
                                word=self.word())
        return task_id, dict(store.get_task(self.conn, task_id)), plan

    def call(self, task_id: str, gate) -> tuple[bool, str]:
        """(ответ обёртки, новые записи журнала задачи и вывод обёртки)."""
        rows = store.task_steps(self.conn, task_id)
        before = rows[-1]["id"] if rows else 0
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            refused = gate()
        new = [f"{r['action']} | {r['detail'] or ''}"
               for r in store.task_steps(self.conn, task_id) if r["id"] > before]
        return refused, "\n".join(new) + "\n--- вывод:\n" + buf.getvalue()

    def test_ac12_unresolved_context_refuses_zones_and_appendix_gates(self):
        """Неразрешённый контекст внешнего проекта: гейт зон и гейт приложений PLAN отказывают с причиной о проекте и контексте, гейт ёмкости не держит.

        Сценарий: для каждого варианта неразрешённого контекста (имени
        проекта нет в `targets.yaml`; запись проекта без поля `base`) —
        задача случайного внешнего проекта в `in_dev` с заявленной зоной и
        PLAN с одним приложением. Обёртка гейта ёмкости отвечает False и не
        пишет отказа гейта ёмкости. Обёртки гейта зон и гейта приложений PLAN
        отвечают True; среди новых записей журнала есть отказ «переход
        отклонён…», и в записях с выводом названы имя проекта, слово
        «контекст» и «не разрешён».

        Ловит мутацию: развилка «не артель — гейт не проверяется» оставлена
        — обёртки зон и приложений отвечают False; неразрешённый контекст
        молча пропускается как «проверять нечем» — то же; причина отказа не
        называет проект либо неразрешённый контекст (например, общий текст
        «git не ответил»); гейт ёмкости стал отказывать при неразрешённом
        контексте — его обёртка отвечает True.
        """
        for variant in ("нет записи", "без base"):
            with self.subTest(variant=variant):
                project = f"pr{self.word()}"
                self.write_targets(project, variant)
                task_id, t, plan = self.new_task(project)
                note = f"зерно: {self.seed}; вариант «{variant}», проект {project}"

                refused, text = self.call(task_id, lambda: fsm_advance._capacity_gate_refuses(
                    self.conn, task_id, t, "in_dev"))
                self.assertFalse(refused, f"{note}; гейт ёмкости держит:\n{text}")
                self.assertNotIn("гейт ёмкости", text, f"{note}:\n{text}")

                gates = {
                    "гейт зон": lambda: fsm_advance._zones_gate_refuses(
                        self.conn, task_id, t, t["branch"], plan),
                    "гейт приложений PLAN": lambda: fsm_advance._plan_appendix_gate_refuses(
                        self.conn, task_id, t, plan),
                }
                for name, gate in gates.items():
                    refused, text = self.call(task_id, gate)
                    where = f"{note}; {name}:\n{text}"
                    self.assertTrue(refused, where)
                    self.assertIn("переход отклонён", text, where)
                    self.assertIn(project, text, where)
                    self.assertIn("контекст", text, where)
                    self.assertIn("не разрешён", text, where)


if __name__ == "__main__":
    unittest.main()
