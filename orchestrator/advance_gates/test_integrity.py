"""Гейт неослабления тестов — узел сравнения `tests/` ветки с базой: ослабление и смена ожидания, сверка с объявленным в SPEC, строгость нового ожидания, храповик (SPEC 01M3FQ2V77QNK95Z599DM124QN, 01M45FJD46BX45VHC36S4VS9QN).

Принцип целостности (ADR-0002, CLAUDE.md, шапка docs/invariants.md)
запрещает роли удалять, переименовывать и ослаблять тесты; до этой задачи
принцип держался текстом промпта и вниманием ревьювера, а на гейте мержа
— ручной сверкой Оператора. Машинного рубежа не было ни на одном
переходе: соседний гейт заявки мутации
(`advance_gates/review.py::_mutation_claim_gate`) удалённый в head файл
тестов МОЛЧА пропускает по своей семантике («нечего проверять на
заявку»), и удаление доходило до main.

Узел здесь ОДИН (`findings`), его зовут оба гейта — обёртка
`_test_integrity_gate_refuses` на `in_dev -> verifying` (требование 6,
fail-closed на сбое git) и `merge_gate_escalates` в
`orchestrator/fsm_merge_gate.py` (требование 7, fail-open на сбое git,
как у соседнего `_protected_path_diff_gate`). Ast-разбор тестов живёт не
здесь, а в `scripts/guard.py` (`qualified_test_methods`/
`test_skip_markers`) — единственный адрес правила «что считается тестовым
методом» в пульте (требование 1).

Послабление SPEC 01M3HWXFYWVDHGW011P6BZJFYA живёт тут же, в узле, и потому
действует на обоих рубежах сразу (его требование 8): маркер пропуска на
НОВОМ тестовом методе — таком, чьего квалифицированного имени в базе
сравнения нет — находкой не считается, если он одновременно условный и с
названной причиной, а сами такие пропуски уходят в журнал задачи:
послаблению нельзя быть молчаливым. Той же правкой закрыт обход рубежа
ранним `return` под условием — 27.09 новый тест оболочки входа выключили
им вместо пропуска, и на машине без `/bin/zsh` он остался зелёным, не
проверив ничего.

Тем же проходом по диффу узел наблюдает и изменённые утверждения метода,
сохранившего имя (SPEC 01M3Y753QNG6TS5C7MTJS1MEV6): нормальную форму
утверждения считает `guard.test_assertions`, находки пишутся в журнал на
обоих рубежах и уходят в ревью-пакет (SPEC 01M3Y753QNG6TS5C7MTJS1MEV6,
решение Оператора 02.10: сначала наблюдение).

Блокировка — SPEC 01M45FJD46BX45VHC36S4VS9QN (решение Оператора 05.10):
изменённые утверждения метода стали находкой узла отказа, кроме смены
ожидания, объявленной в разделе SPEC «Меняемое поведение» и записанной
`approve` гейта SPEC (запись «объявлена смена поведения тестов» — она же
решение Оператора; правка раздела после approve на рубежах не действует).
Различение смены ожидания и ослабления и оценка строгости нового
ожидания живут в `guard.assertion_changes`; здесь — сверка фактических
пар «было → стало» с объявленными, исход по каждому методу (запись
«утверждения тестов: исход рубежа»), храповик (число тестовых методов и
утверждений диффа `tests/` не убывает) и вызов двустороннего прогона
(`two_sided`) на переходе либо сверка его записи с головой ветки на
гейте мержа. Мандат «Ослабление тестов разрешено: …» по-прежнему снимает
любую находку.
"""
import ast
import re
from typing import NamedTuple

from scripts import guard

from .. import artifact_branch as docs_ref
from .. import config, gitcmd, store, workspace
from . import two_sided
from ._base import GateRefusal, _run_gates
# Маркер мандата ослабления и разбор его строки живут в `mandate` — общем
# узле разбора строки мандата (SPEC 01M3GKJBXEBHB6ZA48J7VG8Z8W, требование
# 1); импорт сюда сохраняет прежнее имя `test_integrity.
# TEST_WEAKENING_MANDATE_MARKER` рабочим для `fsm_advance` и тестов.
from .mandate import (TEST_WEAKENING_MANDATE_MARKER, elements,
                      in_weakening_scope)
from .zones import _answer_commit_is_role_step_autocommit

# Именованное действие отказа — общее для перехода и для эскалации на
# гейте мержа (требования 6-7, AC-1/AC-12). Префикс «переход отклонён» —
# по нему `store.refusal_history` доносит отказ до брифа роли.
TEST_INTEGRITY_REFUSAL_ACTION = "переход отклонён: гейт неослабления тестов"

# Действие журнальной записи о находках, покрытых мандатом Оператора
# (требование 4, AC-8): они не попадают в текст отказа, но обязаны
# остаться видимыми — иначе Оператор на приёмке не узнает, что прошло по
# его разрешению.
TEST_INTEGRITY_ALLOWED_ACTION = "ослабление тестов разрешено мандатом Оператора"

# Действие журнальной записи о пропусках, прошедших послабление (SPEC
# 01M3HWXFYWVDHGW011P6BZJFYA, требование 7, AC-2): рубеж по ним молчит, но
# видимыми они остаться обязаны — запись читает ревьювер, и она же
# остаётся Оператору на приёмке. Уровень обычный: это не отказ и не алерт.
TEST_INTEGRITY_CONDITIONAL_SKIP_ACTION = "новый тест с условным пропуском"

# Наблюдение за изменёнными утверждениями метода, сохранившего имя (SPEC
# 01M3Y753QNG6TS5C7MTJS1MEV6, требование 5): записи в прежней форме
# остаются на обоих рубежах и после того, как изменённые утверждения
# стали находкой (SPEC 01M45FJD46BX45VHC36S4VS9QN, требование 8).
ASSERTION_OBSERVATION_ACTION = "изменены утверждения тестов (наблюдение)"
ASSERTION_UNOBSERVED_ACTION = "утверждения тестов: наблюдение не выполнено"
ASSERTION_UNOBSERVED_PREFIX = "наблюдение не выполнено"
ASSERTIONS_CHANGED = "утверждения изменены в"
ASSERTIONS_COVERED = "покрыто мандатом"
# Сколько утверждений одного метода называет текст находки (требование 4).
ASSERTION_TEXTS_SHOWN = 3

