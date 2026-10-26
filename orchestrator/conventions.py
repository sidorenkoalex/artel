"""Конвенции внешнего проекта из файла пульта: чтение, заголовок отметки
разбора, команда `conventions-stamp`, сверка дрейфа (SPEC
01M5T18K1YFBYA7MM1BBRV869A).

ИИ-настройки проекта (`CLAUDE.md`, `AGENTS.md` и прочая обвязка) ролям не
передаются: их разбирает сессия при Операторе в файл
`.artel/projects/<имя>/conventions.md` локального слоя пульта
(`docs/target-onboarding.md`). Бриф берёт текст оттуда, а заголовок
отметки в начале файла помнит, с какого коммита базы и с каких blob
исходных файлов сделан разбор — по нему `doctor` видит дрейф.

Ни чтение, ни сверка, ни отметка не ходят в сеть: база — локальная ссылка
`refs/heads/<base>` клона как есть (`reference_cache.branch_commit`), не
`HEAD` и не рабочее дерево клона.
"""
import os
import posixpath
import re
import stat
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import config, gitcmd, reference_cache, repo_context, yamlmini

FILE_NAME = "conventions.md"
STAMP_KEY = "conventions_stamp"
STAMP_VERSION = 1
ONBOARDING_DOC = "docs/target-onboarding.md"
STAMP_COMMAND = "python3 orchestrator/artel.py conventions-stamp"

# Причины «не разобраны» (требование 4) — различают случаи, не сводя сбой
# чтения к «файла нет».
NOT_FOUND = "файла нет"
NOT_REGULAR = "не обычный файл"
NOT_UTF8 = "текст не в UTF-8"
BROKEN = "заголовок отметки не читается"
NO_STAMP = "нет отметки разбора"
DRIFT = "конвенции проекта изменились с последнего разбора"

# Три вида файла (требование 6).
PLAIN = "plain"
BROKEN_KIND = "broken"
STAMPED = "stamped"

_HEX40 = re.compile(r"[0-9a-f]{40}")
_FENCE = "---"
_REGULAR_FILE_MODES = ("100644", "100755")
_TREE_KINDS = {"040000": "каталог", "120000": "символьная ссылка",
               "160000": "подмодуль"}


@dataclass(frozen=True)
class Parsed:
    """Разбор текста `conventions.md`: вид, поля заголовка (у `STAMPED`) и
    текст, который идёт в бриф (у `PLAIN` — весь файл)."""
    kind: str
    fields: dict | None
    body: str


def path(target: str) -> Path:
    """Файл конвенций проекта в его области — через `projects_root` с его
    охраной подменённого корня пульта (решение гейта 1)."""
    return repo_context.projects_root() / target / FILE_NAME


def rel(target: str) -> str:
    """Относительный путь файла для подписи и пометок (решение гейта 11)."""
    return f".artel/projects/{target}/{FILE_NAME}"


def _os_reason(exc: OSError) -> str:
    return " ".join((exc.strerror or str(exc) or type(exc).__name__).split())


