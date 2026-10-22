"""Автогейт приёмки по правилу планки после G3б: снятие отказа «до гейта неослабления по исходам (G3б)» в границе гейта исходов и побайтная неизменность прежних условий.

Группа: разовый
Красен до реализации: `_plank_rule_refusal` отказывает при любом правиле не по умолчанию — у задачи в границе гейта исходов вместо «критерии manual — AC-<n>» приходит «… до гейта неослабления по исходам (G3б) не исполняется …» (AC-28, первый метод); зелены и на базе ветки методы прежнего поведения: отказ построения правила и правило вне границы (второй метод AC-28), канарейка (AC-29) и эталон пина у артели и `test_profile` (AC-30).

Предмет — условия автогейта `fsm_autogate._autogate_conditions` (закрытая
функция модуля: публичного входа к одним условиям нет, сквозной путь
`verifying -> acceptance` требует CI, ревью и набора моделей, которых в
песочнице нет; поэтому файл — разовый, со снятием «эталона пина»). Стенд —
`tests.sandbox.TmpRootTest`: `targets.yaml` песочницы с записью артели,
записью `test_profile` и учебными проектами `components:` (клон —
`tests.sandbox.make_project_repo`), правило планки и граница гейта исходов —
настоящие (`project_profile.plank_rule`, `project_profile.decide`). Подменены
только внешние источники: ссылка документов (`artifact_source.resolve`,
`artifact_branch.ls_tree/show/rev_sha`) отдаёт файлы планки сценария,
пробный период набора моделей (`models.set_trial_reason`) — «нет», проект
задачи (`workspace.task_target`) — проект сценария, рабочая копия
(`workspace.on_task_branch`) — «не заведена».

Эталон пина (AC-30): текст `orchestrator/fsm_autogate.py` на базе ветки
задачи (`DIFF_BASE` помощника пульта) исполняется отдельным модулем пакета
`orchestrator` — его `_autogate_conditions` даёт эталонные условия и текст,
текущий модуль обязан совпасть с ним побайтно.

Провалидировано временным стабом реализации (удалён, не закоммичен):
`_plank_rule_refusal` с границей `_bounds` и чтение пометок по правилу —
все методы файла зелёные.
"""
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, DIFF_BASE  # noqa: E402

from orchestrator import (artifact_branch, artifact_source, config, fsm_autogate,  # noqa: E402
                          gitcmd, models, project_profile, workspace)
from tests.sandbox import TmpRootTest, make_project_repo  # noqa: E402

BRANCH = "refs/artifacts/T001"
SHA = "c" * 40
TASK = "T001"
CODE_BRANCH = "task/t001-x"
PLANK = f"tasks/{TASK}/acceptance_tests"
G3B_TEXT = "до гейта неослабления по исходам (G3б) не исполняется"

ENTRY_HEAD = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: main
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""


def flow(items) -> str:
    return "[" + ", ".join(str(item) for item in items) + "]"


def pin_autogate():
    """Модуль `fsm_autogate` кода пина: текст с базы ветки задачи,
    исполненный в пакете `orchestrator` (относительные импорты — те же
    модули пульта)."""
    text, reason = gitcmd.show(DIFF_BASE, "orchestrator/fsm_autogate.py",
                               repo=Path(CODE_ROOT))
    if text is None:
        raise AssertionError(f"fsm_autogate.py пина {DIFF_BASE} не прочитан: {reason}")
    module = types.ModuleType("orchestrator.fsm_autogate_pin")
    module.__package__ = "orchestrator"
    exec(compile(text, "fsm_autogate_pin.py", "exec"), module.__dict__)
    return module


