"""Поля компонента `ci_base`, `ci_base_branch`, `ci_base_push_options` записи проекта в разделе `description.components.<имя>` локального слоя: годная запись загружается, каждое нарушение — отказ загрузки с полным именем поля.

Группа: долгоживущий
Красен до реализации: загрузчик записей не знает полей `ci_base`, `ci_base_branch`, `ci_base_push_options` — годная запись-образец отказывает «неизвестное поле 'ci_base'», и каждый случай краснеет на её загрузке, до проверки нарушения.

Провалидировано временным стабом правил загрузчика (удалён, не
закоммичен): все методы файла зелёные.

Свойство — правило загрузчика записей `targets.load()`; песочница —
`tmp_root` (пути `config` во временном каталоге): запись внешнего проекта
пишется в локальный слой песочницы (`targets.local_path()`), запись артели
— посеянная песочницей. Каждый случай сначала загружает годную запись-
образец (тот же проект без нарушения) — отказ случая не может прийти от
порчи образца.

Имена проекта, компонентов, заданий, ветки отчёта базы и параметров
отправки — из `random`; зерно печатается и входит в текст провала.
"""
import random

import pytest

from orchestrator import config, targets

LETTERS = "abcdefghijkmnpqrstuvwxyz"


class Scene:
    def __init__(self):
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.used: set = set()

    def word(self, size: int = 6) -> str:
        while True:
            text = "".join(self.rng.choice(LETTERS) for _ in range(size))
            if text not in self.used:
                self.used.add(text)
                return text

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def option(self) -> str:
        name = f"V{self.word().upper()}"
        return self.rng.choice([f"{name}={self.word()}",
                                f"ci.variable={name}={self.word()}"])


@pytest.fixture
def scene(tmp_root):
    return Scene()


def component(name: str, job: str, base_fields: dict, paths: str | None) -> list:
    lines = [f"        {name}:", "          command: [python3, -m, pytest]",
             "          report: junit-xml", "          long_lived_dir: tests",
             "          long_lived_name: test_<id>_<name>.py",
             "          full_suite: ci", f"          ci_job: {job}"]
    if paths is not None:
        lines.append(f"          paths: [{paths}]")
    lines += [f"          {k}: {v}" for k, v in base_fields.items()]
    return lines


def entry_text(name: str, base: str, comps: list, forbidden=None) -> str:
    """Запись локального слоя: `comps` — [(компонент, задание, поля
    `ci_base*`)]; несколько компонентов — каждый со своим `paths`."""
    lines = [f"  {name}:", "    description:", f"      base: {base}",
             "      components:"]
    multi = len(comps) > 1
    for comp, job, fields in comps:
        lines += component(comp, job, fields, f"^{comp}/" if multi else None)
    lines += ["    policy:", "      no_paths: []", "      project_skills: []",
              "      merge_gate: target-human"]
    if forbidden is not None:
        lines.append(f"      push_options_forbidden: [{', '.join(forbidden)}]")
    lines.append("      components:")
    for comp, _job, _fields in comps:
        lines += [f"        {comp}:", "          weakening_scope: [tests/**]",
                  "          mutation_claim_scope: [tests/test_*.py]"]
    lines += ["    machine:", "      forge: gitlab",
              f"      url: https://localhost/artel-tests/{name}",
              f"      token_slot: {name}-token"]
    return "\n".join(lines) + "\n"


def write(text: str) -> None:
    path = targets.local_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("targets:\n" + text, encoding="utf-8")


def flow(items) -> str:
    return "[" + ", ".join(items) + "]"


def good_fields(scene, branch: str, options: list) -> dict:
    return {"ci_base": "branch", "ci_base_branch": branch,
            "ci_base_push_options": flow(options)}


def load_refusal(scene) -> str:
    with pytest.raises(targets.TargetsError) as caught:
        targets.load()
    return str(caught.value)


CASES = ("нет ci_base_branch", "ci_base_branch = base",
         "ci_base_branch по шаблону веток задач", "параметр ci.skip",
         "параметр merge_request.*", "base не основная ветка",
         "разные ci_base_branch", "разные ci_base_push_options")


