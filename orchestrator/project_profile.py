"""Профиль тестов проекта в проверках тестов пульта (ADR-0021 пп. 8-9;
SPEC 01M45FJVGQT1K0P8HDEXZX6HS7, требования 2-5).

Значения, зависящие от языка проекта, — команда прогона, области гейта
неослабления и заявки мутации, каталог и шаблон имени долгоживущего файла —
проверки берут из профиля проекта (`repo_context.profile_of`), а не из
своего кода. Одно правило на все места проверок (`decide`):

- контекст проекта не разрешён (`repo_context.resolve` вернул `None`) —
  отказ: молча проверка не пропускается;
- профиль есть — проверки идут по нему;
- профиля нет у внешнего проекта — проверки, зависящие от языка, не
  выполняются, и каждый пропуск пишет запись в журнал задачи
  (`journal_skip`): молча не отключается ничего;
- профиля нет у артели либо он не прочитан — отказ, а не отключение
  (ADR-0002, fail-closed): гейты целостности тестов пульта не отключаются
  ни в одном месте.
"""
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType

from scripts import guard

from . import config, repo_context, store, targets

# Действие журнала отказа перехода по профилю или контексту проекта —
# класс «чинит Оператор» (`advance_gates.refusal_classes`): чинится
# `targets.yaml`, не артефакт роли.
REFUSAL_ACTION = "переход отклонён: профиль тестов проекта"
# Префикс действия записи о пропуске проверки у проекта без профиля;
# за двоеточием — название проверки.
SKIP_ACTION = "проверка тестов не выполняется"

# Названия проверок в записях о пропуске (таблица требования 5).
CHECK_WEAKENING = "гейт неослабления тестов"
CHECK_ASSERTIONS_SECTION = "раздел изменённых утверждений пакета ревью"
CHECK_MUTATION = "гейт заявки мутации"
CHECK_LONG_LIVED = "долгоживущие файлы"
CHECK_GROUPS = "строки группы приёмочных тестов"
CHECK_MANIFEST = "перечень долгоживущих тестов и лок планки"
CHECK_LONG_LIVED_RUN = "прогон долгоживущих тестов"


def mask_matches(mask: str, path: str) -> bool:
    """Путь подходит под маску профиля: `*` — любые символы внутри одного
    сегмента пути, `**` — любое число сегментов, включая ноль."""
    if not path:
        return False
    regex = ""
    segments = mask.split("/")
    for i, segment in enumerate(segments):
        last = i == len(segments) - 1
        if segment == "**":
            regex += ".*" if last else "(?:[^/]*/)*"
            continue
        regex += "".join("[^/]*" if ch == "*" else re.escape(ch)
                         for ch in segment)
        if not last:
            regex += "/"
    return re.fullmatch(regex, path) is not None