class AutogateRuleSandbox(TmpRootTest):
    """Песочница путей с учебными проектами и подменой внешних
    источников условий автогейта."""

    def append_entry(self, text: str) -> None:
        old = config.TARGETS.read_text(encoding="utf-8")
        config.TARGETS.write_text(old.rstrip("\n") + "\n" + text, encoding="utf-8")

    def vitest_entry(self, name: str, with_tests: bool = True) -> str:
        """Запись с единственным компонентом `pult-vitest`; (имя
        компонента)."""
        comp = f"c{name}"
        fields = {"command": flow(project_profile.VITEST_BASE_ARGV),
                  "report": "pult-vitest",
                  "plank_layout": "frontend/src/.pv/<id>",
                  "long_lived": "frontend/src/<dir>/<name>.<id>.test.jsx",
                  "weakening_scope": flow(["frontend/src/**"]),
                  "mutation_claim_scope": flow(["frontend/claims/**"])}
        if with_tests:
            fields["tests"] = flow(["frontend/src/**/*.test.jsx"])
        lines = [ENTRY_HEAD.format(name=name), "    components:\n", f"      {comp}:\n"]
        lines += [f"        {key}: {value}\n" for key, value in fields.items()]
        self.append_entry("".join(lines))
        make_project_repo(name, origin=False)
        return comp

    def own_profile_entry(self, name: str) -> None:
        fields = {"command": flow(["/opt/x/pytest"]), "report": "junit-xml",
                  "runner": "pytest-own", "long_lived_dir": "tests",
                  "long_lived_name": "test_<id>_<name>.py",
                  "weakening_scope": flow(["tests/**"]),
                  "mutation_claim_scope": flow(["tests/**"])}
        lines = [ENTRY_HEAD.format(name=name), "    test_profile:\n"]
        lines += [f"      {key}: {value}\n" for key, value in fields.items()]
        self.append_entry("".join(lines))
        make_project_repo(name, origin=False)

    def conditions(self, target: str, files: dict, *, canary: bool = False,
                   module=None):
        """(выполненные условия, причина) `_autogate_conditions` задачи
        проекта `target` с файлами планки `files` {имя: текст}."""
        module = module or fsm_autogate
        listed = [f"{PLANK}/{name}" for name in files]
        t = {"branch": CODE_BRANCH, "target": target, "is_canary": int(canary),
             "spent_usd": 0.0, "budget_usd": 5.0}

        def show(task_id, branch, rel):
            name = rel.rsplit("/", 1)[-1]
            return (files[name], "") if name in files else (None, "нет файла")
        with mock.patch.object(artifact_source, "resolve", return_value=(BRANCH, True)), \
                mock.patch.object(artifact_branch, "rev_sha", return_value=SHA), \
                mock.patch.object(artifact_branch, "ls_tree", return_value=listed), \
                mock.patch.object(artifact_branch, "show", side_effect=show), \
                mock.patch.object(models, "set_trial_reason", return_value=None), \
                mock.patch.object(workspace, "task_target", return_value=target), \
                mock.patch.object(workspace, "on_task_branch", return_value=False):
            return module._autogate_conditions(object(), TASK, t, Path("/no/such"), 1)


class Ac28RuleInBoundsTest(AutogateRuleSandbox):

    def test_ac28_labelled_plank_in_bounds_reads_markers_by_rule(self):
        """Правило планки не по умолчанию у задачи в границе гейта исходов (не канарейка): отказа G3б нет, пометка manual в файле планки по правилу даёт «критерии manual — AC-<n>».

        Сценарий: проект с единственным компонентом `pult-vitest` (`tests`
        — маски `*.test.jsx`, граница гейта исходов); в планке файл
        `p.test.jsx` с тестом `it('AC-1: …')` и строкой `// AC-3: manual —
        причина`. Причина автогейта — ровно «автогейт: критерии manual —
        AC-3 (источник планки: ветка <ветка>, sha <sha>)»; текста G3б нет.

        Ловит мутацию: отказ G3б оставлен при правиле не по умолчанию —
        причина «… (G3б) не исполняется …»; пометки читаются прежним
        разбором Python без правила — `//`-пометка не видна, причина иная
        («каталог пуст» либо дальнейшее условие).
        """
        comp = self.vitest_entry("pin")
        self.assertFalse(project_profile.plank_rule("pin").is_default, comp)
        text = ("import { expect, it } from 'vitest';\n\n"
                "// AC-3: manual — проверит Оператор на приёмке.\n"
                "it('AC-1: кнопка', () => { expect(1).toBe(1); });\n")
        ok, reason = self.conditions("pin", {"p.test.jsx": text})
        self.assertEqual(reason, f"автогейт: критерии manual — AC-3 (источник планки: "
                                 f"ветка {BRANCH}, sha {SHA})", ok)

    def test_ac28_rule_refusal_and_out_of_bounds_keep_old_texts(self):
        """Отказ построения правила — прежний текст «автогейт: <причина>»; правило не по умолчанию у профиля вне границы — прежний отказ G3б.

        Сценарий (подслучай): (а) компонент `pult-vitest` без `tests` —
        причина «автогейт: у компонента <имя> нет tests — допустимые файлы
        планки не определены»; (б) правило не по умолчанию, а решение
        профиля проекта для гейта исходов — отказ (подмена
        `project_profile.decide`): причина несёт «до гейта неослабления по
        исходам (G3б) не исполняется».

        Ловит мутацию: отказ построения правила проглочен — иная причина;
        граница не проверяется — у профиля вне границы отказ G3б снят и
        причина — пометки планки.
        """
        with self.subTest(case="отказ правила"):
            comp = self.vitest_entry("rfs", with_tests=False)
            ok, reason = self.conditions("rfs", {"p.test.jsx": "// пусто\n"})
            self.assertEqual(reason, f"автогейт: у компонента {comp} нет tests — "
                                     f"допустимые файлы планки не определены", ok)
        with self.subTest(case="вне границы"):
            self.vitest_entry("oob")
            text = ("// AC-3: manual — проверит Оператор.\n"
                    "it('AC-1: кнопка', () => { expect(1).toBe(1); });\n")
            refused = project_profile.Decision("oob", refusal="профиль сценария не прочитан")
            with mock.patch.object(project_profile, "decide", return_value=refused):
                ok, reason = self.conditions("oob", {"p.test.jsx": text})
            self.assertIn(G3B_TEXT, reason or "", ok)