# Смена поведения в существующих тестах (SPEC 01M45FJD46BX45VHC36S4VS9QN).
# Запись approve гейта SPEC — объявленный перечень и решение Оператора
# (требования 3-4); её пишет `fsm._approve_spec_gate`, читает этот узел.
DECLARED_CHANGE_ACTION = "объявлена смена поведения тестов"
# Исход рубежа по каждому изменённому или объявленному методу (требование 8).
OUTCOME_ACTION = "утверждения тестов: исход рубежа"
# Запись перехода о доказанной смене поведения (требование 10); гейт мержа
# сверяет её sha с головой ветки (требование 11).
TWO_SIDED_PASSED_ACTION = "двусторонний прогон пройден"
# Три причины находки об утверждениях метода (требование 7).
REASON_OUTSIDE = "смена вне раздела «Меняемое поведение»"
REASON_WEAKENING = "ослабление"
REASON_MISMATCH = "смена не совпала с объявленным"
REASON_TWO_SIDED_MISSING = "двусторонний прогон для текущей головы не записан"
OUTCOME_EXPECTATION = "смена ожидания по SPEC (требование {n})"
OUTCOME_UNCHANGED = "объявлен в SPEC, утверждения не изменены"
OUTCOME_FINDING = "находка"
TWO_SIDED_FOR_HEAD = "двусторонний прогон для текущей головы"
TWO_SIDED_NOT_RECORDED = "не записан"
_TWO_SIDED_RECORD = re.compile(r"^голова ([0-9a-f]+); база ([0-9a-f]*); "
                               r"методы: (.*)$", re.S)

# Декораторы пропуска, несущие УСЛОВИЕ — подмножество
# `guard.SKIP_DECORATOR_NAMES`. Остальные из того набора (`skip`,
# `expectedFailure`, `xfail`) гасят тест на ВСЕХ машинах навсегда и
# послаблению не подлежат, даже когда причина у них названа (требование 3).
_CONDITIONAL_DECORATORS = frozenset(("skipIf", "skipUnless", "skipif"))

# Точечное имя декоратора и вызываемого — тем же разбором, которым его
# видит `guard.test_skip_markers`. Текст маркера здесь обязан совпасть с
# её ключами байт-в-байт: иначе послабление сверяется с маркером, которого
# в наборе нет, и молча не срабатывает. Своя копия разбора разошлась бы с
# эталоном при первой правке `scripts/guard.py`, а публичного имени там
# завести нельзя — SPEC задачи называет этот файл только для чтения.
_called_dotted_name = guard._called_dotted_name


class Finding(NamedTuple):
    """Одна находка узла: `path` — путь файла в БАЗЕ сравнения (у
    переименования — старый путь: он же идёт первым в колонку detail),
    `name` — квалифицированное имя метода или класса (пустое — находка о
    файле целиком), `text` — «что именно» для колонки detail, `alias` —
    второй путь того же файла у распознанной пары переименования (путь в
    head), пустой у всех остальных находок."""

    path: str
    name: str
    text: str
    alias: str = ""

    @property
    def line(self) -> str:
        return f"{self.path}: {self.text}"

    @property
    def mandate_elements(self) -> tuple:
        """Элементы мандата, которые покрывают ЭТУ находку: путь файла
        покрывает все его находки, элемент `путь::Класс` — находки о самом
        классе и о любом его методе, элемент `путь::Класс::метод` — только
        находку об этом методе (требование 4; SPEC
        01M42NB9GKXNP74HAYEJ7C7CA8, требование 1).

        Класс засчитывается через префиксы квалифицированного имени по
        целым частям `::`, а не префиксом строки: элемент `путь::A` не
        покрывает класс `AB` того же файла, элемент `путь::A::m1` — метод
        `A::m1_x`. До этого правила элемент-класс не покрывал находок о
        методах вовсе, и 03.10 ANSWER-1 задачи 01M41VTQJ9DSX64NFMFAF9W53B с
        двумя классами получил отказ по двенадцати методам.

        У пары переименования засчитываются ОБА пути — старый (`path`) и
        новый (`alias`). Оператор пишет мандат, глядя на ветку и на PR,
        где файл уже лежит под новым именем, и признание одного лишь
        пути из базы сравнения стоило бы ему лишнего круга `advance` на
        безупречно выписанном разрешении (REVIEW итерация 1, R1-F2).
        """
        paths = (self.path, self.alias) if self.alias else (self.path,)
        if not self.name:
            return paths
        parts = self.name.split(guard.TEST_NAME_SEP)
        names = [guard.TEST_NAME_SEP.join(parts[:i])
                 for i in range(len(parts), 0, -1)]
        return paths + tuple(f"{p}{guard.TEST_NAME_SEP}{n}"
                             for p in paths for n in names)


class ConditionalSkip(NamedTuple):
    """Пропуск, прошедший послабление требования 2: `path` — путь файла в
    HEAD (его роль и ревьювер видят в ветке), `name` — квалифицированное
    имя метода, `reason` — названная причина."""

    path: str
    name: str
    reason: str

    @property
    def line(self) -> str:
        """Элемент detail журнальной записи требования 7:
        «<файл>::<квалифицированное имя метода> — <причина>». Разделитель —
        тот же `guard.TEST_NAME_SEP`, которым Оператор называет метод в
        мандате: двух разных написаний одного адреса в пульте быть не
        должно."""
        return f"{self.path}{guard.TEST_NAME_SEP}{self.name} — {self.reason}"


def _in_scope(path) -> bool:
    """Путь принадлежит области узла — `tests/**/*.py` на ЛЮБОЙ глубине
    (требование 2), не только верхний уровень, как у гейта заявки мутации.

    Полный набор гоняется как `pytest tests` (`acceptance.run_full_suite`),
    то есть собирает подкаталоги наравне с верхним уровнем: тест,
    заведённый в `tests/<подкаталог>/test_x.py`, при верхнеуровневом
    фильтре можно было бы удалить вне поля зрения рубежа. Файлы планок
    `tasks/*/acceptance_tests` под `tests/` не лежат и в область не входят
    — их держит лок планки (AC-5).

    Сама формула живёт в `mandate.in_weakening_scope` — общий узел с
    проверкой элемента мандата при записи ответа (REVIEW итерация 1,
    R1-F2): область гейта и правило годности элемента обязаны совпадать,
    иначе элемент вида `tests/fixtures/data.json` записывается без отказа
    и молча не срабатывает.
    """
    return in_weakening_scope(path)


def _pair(status: str, first: str, second):
    """(путь в base, путь в head, «переименован в») одной записи
    `git diff -M --name-status`.

    `R` — пара переименования от git (требование 3); `D` — файла в head
    нет; `A`/`C` — базовой стороны нет (копия — это НОВЫЙ файл: оригинал
    остался на месте и своей защиты не терял); остальные статусы (`M`,
    `T`, `U`) — тот же путь по обе стороны.
    """
    kind = status[:1]
    if kind == "R":
        return first, second, second
    if kind == "D":
        return first, None, None
    if kind in ("A", "C"):
        return None, second or first, None
    return first, first, None


def _git_silence(what: str) -> str:
    """Текст detail на молчание git — общий вид для всех трёх точек чтения
    (требование 6, AC-11)."""
    return (f"гейт неослабления тестов: git не ответил на {what} — "
           f"сверка тестов ветки с базой невозможна")