@dataclass(frozen=True)
class Profile:
    """Разобранный профиль тестов проекта (подполя — `targets.
    PROFILE_FIELDS`)."""
    command: tuple
    long_lived_dir: str
    long_lived_name: str
    weakening_scope: tuple
    mutation_claim_scope: tuple
    report: str = ""
    install: tuple = ()
    full_suite_timeout_sec: int | None = None
    runner: str = targets.PROFILE_RUNNER_DEFAULT
    workdir: str = ""
    # Неизменяемое отображение под стать frozen; `dict` нехэшируем, поэтому
    # поле вне хэша (равенство его по-прежнему сравнивает).
    env: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType({}), hash=False)
    long_lived_imports: tuple = ()
    # Объявленные инструменты компонента «имя → версия» (SPEC
    # 01M58PG72PG64GS790XM2EWS61, требование 9): заполняет `with_tools`, у
    # записей с `test_profile` пусто. Вне хэша — по той же причине, что `env`.
    tools: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType({}), hash=False)
    # Поля компонента (SPEC 01M590GJAF0EDV4NBC4C99MFVH, требования 1-7, 13):
    # заполняет `with_tools` (у записи `components:`) либо
    # `component_profiles`; у `test_profile` — имя `default` и проект. Вне
    # сравнения: профиль записи `test_profile` и её единственного
    # компонента с теми же подполями — один профиль (SPEC
    # 01M58FNWBV25FF26E7AZ9Q9912); ключ итога читает поля явно.
    component: str = field(default="", compare=False)
    project: str = field(default="", compare=False)
    report_args: tuple = field(default=(), compare=False)
    select: tuple = field(default=(), compare=False)
    failure_errors: tuple = field(default=(), compare=False)
    checks_local: tuple = field(default=(), compare=False)
    # Профиль взят из записи `components:` — признак различителя
    # «итог из отчёта» (`reported`).
    from_components: bool = field(default=False, compare=False)
    # Маски `tests` и `plank_layout` компонента (SPEC
    # 01M59KMPG2ZMK10V556VZVQD65, требование 2) — вне сравнения по той же
    # причине, что поля выше.
    tests: tuple = field(default=(), compare=False)
    plank_layout: str = field(default="", compare=False)
    # Шаблон `long_lived` компонента (SPEC 01M5AA5TS90RDJ2AFXB882WTPD,
    # требование 2): пара `long_lived_dir`/`long_lived_name` тогда выведена
    # из него. У явной пары, `test_profile` и артели — пусто; вне сравнения
    # по той же причине, что поля выше.
    long_lived_template: str = field(default="", compare=False)
    # Маски `test_support`, слои `layers` и выражения `paths` компонента
    # (SPEC 01M5J0JYW3GZSSHHK3TYCYTQ3J, требование 1) — читает гейт
    # исходов; вне сравнения по той же причине, что поля выше.
    test_support: tuple = field(default=(), compare=False)
    layers: tuple = field(default=(), compare=False)
    paths: tuple = field(default=(), compare=False)
    # Поле `layers` компонента задано, пусть и пустым (SPEC
    # 01M5JGSAANR1NZYQD4FCSVE48Y, требование 7): `layers: []` у pytest —
    # строгий режим, а не `python-ast` по умолчанию.
    layers_declared: bool = field(default=False, compare=False)

    @classmethod
    def from_values(cls, values: dict) -> "Profile":
        return cls(command=tuple(values["command"]),
                   long_lived_dir=values["long_lived_dir"],
                   long_lived_name=values["long_lived_name"],
                   weakening_scope=tuple(values["weakening_scope"]),
                   mutation_claim_scope=tuple(values["mutation_claim_scope"]),
                   report=values.get("report") or "",
                   install=tuple(values.get("install") or ()),
                   full_suite_timeout_sec=values.get("full_suite_timeout_sec"),
                   runner=values.get("runner") or targets.PROFILE_RUNNER_DEFAULT,
                   workdir=values.get("workdir") or "",
                   env=MappingProxyType(dict(values.get("env") or {})),
                   long_lived_imports=tuple(
                       values.get("long_lived_imports") or ()))

    def in_weakening_scope(self, path: str | None) -> bool:
        return bool(path) and any(mask_matches(mask, path)
                                  for mask in self.weakening_scope)

    def in_mutation_claim_scope(self, path: str | None) -> bool:
        return bool(path) and any(mask_matches(mask, path)
                                  for mask in self.mutation_claim_scope)

    def long_lived_prefix(self, task_id: str) -> str:
        return guard.long_lived_path_prefix(task_id, self.long_lived_dir,
                                            self.long_lived_name)

    def long_lived_example(self, task_id: str) -> str:
        """Путь долгоживущего файла задачи с `<имя>` вместо имени — для
        подсказок (у артели `tests/test_<id>_<имя>.py`)."""
        return guard.long_lived_example(task_id, self.long_lived_dir,
                                        self.long_lived_name)

    def long_lived_hint(self, task_id: str, name: str = "<имя>") -> str:
        """Пример пути долгоживущего файла в подсказках, называвших его
        префиксом и хвостом «<имя>.py»/«*.py» (SPEC
        01M5AA5TS90RDJ2AFXB882WTPD, требование 4): у профиля из шаблона —
        пример `guard.long_lived_example` с подстановкой `name`, у явной
        пары, `test_profile` и артели — прежняя склейка."""
        if self.long_lived_template:
            return guard.long_lived_example(task_id, self.long_lived_dir,
                                            self.long_lived_name, name)
        return f"{self.long_lived_prefix(task_id)}{name}.py"

    def is_long_lived(self, task_id: str, rel: str) -> bool:
        return guard.is_long_lived_test_path(task_id, rel, self.long_lived_dir,
                                             self.long_lived_name)