class Ac29CanaryTest(AutogateRuleSandbox):

    def test_ac29_canary_in_bounds_keeps_g3b_refusal(self):
        """Канареечная задача с профилем в границе и правилом не по умолчанию — прежний отказ «до гейта неослабления по исходам (G3б) не исполняется».

        Сценарий: тот же проект `pult-vitest`, что в AC-28, задача с
        `is_canary`; в планке — пометка manual. Причина автогейта несёт
        текст G3б, а не «критерии manual».

        Ловит мутацию: граница снятия — `in_outcome_bounds` профиля без
        признака канарейки — у канарейки отказ G3б снят.
        """
        self.vitest_entry("cnr")
        text = ("// AC-3: manual — проверит Оператор.\n"
                "it('AC-1: кнопка', () => { expect(1).toBe(1); });\n")
        ok, reason = self.conditions("cnr", {"p.test.jsx": text}, canary=True)
        self.assertIn(G3B_TEXT, reason or "", ok)
        self.assertNotIn("критерии manual", reason or "", ok)


class Ac30PinReferenceTest(AutogateRuleSandbox):

    def test_ac30_artel_and_test_profile_conditions_equal_pin(self):
        """У артели и записи `test_profile` условия и текст автогейта побайтно равны эталону, снятому с кода пина.

        Сценарий (подслучай): задача артели и задача проекта `test_profile`
        с планкой `test_x.py` (а) с пометкой `# AC-2: manual — …`; (б) с
        пометкой `# AC-2: skip — …`; (в) без пометок (условия доходят до
        полного набора — рабочая копия не заведена); (г) пустой каталог.
        Пара (условия, причина) текущего `_autogate_conditions` равна паре
        модуля пина.

        Ловит мутацию: правило по умолчанию пошло через чтение по правилу
        (пары путь-текст) — иной разбор и иная причина; текст отказа или
        пометки источника изменён — расхождение с пином.
        """
        self.own_profile_entry("tpr")
        pin = pin_autogate()
        plank = {"manual": "# AC-2: manual — проверит Оператор.\n",
                 "skip": "# AC-2: skip — не проверяется сейчас.\n",
                 "чисто": ("import unittest\n\n\nclass T(unittest.TestCase):\n"
                           "    def test_ac2_x(self):\n        self.assertTrue(True)\n"),
                 "пусто": None}
        for target in (config.DEFAULT_TARGET, "tpr"):
            for label, text in plank.items():
                with self.subTest(target=target, case=label):
                    files = {} if text is None else {"test_x.py": text}
                    current = self.conditions(target, files)
                    reference = self.conditions(target, files, module=pin)
                    self.assertEqual(current, reference)


if __name__ == "__main__":
    unittest.main()