def _constant_reason(call: ast.Call, position: int) -> str:
    """Названная причина маркера: строковая КОНСТАНТА, непустая после
    отбрасывания пробелов — позиционным аргументом `position` либо
    именованным `reason=` (требование 2). Пустая строка — причины нет.

    Вычисляемое выражение (переменная, конкатенация, f-строка) причиной не
    считается: его текст статическим разбором не восстановить, и в журнал
    требования 7 ушло бы либо пусто, либо исходный код выражения вместо
    объяснения для ревьювера — рубеж закрывается в пользу находки.
    """
    candidates = [kw.value for kw in call.keywords if kw.arg == "reason"]
    if len(call.args) > position:
        candidates.insert(0, call.args[position])
    for node in candidates:
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and node.value.strip():
            return node.value.strip()
    return ""


def _decorator_occurrence(decorator, dotted: str) -> tuple:
    """(маркер, причина) одного декоратора пропуска. Причина пустая —
    декоратор под послабление не годится: он безусловен
    (`skip`/`expectedFailure`/`xfail`), у него нет аргумента условия либо
    причина не названа строковой константой.

    Значим ПОСЛЕДНИЙ сегмент точечного имени — то же правило, по которому
    маркер вообще опознан (`guard.SKIP_DECORATOR_NAMES`): один набор
    покрывает и `@unittest.skipIf`, и `@skipIf` от `from unittest import
    skipIf`, и `@pytest.mark.skipif`.
    """
    marker = f"@{dotted}"
    if dotted.rsplit(".", 1)[-1] not in _CONDITIONAL_DECORATORS:
        return marker, ""
    if not isinstance(decorator, ast.Call) or not decorator.args:
        # Условие — первый позиционный аргумент; `@skipIf` без скобок или
        # `@pytest.mark.skipif(reason="…")` без условия выключают тест
        # безусловно, как ни назови причину.
        return marker, ""
    return marker, _constant_reason(decorator, 1)


def _skip_calls(node, inside_if: bool):
    """(вызов пропуска, точечное имя, внутри ли он `if`) по всему узлу —
    тот же обход, что у `guard._body_skip_markers` (весь метод, включая
    декораторы и вложенные функции), плюс память о ветке `if`.

    Условным считается вызов в теле `if` либо `else` на ЛЮБОЙ глубине
    вложенности (требование 2). Вызов в самом УСЛОВИИ условным не
    считается: условие вычисляется всегда, и `if self.skipTest("x"):`
    гасит тест на каждой машине.
    """
    if isinstance(node, ast.If):
        yield from _skip_calls(node.test, inside_if)
        for sub in node.body + node.orelse:
            yield from _skip_calls(sub, True)
        return
    if isinstance(node, ast.Call):
        dotted = _called_dotted_name(node.func)
        if dotted and (dotted.rsplit(".", 1)[-1] == "skipTest"
                       or dotted in guard.SKIP_CALL_NAMES):
            yield node, dotted, inside_if
    for child in ast.iter_child_nodes(node):
        yield from _skip_calls(child, inside_if)


def _excused_skips(node) -> dict:
    """{маркер: причина} по маркерам пропуска ОДНОГО тестового метода,
    которые годятся под послабление требования 2 — условные и с названной
    причиной.

    Маркер попадает сюда только если КАЖДОЕ его вхождение в метод годится:
    `guard.test_skip_markers` сводит вхождения к одному тексту маркера, и
    безусловный `self.skipTest("причина")` первой строкой тела не имеет
    права уйти из находок за компанию с условным вызовом того же вида
    ниже (рубеж закрывается в пользу находки).
    """
    occurrences: list = []
    for decorator in getattr(node, "decorator_list", []):
        dotted = _called_dotted_name(decorator)
        if dotted and dotted.rsplit(".", 1)[-1] in guard.SKIP_DECORATOR_NAMES:
            occurrences.append(_decorator_occurrence(decorator, dotted))
    for call, dotted, inside_if in _skip_calls(node, False):
        occurrences.append((f"{dotted}(",
                            _constant_reason(call, 0) if inside_if else ""))

    excused: dict = {}
    rejected: set = set()
    for marker, reason in occurrences:
        if reason and marker not in rejected:
            excused.setdefault(marker, reason)
        else:
            rejected.add(marker)
            excused.pop(marker, None)
    return excused


def _has_early_return(node) -> bool:
    """ПЕРВЫЙ исполняемый оператор тела метода (докстринг не в счёт) —
    оператор `if`, тело ветки которого ровно один `return` без значения
    (требование 5). Иные формы раннего выхода в границы не входят: SPEC
    перечисляет их в «Не входит» дословно.
    """
    body = list(node.body)
    if body and isinstance(body[0], ast.Expr) \
            and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        body = body[1:]
    if not body or not isinstance(body[0], ast.If):
        return False
    branch = body[0].body
    return len(branch) == 1 and isinstance(branch[0], ast.Return) \
        and branch[0].value is None


def _early_return_names(methods: dict) -> set:
    """Квалифицированные имена методов с ранним `return` под условием."""
    return {name for name, node in methods.items() if _has_early_return(node)}


def _early_return_text(name: str) -> str:
    """Текст находки о раннем `return` — отличим от текста находки о
    пропуске («<маркер> на <имя>»), как требует требование 6."""
    return f"ранний return под условием в {name}"


