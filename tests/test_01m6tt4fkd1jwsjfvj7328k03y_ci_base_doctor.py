"""Строка `doctor` компонента с `ci_base: branch`: `ok` — ветка отчёта базы `ci_base_branch` не защищена, отправку в неё пропускают белый список и политика клона; невыполненное условие — `warn` с причиной; у записей без `ci_base` строк о ветке отчёта базы нет.

Группа: долгоживущий
Красен до реализации: поля компонента `ci_base`/`ci_base_branch` загрузчик записей отказывает «неизвестное поле» — запись проекта не читается, строки о ветке отчёта базы нет; тест записей без `ci_base` (AC-14) зелёный с рождения.

Провалидировано временным стабом строки (удалён, не закоммичен): все
методы файла зелёные.

Связка, которую держит файл: «запись проекта в `targets.yaml` песочницы —
`doctor.project_entry_checks`/`doctor.project_checks.component_checks` —
`forge` — клон проекта». Песочница — `initialized_tmp_root`; признак
процесса роли снят. Функции `forge.project_info`, `forge.protections`,
`forge.branch_pipeline` подменены поддельным хостингом: защищённые ветки
задаёт тест. Клон — настоящий локальный репозиторий
(`tests.sandbox.make_project_repo`) со своим голым `origin` — адресом
записи; каталог хуков пульта `scripts/git-hooks` проверяемого дерева
скопирован в корень песочницы, клону поставлены хуки и файл политики
пульта (`workspace.set_clone_hooks`, `workspace.write_push_policy`).

Строка находится по имени: в исправном мире — строка, чей текст называет
`ci_base_branch`; та же строка (то же имя) после порчи условия.

Имена проекта, компонента, задания и ветки отчёта базы — из `random`;
зерно печатается и входит в текст провала.
"""
import random
import shutil
from pathlib import Path

import pytest

from orchestrator import config, doctor, forge, runner, targets, workspace
from tests.sandbox import artel_target_entry, make_project_repo

CODE_ROOT = Path(__file__).resolve().parent.parent
LETTERS = "abcdefghijkmnpqrstuvwxyz"


class FakeForge:
    """Поддельный хостинг: защищённые ветки задаёт тест."""

    def __init__(self):
        self.info = forge.ProjectInfo(config.MAIN_BRANCH, 40)
        self.prot = forge.Protections([config.MAIN_BRANCH], [])
        self.pipeline = forge.BranchPipeline("a" * 40, forge.GREEN)

    def project_info(self, target):
        return self.info

    def protections(self, target):
        return self.prot

    def branch_pipeline(self, target, branch):
        return self.pipeline


class Scene:
    def __init__(self, monkeypatch):
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.hosting = FakeForge()
        for attr in ("project_info", "protections", "branch_pipeline"):
            monkeypatch.setattr(forge, attr, getattr(self.hosting, attr))
        monkeypatch.setattr(runner, "in_role_environment", lambda env=None: False)
        shutil.copytree(CODE_ROOT / "scripts" / "git-hooks",
                        Path(config.ROOT) / "scripts" / "git-hooks",
                        ignore=shutil.ignore_patterns("__pycache__"),
                        dirs_exist_ok=True)

    def word(self, size: int = 7) -> str:
        return "".join(self.rng.choice(LETTERS) for _ in range(size))

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def project(self, ci_base: bool = True, forge_name: str = "gitlab"):
        """Запись `target-human` с компонентом `full_suite: ci` (у GitHub —
        `test_profile`) и её клон с хуками и файлом политики пульта."""
        self.name = f"p{self.word()}"
        self.comp, self.job = f"c{self.word()}", f"t{self.word()}"
        self.cbb = f"artel-base-{self.word()}"
        bare = config.PROJECTS / self.name / "origin.git"
        lines = [f"  {self.name}:", f"    forge: {forge_name}",
                 f"    url: {bare}", f"    base: {config.MAIN_BRANCH}",
                 f"    token_slot: {self.name}-token", "    no_paths: []",
                 "    project_skills: []", "    merge_gate: target-human"]
        if forge_name == "gitlab":
            lines += ["    components:", f"      {self.comp}:",
                      "        command: [python3, -m, pytest]",
                      "        report: junit-xml", "        long_lived_dir: tests",
                      "        long_lived_name: test_<id>_<name>.py",
                      "        weakening_scope: [tests/**]",
                      "        mutation_claim_scope: [tests/test_*.py]",
                      "        full_suite: ci", f"        ci_job: {self.job}"]
            if ci_base:
                lines += ["        ci_base: branch",
                          f"        ci_base_branch: {self.cbb}"]
        else:
            lines += ["    test_profile:", "      command: [python3, -m, pytest]",
                      "      long_lived_dir: tests",
                      "      long_lived_name: test_<id>_<name>.py",
                      "      weakening_scope: [tests/**]",
                      "      mutation_claim_scope: [tests/test_*.py]"]
        config.TARGETS.write_text("targets:\n" + artel_target_entry().rstrip("\n")
                                  + "\n" + "\n".join(lines) + "\n",
                                  encoding="utf-8")
        self.clone = make_project_repo(self.name)
        assert workspace.set_clone_hooks(self.clone, self.name) is None
        assert workspace.write_push_policy(self.clone, self.name) is None

    def checks(self) -> list:
        entry = targets.target(self.name)
        return (list(doctor.project_entry_checks(self.name, entry))
                + list(doctor.project_checks.component_checks(self.name, entry)))