def read_file(target: str) -> tuple[str | None, str]:
    """(текст, "") `conventions.md` проекта; (None, причина) — файла нет,
    это не обычный файл (символьная ссылка тоже: её цель вне области
    проекта), текст не в UTF-8 или ошибка ОС (требование 4).

    `lstat` до открытия, `O_NOFOLLOW` и `fstat` после: ссылка, подставленная
    между проверкой и чтением, тоже отказывает, а не читается по цели."""
    own = path(target)
    try:
        info = os.lstat(own)
    except FileNotFoundError:
        return None, NOT_FOUND
    except OSError as exc:
        return None, _os_reason(exc)
    if not stat.S_ISREG(info.st_mode):
        return None, NOT_REGULAR
    try:
        fd = os.open(own, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        return None, NOT_FOUND
    except OSError as exc:
        if os.path.islink(own):
            return None, NOT_REGULAR
        return None, _os_reason(exc)
    try:
        with os.fdopen(fd, "rb") as fh:
            if not stat.S_ISREG(os.fstat(fh.fileno()).st_mode):
                return None, NOT_REGULAR
            data = fh.read()
    except OSError as exc:
        return None, _os_reason(exc)
    try:
        return data.decode("utf-8"), ""
    except UnicodeDecodeError:
        return None, NOT_UTF8


def _valid_stamp(fields: dict) -> bool:
    branch = fields.get("base_branch")
    sha = fields.get("base_sha")
    sources = fields.get("sources")
    if not isinstance(branch, str) or not branch.strip():
        return False
    if not isinstance(sha, str) or not _HEX40.fullmatch(sha):
        return False
    if not isinstance(sources, dict) or not sources:
        return False
    return all(isinstance(name, str) and name and isinstance(blob, str)
               and _HEX40.fullmatch(blob) for name, blob in sources.items())


def parse(text: str) -> Parsed:
    """Вид файла по требованию 6. Заголовок — блок от первой строки `---`
    до следующей строки `---` включительно; тело блока разбирает
    `yamlmini.mapping` (вложенное `sources` плоский `frontmatter` не
    разбирает)."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != _FENCE:
        return Parsed(PLAIN, None, text)
    end = next((i for i in range(1, len(lines))
                if lines[i].rstrip("\r\n") == _FENCE), None)
    if end is None:
        return Parsed(BROKEN_KIND, None, "")
    try:
        fields = yamlmini.mapping("".join(lines[1:end]))
    except yamlmini.YamlError:
        return Parsed(BROKEN_KIND, None, "")
    if not isinstance(fields, dict) or STAMP_KEY not in fields:
        return Parsed(PLAIN, None, text)
    if not _valid_stamp(fields):
        return Parsed(BROKEN_KIND, None, "")
    return Parsed(STAMPED, fields, "".join(lines[end + 1:]))


def brief_text(target: str) -> tuple[str | None, str]:
    """(текст для брифа, "") — без заголовка отметки (требование 2);
    (None, причина) — файл не читается или заголовок сломан (требование
    4)."""
    text, reason = read_file(target)
    if text is None:
        return None, reason
    parsed = parse(text)
    if parsed.kind == BROKEN_KIND:
        return None, BROKEN
    return parsed.body, ""


def render_header(base: str, sha: str, sources: dict) -> str:
    """Заголовок отметки требования 6: sha и blob — в двойных кавычках,
    чтобы строка из одних цифр не разобралась числом."""
    lines = [_FENCE, f"{STAMP_KEY}: {STAMP_VERSION}", f"base_branch: {base}",
             f'base_sha: "{sha}"', "sources:"]
    lines += [f'  {name}: "{blob}"' for name, blob in sources.items()]
    lines.append(_FENCE)
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------- git клона

def _git(clone: Path, *args: str) -> tuple[bytes | None, str]:
    """(stdout, "") git-команды в клоне; (None, причина) — git не ответил
    или отказал. Только локальные команды: сетевых вызовов модуль не
    делает (решение гейта 4)."""
    try:
        res = gitcmd.read(clone, *args,
                          timeout=config.CORE_REFERENCE_GIT_TIMEOUT_SEC)
    except gitcmd.Timeout:
        return None, "git не ответил (TimeoutExpired)"
    except OSError as exc:
        return None, f"git не ответил ({type(exc).__name__})"
    if res.returncode != 0:
        err = " ".join(res.stderr.decode("utf-8", "replace").split())
        return None, f"git {args[0]}: {err or f'код возврата {res.returncode}'}"
    return res.stdout, ""


def clone_refusal(clone: Path) -> str:
    """Причина, по которой клон не читается; "" — читается. Каталог внутри
    чужого репозитория (песочница, область проектов) клоном не считается:
    верх его рабочего дерева — не он сам."""
    if not clone.is_dir():
        return f"клона проекта нет: {clone}"
    out, _reason = _git(clone, "rev-parse", "--show-toplevel")
    top = out.decode("utf-8", "replace").strip() if out is not None else ""
    if not top or Path(top).resolve() != clone.resolve():
        return f"клон проекта — не репозиторий git: {clone}"
    return ""


def base_commit(ctx) -> tuple[str | None, str]:
    """(sha `refs/heads/<base>` клона, "") без обращения к сети; (None,
    причина) — клон или базовая ветка не читается."""
    refusal = clone_refusal(ctx.path)
    if refusal:
        return None, refusal
    sha, reason = reference_cache.branch_commit(ctx.path, ctx.base)
    if sha is None:
        return None, f"базовая ветка {ctx.base} не читается: {reason}"
    return sha, ""


def tree_objects(clone: Path, sha: str,
                 paths: list) -> tuple[dict | None, str]:
    """({путь: (режим, id объекта)}, "") — записи дерева коммита `sha` для
    `paths` (пути, которых в дереве нет, в ответе отсутствуют); (None,
    причина) — git не ответил."""
    out, reason = _git(clone, "--literal-pathspecs", "ls-tree", "-z", sha,
                       "--", *paths)
    if out is None:
        return None, reason
    found = {}
    for record in out.split(b"\0"):
        meta, _, name = record.partition(b"\t")
        fields = meta.decode("ascii", "replace").split()
        if len(fields) >= 3 and name:
            found[name.decode("utf-8", "replace")] = (fields[0], fields[2])
    return found, ""


def _source_refusal(name: str, entry) -> str:
    if entry is None:
        return f"{name}: нет в дереве коммита базы"
    mode, _oid = entry
    if mode in _TREE_KINDS:
        return f"{name}: в дереве коммита базы — {_TREE_KINDS[mode]}"
    if mode not in _REGULAR_FILE_MODES:
        return f"{name}: в дереве коммита базы — {NOT_REGULAR}"
    return ""


# --------------------------------------------------------- conventions-stamp

STAMP_USAGE = "conventions-stamp <проект> <файл>…"


def _normalized_source(name: str) -> str | None:
    rel_path = posixpath.normpath(name)
    if (not name or rel_path in (".", "") or rel_path.startswith("/")
            or rel_path == ".." or rel_path.startswith("../")):
        return None
    return rel_path


def stamp_refusal(project: str, files: list) -> tuple[str, str, Path | None]:
    """("", новый текст файла, путь) — отметка готова к записи; (причина,
    "", None) — отказ требования 7, файл не трогается."""
    if not project:
        return f"использование: {STAMP_USAGE}", "", None
    if repo_context.is_artel(project):
        return (f"проект {project} — артель: конвенции артели живут в её "
                f"репозитории, отметка не ставится"), "", None
    ctx = repo_context.resolve(project)
    if ctx is None:
        return repo_context.unresolved_reason(project), "", None
    sha, reason = base_commit(ctx)
    if sha is None:
        return reason, "", None
    if not files:
        return (f"файлы не названы: {STAMP_USAGE} — пути исходных файлов "
                f"проекта, с которых сделан разбор"), "", None
    sources = []
    for name in files:
        normalized = _normalized_source(name)
        if normalized is None:
            return f"{name}: не путь файла в репозитории проекта", "", None
        sources.append(normalized)
    sources = list(dict.fromkeys(sources))
    entries, reason = tree_objects(ctx.path, sha, sources)
    if entries is None:
        return f"дерево коммита {sha} не прочитано: {reason}", "", None
    for name in sources:
        refusal = _source_refusal(name, entries.get(name))
        if refusal:
            return refusal, "", None
    text, reason = read_file(project)
    if text is None:
        return f"{rel(project)}: {reason}", "", None
    parsed = parse(text)
    if parsed.kind == BROKEN_KIND:
        return f"{rel(project)}: {BROKEN}", "", None
    blobs = {name: entries[name][1] for name in sources}
    new_text = render_header(ctx.base, sha, blobs) + parsed.body
    check = parse(new_text)
    if (check.kind != STAMPED or check.body != parsed.body
            or check.fields.get("base_branch") != ctx.base
            or check.fields.get("sources") != blobs):
        return (f"имя базовой ветки или путь файла не записывается в "
                f"заголовок отметки без искажения: {ctx.base}, "
                f"{', '.join(sources)}"), "", None
    return "", new_text, path(project)


def _write_atomic(target: Path, text: str) -> None:
    """Замена файла целиком: временный файл рядом и `os.replace` — прочие
    читатели видят либо прежний текст, либо новый."""
    fd, tmp = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        os.chmod(tmp, stat.S_IMODE(os.lstat(target).st_mode))
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def cmd_conventions_stamp(rest: list) -> None:
    """`conventions-stamp <проект> <файл>…` (требование 7): заголовок
    отметки по `refs/heads/<base>` клона в начало `conventions.md`, прежний
    заголовок заменяется, текст под ним — побайтно прежний. Отказ —
    ненулевой код выхода с причиной, файл не меняется."""
    project, files = (rest[0], rest[1:]) if rest else ("", [])
    refusal, text, target = stamp_refusal(project, files)
    if refusal:
        sys.exit(f"conventions-stamp: отказ — {refusal}")
    try:
        _write_atomic(target, text)
    except OSError as exc:
        sys.exit(f"conventions-stamp: отказ — {rel(project)} не записан: "
                 f"{_os_reason(exc)}")
    fields = parse(text).fields
    print(f"{rel(project)}: отметка разбора поставлена — ветка "
          f"{fields['base_branch']}, коммит {fields['base_sha']}, файлы "
          f"{', '.join(fields['sources'])}")


# ------------------------------------------------------------ сверка дрейфа

def drift(target: str) -> tuple[str, str]:
    """(статус, пояснение) сверки `conventions.md` проекта с
    `refs/heads/<base>` его клона (требование 8): `ok` — blob каждого файла
    `sources` прежний; иначе `warn` с причиной. Файл не меняется, сеть не
    трогается, исключения git и файловой системы — причиной, не
    исключением."""
    own = rel(target)
    text, reason = read_file(target)
    if text is None:
        if reason == NOT_FOUND:
            return "warn", (f"{own}: {NOT_FOUND} — конвенции проекта не "
                            f"разобраны; порядок разбора — {ONBOARDING_DOC}")
        return "warn", f"{own}: {reason}"
    parsed = parse(text)
    if parsed.kind == PLAIN:
        return "warn", (f"{own}: {NO_STAMP} — поставь её: {STAMP_COMMAND} "
                        f"{target} <файл>…")
    if parsed.kind == BROKEN_KIND:
        return "warn", f"{own}: {BROKEN}"
    ctx = repo_context.resolve(target)
    if ctx is None:
        return "warn", repo_context.unresolved_reason(target)
    sha, reason = base_commit(ctx)
    if sha is None:
        return "warn", reason
    sources = parsed.fields["sources"]
    entries, reason = tree_objects(ctx.path, sha, list(sources))
    if entries is None:
        return "warn", f"дерево коммита {sha} не прочитано: {reason}"
    changed = [name for name, blob in sources.items()
               if entries.get(name) is None or entries[name][1] != blob]
    if changed:
        return "warn", (f"{DRIFT}: {', '.join(changed)} — пересмотри {own} "
                        f"по {ONBOARDING_DOC} и поставь отметку заново: "
                        f"{STAMP_COMMAND} {target} <файл>…")
    stamped_branch = parsed.fields["base_branch"]
    if stamped_branch != ctx.base:
        return "warn", (f"{own}: отметка поставлена по ветке "
                        f"{stamped_branch}, база записи проекта — {ctx.base}")
    return "ok", (f"{own}: файлы разбора не менялись с отметки (ветка "
                  f"{ctx.base}, коммит {sha[:12]})")