def _file_findings(base_path, head_path, renamed_to, base_source,
                   head_source) -> tuple:
    """(находки одного файла, прошедшие послабление пропуски).

    Находки: удаление/переименование (только если в base есть хоть один
    тестовый метод — требование 5 SPEC 01M3FQ2V77QNK95Z599DM124QN: защиты в
    пустом файле нет, удалять нечего), исчезнувшие методы, ПОЯВИВШИЕСЯ
    маркеры пропуска и ПОЯВИВШИЙСЯ ранний `return` под условием.

    У распознанной пары переименования сравнение идёт между СТАРЫМ путём
    в base и НОВЫМ в head (требование 3, последняя фраза): переименование
    с одновременным удалением метода даёт обе находки, не одну. Оба пути
    такой пары становятся `alias` КАЖДОЙ её находки — и самого
    переименования, и исчезнувшего метода, и появившегося маркера: мандат
    Оператора обязан читаться по любому из двух имён файла (R1-F2), а не
    только по тому, которого в ветке уже нет.
    """
    base_methods = guard.qualified_test_methods(base_source)
    path = base_path or head_path
    alias = renamed_to or ""
    found: list = []
    passed: list = []

    if base_methods:
        if head_path is None:
            found.append(Finding(path, "", "удалён"))
        elif renamed_to:
            found.append(Finding(path, "", f"переименован в {renamed_to}",
                                 alias))

    if head_path is None:
        # Методы удалённого файла по отдельности не перечисляются: находка
        # о самом файле уже называет потерю целиком, и мандат на путь
        # (требование 4) покрывает её одним элементом.
        return found, passed

    head_methods = guard.qualified_test_methods(head_source)
    for name in base_methods:
        if name not in head_methods:
            found.append(Finding(path, name, f"метод {name} исчез", alias))

    base_markers = guard.test_skip_markers(base_source)
    for name, markers in guard.test_skip_markers(head_source).items():
        # Послабление SPEC 01M3HWXFYWVDHGW011P6BZJFYA действует только на
        # имени МЕТОДА, которого в базе сравнения нет (его требования 1-2,
        # 4). Ключ `test_skip_markers`, отсутствующий среди методов head, —
        # это имя КЛАССА: один декоратор над классом гасит все его тесты
        # разом и остаётся находкой даже в новом файле.
        new_name = name in head_methods and name not in base_methods
        excused = _excused_skips(head_methods[name]) if new_name else {}
        for marker in sorted(markers - base_markers.get(name, set())):
            if marker in excused:
                # Путь HEAD, а не базы: перечень уходит в журнал задачи для
                # ревьювера, а он читает ветку.
                passed.append(ConditionalSkip(head_path, name,
                                              excused[marker]))
                continue
            found.append(Finding(path, name, f"{marker} на {name}", alias))

    # Ранний `return` — по тому же правилу появления, что маркеры пропуска
    # (требование 6): для нового метода база пуста, значит находка; тот же
    # ранний выход, стоявший на том же имени в базе, находки не даёт.
    for name in sorted(_early_return_names(head_methods)
                       - _early_return_names(base_methods)):
        found.append(Finding(path, name, _early_return_text(name), alias))
    return found, passed


class MethodChange(NamedTuple):
    """Метод, сохранивший имя, с изменёнными утверждениями: путь в базе
    (`path`), второй путь пары переименования (`alias`), путь в голове,
    квалифицированное имя, исход `guard.assertion_changes` и тексты файла
    по обе стороны (их берёт двусторонний прогон)."""

    path: str
    alias: str
    head_path: str
    name: str
    change: guard.AssertionChange
    base_source: str
    head_source: str

    @property
    def address(self) -> str:
        return f"{self.path}{guard.TEST_NAME_SEP}{self.name}"

    @property
    def head_address(self) -> str:
        return f"{self.head_path}{guard.TEST_NAME_SEP}{self.name}"


def _assertion_observation(base_path, head_path, renamed_to, base_source,
                           head_source) -> tuple:
    """(находки об изменённых утверждениях одного файла, причина, по
    которой наблюдение по нему не выполнено, изменения по методам) — SPEC
    01M3Y753QNG6TS5C7MTJS1MEV6, требования 3-4; изменения по методам —
    `guard.assertion_changes` (SPEC 01M45FJD46BX45VHC36S4VS9QN, требование
    5).

    Удалённый и добавленный файл не сравниваются: у удалённого находка о
    самом файле уже названа, у нового базы нет. Метод, исчезнувший из head,
    сюда не попадает — `guard.changed_test_assertions` сравнивает только
    имена, живые по обе стороны, и находка «метод … исчез» остаётся
    единственной (AC-5). Неразбираемая сторона — не исключение и не
    находка, а названная причина (AC-9)."""
    if base_path is None or head_path is None:
        return [], "", []
    path = base_path
    base = guard.test_assertions(base_source)
    head = guard.test_assertions(head_source)
    broken = [side for side, parsed in (("base", base), ("head", head))
              if parsed is None]
    if broken:
        return [], (f"{path}: не разбирается ({', '.join(broken)}) — "
                    f"утверждения не сравнивались"), []
    found = []
    for name, texts in guard.changed_test_assertions(base, head).items():
        shown = "; ".join(texts[:ASSERTION_TEXTS_SHOWN])
        if len(texts) > ASSERTION_TEXTS_SHOWN:
            shown += f"; и ещё {len(texts) - ASSERTION_TEXTS_SHOWN}"
        found.append(Finding(path, name, f"{ASSERTIONS_CHANGED} {name}: "
                                         f"{shown}", renamed_to or ""))
    changes = [MethodChange(path, renamed_to or "", head_path, name, change,
                            base_source, head_source)
               for name, change in (guard.assertion_changes(
                   base_source, head_source) or {}).items()]
    return found, "", changes


class Comparison(NamedTuple):
    """Один проход по диффу `tests/` (`_compare`): находки о файлах,
    прошедшие послабление пропуски, находки наблюдения утверждений,
    причины невыполненного наблюдения, изменения утверждений по методам,
    файлы диффа (путь base, путь head, текст base, текст head) для
    храповика, база сравнения и текст сбоя git. Сбой git — `found` равен
    `None`, остальное пусто."""

    found: list | None
    passed: list
    observed: list | None
    unobserved: list
    changes: list
    files: list
    base: str
    git_detail: str


def _git_failure(detail: str) -> Comparison:
    return Comparison(None, [], None, [], [], [], "", detail)


def _compare(code_branch: str, repo=None) -> Comparison:
    """Один проход по диффу `tests/` для всех наблюдателей узла.

    `repo` — клон проекта задачи, в котором живёт `code_branch` (ADR-0021
    п.1). Храповик (SPEC 01M45FJD46BX45VHC36S4VS9QN, требование 12) считает
    по тем же текстам файлов этого прохода: новых запросов git нет."""
    base = gitcmd.diff_base(code_branch, repo=repo)
    if base is None:
        return _git_failure(_git_silence(
            f"определение базы сравнения (merge-base с origin/"
            f"{config.MAIN_BRANCH} либо локальным {config.MAIN_BRANCH}) "
            f"для ветки {code_branch}"))
    entries = gitcmd.diff_name_status(base, code_branch, repo=repo)
    if entries is None:
        return _git_failure(_git_silence(
            f"список файлов диффа (база {base}...{code_branch})"))

    found: list = []
    passed: list = []
    observed: list = []
    unobserved: list = []
    changes: list = []
    files: list = []
    for status, first, second in entries:
        base_path, head_path, renamed_to = _pair(status, first, second)
        if not _in_scope(base_path) and not _in_scope(head_path):
            continue
        sources = {}
        for side, ref, path in (("base", base, base_path),
                                ("head", code_branch, head_path)):
            if path is None:
                sources[side] = None
                continue
            text, reason = gitcmd.show(ref, path, repo=repo)
            if text is None:
                # Путь существует в СВОЁМ дереве по построению: его назвал
                # сам `git diff --name-status` этой стороной записи —
                # значит `None` здесь всегда сбой чтения, не легитимное
                # отсутствие (различать их по тексту причины, как это
                # вынужден делать гейт заявки мутации, тут не нужно).
                return _git_failure(_git_silence(
                    f"чтение {path} из {ref} ({reason})"))
            sources[side] = text
        files.append((base_path, head_path, sources["base"], sources["head"]))
        file_found, file_passed = _file_findings(
            base_path, head_path, renamed_to, sources["base"], sources["head"])
        found += file_found
        passed += file_passed
        file_observed, reason, file_changes = _assertion_observation(
            base_path, head_path, renamed_to, sources["base"], sources["head"])
        observed += file_observed
        changes += file_changes
        if reason:
            unobserved.append(reason)
    return Comparison(found, passed, observed, unobserved, changes, files,
                      base, "")