@dataclass(frozen=True)
class Decision:
    """Как проверкам тестов поступить с проектом задачи: `profile` — идти
    по нему; `refusal` — отказать с этой причиной; `skip` — проверки,
    зависящие от языка, не выполняются, причина пропуска для журнала."""
    target: str
    profile: Profile | None = None
    refusal: str = ""
    skip: str = ""
    # Отказ — из-за неразрешённого контекста, а не из-за профиля: раздел
    # пакета ревью в этом случае называет, что не собран, а не роняет пакет.
    unresolved: bool = False


def unresolved_reason(target: str) -> str:
    return (f"{repo_context.unresolved_reason(target)} — проверки тестов без "
            f"него не выполняются")


def decide(target: str) -> Decision:
    """Решение по проекту `target` (правило — докстринг модуля)."""
    ctx = repo_context.resolve(target)
    if ctx is None:
        return Decision(target, refusal=unresolved_reason(target),
                        unresolved=True)
    answer = repo_context.profile_of(target)
    if answer.outcome == repo_context.PROFILE_PRESENT:
        return Decision(target, profile=with_tools(
            target, Profile.from_values(answer.values)))
    if answer.outcome == repo_context.PROFILE_UNREAD and answer.multi:
        return Decision(target, refusal=(
            f"профиль тестов проекта «{target}» не прочитан (поле "
            f"{targets.COMPONENTS_FIELD} записи в targets.yaml): "
            f"{answer.reason}"))
    if answer.outcome == repo_context.PROFILE_UNREAD:
        return Decision(target, refusal=(
            f"профиль тестов проекта «{target}» не прочитан (поле "
            f"test_profile записи в targets.yaml): {answer.reason}"))
    if repo_context.is_artel(ctx):
        return Decision(target, refusal=(
            f"у проекта «{target}» нет поля test_profile в targets.yaml — "
            f"гейты целостности тестов пульта без профиля не отключаются "
            f"(ADR-0002)"))
    return Decision(target, skip=(f"у проекта «{target}» нет test_profile в "
                                  f"targets.yaml"))


def is_multi(target: str) -> bool:
    """Запись проекта несёт несколько компонентов — профиль задачи
    выбирается по её зонам (`for_task`)."""
    return repo_context.profile_of(target).multi


def long_lived_imports(target: str, profile: Profile | None):
    """Правило импортов долгоживущих файлов проекта для
    `guard.long_lived_errors_from_files(project_imports=…)` (SPEC
    01M5633WZ3Y3A0P4KKBZDB3KER): `None` — артель, правило пульта; у
    внешнего проекта — перечень его профиля, пустой без подполя."""
    if repo_context.is_artel(target):
        return None
    return profile.long_lived_imports if profile is not None else ()


def for_task(conn, task_id: str) -> Decision:
    """Решение по задаче: `decide_task(<проект>, <зоны строки задачи>)`
    (SPEC 01M5JGSAANR1NZYQD4FCSVE48Y, требование 1). Колонки зон строки
    читаются только у записи из нескольких компонентов — у прочих
    решение `decide` как есть."""
    return for_task_target(store.task_target(conn, task_id), task_id, conn)


def for_task_target(target: str, task_id: str, conn=None) -> Decision:
    """`for_task` для места, которому проект задачи уже известен: решение
    `decide(target)`, а у записи из нескольких компонентов — компонент по
    зонам строки задачи из `conn` (не передан — БД пульта)."""
    def zones():
        db = conn if conn is not None else store.db()
        row = db.execute("SELECT zones, zones_extension FROM tasks "
                         "WHERE id=?", (task_id,)).fetchone()
        return _row_zones(row) if row is not None else set()
    return _by_zones(target, decide(target), zones)


