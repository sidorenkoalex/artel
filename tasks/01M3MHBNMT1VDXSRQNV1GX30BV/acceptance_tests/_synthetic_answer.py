"""Общие помощники планки 01M3MHBNMT1VDXSRQNV1GX30BV (синтетический
ответ канарейки на эскалацию): наблюдение текста ответа, разбор констант
модуля `orchestrator/canary.py`, сверка с базой диффа задачи, прогон уже
существующих тестов пульта.

Модуль-надстройка сценария, не копия песочницы переходов: лёгкую
песочницу FSM здесь не нужна вовсе (предмет критериев — текст, который
`canary._pass_escalated_with_synthetic_answer` отдаёт каналу ANSWER, и
константы модуля), а окружение БД берётся импортом
`tests.sandbox.SchemaConnTmpRootTest` прямо в файлах тестов.

Текст ответа наблюдается ПОДМЕНОЙ `answer.cmd_answer` (`answer_text`
ниже): настоящий канал записи ANSWER-n.md требует lease пульта,
артефактной ветки и origin-заглушки, а критерии AC-1/AC-2/AC-4/AC-5
говорят о тексте, который канарейка в этот канал отдаёт. Обёртку
документа (frontmatter `task: <id>`, заголовки `# ANSWER-n`/`## Ответы`)
добавляет сам `orchestrator/answer.py::_answer_document` — она вне
объёма задачи («Не входит»: `answer.py` только читается), и номер задачи
в ней законен, поэтому критерии применяются к тексту канарейки, а не к
готовому документу.
"""
import ast
import inspect
import io
import re
import subprocess
import sys
import tokenize
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import canary, gitcmd, idgen, store  # noqa: E402

TASK = "01M3MHBNMT1VDXSRQNV1GX30BV"

# Состояния, из которых канарейка возвращает задачу синтетическим ответом
# (AC-5) — перечислены самим критерием.
ESCALATED_FROM_STATES = ("spec_writing", "tests_writing", "in_dev", "review")

# Раздел docs/stack.md, названный AC-9.
STACK_CANARY_SET_HEADING = ("### Набор ролей канарейки: `canary_sets:` и "
                            "`canary --set`")

# Алфавит Crockford base32 — внешняя константа спецификации ULID, на
# которой стоит генератор `orchestrator/idgen.py` (не крутилка пульта).
# Длина берётся от САМОГО генератора: формат идентификатора знает только
# он, и планка не должна нести своё число символов (scripts/guard.py,
# образец формата id).
CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
ID_LENGTH = len(idgen.new_task_id())

# Идентификатор задачи пульта в произвольном тексте: ровно ID_LENGTH
# символов алфавита генератора, не продолжающиеся таким же символом ни
# влево, ни вправо (иначе более длинная «простыня» заглавных букв
# считалась бы идентификатором).
ID_IN_TEXT = re.compile(
    "(?<![{a}])[{a}]{{{n}}}(?![{a}])".format(a=CROCKFORD_ALPHABET,
                                             n=ID_LENGTH))

# Заголовок вида `## <название>`, названный внутри произвольного текста:
# `###` и глубже — не он, название обрывается на конце строки, обратной
# кавычке или кавычке-ёлочке.
_HEADING_IN_TEXT = re.compile(r"(?<!#)##(?!#)[ \t]*([^\n`»\"']+)")