def findings(code_branch: str, repo=None) -> tuple:
    """(находки ветки против базы сравнения о файлах и методах, прошедшие
    послабление пропуски, текст сбоя git).

    База — `gitcmd.diff_base` (merge-base с origin/main), та же, что у
    гейта заявки мутации и у `_protected_path_diff_gate`. Git не ответил
    на базу, на список файлов диффа или на чтение содержимого пути,
    который по ответу самого git существует в своём дереве, — находки НЕ
    собраны: `(None, [], detail)`. Как на это реагировать, решает
    вызывающий гейт (fail-closed на переходе, fail-open на мерже), а не
    этот узел.

    Второй элемент — пропуски, прошедшие послабление требования 2 SPEC
    01M3HWXFYWVDHGW011P6BZJFYA: находками они не стали, но потеряться не
    имеют права, и вызывающий вход (`uncovered`) пишет их в журнал задачи.

    Находки об изменённых утверждениях сюда не входят: их исход зависит от
    объявленного в SPEC и от мандата, его считает общий вход `uncovered`.
    """
    cmp = _compare(code_branch, repo=repo)
    return cmp.found, cmp.passed, cmp.git_detail


def _observation_lines(observed: list, mandate: dict) -> list:
    """Строки detail записи наблюдения: «файл: утверждения изменены в …»,
    у покрытых мандатом — с отметкой «покрыто мандатом ANSWER-n»
    (требование 5, AC-7). Покрытие — тем же правилом, что у находок
    отказа (`Finding.mandate_elements`): путь файла покрывает все находки
    файла, элемент-класс — находки о его методах, элемент-метод — только
    названный метод."""
    lines = []
    for finding in observed:
        source = _covering_source(finding, mandate)
        lines.append(finding.line if source is None
                     else f"{finding.line} — {ASSERTIONS_COVERED} {source}")
    return lines


def _covering_source(finding: Finding, mandate: dict):
    """Имя ANSWER-n, чей элемент мандата покрывает `finding`; `None` — не
    покрыта."""
    return next((mandate[e] for e in finding.mandate_elements
                 if e in mandate), None)


def assertion_observation(task_id: str, code_branch: str,
                          artifact_branch: str) -> tuple:
    """(строки находок об изменённых утверждениях с отметкой мандата,
    причины невыполненного наблюдения по файлам, текст сбоя git).
    Ничего не журналирует: запись пишут рубежи через `uncovered`."""
    repo = workspace.task_repo(task_id)
    cmp = _compare(code_branch, repo=repo)
    if cmp.observed is None:
        return [], [], cmp.git_detail
    mandate = _answer_mandate(artifact_branch, task_id) if cmp.observed else {}
    return _observation_lines(cmp.observed, mandate), cmp.unobserved, ""


def _journal_observation(conn, task_id: str, lines: list,
                         unobserved: list) -> None:
    """Записи наблюдения рубежа (требование 5, AC-6/AC-8/AC-9): одна —
    о находках, одна — о невыполненном наблюдении; без находок и без
    причин журнал не трогается."""
    if lines:
        store.journal(conn, task_id, "fsm", ASSERTION_OBSERVATION_ACTION,
                      "; ".join(lines))
    if unobserved:
        store.journal(conn, task_id, "fsm", ASSERTION_UNOBSERVED_ACTION,
                      "; ".join(f"{ASSERTION_UNOBSERVED_PREFIX}: {reason}"
                                for reason in unobserved))


def _answer_mandate(artifact_branch: str, task_id: str) -> dict:
    """{элемент мандата: имя файла ANSWER} по ВСЕМ `tasks/<id>/ANSWER-n.md`
    ветки задачи — тем же приёмом, что мандат расширения зон
    (`zones._answer_zones_mandate`), включая отказ засчитывать файл, чей
    последний коммит — доказанный автокоммит шага роли: иначе developer
    выписал бы себе разрешение сам, положив ANSWER-n.md в собственный
    `tasks/<id>/` прямо в шаге `in_dev` (AC-9). Саму строку разбирает общий
    узел `mandate.elements` (SPEC 01M3GKJBXEBHB6ZA48J7VG8Z8W, требование
    1) — тот же, что и у мандата зон, на том же правиле `startswith` и том
    же делении по запятым."""
    paths = docs_ref.ls_tree(task_id, artifact_branch, f"tasks/{task_id}") or []
    mandate: dict = {}
    for p in sorted(paths):
        name = p.rsplit("/", 1)[-1]
        if not (name.startswith("ANSWER-") and name.endswith(".md")):
            continue
        if _answer_commit_is_role_step_autocommit(artifact_branch, task_id, p):
            continue
        text, _reason = docs_ref.show(task_id, artifact_branch, p)
        if text is None:
            continue
        for line in text.splitlines():
            allowed = elements(line, TEST_WEAKENING_MANDATE_MARKER)
            for element in allowed or ():
                mandate.setdefault(element, name[:-len(".md")])
    return mandate


def declared_changes(conn, task_id: str) -> dict:
    """{`путь::Класс::метод`: guard.BehaviorChange} из ПОСЛЕДНЕЙ записи
    «объявлена смена поведения тестов» (требование 4): объявленное берётся
    из approve гейта SPEC, а не из текущего текста SPEC — правка раздела
    после approve на рубежах не действует до нового approve. Записи нет —
    пусто."""
    records = [row["detail"] or "" for row in store.task_steps(conn, task_id)
               if row["action"] == DECLARED_CHANGE_ACTION]
    if not records:
        return {}
    items: dict = {}
    for line in records[-1].splitlines():
        item, _reason = guard.parse_behavior_change_line(line)
        if item is not None:
            items[item.address] = item
    return items


def _declared_item(declared: dict, path: str, alias: str, name: str):
    for p in (path, alias):
        if p:
            item = declared.get(f"{p}{guard.TEST_NAME_SEP}{name}")
            if item is not None:
                return item
    return None


def _pairs_text(pairs) -> str:
    return "; ".join(f"`{old!r}` → `{new!r}`" for old, new in pairs)


def _declared_text(item) -> str:
    """Строка «было → стало (требование N)» объявленного метода — из
    записи approve (требование 13)."""
    pairs = "; ".join(f"`{old}` → `{new}`" for old, new in item.pairs)
    return f"было → стало: {pairs} (требование {item.requirement})"