def for_row(row) -> Decision:
    """`for_task` по строке задачи (колонки `target`, а у записи из
    нескольких компонентов — `zones`/`zones_extension`)."""
    target = row["target"] or config.DEFAULT_TARGET
    return _by_zones(target, decide(target), lambda: _row_zones(row))


def _row_zones(row) -> set:
    # store -> ... -> project_profile; zone_lock -> lease -> runner ->
    # project_profile: цикл импорта.
    from .zone_lock import task_zone_paths
    return task_zone_paths(row)


# Отказы выбора компонента задачи на записи из нескольких компонентов
# (требование 1): к каждому дописывается причина `decide` дословно.
ZONES_NOT_SET = ("зоны задачи не заданы — компонент задачи на записи из "
                 "нескольких компонентов не выбран")
ZONES_NOT_TOUCHING = "зоны задачи не задевают ни одного компонента записи"
SEVERAL_COMPONENTS = ("задача затрагивает несколько компонентов ({names}) — "
                      "дели задачу по компонентам (решение Оператора 20.10)")


class ZoneListingError(Exception):
    """Перечень файлов базы под зоной-каталогом не получен — выбор
    компонента задачи невозможен (fail-closed, не пустой выбор)."""


def _base_files(target: str, directory: str) -> list:
    """Файлы репозитория проекта на базе под префиксом `directory`."""
    ctx = repo_context.resolve(target)
    if ctx is None:
        raise ZoneListingError(repo_context.unresolved_reason(target))
    remote_ref = f"refs/remotes/origin/{ctx.base}"
    probe = repo_context.git(ctx, "rev-parse", "--verify", "-q", remote_ref)
    ref = remote_ref if probe is not None and probe.returncode == 0 \
        else ctx.base
    res = repo_context.git(ctx, "ls-tree", "-r", "--name-only", ref, "--",
                           directory)
    if res is None or res.returncode != 0:
        detail = (res.stderr or "").strip() if res is not None else ""
        raise ZoneListingError(
            f"перечень файлов базы {ref} под зоной-каталогом {directory} не "
            f"получен в клоне {ctx.path}: {detail or 'git не ответил'}")
    return [p for p in res.stdout.splitlines() if p]


def _own_touch(component: "Component", path: str) -> bool:
    """Путь задевает компонент сам — его `paths` или маски `test_support`,
    без `depends_on` (потребитель компонентом задачи не становится)."""
    fields = component.fields
    if any(re.search(regex, path) for regex in _regexes(fields.get("paths"))):
        return True
    return any(mask_matches(mask, path)
               for mask in fields.get("test_support") or ())


def task_components(target: str, zones) -> tuple[str, ...]:
    """Компоненты записи `target`, которые задевают зоны задачи `zones`,
    в порядке записи (SPEC 01M5JGSAANR1NZYQD4FCSVE48Y, требование 1).
    Зона-файл сопоставляется сама; зона-каталог (оканчивается на «/») —
    файлами репозитория на базе под ней. Пути вне компонентов выбор не
    расширяют. ZoneListingError — перечень файлов не получен."""
    comps = components(target)
    paths = set()
    for zone in zones or ():
        if zone.endswith("/"):
            paths.update(_base_files(target, zone))
        else:
            paths.add(zone)
    return tuple(c.name for c in comps
                 if any(_own_touch(c, path) for path in paths))


def decide_task(target: str, zones) -> Decision:
    """Решение по проекту `target` для задачи с зонами `zones` (требование
    1): у записи из нескольких компонентов — профиль компонента задачи
    либо отказ выбора; у прочих — `decide(target)` как есть."""
    return _by_zones(target, decide(target), lambda: zones)


