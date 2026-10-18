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
from dataclasses import dataclass, field
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
        name = self.long_lived_name.replace("<id>", task_id.lower())
        return f"{self.long_lived_dir}/{name.replace('<name>', '<имя>')}"

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
        return Decision(target, profile=Profile.from_values(answer.values))
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


def long_lived_imports(target: str, profile: Profile | None):
    """Правило импортов долгоживущих файлов проекта для
    `guard.long_lived_errors_from_files(project_imports=…)` (SPEC
    01M5633WZ3Y3A0P4KKBZDB3KER): `None` — артель, правило пульта; у
    внешнего проекта — перечень его профиля, пустой без подполя."""
    if repo_context.is_artel(target):
        return None
    return profile.long_lived_imports if profile is not None else ()


def for_task(conn, task_id: str) -> Decision:
    return decide(store.task_target(conn, task_id))


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


def journal_skip(conn, task_id: str, check: str, decision: Decision) -> None:
    """Запись о невыполненной проверке у проекта без профиля: какая
    проверка и почему (требование 3)."""
    store.journal(conn, task_id, "fsm", f"{SKIP_ACTION}: {check}",
                  decision.skip)


def refusal_hint(task_id: str) -> str:
    return (f"почини {config.TARGETS.name} (запись проекта и её поле "
            f"test_profile) и повтори artel.py advance {task_id}")