def _change_reason(method: MethodChange, item) -> str:
    """Причина находки об утверждениях метода (требование 7б); пустая —
    исход 7а: смена ожидания, совпавшая с объявленным, со строгостью не
    ниже прежней."""
    change = method.change
    if change.kind != guard.ASSERTION_CHANGE_EXPECTATION or change.signs:
        return f"{REASON_WEAKENING}: {'; '.join(change.signs)}"
    if item is None:
        return REASON_OUTSIDE
    if guard.literal_pair_keys(item.pairs) != guard.value_pair_keys(change.pairs):
        return f"{REASON_MISMATCH}: фактически {_pairs_text(change.pairs)}"
    return ""


class _Decline(NamedTuple):
    """Убыль храповика: (методы, утверждения) базы и головы по файлам
    диффа и файлы с убылью — (путь в base, второй путь, имена методов,
    исчезнувших или потерявших утверждения)."""

    before: tuple
    after: tuple
    files: list

    @property
    def finding(self) -> Finding:
        paths = ", ".join(p for p, _alias, _names in self.files)
        return Finding(self.files[0][0], "",
                       f"храповик: число тестов и утверждений tests/ убыло — "
                       f"методы {self.before[0]} → {self.after[0]}, "
                       f"утверждения {self.before[1]} → {self.after[1]}; "
                       f"убыль в: {paths}", self.files[0][1])


def _counts(source) -> tuple:
    """(тестовые методы, утверждения по методам) одной стороны файла;
    неразбираемая или отсутствующая сторона — ноль."""
    methods = guard.qualified_test_methods(source)
    assertions = guard.test_assertions(source) or {}
    return methods, {name: len(found) for name, found in assertions.items()}


def _ratchet_decline(files: list) -> _Decline | None:
    """Храповик (требование 12): общее число тестовых методов и утверждений
    по файлам диффа `tests/` в голове не меньше, чем в базе. Неизменённые
    файлы вносят в обе стороны одно и то же и потому не читаются."""
    before, after, declining = [0, 0], [0, 0], []
    for base_path, head_path, base_source, head_source in files:
        base_methods, base_counts = _counts(base_source)
        head_methods, head_counts = _counts(head_source)
        b = (len(base_methods), sum(base_counts.values()))
        h = (len(head_methods), sum(head_counts.values()))
        before = [before[0] + b[0], before[1] + b[1]]
        after = [after[0] + h[0], after[1] + h[1]]
        if h[0] < b[0] or h[1] < b[1]:
            names = [n for n in base_methods if n not in head_methods] + \
                [n for n, count in base_counts.items()
                 if n in head_counts and head_counts[n] < count]
            path = base_path or head_path
            alias = head_path if head_path and head_path != path else ""
            declining.append((path, alias, names))
    if after[0] >= before[0] and after[1] >= before[1]:
        return None
    return _Decline(tuple(before), tuple(after), declining)


def _decline_source(decline: _Decline, mandate: dict):
    """ANSWER-n мандата, покрывающего убыль: каждый файл с убылью покрыт
    путём (любым путём пары переименования) либо элементами
    `путь::Класс`/`путь::Класс::метод`, покрывающими каждый его метод,
    который исчез или потерял утверждения; `None` — не покрыта."""
    sources = []
    for path, alias, names in decline.files:
        source = next((mandate[p] for p in (path, alias) if p in mandate), None)
        if source is None and names:
            found = [_covering_source(Finding(path, name, "", alias), mandate)
                     for name in names]
            source = found[0] if all(found) else None
        if source is None:
            return None
        sources.append(source)
    return ", ".join(dict.fromkeys(sources))


def ratchet_finding(base: dict, head: dict, mandate: dict):
    """Находка храповика (требование 12) на синтетических входах: `base`/
    `head` — {путь файла диффа `tests/`: текст либо `None`}, `mandate` —
    {элемент мандата: ANSWER-n}. `None` — убыли нет либо мандат её
    покрывает; иначе `Finding`, называющая числа «было → стало» методов и
    утверждений и файлы с убылью."""
    files = [(path, path, base.get(path), head.get(path))
             for path in sorted(set(base) | set(head))]
    decline = _ratchet_decline(files)
    if decline is None or _decline_source(decline, mandate):
        return None
    return decline.finding


def _proven_addresses(conn, task_id: str, head_sha: str) -> set:
    """Адреса методов (`путь::Класс::метод`) из записей «двусторонний
    прогон пройден» для головы `head_sha` (требование 11)."""
    proven: set = set()
    if not head_sha:
        return proven
    for row in store.task_steps(conn, task_id):
        if row["action"] != TWO_SIDED_PASSED_ACTION:
            continue
        match = _TWO_SIDED_RECORD.match(row["detail"] or "")
        if match and match.group(1) == head_sha:
            proven.update(a.strip() for a in match.group(3).split(", "))
    return proven


class _Evaluation(NamedTuple):
    """Итог узла для рубежа без записей журнала: `rest` — находки без
    мандата (`None` — git не ответил), `allowed` — строки покрытых
    мандатом находок, `outcomes` — {`путь::Класс::метод`: исход рубежа},
    `expectation` — методы исхода 7а без мандата (`MethodChange`),
    `declared` — объявленное approve, `mandate` и сам проход `cmp`."""

    rest: list | None
    allowed: list
    outcomes: dict
    expectation: list
    declared: dict
    mandate: dict
    cmp: Comparison