def _by_zones(target: str, decision: Decision, zones) -> Decision:
    """Компонент по зонам (`zones()` зовётся лениво) — только если
    `decision` — отказ записи из нескольких компонентов."""
    if not decision.refusal or decision.unresolved or not is_multi(target):
        return decision
    reason = decision.refusal

    def refuse(text: str) -> Decision:
        return Decision(target, refusal=f"{text}; {reason}")
    chosen_zones = set(zones() or ())
    if not chosen_zones:
        return refuse(ZONES_NOT_SET)
    try:
        chosen = task_components(target, chosen_zones)
    except (ZoneListingError, targets.TargetsError) as exc:
        return refuse(f"компонент задачи не выбран: {exc}")
    if not chosen:
        return refuse(ZONES_NOT_TOUCHING)
    if len(chosen) > 1:
        return refuse(SEVERAL_COMPONENTS.format(names=", ".join(chosen)))
    (comp,) = [c for c in components(target) if c.name == chosen[0]]
    fields = comp.fields
    # Та же проверка обязательных подполей, что у `repo_context.
    # profile_of` записи из одного компонента.
    for sub in targets.PROFILE_FIELDS:
        if sub not in targets.PROFILE_OPTIONAL and sub not in fields:
            return refuse(
                f"профиль тестов проекта «{target}» не прочитан (поле "
                f"{targets.COMPONENTS_FIELD} записи в targets.yaml): "
                f"{config.TARGETS}: target '{target}': компонент "
                f"'{comp.name}': нет подполя '{sub}', обязательного у "
                f"профиля тестов")
    values = {sub: fields[sub] for sub in targets.PROFILE_FIELDS
              if sub in fields}
    return Decision(target, profile=_with_component_fields(
        replace(Profile.from_values(values), project=target), comp))


def full_suite_limit(target: str) -> tuple[int, str]:
    """Действующий предел полного набора и его источник для проекта."""
    answer = repo_context.profile_of(target)
    if answer.outcome == repo_context.PROFILE_UNREAD:
        raise targets.TargetsError(answer.reason)
    value = (answer.values or {}).get("full_suite_timeout_sec")
    if value is not None:
        return value, f"профиль тестов проекта {target}"
    return config.FULL_SUITE_TIMEOUT_SEC, "config"


# Имя компонента записи с `test_profile` (SPEC 01M58FNWBV25FF26E7AZ9Q9912,
# требование 4).
DEFAULT_COMPONENT = "default"


@dataclass(frozen=True)
class Component:
    """Компонент записи проекта: имя и поля (`targets.COMPONENT_FIELDS`;
    у `default` — подполя `test_profile`)."""
    name: str
    fields: Mapping = field(hash=False)


def components(target: str) -> tuple:
    """Компоненты записи проекта `target` в порядке записи (ADR-0026 п. 3):
    `test_profile` — один `default`, запись без профиля и компонентов —
    пусто. TargetsError — файл или запись не годны."""
    entry = targets.target(target)
    comps = entry.get(targets.COMPONENTS_FIELD)
    if comps is not None:
        return tuple(Component(name, MappingProxyType(dict(fields)))
                     for name, fields in comps.items())
    profile = entry.get(targets.PROFILE_FIELD)
    if profile is not None:
        return (Component(DEFAULT_COMPONENT, MappingProxyType(dict(profile))),)
    return ()


def with_tools(target: str, profile: Profile) -> Profile:
    """`profile` с объявленными `tools` единственного компонента записи
    `target` (SPEC 01M58PG72PG64GS790XM2EWS61, требование 9) и полями
    компонента, которых нет в `targets.PROFILE_FIELDS` (`report_args`,
    `select`, `failure_errors`, `checks_local`, имя, проект; SPEC
    01M590GJAF0EDV4NBC4C99MFVH, требование 15) — один помощник на `decide`,
    `acceptance._task_own_profile` и `suite_run._profile_command`, чтобы
    профиль и ключ итога всех входов совпадали. У `test_profile` таких
    полей нет — только имя `default` и проект."""
    entry = targets.target(target)
    comps = components(target)
    if entry.get(targets.COMPONENTS_FIELD) is None or len(comps) != 1:
        return replace(profile, component=DEFAULT_COMPONENT, project=target)
    return _with_component_fields(replace(profile, project=target), comps[0])


