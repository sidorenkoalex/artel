"""Узел сравнения `tests/` ветки задачи с базой и два гейта на нём — гейт
неослабления тестов (SPEC 01M3FQ2V77QNK95Z599DM124QN).

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
"""
import ast
from typing import NamedTuple

from scripts import guard

from .. import config, gitcmd, store
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
        покрывает все его находки, элемент с `::` — только названный
        метод или класс (требование 4).

        У пары переименования засчитываются ОБА пути — старый (`path`) и
        новый (`alias`). Оператор пишет мандат, глядя на ветку и на PR,
        где файл уже лежит под новым именем, и признание одного лишь
        пути из базы сравнения стоило бы ему лишнего круга `advance` на
        безупречно выписанном разрешении (REVIEW итерация 1, R1-F2).
        """
        paths = (self.path, self.alias) if self.alias else (self.path,)
        if not self.name:
            return paths
        return paths + tuple(f"{p}{guard.TEST_NAME_SEP}{self.name}"
                             for p in paths)


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


def findings(code_branch: str) -> tuple:
    """(находки ветки против базы сравнения, прошедшие послабление
    пропуски, текст сбоя git).

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
    """
    base = gitcmd.diff_base(code_branch)
    if base is None:
        return None, [], _git_silence(
            f"определение базы сравнения (merge-base с origin/"
            f"{config.MAIN_BRANCH} либо локальным {config.MAIN_BRANCH}) "
            f"для ветки {code_branch}")
    entries = gitcmd.diff_name_status(base, code_branch)
    if entries is None:
        return None, [], _git_silence(
            f"список файлов диффа (база {base}...{code_branch})")

    found: list = []
    passed: list = []
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
            text, reason = gitcmd.show(ref, path)
            if text is None:
                # Путь существует в СВОЁМ дереве по построению: его назвал
                # сам `git diff --name-status` этой стороной записи —
                # значит `None` здесь всегда сбой чтения, не легитимное
                # отсутствие (различать их по тексту причины, как это
                # вынужден делать гейт заявки мутации, тут не нужно).
                return None, [], _git_silence(
                    f"чтение {path} из {ref} ({reason})")
            sources[side] = text
        file_found, file_passed = _file_findings(
            base_path, head_path, renamed_to, sources["base"], sources["head"])
        found += file_found
        passed += file_passed
    return found, passed, ""


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
    paths = gitcmd.ls_tree_files(artifact_branch, f"tasks/{task_id}") or []
    mandate: dict = {}
    for p in sorted(paths):
        name = p.rsplit("/", 1)[-1]
        if not (name.startswith("ANSWER-") and name.endswith(".md")):
            continue
        if _answer_commit_is_role_step_autocommit(artifact_branch, task_id, p):
            continue
        text, _reason = gitcmd.show(artifact_branch, p)
        if text is None:
            continue
        for line in text.splitlines():
            allowed = elements(line, TEST_WEAKENING_MANDATE_MARKER)
            for element in allowed or ():
                mandate.setdefault(element, name[:-len(".md")])
    return mandate


def uncovered(conn, task_id: str, code_branch: str,
              artifact_branch: str) -> tuple:
    """(находки без мандата Оператора, текст сбоя git) — общий вход обоих
    гейтов.

    Покрытые мандатом находки в возврат не попадают, а уходят ОДНОЙ
    записью журнала «разрешено ANSWER-n» (требование 4, AC-8): Оператор
    видит и то, что рубеж их встретил, и чем именно они разрешены.

    Тем же приёмом и тут же — пропуски, прошедшие послабление требования 2
    SPEC 01M3HWXFYWVDHGW011P6BZJFYA: ОДНА запись журнала «новый тест с
    условным пропуском» (его требование 7). Место записи — этот общий
    вход, а не обёртки: он единственный у узла, кому доступны `conn` и
    `task_id`, и зовут его оба рубежа, так что запись появляется на
    каждом.
    """
    found, passed, git_detail = findings(code_branch)
    if found is None:
        return None, git_detail
    if passed:
        store.journal(conn, task_id, "fsm",
                      TEST_INTEGRITY_CONDITIONAL_SKIP_ACTION,
                      "; ".join(skip.line for skip in passed))
    if not found:
        return [], ""

    mandate = _answer_mandate(artifact_branch, task_id)
    if not mandate:
        return found, ""

    allowed: list = []
    rest: list = []
    for finding in found:
        source = next((mandate[e] for e in finding.mandate_elements
                       if e in mandate), None)
        if source is None:
            rest.append(finding)
        else:
            allowed.append(f"{finding.line} — разрешено {source}")
    if allowed:
        store.journal(conn, task_id, "fsm", TEST_INTEGRITY_ALLOWED_ACTION,
                      "; ".join(allowed))
    return rest, ""


def refusal_detail(found: list) -> str:
    """Колонка detail отказа — перечень «файл: что именно» (требование 6)
    по находкам, мандатом НЕ покрытым."""
    return "; ".join(f.line for f in found)


def _mandate_hint(task_id: str) -> str:
    return (f"либо верни тесты на место, либо получи мандат Оператора — "
           f"строка «{TEST_WEAKENING_MANDATE_MARKER} <пути и имена>» в "
           f"tasks/{task_id}/ANSWER-n.md (команда answer, со ссылкой на "
           f"основание), и повтори artel.py advance {task_id}")


def _test_integrity_gate(conn, task_id: str, t,
                         artifact_branch: str) -> GateRefusal | None:
    """Гейт `in_dev -> verifying` (требование 6): удаление, переименование
    и ослабление тестов `tests/` без мандата Оператора переход не проходят.

    Место в маршруте — сразу ПОСЛЕ гейта заявки мутации и до гейта
    отработки замечаний ревью: оба соседа читают ту же базу сравнения и
    тот же набор файлов `tests/` через git, а постановка ПЕРЕД гейтом
    заявки мутации переставила бы старшинство отказов на диффе,
    задевающем оба, и изменила бы журнал и stdout уже существующих
    сценариев (`tests/test_fsm_advance_gate_smoke.py` сверяет их
    байт-в-байт).

    Канареечная задача и внешний target — гейт не проверяется, тем же
    условием и по тем же доводам, что у `_mutation_claim_gate` (AC-10):
    дифф в `config.ROOT` не видит код внешнего target, а канареечный
    `verifying` убивает задачу сразу по входу.

    Git не ответил — отказ, не пропуск (fail-closed, ADR-0002, AC-11):
    сломанный git не значит «ослабления нет», значит «сверить нечем».
    """
    if t["is_canary"] or t["target"] != config.DEFAULT_TARGET:
        return None
    found, git_detail = uncovered(conn, task_id, t["branch"], artifact_branch)
    if found is None:
        hint = (f"разберись, почему git не отвечает, и повтори "
               f"artel.py advance {task_id}")
        return GateRefusal(TEST_INTEGRITY_REFUSAL_ACTION, git_detail, hint)
    if not found:
        return None
    return GateRefusal(TEST_INTEGRITY_REFUSAL_ACTION, refusal_detail(found),
                       _mandate_hint(task_id))


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
    эскалация с тем же текстом отказа, что на переходе.

    `True` — эскалировано (`store.set_state` уже отжурналировал детали),
    вызывающий код обязан остановиться. Молчание git — `False`, fail-open,
    ровно как у соседнего `_protected_path_diff_gate`: состояние к этому
    моменту ещё не тронуто, сломанный git тем же вызовом упрётся в отказ
    ниже по маршруту мержа, а тот же дифф уже проходил fail-closed рубеж
    на `in_dev -> verifying` — второй fail-closed на том же сбое защиты не
    добавляет (AC-12).
    """
    found, _git_detail = uncovered(conn, task_id, code_branch,
                                   artifact_branch)
    if not found:
        return False
    store.set_state(conn, task_id, "escalated", "fsm", expected_state=state,
                    detail=refusal_detail(found))
    return True
