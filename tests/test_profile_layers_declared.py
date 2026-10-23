"""Явное пустое `layers: []` компонента pytest — строгий режим гейта исходов (SPEC 01M5JGSAANR1NZYQD4FCSVE48Y, требование 7).

Стенд — `tests.sandbox.TmpRootTest`: `targets.yaml` песочницы с записями
из одного компонента pytest, различающимися только полем `layers`; профиль
— публичные `project_profile.decide` и `project_profile.component_profiles`.
"""
from orchestrator import config, project_profile
from tests.sandbox import TmpRootTest, make_project_repo

ENTRY = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: main
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
    components:
      api:
        command: [python3, -m, pytest]
        report: junit-xml
        long_lived_dir: tests
        long_lived_name: test_<id>_<name>.py
        weakening_scope: [tests/**]
        mutation_claim_scope: [tests/test_*.py]
{layers}"""


class LayersDeclaredTest(TmpRootTest):

    def record(self, name: str, layers: str) -> str:
        text = config.TARGETS.read_text(encoding="utf-8")
        config.TARGETS.write_text(
            text.rstrip("\n") + "\n" + ENTRY.format(name=name, layers=layers),
            encoding="utf-8")
        make_project_repo(name, origin=False)
        return name

    def test_explicit_empty_layers_strict_absent_keeps_python_ast(self):
        """`layers: []` у pytest — действующих слоёв нет (строгий режим); без поля — `python-ast`; `profile.layers` в обоих случаях пуст.

        Сценарий: две записи из одного компонента pytest — с `layers: []`
        и без поля; слои берутся у профиля `decide` и у профиля
        `component_profiles`.

        Ловит мутацию: `layers_of` смотрит только на `profile.layers` —
        у `layers: []` снова `python-ast`; признак «поле задано» ставится
        и без поля — у компонента без `layers` пропадает `python-ast`;
        признак кладётся в само `profile.layers` — оно перестаёт быть
        пустым.
        """
        strict = self.record("strogiy", "        layers: []\n")
        default = self.record("obychny", "")
        for name, expected in ((strict, ()), (default, ("python-ast",))):
            for profile in (project_profile.decide(name).profile,
                            *project_profile.component_profiles(name)):
                with self.subTest(project=name):
                    self.assertEqual(project_profile.layers_of(profile),
                                     expected)
                    self.assertEqual(profile.layers, ())