def _with_component_fields(profile: Profile, comp: Component) -> Profile:
    fields = comp.fields
    return replace(
        profile, component=comp.name, from_components=True,
        tools=MappingProxyType(dict(fields.get("tools") or {})),
        report_args=tuple(fields.get("report_args") or ()),
        select=tuple(fields.get("select") or ()),
        failure_errors=tuple(fields.get("failure_errors") or ()),
        checks_local=tuple(fields.get("checks_local") or ()),
        tests=tuple(fields.get("tests") or ()),
        plank_layout=fields.get("plank_layout") or "",
        long_lived_template=fields.get("long_lived") or "",
        test_support=tuple(fields.get("test_support") or ()),
        layers=tuple(fields.get("layers") or ()),
        layers_declared=fields.get("layers") is not None,
        paths=tuple(_regexes(fields.get("paths"))))


def layers_of(profile) -> tuple:
    """Действующие слои компонента (SPEC 01M5J0JYW3GZSSHHK3TYCYTQ3J,
    требование 1): явное поле `layers`, без него — `python-ast` у команды
    pytest и ничего у прочих; без `python-ast` гейт исходов судит правки
    тестов строгим режимом. Явное пустое `layers: []` — ничего (SPEC
    01M5JGSAANR1NZYQD4FCSVE48Y, требование 7)."""
    if profile.layers or getattr(profile, "layers_declared", False):
        return tuple(profile.layers)
    # acceptance -> ... -> store -> ... -> project_profile: цикл импорта.
    from .acceptance import is_pytest_command
    return ("python-ast",) if is_pytest_command(profile.command) else ()


def component_profiles(target: str, names=None) -> tuple:
    """Профили компонентов записи `target` (все либо названные `names`, в
    порядке записи) — для узлов полного прогона по компонентам (SPEC
    01M590GJAF0EDV4NBC4C99MFVH, требование 11). Поля профиля, которых у
    компонента записи из нескольких компонентов может не быть
    (`long_lived_dir` и др.), — пустые: прогону полного набора компонента
    они не нужны. TargetsError — запись не годна."""
    chosen = []
    for comp in components(target):
        if names is not None and comp.name not in names:
            continue
        fields = comp.fields
        profile = Profile(
            command=tuple(fields.get("command") or ()),
            long_lived_dir=fields.get("long_lived_dir") or "",
            long_lived_name=fields.get("long_lived_name") or "",
            weakening_scope=tuple(fields.get("weakening_scope") or ()),
            mutation_claim_scope=tuple(fields.get("mutation_claim_scope") or ()),
            report=fields.get("report") or "",
            install=tuple(fields.get("install") or ()),
            full_suite_timeout_sec=fields.get("full_suite_timeout_sec"),
            runner=fields.get("runner") or targets.PROFILE_RUNNER_DEFAULT,
            workdir=fields.get("workdir") or "",
            env=MappingProxyType(dict(fields.get("env") or {})),
            long_lived_imports=tuple(fields.get("long_lived_imports") or ()),
            project=target)
        chosen.append(_with_component_fields(profile, comp))
    return tuple(chosen)


# Отчёт компонента, итог которого читается только из отчёта пульта (SPEC
# 01M590GJAF0EDV4NBC4C99MFVH, требования 1, 5).
REPORT_JUNIT = "junit-xml"
REPORT_VITEST = "pult-vitest"
# Умолчание `report_args` у `junit-xml` (требование 2): `{path}` — файл
# отчёта вне рабочей копии.
JUNIT_DEFAULT_REPORT_ARGS = ("--junitxml", "{path}")


def reported(profile) -> bool:
    """Итог прогона по профилю читается только из отчёта (требование 4):
    `report` объявлен у компонента записи `components:` либо у записи
    `test_profile` с `runner: pytest-own`. Запись артели (`pult-pytest`) и
    записи без `report` — прежний разбор по коду возврата и тексту
    pytest."""
    if not getattr(profile, "report", ""):
        return False
    return bool(getattr(profile, "from_components", False)) or \
        getattr(profile, "runner", "") == targets.PROFILE_RUNNER_OWN