@pytest.mark.parametrize("case", CASES)
def test_ac9_violation_refuses_load_naming_field(scene, case):
    """Каждое нарушение правил полей `ci_base*` — отказ загрузки записи, текст отказа называет поле полным именем.

    Сценарий (по случаю): сначала загружается годная запись-образец
    (компонент `full_suite: ci`, `ci_base: branch`, `ci_base_branch` и
    `ci_base_push_options`; у случаев с двумя компонентами — оба с
    одинаковыми значениями). Затем та же запись с нарушением: (а) без
    `ci_base_branch`; (б) `ci_base_branch` = `base` записи; (в)
    `ci_base_branch` подходит под шаблон веток задач `task/{id}-{slug}`;
    (г) в `ci_base_push_options` — `ci.skip`; (д) —
    `merge_request.create`; (е) `base` записи — не `config.MAIN_BRANCH`;
    (ж) два компонента `ci_base: branch` с разными `ci_base_branch`; (з)
    — с разными `ci_base_push_options`. `targets.load()` —
    `TargetsError`, текст содержит имя поля: `ci_base_branch` (а, б, в,
    ж), `ci_base_push_options` (г, д, з), `ci_base` или `base` (е).

    Ловит мутацию: правило случая не проверяется — запись загружается;
    проверка параметров отправки не зовёт `push_option_error` с
    запретами записи — `ci.skip` проходит; сравнение значений
    компонентов пропущено — разные ветки отчёта базы загружаются.
    """
    name, branch = f"p{scene.word()}", f"artel-base-{scene.word()}"
    options = [scene.option(), scene.option()]
    comp, job = f"c{scene.word()}", f"t{scene.word()}"
    two = case.startswith("разные")
    comps = [(comp, job, good_fields(scene, branch, options))]
    if two:
        comps.append((f"d{scene.word()}", f"u{scene.word()}",
                      good_fields(scene, branch, options)))
    write(entry_text(name, config.MAIN_BRANCH, comps))
    assert name in targets.load(), scene.note("образец не загрузился")
    base = config.MAIN_BRANCH
    fields = comps[-1][2]
    if case == "нет ci_base_branch":
        fields.pop("ci_base_branch")
        expected = ("ci_base_branch",)
    elif case == "ci_base_branch = base":
        fields["ci_base_branch"] = config.MAIN_BRANCH
        expected = ("ci_base_branch",)
    elif case == "ci_base_branch по шаблону веток задач":
        fields["ci_base_branch"] = f"task/{scene.word()}-{scene.word()}"
        expected = ("ci_base_branch",)
    elif case == "параметр ci.skip":
        fields["ci_base_push_options"] = flow(options + ["ci.skip"])
        expected = ("ci_base_push_options",)
    elif case == "параметр merge_request.*":
        fields["ci_base_push_options"] = flow(
            options + ["merge_request.create"])
        expected = ("ci_base_push_options",)
    elif case == "base не основная ветка":
        base = f"dev-{scene.word()}"
        expected = ("ci_base", "'base'", "description.base")
    elif case == "разные ci_base_branch":
        fields["ci_base_branch"] = f"artel-base-{scene.word()}"
        expected = ("ci_base_branch",)
    else:
        fields["ci_base_push_options"] = flow([scene.option()])
        expected = ("ci_base_push_options",)
    write(entry_text(name, base, comps))
    text = load_refusal(scene)
    assert any(field in text for field in expected), scene.note(
        f"отказ без имени поля {expected}: {text}")


@pytest.mark.parametrize("form", ["ИМЯ=значение", "ci.variable=ИМЯ=значение"])
def test_ac9_valid_push_option_forms_load(scene, form):
    """Параметр `ci_base_push_options` формы `ИМЯ=значение` (и `ci.variable=ИМЯ=значение`), допустимый `targets.push_option_error`, загрузку не отказывает.

    Сценарий (по случаю): запись с компонентом `ci_base: branch`, чей
    единственный параметр отправки — случайное имя и значение в форме
    случая; `targets.push_option_error(<параметр>, [])` — `None`.
    `targets.load()` отдаёт запись проекта.

    Ловит мутацию: проверка параметров отправки базы допускает только
    форму `ci.variable=…` (или требует запрещённый список полностью
    пустым) — годный `ИМЯ=значение` отказывается.
    """
    name, branch = f"p{scene.word()}", f"artel-base-{scene.word()}"
    var = f"V{scene.word().upper()}"
    option = (f"{var}={scene.word()}" if form == "ИМЯ=значение"
              else f"ci.variable={var}={scene.word()}")
    assert targets.push_option_error(option, []) is None, scene.note(option)
    comps = [(f"c{scene.word()}", f"t{scene.word()}",
              good_fields(scene, branch, [option]))]
    write(entry_text(name, config.MAIN_BRANCH, comps))
    assert name in targets.load(), scene.note("запись не загрузилась")
