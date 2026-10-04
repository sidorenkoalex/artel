"""`python3 scripts/guard.py <путь>/SPEC.md` сверяет пути SPEC с зонами тем
же узлом и тем же текстом, что `approve` на `spec_gate`.

Группа: долгоживущий

Красен до реализации: вызов guard по одному файлу SPEC не зовёт `guard.spec_unclassified_paths` — на SPEC с неклассифицированным путём guard печатает «ок» и завершается нулём (AC-8 красный); AC-9 (классифицированный SPEC без находки, отказ `approve`) держит существующее поведение и зелёный.

Guard гоняется настоящим CLI — `python3 scripts/guard.py <файл>` отдельным
процессом из корня рабочей копии кода (`config.ROOT` процесса guard —
этот корень, пути SPEC сверяются с его файлами). SPEC лежит во временном
каталоге. `approve` на `spec_gate` — `fsm.cmd_approve` в лёгкой песочнице
переходов (`LightTransitionSandbox`): SPEC.md кладётся в каталог задачи
песочницы, упомянутый путь — копией файла в её корень, так что гейт
видит тот же путь существующим. Упомянутый путь, зона и раздел, в котором
путь назван, — из `random` (модули `orchestrator/*.py` вне общих зон),
зерно печатается и входит в текст провала.
"""
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from orchestrator import config, fsm
from scripts import guard
from tests.sandbox import LightTransitionSandbox, capture

CODE_ROOT = Path(__file__).resolve().parent.parent

SPEC_TEMPLATE = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: {zones}
budget_usd: 25
---

# SPEC: фикстура сверки путей

## Контекст

{context}

## Требования

1. {requirement}

## Критерии приёмки

AC-1. {ac}

## Оценка объёма и деление

Прогноз диффа: 2 КиБ.

## Не входит

{excluded}

## Материалы