def _evaluate(conn, task_id: str, code_branch: str, artifact_branch: str,
              merge_route: bool = False) -> _Evaluation:
    """Сравнение, различение и сверка с объявленным (требования 4-7, 11-12)
    без записей журнала — общая часть обоих рубежей и ревью-пакета.

    `merge_route` — гейт мержа: метод исхода 7а проходит, только если для
    текущей головы ветки записан пройденный двусторонний прогон, иначе —
    находка (требование 11). Храповик добавляет находку, только когда
    иных непокрытых находок в проходе нет: иначе отказ уже стоит и
    адресно называет причину убыли."""
    repo = workspace.task_repo(task_id)
    cmp = _compare(code_branch, repo=repo)
    declared = declared_changes(conn, task_id) if conn is not None else {}
    if cmp.found is None:
        return _Evaluation(None, [], {}, [], declared, {}, cmp)
    mandate = _answer_mandate(artifact_branch, task_id) \
        if cmp.found or cmp.observed else {}

    # Находка об утверждениях метода по адресу — сам объект: по нему ниже
    # видно, ушла ли она в остаток или покрыта мандатом.
    reasons: dict = {}
    expectation: list = []
    findings_: list = list(cmp.found)

    def add(method: MethodChange, reason: str) -> None:
        finding = Finding(method.path, method.name,
                          f"{method.name}: {reason}", method.alias)
        reasons[method.address] = (reason, finding)
        findings_.append(finding)

    for method in cmp.changes:
        item = _declared_item(declared, method.path, method.alias, method.name)
        reason = _change_reason(method, item)
        if reason:
            add(method, reason)
        else:
            expectation.append((method, item))

    outcomes: dict = {}
    run: list = []
    proven = set()
    if merge_route and expectation:
        proven = _proven_addresses(
            conn, task_id, gitcmd.branch_head_sha(code_branch, repo=repo))
    for method, item in expectation:
        text = OUTCOME_EXPECTATION.format(n=item.requirement)
        source = _covering_source(Finding(method.path, method.name, "",
                                          method.alias), mandate)
        if source is not None:
            outcomes[method.address] = f"{text}; {ASSERTIONS_COVERED} {source}"
            continue
        run.append(method)
        outcomes[method.address] = text
        if merge_route:
            if method.head_address in proven:
                outcomes[method.address] = (f"{text}; {TWO_SIDED_FOR_HEAD}: "
                                            f"{two_sided.PASSED}")
            else:
                add(method, REASON_TWO_SIDED_MISSING)

    allowed: list = []
    rest: list = []
    for finding in findings_:
        source = _covering_source(finding, mandate)
        if source is None:
            rest.append(finding)
        else:
            allowed.append(f"{finding.line} — разрешено {source}")
    if not rest:
        decline = _ratchet_decline(cmp.files)
        if decline is not None:
            source = _decline_source(decline, mandate)
            if source is None:
                rest.append(decline.finding)
            else:
                allowed.append(f"{decline.finding.line} — разрешено {source}")

    for method in cmp.changes:
        if method.address not in reasons:
            continue
        reason, finding = reasons[method.address]
        prefix = outcomes.get(method.address)
        if any(f is finding for f in rest):
            text = f"{OUTCOME_FINDING}: {reason}"
        else:
            text = f"{ASSERTIONS_COVERED} {_covering_source(finding, mandate)}"
        outcomes[method.address] = f"{prefix}; {text}" if prefix else text
    changed = {m.address for m in cmp.changes} | \
        {f"{m.alias}{guard.TEST_NAME_SEP}{m.name}" for m in cmp.changes if m.alias}
    for address, item in declared.items():
        if address in changed:
            continue
        named = [f for f in cmp.found if f.name == item.name
                 and item.path in (f.path, f.alias)]
        if named:
            source = _covering_source(named[0], mandate)
            outcomes[address] = (f"{OUTCOME_FINDING}: {named[0].text}"
                                 if source is None
                                 else f"{ASSERTIONS_COVERED} {source}")
        else:
            outcomes[address] = OUTCOME_UNCHANGED
    return _Evaluation(rest, allowed, outcomes, run, declared, mandate, cmp)


def _journal_pass(conn, task_id: str, ev: _Evaluation) -> None:
    """Записи прохода, общие обоим рубежам: пропуски, прошедшие
    послабление, наблюдение утверждений в прежней форме, находки,
    разрешённые мандатом."""
    cmp = ev.cmp
    if cmp.found is None:
        _journal_observation(conn, task_id, [], [cmp.git_detail])
        return
    if cmp.passed:
        store.journal(conn, task_id, "fsm",
                      TEST_INTEGRITY_CONDITIONAL_SKIP_ACTION,
                      "; ".join(skip.line for skip in cmp.passed))
    _journal_observation(conn, task_id,
                         _observation_lines(cmp.observed, ev.mandate),
                         cmp.unobserved)
    if ev.allowed:
        store.journal(conn, task_id, "fsm", TEST_INTEGRITY_ALLOWED_ACTION,
                      "; ".join(ev.allowed))


def _journal_outcome(conn, task_id: str, outcomes: dict) -> None:
    """Запись «утверждения тестов: исход рубежа» (требование 8) — на
    каждом проходе, где есть изменённый или объявленный метод."""
    if outcomes:
        store.journal(conn, task_id, "fsm", OUTCOME_ACTION,
                      "; ".join(f"{address} — {text}"
                                for address, text in outcomes.items()))


def uncovered(conn, task_id: str, code_branch: str,
              artifact_branch: str) -> tuple:
    """(находки без мандата Оператора, текст сбоя git) — общий вход обоих
    гейтов.

    Покрытые мандатом находки в возврат не попадают, а уходят ОДНОЙ
    записью журнала «разрешено ANSWER-n» (требование 4, AC-8): Оператор
    видит и то, что рубеж их встретил, и чем именно они разрешены.

    Тем же приёмом и тут же — пропуски, прошедшие послабление требования 2
    SPEC 01M3HWXFYWVDHGW011P6BZJFYA: ОДНА запись журнала «новый тест с
    условным пропуском» (его требование 7), и наблюдение за изменёнными
    утверждениями в прежней форме (SPEC 01M3Y753QNG6TS5C7MTJS1MEV6).
    Молчание git — запись «наблюдение не выполнено» рядом с обычной
    реакцией рубежа на сбой.

    Изменённые утверждения — находки, кроме смены ожидания, объявленной в
    SPEC (SPEC 01M45FJD46BX45VHC36S4VS9QN, требование 7); храповик — тоже
    здесь. Двусторонний прогон и запись исхода рубежа — дело самих гейтов.
    """
    ev = _evaluate(conn, task_id, code_branch, artifact_branch)
    _journal_pass(conn, task_id, ev)
    return ev.rest, ev.cmp.git_detail


def review_lines(conn, task_id: str, code_branch: str,
                 artifact_branch: str) -> tuple:
    """(строки раздела «Изменённые утверждения тестов» ревью-пакета,
    причины невыполненного наблюдения, текст сбоя git) — требование 13.
    По каждому методу: прежняя строка наблюдения, исход рубежа, для
    объявленного — «было → стало (требование N)» из записи approve, для
    метода исхода 7а — итог двустороннего прогона для текущей головы.
    Ничего не журналирует."""
    ev = _evaluate(conn, task_id, code_branch, artifact_branch)
    cmp = ev.cmp
    if cmp.found is None:
        return [], [], cmp.git_detail
    proven: set = set()
    if ev.expectation:
        proven = _proven_addresses(conn, task_id, gitcmd.branch_head_sha(
            code_branch, repo=workspace.task_repo(task_id)))
    run = {m.address: m for m in ev.expectation}
    shown: set = set()
    lines = []
    for finding, line in zip(cmp.observed,
                             _observation_lines(cmp.observed, ev.mandate)):
        address = f"{finding.path}{guard.TEST_NAME_SEP}{finding.name}"
        shown.add(address)
        parts = [line]
        if address in ev.outcomes:
            parts.append(f"исход рубежа: {ev.outcomes[address]}")
        item = _declared_item(ev.declared, finding.path, finding.alias,
                              finding.name)
        if item is not None:
            parts.append(_declared_text(item))
        if address in run:
            result = two_sided.PASSED if run[address].head_address in proven \
                else TWO_SIDED_NOT_RECORDED
            parts.append(f"{TWO_SIDED_FOR_HEAD}: {result}")
        lines.append(" — ".join(parts))
    for address, outcome in ev.outcomes.items():
        if address in shown:
            continue
        parts = [f"{address}: исход рубежа: {outcome}"]
        item = ev.declared.get(address)
        if item is not None:
            parts.append(_declared_text(item))
        lines.append(" — ".join(parts))
    return lines, cmp.unobserved, ""