def report_args_of(profile) -> tuple:
    """Действующие `report_args` профиля с отчётом: явные — как есть, у
    `junit-xml` без них — умолчание `JUNIT_DEFAULT_REPORT_ARGS`
    (требование 2)."""
    if profile.report_args:
        return tuple(profile.report_args)
    if profile.report == REPORT_JUNIT:
        return JUNIT_DEFAULT_REPORT_ARGS
    return ()


# Базовый argv команды компонента `pult-vitest` (требование 7): `command`
# компонента обязан совпасть с ним; флаги пульта добавляются после.
VITEST_BASE_ARGV = ("node_modules/.bin/vitest", "run", "--config",
                    "vitest.config.js", "--allowOnly=false", "--update=false",
                    "--retry=0")
VITEST_REQUIRE_ASSERTIONS = "--expect.requireAssertions"


@dataclass(frozen=True)
class VitestFlags:
    """Флаги пульта для главной версии Vitest: флаг каталога кэша и
    принимает ли версия `--expect.requireAssertions`; `probe` — чем
    подтверждено значение."""
    cache_flag: str
    require_assertions: bool
    probe: str


# Главная версия Vitest → флаги пульта (ANSWER-2, В1). Версия вне таблицы —
# отказ подготовки прогона: флаг кэша для неё не подтверждён. Значение для
# Vitest 4 — кандидат; правит его проба этапа 2 (перевод записи sled).
VITEST_VERSION_FLAGS = {
    4: VitestFlags("--cacheDir", True, "не подтверждено пробой (этап 2)"),
}


def vitest_flags(major: int):
    """Запись `VITEST_VERSION_FLAGS` главной версии `major` (ключ — число
    или его строка); `None` — версии в таблице нет."""
    table = VITEST_VERSION_FLAGS
    return table.get(major, table.get(str(major)))


def component_limit(profile) -> tuple[int, str]:
    """Предел полного набора компонента — его `full_suite_timeout_sec`
    (требование 10), иначе `config`."""
    if profile.full_suite_timeout_sec is not None:
        return (profile.full_suite_timeout_sec,
                f"компонент {profile.component} проекта {profile.project}")
    return config.FULL_SUITE_TIMEOUT_SEC, "config"


def _regexes(value) -> list:
    if value is None:
        return []
    return [value] if isinstance(value, str) else list(value)


def _touches(component: Component, path: str) -> bool:
    """Путь задевает компонент: его `paths`, маски `test_support` или
    `paths` поставщика `depends_on` вида `paths`/`files` (компонент —
    потребитель). `contract` выбор не расширяет."""
    fields = component.fields
    regexes = _regexes(fields.get("paths"))
    for dep in (fields.get("depends_on") or {}).values():
        if dep.get("via") in ("paths", "files"):
            regexes += _regexes(dep.get("paths"))
    if any(re.search(regex, path) for regex in regexes):
        return True
    return any(mask_matches(mask, path)
               for mask in fields.get("test_support") or ())


def select_components(target: str, paths) -> tuple[str, ...]:
    """Имена компонентов, затронутых путями `paths` (от корня репозитория),
    в порядке записи. Путь, не задевший ни одного компонента, — все
    компоненты; пустой набор путей — тоже все (ничего не гонять — не
    вывод из пустого набора). У записи с одним компонентом — он."""
    comps = components(target)
    names = tuple(c.name for c in comps)
    if len(comps) <= 1:
        return names
    chosen = set()
    for path in paths:
        hit = {c.name for c in comps if _touches(c, path)}
        if not hit:
            return names
        chosen |= hit
    if not chosen:
        return names
    return tuple(name for name in names if name in chosen)


def test_id(component: str, path: str, name: str, n: int | None = None) -> str:
    """Идентификатор теста компонента `<компонент>:<путь>::<полное
    имя>[#<n>]` (ADR-0026 п. 3)."""
    if ":" in component:
        raise ValueError(f"имя компонента '{component}' с ':'")
    text = f"{component}:{path}::{name}"
    return text if n is None else f"{text}#{n}"