{materials}
"""

CHECKED = ("context", "requirement", "ac")


class GuardSpecPathsSandbox(LightTransitionSandbox):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        pool = sorted(f"orchestrator/{p.name}"
                      for p in (CODE_ROOT / "orchestrator").glob("*.py")
                      if not any(f"orchestrator/{p.name}".startswith(z)
                                 for z in config.COMMON_ZONES)
                      and p.name != "__init__.py")
        self.mentioned, self.zone = self.rng.sample(pool, 2)
        for rel in (self.mentioned, self.zone):
            dest = self.root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text("# фикстура\n", encoding="utf-8")
        scratch = Path(tempfile.mkdtemp(prefix="artel-guard-spec-"))
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        self.spec_file = scratch / "SPEC.md"

    def note(self, text: str) -> str:
        return f"{text} (зерно {self.seed})"

    def spec_text(self, *, zones: str, section: str, excluded: str = "Ничего.",
                  materials: str = "Нет.") -> str:
        fields = {name: "Фикстура." for name in CHECKED}
        fields[section] = f"Починить `{self.mentioned}`."
        return SPEC_TEMPLATE.format(task=self.TASK, zones=zones,
                                    excluded=excluded, materials=materials,
                                    **fields)

    def run_guard(self, text: str) -> tuple[int, str]:
        self.spec_file.write_text(text, encoding="utf-8")
        res = subprocess.run([sys.executable, "scripts/guard.py",
                              str(self.spec_file)],
                             cwd=CODE_ROOT, capture_output=True, text=True,
                             timeout=60)
        return res.returncode, res.stdout + res.stderr

    def approve(self, text: str) -> str:
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "SPEC.md").write_text(text, encoding="utf-8")
        self.set_state("spec_gate")
        return capture(fsm.cmd_approve, self.TASK)


class UnclassifiedPathTest(GuardSpecPathsSandbox):

    def test_ac8_guard_cli_reports_unclassified_path_like_approve(self):
        """Guard по одному SPEC с неклассифицированным путём — ненулевой код и текст `guard.unclassified_paths_refusal`, тот же, что у отказа `approve`.

        Сценарий: SPEC с `zones:` на другой модуль, путь существующего
        модуля назван в случайном проверяемом разделе («Контекст»,
        «Требования» или «Критерии приёмки») и не назван в «Не входит»/
        «Материалы». `python3 scripts/guard.py <SPEC.md>` завершается
        ненулевым кодом и печатает `guard.unclassified_paths_refusal([путь])`;
        `approve` на `spec_gate` по тому же SPEC печатает тот же текст.

        Ловит мутацию: проверка путей не подключена к вызову guard по
        файлу (как на пине) — «ок», код 0; находка печатается
        предупреждением, но код возврата 0; guard строит свой текст мимо
        `unclassified_paths_refusal` (расходится с текстом `approve`);
        проверка подключена с корнем не рабочей копии, и существующий путь
        не находится.
        """
        section = self.rng.choice(CHECKED)
        text = self.spec_text(zones=self.zone, section=section)
        expected = guard.unclassified_paths_refusal([self.mentioned])

        code, out = self.run_guard(text)
        approve_out = self.approve(text)

        self.assertIn(expected, approve_out, self.note(
            f"предпосылка: approve не отказал тем же текстом:\n{approve_out}"))
        self.assertNotEqual(code, 0, self.note(
            f"guard по SPEC с путём {self.mentioned} в разделе {section} "
            f"завершился нулём:\n{out}"))
        self.assertIn(expected, out, self.note(
            f"guard не напечатал текст отказа approve для {self.mentioned} "
            f"в разделе {section}:\n{out}"))


class ClassifiedPathTest(GuardSpecPathsSandbox):

    def test_ac9_classified_spec_no_finding_and_approve_still_refuses(self):
        """Все пути SPEC классифицированы — guard без находки; `approve` по SPEC с неклассифицированным путём по-прежнему отказывает.

        Сценарий: путь назван в случайном проверяемом разделе и
        классифицирован случайным способом — `zones:` на сам файл,
        `zones:` на каталог `orchestrator/`, упоминание в «Не входит» или
        в «Материалы». Вывод `python3 scripts/guard.py <SPEC.md>` не несёт
        подсказки `guard.UNCLASSIFIED_PATH_HINT` и текста отказа по пути.
        Затем `approve` на `spec_gate` по SPEC с тем же путём без
        классификации печатает `guard.unclassified_paths_refusal([путь])`,
        задача остаётся на `spec_gate`.

        Ловит мутацию: guard на файле не учитывает вложенность каталога-
        зоны или разделы-декларации (ложная находка на честном SPEC);
        перенос проверки в guard снял её с `approve` — гейт пропускает
        неклассифицированный путь.
        """
        section = self.rng.choice(CHECKED)
        how = self.rng.choice(("зона-файл", "зона-каталог", "Не входит",
                               "Материалы"))
        kwargs = {"zones": self.zone}
        if how == "зона-файл":
            kwargs["zones"] = f"{self.zone}, {self.mentioned}"
        elif how == "зона-каталог":
            kwargs["zones"] = "orchestrator/"
        elif how == "Не входит":
            kwargs["excluded"] = f"Правка `{self.mentioned}`."
        else:
            kwargs["materials"] = f"`{self.mentioned}`."
        refusal = guard.unclassified_paths_refusal([self.mentioned])

        _code, out = self.run_guard(self.spec_text(section=section, **kwargs))

        self.assertNotIn(guard.UNCLASSIFIED_PATH_HINT, out, self.note(
            f"guard дал находку на SPEC, классифицированном «{how}»:\n{out}"))
        self.assertNotIn(refusal, out, self.note(
            f"guard дал находку на SPEC, классифицированном «{how}»:\n{out}"))

        approve_out = self.approve(self.spec_text(zones=self.zone,
                                                  section=section))

        self.assertIn(refusal, approve_out, self.note(
            f"approve пропустил неклассифицированный путь {self.mentioned}:\n"
            f"{approve_out}"))
        self.assertEqual(self.state(), "spec_gate", self.note(
            "approve с неклассифицированным путём увёл задачу с гейта"))


if __name__ == "__main__":
    unittest.main()
