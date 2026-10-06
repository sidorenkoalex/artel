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
from dataclasses import dataclass

from scripts import guard

from . import config, repo_context, store

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

    @classmethod
    def from_values(cls, values: dict) -> "Profile":
        return cls(command=tuple(values["command"]),
                   long_lived_dir=values["long_lived_dir"],
                   long_lived_name=values["long_lived_name"],
                   weakening_scope=tuple(values["weakening_scope"]),
                   mutation_claim_scope=tuple(values["mutation_claim_scope"]),
                   report=values.get("report") or "",
                   install=tuple(values.get("install") or ()))

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


def for_task(conn, task_id: str) -> Decision:
    return decide(store.task_target(conn, task_id))


def journal_skip(conn, task_id: str, check: str, decision: Decision) -> None:
    """Запись о невыполненной проверке у проекта без профиля: какая
    проверка и почему (требование 3)."""
    store.journal(conn, task_id, "fsm", f"{SKIP_ACTION}: {check}",
                  decision.skip)


def refusal_hint(task_id: str) -> str:
    return (f"почини {config.TARGETS.name} (запись проекта и её поле "
            f"test_profile) и повтори artel.py advance {task_id}")