def answer_text(conn, task_id: str, escalated_from: str = "in_dev") -> str:
    """Текст, который `canary._pass_escalated_with_synthetic_answer`
    отдаёт `answer.cmd_answer` — ровно содержимое будущего ANSWER-n.md
    (`answer._cmd_answer` читает файл и кладёт его текст в документ).

    Задача приводится в `escalated` с заданным `escalated_from`, ответ
    перехватывается подменой канала, состояние после вызова возвращается
    в `escalated` — помощник переиспользуем в одном тесте несколько раз
    (AC-5 сверяет четыре состояния подряд).
    """
    captured: list[str] = []

    def spy(_task_id, file_path, *args, **kwargs):
        captured.append(Path(file_path).read_text(encoding="utf-8"))

    state = store.get_task(conn, task_id)["state"]
    if state != "escalated":
        store.set_state(conn, task_id, "escalated", "acceptance",
                        expected_state=state)
    store.update_task(conn, task_id, escalated_from=escalated_from)
    with mock.patch.object(canary.answer, "cmd_answer", side_effect=spy):
        canary._pass_escalated_with_synthetic_answer(conn, task_id)
    after = store.get_task(conn, task_id)["state"]
    if after != "escalated":
        store.set_state(conn, task_id, "escalated", "acceptance",
                        expected_state=after)
    if len(captured) != 1:
        raise AssertionError(
            "_pass_escalated_with_synthetic_answer не отдал ровно один файл "
            f"ответа в answer.cmd_answer (перехвачено: {len(captured)})")
    return captured[0]


def module_str_constants() -> dict:
    """Строковые константы модульного уровня `orchestrator/canary.py`
    (имя в верхнем регистре, в том числе с ведущим подчёркиванием —
    принятая в модуле форма `_CEILING_EXHAUSTED_REASON`)."""
    return {name: value for name, value in vars(canary).items()
            if name.isupper() and isinstance(value, str) and value.strip()}


def constants_equal_to(text: str) -> list:
    """Имена констант модуля, чьё значение совпадает с `text` (с точностью
    до обрамляющих пробелов и перевода строки файла ответа)."""
    return sorted(name for name, value in module_str_constants().items()
                  if value.strip() == text.strip())


def anchor_constants(text: str) -> dict:
    """Константы-якоря: значение входит в `text` дословно, не равно ему
    целиком и является ФРАЗОЙ (несёт пробел) — метка-слово вроде
    `CANARY_MARK_ACTOR` якорем утверждения не является."""
    return {name: value for name, value in module_str_constants().items()
            if value.strip() != text.strip() and " " in value and value in text}


def atomic_anchors(anchors: dict) -> dict:
    """Якоря-утверждения без обёрток: константа, внутри значения которой
    лежит значение другого якоря (текст целиком, журнальная приписка
    вокруг якоря), отдельным утверждением не считается и в счёт четырёх
    не идёт — иначе «четыре якоря» выродились бы в одну фразу и её
    обрамления."""
    return {name: value for name, value in anchors.items()
            if not any(other != value and other in value
                       for other in anchors.values())}


def docs_and_comments(func) -> str:
    """Докстринг + комментарии тела функции, БЕЗ строковых литералов: сам
    текст ответа — литерал (или ссылка на константу), и AC-6 требует
    различать «номер в докстринге» от «номер в тексте, который читает
    роль»."""
    parts = [inspect.getdoc(func) or ""]
    try:
        source = inspect.getsource(func)
    except OSError:  # pragma: no cover — исходник функции всегда на диске
        return parts[0]
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                parts.append(tok.string)
    except (tokenize.TokenError, IndentationError):
        pass
    return "\n".join(parts)


def base_source(rel: str) -> str:
    """Текст файла `rel` в ТОЧКЕ РАСХОЖДЕНИЯ ветки задачи с основной
    веткой — одной точкой правды пульта (`gitcmd.diff_base`), не своим
    `git merge-base`: локальная основная ветка равна пину пульта и
    отстаёт от origin на все смерженные с тех пор задачи."""
    base = gitcmd.diff_base("HEAD")
    if not base:
        raise AssertionError("git не ответил на gitcmd.diff_base('HEAD') — "
                             "база сравнения ветки задачи неизвестна")
    text, reason = gitcmd.show(base, rel)
    if text is None:
        raise AssertionError(f"{rel} не читается из базы {base}: {reason}")
    return text