def parse_test_id(text: str) -> tuple[str, str, str, int | None]:
    """Обратный разбор `test_id`: (компонент, путь, полное имя, номер или
    `None`). Полное имя может само нести `::`. ValueError — не та форма."""
    component, sep, rest = text.partition(":")
    path, sep2, name = rest.partition("::")
    if not (sep and sep2 and component and path and name):
        raise ValueError(f"'{text}' — не идентификатор теста компонента "
                         f"<компонент>:<путь>::<полное имя>[#<n>]")
    n = None
    head, hash_, tail = name.rpartition("#")
    if hash_ and tail.isascii() and tail.isdigit() and head:
        name, n = head, int(tail)
    return component, path, name, n


# Действие журнала: правило планки проекта не построено по записи, взято
# умолчание (SPEC 01M59KMPG2ZMK10V556VZVQD65, требование 2) — чекпоинт,
# автогейт и документы перед мержем; деталь — причина отказа построения.
PLANK_RULE_DEFAULT_ACTION = "правило планки: взято умолчание"


def plank_rule(target: str) -> guard.PlankRule:
    """Правило планки проекта `target` (SPEC 01M59KMPG2ZMK10V556VZVQD65,
    требование 2): умолчание — артели (запись не читается), записи
    `test_profile`, непрочитанной записи и записи, где ни один компонент
    не получает правила по маскам (нет `tests` либо pytest-команда).
    Иначе — компоненты в порядке записи: по последнему сегменту масок
    `tests` с меткой `AC-<n>: ` и пометками `//`, прочие — по умолчанию.
    Компонент `report: pult-vitest` без `tests` — отказ построения:
    умолчание с причиной в `refusal`. `decide` не зовётся: запись с
    несколькими компонентами правило строит без отказа."""
    # acceptance -> ... -> store -> ... -> project_profile: цикл импорта.
    from .acceptance import is_pytest_command
    if repo_context.is_artel(target):
        return guard.DEFAULT_PLANK_RULE
    try:
        if targets.target(target).get(targets.COMPONENTS_FIELD) is None:
            return guard.DEFAULT_PLANK_RULE
        comps = components(target)
    except targets.TargetsError:
        return guard.DEFAULT_PLANK_RULE
    for comp in comps:
        if comp.fields.get("report") == REPORT_VITEST and \
                not comp.fields.get("tests"):
            return guard.PlankRule(refusal=(
                f"у компонента {comp.name} нет tests — допустимые файлы "
                f"планки не определены"))
    built = []
    for comp in comps:
        masks = tuple(comp.fields.get("tests") or ())
        if not masks or is_pytest_command(comp.fields.get("command")):
            built.append(guard.PlankComponent(comp.name, masks))
        else:
            built.append(guard.PlankComponent(
                comp.name, masks, guard.LABEL_AC, guard.MARKER_SLASH))
    if all(c.label == guard.LABEL_TEST_AC for c in built):
        return guard.DEFAULT_PLANK_RULE
    return guard.PlankRule(components=tuple(built))


def long_lived_rule(target: str, profile: Profile) -> "guard.PlankRule | None":
    """Правило планки проекта для долгоживущих файлов (SPEC
    01M5AA5TS90RDJ2AFXB882WTPD, требования 5-7): только у профиля из
    шаблона `long_lived`; `None` — прежний разбор долгоживущих файлов
    (явная пара, `test_profile`, артель)."""
    if not profile.long_lived_template:
        return None
    return plank_rule(target)


def journal_plank_default(conn, task_id: str, actor: str,
                          rule: guard.PlankRule) -> None:
    """Запись о взятом умолчании при отказе построения правила планки; без
    отказа — ничего."""
    if rule.refusal:
        store.journal(conn, task_id, actor, PLANK_RULE_DEFAULT_ACTION,
                      rule.refusal)


def journal_skip(conn, task_id: str, check: str, decision: Decision) -> None:
    """Запись о невыполненной проверке у проекта без профиля: какая
    проверка и почему (требование 3)."""
    store.journal(conn, task_id, "fsm", f"{SKIP_ACTION}: {check}",
                  decision.skip)


def refusal_hint(task_id: str) -> str:
    return (f"почини {config.TARGETS.name} (запись проекта и её поле "
            f"test_profile) и повтори artel.py advance {task_id}")