def refusal_detail(found: list) -> str:
    """Колонка detail отказа — перечень «файл: что именно» (требование 6)
    по находкам, мандатом НЕ покрытым."""
    return "; ".join(f.line for f in found)


def _mandate_hint(task_id: str) -> str:
    """Обе формы доставки мандата (SPEC 01M42NB9GKXNP74HAYEJ7C7CA8,
    требование 5): `answer` в `in_dev` уточняет мандат без шага роли,
    `answer` в `escalated` — прежний ответ на эскалацию."""
    return (f"либо верни тесты на место, либо получи мандат Оператора — "
           f"строка «{TEST_WEAKENING_MANDATE_MARKER} <пути и имена>» в "
           f"tasks/{task_id}/ANSWER-n.md (команда artel.py answer {task_id} "
           f"<файл>: в состоянии in_dev — без смены состояния, в состоянии "
           f"escalated — ответом на эскалацию; со ссылкой на основание), и "
           f"повтори artel.py advance {task_id}")


def _two_sided_methods(ev: _Evaluation) -> list:
    return [two_sided.Method(m.path, m.head_path, m.name, m.base_source,
                             m.head_source) for m in ev.expectation]


def _test_integrity_gate(conn, task_id: str, t,
                         artifact_branch: str) -> GateRefusal | None:
    """Гейт `in_dev -> verifying` (требование 6): удаление, переименование
    и ослабление тестов `tests/` без мандата Оператора переход не проходят;
    смена утверждений вне раздела SPEC «Меняемое поведение» и несовпадение
    с объявленным — тоже (SPEC 01M45FJD46BX45VHC36S4VS9QN, требование 7).

    Место в маршруте — сразу ПОСЛЕ гейта заявки мутации и до гейта
    отработки замечаний ревью: оба соседа читают ту же базу сравнения и
    тот же набор файлов `tests/` через git, а постановка ПЕРЕД гейтом
    заявки мутации переставила бы старшинство отказов на диффе,
    задевающем оба, и изменила бы журнал и stdout уже существующих
    сценариев (`tests/test_fsm_advance_gate_smoke.py` сверяет их
    байт-в-байт).

    Двусторонний прогон (требование 10) — здесь же, после сравнения и
    только если оно не дало непокрытых находок: прогон дорогой, дешёвые
    отказы идут первыми. Нет методов исхода 7а — ни git, ни pytest, ни
    записи.

    Канареечная задача и внешний target — гейт не проверяется, тем же
    условием и по тем же доводам, что у `_mutation_claim_gate` (AC-10):
    дифф в `config.ROOT` не видит код внешнего target, а канареечный
    `verifying` убивает задачу сразу по входу.

    Git не ответил — отказ, не пропуск (fail-closed, ADR-0002, AC-11):
    сломанный git не значит «ослабления нет», значит «сверить нечем».
    """
    if t["is_canary"] or t["target"] != config.DEFAULT_TARGET:
        return None
    ev = _evaluate(conn, task_id, t["branch"], artifact_branch)
    _journal_pass(conn, task_id, ev)
    if ev.rest is None:
        hint = (f"разберись, почему git не отвечает, и повтори "
               f"artel.py advance {task_id}")
        return GateRefusal(TEST_INTEGRITY_REFUSAL_ACTION, ev.cmp.git_detail,
                           hint)
    outcomes = dict(ev.outcomes)
    if ev.rest:
        for method in ev.expectation:
            outcomes[method.address] += ("; двусторонний прогон не "
                                         "выполнялся: есть непокрытые находки")
        _journal_outcome(conn, task_id, outcomes)
        return GateRefusal(TEST_INTEGRITY_REFUSAL_ACTION,
                           refusal_detail(ev.rest), _mandate_hint(task_id))
    if not ev.expectation:
        _journal_outcome(conn, task_id, outcomes)
        return None
    methods = _two_sided_methods(ev)
    result = two_sided.run(workspace.task_repo(task_id), t["branch"],
                           ev.cmp.base, methods)
    for method in methods:
        outcomes[f"{method.base_path}{guard.TEST_NAME_SEP}{method.name}"] += (
            f"; двусторонний прогон: {result.results.get(method.address, '')}")
    _journal_outcome(conn, task_id, outcomes)
    if result.refusals:
        return GateRefusal(TEST_INTEGRITY_REFUSAL_ACTION,
                           "; ".join(result.refusals), _mandate_hint(task_id))
    store.journal(conn, task_id, "fsm", TWO_SIDED_PASSED_ACTION,
                  f"голова {result.head_sha}; база {result.base_sha}; методы: "
                  f"{', '.join(m.address for m in methods)}")
    return None


def _test_integrity_gate_refuses(conn, task_id: str, t,
                                 artifact_branch: str) -> bool:
    """Публичная обёртка гейта — та же форма, что у соседей по `in_dev`
    (`_review_rework_gate_refuses`): `artifact_branch` — ветка-источник
    `tasks/<id>/` (мандат Оператора), `t["branch"]` — кодовая ветка
    (дифф)."""
    return _run_gates(conn, task_id,
                      [lambda: _test_integrity_gate(conn, task_id, t,
                                                    artifact_branch)])


def merge_gate_escalates(conn, task_id: str, state: str, code_branch: str,
                         artifact_branch: str) -> bool:
    """Тот же узел на гейте мержа (требование 7): находка без мандата —
    эскалация с тем же текстом отказа, что на переходе. Двусторонний
    прогон здесь не повторяется: метод исхода 7а проходит только с
    записью «двусторонний прогон пройден» для текущей головы ветки (SPEC
    01M45FJD46BX45VHC36S4VS9QN, требование 11).

    `True` — эскалировано (`store.set_state` уже отжурналировал детали),
    вызывающий код обязан остановиться. Молчание git — `False`, fail-open,
    ровно как у соседнего `_protected_path_diff_gate`: состояние к этому
    моменту ещё не тронуто, сломанный git тем же вызовом упрётся в отказ
    ниже по маршруту мержа, а тот же дифф уже проходил fail-closed рубеж
    на `in_dev -> verifying` — второй fail-closed на том же сбое защиты не
    добавляет (AC-12).
    """
    ev = _evaluate(conn, task_id, code_branch, artifact_branch,
                   merge_route=True)
    _journal_pass(conn, task_id, ev)
    if ev.rest is None:
        return False
    _journal_outcome(conn, task_id, ev.outcomes)
    if not ev.rest:
        return False
    store.set_state(conn, task_id, "escalated", "fsm", expected_state=state,
                    detail=refusal_detail(ev.rest))
    return True