def base_config_value(name: str):
    """Значение константы `orchestrator/config.py` в базе диффа задачи —
    предпосылка «крутилку Оператора задача не двигала» сверяется с базой,
    а не с зашитым в планку сегодняшним числом (урок 28.08: литерал
    потолка в фикстуре покраснел, когда Оператор его поднял)."""
    tree = ast.parse(base_source("orchestrator/config.py"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == name:
                return ast.literal_eval(node.value)
    raise AssertionError(f"в базе диффа нет присваивания config.{name}")


def _normalized(segment: str) -> str:
    return " ".join((segment or "").split())


def assert_statements(source: str, class_name: str = None) -> set:
    """Нормализованные тексты ассертов (`assert`, любой вызов
    `assert*`/`fail`) файла целиком либо одного класса — «ожидания»
    теста в смысле AC-7/AC-8, без докстрингов и служебного обвеса."""
    tree = ast.parse(source)
    scope = tree
    if class_name is not None:
        found = [node for node in ast.walk(tree)
                 if isinstance(node, ast.ClassDef) and node.name == class_name]
        if not found:
            raise AssertionError(f"класса {class_name} нет в разбираемом файле")
        scope = found[0]
    out = set()
    for node in ast.walk(scope):
        if isinstance(node, ast.Assert):
            out.add(_normalized(ast.get_source_segment(source, node)))
        elif isinstance(node, ast.Call):
            name = getattr(node.func, "attr", None) or getattr(node.func, "id", "")
            if name.startswith("assert") or name == "fail":
                out.add(_normalized(ast.get_source_segment(source, node)))
    return out


def run_pytest(*targets: str, timeout: int = 90) -> tuple:
    """(код возврата, хвост вывода) прогона уже существующих тестов пульта
    тем же интерпретатором, которым идёт планка, из корня рабочего
    каталога кода: критерии AC-7/AC-8/AC-9 требуют именно их зелени.
    Пути относительные — сторож роли `conftest.py` принимает только
    адресные цели ниже `tests/`."""
    cmd = [sys.executable, "-m", "pytest", *targets,
           "-p", "no:cacheprovider", "-q"]
    res = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True,
                         timeout=timeout)
    return res.returncode, (res.stdout + res.stderr)[-2000:]


def stack_section(heading: str) -> str:
    """Тело раздела `docs/stack.md` под заголовком `heading` — до
    следующего заголовка того же или более высокого уровня."""
    text = (REPO_ROOT / "docs" / "stack.md").read_text(encoding="utf-8")
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip() == heading:
            start = index + 1
            break
    if start is None:
        raise AssertionError(f"в docs/stack.md нет раздела {heading!r}")
    body = []
    for line in lines[start:]:
        if line.startswith("## ") or line.startswith("### "):
            break
        body.append(line)
    return "\n".join(body)


def template_headings() -> set:
    """Названия разделов `## <название>` всех шаблонов `templates/*.md`."""
    out = set()
    for path in sorted((REPO_ROOT / "templates").glob("*.md")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("## ") and not line.startswith("### "):
                out.add(line[3:].strip())
    return out


def headings_named_in(text: str) -> list:
    """Названия разделов вида `## <название>`, названные внутри `text`."""
    names = []
    for raw in _HEADING_IN_TEXT.findall(text):
        name = raw.strip().strip("`»«\"'.,;:!?()")
        if name:
            names.append(name)
    return names


def heading_exists(name: str, headings: set) -> bool:
    """Название `name` из текста существует заголовком шаблона: само либо
    своим начальным словом/словами. Текст называет раздел живой фразой
    («## Риски своего артефакта»), а требование критерия — чтобы
    НАЗВАННЫЙ раздел существовал, поэтому сверяются начальные словосочета-
    ния, а не одна только полная фраза."""
    words = name.split()
    return any(" ".join(words[:count]) in headings
               for count in range(len(words), 0, -1))
