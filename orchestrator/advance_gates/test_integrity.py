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
"""
from typing import NamedTuple

from scripts import guard

from .. import config, gitcmd, store
from ._base import GateRefusal, _run_gates
# Маркер мандата ослабления и разбор его строки живут в `mandate` — общем
# узле разбора строки мандата (SPEC 01M3GKJBXEBHB6ZA48J7VG8Z8W, требование
# 1); импорт сюда сохраняет прежнее имя `test_integrity.
# TEST_WEAKENING_MANDATE_MARKER` рабочим для `fsm_advance` и тестов.
from .mandate import TEST_WEAKENING_MANDATE_MARKER, elements
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


def _in_scope(path) -> bool:
    """Путь принадлежит области узла — `tests/**/*.py` на ЛЮБОЙ глубине
    (требование 2), не только верхний уровень, как у гейта заявки мутации.

    Полный набор гоняется как `pytest tests` (`acceptance.run_full_suite`),
    то есть собирает подкаталоги наравне с верхним уровнем: тест,
    заведённый в `tests/<подкаталог>/test_x.py`, при верхнеуровневом
    фильтре можно было бы удалить вне поля зрения рубежа. Файлы планок
    `tasks/*/acceptance_tests` под `tests/` не лежат и в область не входят
    — их держит лок планки (AC-5).
    """
    return bool(path) and path.startswith("tests/") and path.endswith(".py")


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


def _file_findings(base_path, head_path, renamed_to, base_source,
                   head_source) -> list:
    """Находки одного файла: удаление/переименование (только если в base
    есть хоть один тестовый метод — требование 5: защиты в пустом файле
    нет, удалять нечего), исчезнувшие методы и ПОЯВИВШИЕСЯ маркеры
    пропуска.

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
        return found

    head_methods = guard.qualified_test_methods(head_source)
    for name in base_methods:
        if name not in head_methods:
            found.append(Finding(path, name, f"метод {name} исчез", alias))

    base_markers = guard.test_skip_markers(base_source)
    for name, markers in guard.test_skip_markers(head_source).items():
        for marker in sorted(markers - base_markers.get(name, set())):
            found.append(Finding(path, name, f"{marker} на {name}", alias))
    return found


def findings(code_branch: str) -> tuple:
    """(находки ветки против базы сравнения, текст сбоя git).

    База — `gitcmd.diff_base` (merge-base с origin/main), та же, что у
    гейта заявки мутации и у `_protected_path_diff_gate`. Git не ответил
    на базу, на список файлов диффа или на чтение содержимого пути,
    который по ответу самого git существует в своём дереве, — находки НЕ
    собраны: `(None, detail)`. Как на это реагировать, решает вызывающий
    гейт (fail-closed на переходе, fail-open на мерже), а не этот узел.
    """
    base = gitcmd.diff_base(code_branch)
    if base is None:
        return None, _git_silence(
            f"определение базы сравнения (merge-base с origin/"
            f"{config.MAIN_BRANCH} либо локальным {config.MAIN_BRANCH}) "
            f"для ветки {code_branch}")
    entries = gitcmd.diff_name_status(base, code_branch)
    if entries is None:
        return None, _git_silence(
            f"список файлов диффа (база {base}...{code_branch})")

    found: list = []
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
                return None, _git_silence(f"чтение {path} из {ref} ({reason})")
            sources[side] = text
        found += _file_findings(base_path, head_path, renamed_to,
                                sources["base"], sources["head"])
    return found, ""


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
    """
    found, git_detail = findings(code_branch)
    if found is None:
        return None, git_detail
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