@pytest.fixture
def scene(initialized_tmp_root, monkeypatch):
    return Scene(monkeypatch)


def base_line(scene) -> str:
    """Имя строки, чей текст в исправном мире называет `ci_base_branch`;
    проверка, что она `ok`."""
    found = [c for c in scene.checks() if scene.cbb in (c.detail or "")]
    assert found, scene.note("строки о ci_base_branch нет: "
                             + repr([(c.name, c.status, c.detail)
                                     for c in scene.checks()]))
    assert all(c.status == "ok" for c in found), scene.note(repr(found))
    return found[0].name


@pytest.mark.parametrize("damage", ["ветка защищена", "политика клона"])
def test_ac13_ci_base_line_ok_then_warn_on_broken_condition(scene, damage):
    """Компонент с `ci_base: branch`: в исправном мире строка `doctor` о ветке отчёта базы — `ok`; ветка защищена или политика клона её отправку не пропускает — та же строка `warn` с причиной.

    Сценарий (по случаю): запись `target-human` GitLab с компонентом
    `full_suite: ci`, `ci_base: branch`; хостинг защищает только `main`;
    клону поставлены хуки и эталон файла политики. Строки
    `project_entry_checks` и `component_checks`: среди них есть строка с
    именем `ci_base_branch` в тексте, все такие — `ok`. Порча: (а)
    хостинг называет `ci_base_branch` защищённой; (б) файл политики клона
    переписан текстом без ключа `ci_base_branch` (политика клона отправку
    в ветку не пропустит). Та же строка (по имени) — `warn`, текст
    непустой.

    Ловит мутацию: строка не смотрит на защиты хостинга либо на файл
    политики клона — после порчи по-прежнему `ok`; строка всегда `warn` —
    в исправном мире не `ok`.
    """
    scene.project()
    name = base_line(scene)
    if damage == "ветка защищена":
        scene.hosting.prot = forge.Protections([config.MAIN_BRANCH, scene.cbb],
                                               [])
    else:
        policy = scene.clone / ".git" / workspace.PUSH_POLICY_NAME
        policy.write_text(
            f"project={scene.name}\nbase={config.MAIN_BRANCH}\n"
            f"branch_template={targets.DEFAULT_BRANCH_TEMPLATE}\n"
            f"artifacts_prefix=refs/artifacts/\n", encoding="utf-8")
    found = [c for c in scene.checks() if c.name == name]
    assert found and found[0].status == "warn", scene.note(repr(found))
    assert (found[0].detail or "").strip(), scene.note(repr(found))


@pytest.mark.parametrize("kind", ["gitlab без ci_base", "github"])
def test_ac14_records_without_ci_base_have_no_base_branch_line(scene, kind):
    """Записи без `ci_base` (GitLab и GitHub): ни одна строка `doctor` записи не говорит о ветке отчёта базы, предупреждений о ней нет.

    Сценарий (по случаю): запись `target-human` GitLab с компонентом
    `full_suite: ci` без `ci_base`; запись GitHub с `test_profile`.
    Строки `project_entry_checks` и `component_checks`: ни в одном имени
    и тексте нет слов `ci_base`/«отчёта базы» и имени ветки, которую
    тест держит про запас.

    Ловит мутацию: строка ветки отчёта базы выводится для любого
    компонента `full_suite: ci` (с веткой по умолчанию или `warn` «поле
    не задано») — у прежних записей появляется новая строка.
    """
    scene.project(ci_base=False,
                  forge_name="gitlab" if kind.startswith("gitlab") else "github")
    for check in scene.checks():
        text = f"{check.name} {check.detail or ''}"
        assert "ci_base" not in text and "отчёта базы" not in text, \
            scene.note(repr(check))
        assert scene.cbb not in text, scene.note(repr(check))
