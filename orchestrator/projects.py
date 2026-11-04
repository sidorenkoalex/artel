"""Каталог проекта в .artel/: структура target'а (ADR-0003 3д).

Единица управления — проект: подключение, отключение и восстановление
это операции над одним каталогом. Здесь заводится сам каталог со всем,
что у проекта есть: эфемерный клон целевого (workspace), первичка
артефактов (tasks), производные знания (knowledge) и логи прогонов.

Своего git-репозитория у каталога проекта нет: репозиторий фиксации
области проекта (ADR-0003 п.15) упразднён (ADR-0021 п.2, этап 1, часть
б2) — зафиксированное состояние документов задачи — коммит ссылки
`refs/artifacts/<id>` в репозитории задачи (`artifact_branch.task_repo`).
"""
import copy
import os
import sys
import tempfile
import time
from pathlib import Path

from . import (config, reference_cache, repo_context, store, targets, workspace,
               yamlmini)

REFERENCE_LABEL = "справочник ядра"
NO_JOURNAL = "журнал недоступен — сначала init"
REFERENCE_USAGE = "reference <проект> [--sha <sha>]"


def project_dir(name: str) -> Path:
    return config.PROJECTS / name


def init_project(name: str) -> list[str]:
    """Создаёт каталоги target'а; список строк — что вышло с каждым.

    Идемпотентность — свойство самой операции, а не проверки «уже есть»:
    каталог создаётся с exist_ok, поэтому повторный вызов ничего не
    ломает и после подключения, и после ручного удаления одного из
    подкаталогов (недостающее доводится, существующее не трогается).
    """
    notes = []
    for sub in config.PROJECT_DIRS:
        path = project_dir(name) / sub
        existed = path.is_dir()
        path.mkdir(parents=True, exist_ok=True)
        notes.append(f"{'уже был' if existed else 'создан'}: {path}")
    return notes


def cmd_target_init(name: str) -> None:
    """Подключение target'а: каталог проекта по декларации targets.yaml и
    клон проекта (SPEC 01M4RRW7FT1EE77EY9Y462AZKC, требование 6).

    Имя сверяется с декларацией ДО каталогов: необъявленный проект не
    оставляет каталога-сироты. Клон — тем же `workspace.ensure_clone`, что
    у `new`: существующий не трогается; неудача — отказ с причиной, а
    созданные каталоги остаются (повтор `target-init` их доведёт)."""
    try:
        entry = targets.target(name)
    except targets.TargetsError as exc:
        sys.exit(f"target-init: {exc}")

    try:
        notes = init_project(name)
    except OSError as exc:
        sys.exit(f"target-init: каталог проекта {name} не создан: {exc}")

    print(f"target {name}: forge {entry['forge']}, база {entry['base']}, "
          f"гейт мержа {entry['merge_gate']}")
    for note in notes:
        print(f"  {note}")

    clone, error = workspace.ensure_clone(name)
    if error is not None:
        sys.exit(f"target-init: {error}")
    print(f"  клон проекта: {clone}")
    for line in _target_init_reference(name, entry, clone):
        print(f"  {line}")


def _target_init_reference(name: str, entry: dict, clone: Path) -> list[str]:
    """Справочник ядра после клона (SPEC 01M4TVBT9ZCRQDY669QV3S95MA,
    требование 5): строки сводки. Сбой сборки печатается причиной и
    `target-init` не отменяет — каталоги и клон остаются."""
    setting = entry.get(targets.REFERENCE_FIELD)
    if setting is None:
        return [f"{REFERENCE_LABEL}: выключен (нет поля {targets.REFERENCE_FIELD})"]
    if not store.db_usable():
        return [f"{REFERENCE_LABEL}: {NO_JOURNAL}"]
    sha, why = reference_cache.branch_commit(clone, entry["base"])
    if sha is None:
        return [f"{REFERENCE_LABEL}: не собран — коммит базы {entry['base']} "
                f"не узнан: {why}"]
    try:
        result = reference_cache.get_reference_for_target(
            store.db(), name, reason=reference_cache.REFERENCE_REASON, sha=sha)
    except Exception as exc:  # noqa: BLE001 — сбой сборки не отменяет target-init
        return [f"{REFERENCE_LABEL}: не собран — {type(exc).__name__}: {exc}"]
    return reference_summary(name, setting, sha, result)


MIGRATE_NEXT_STEP = ("дальше: убери запись {name} из targets.yaml командой "
                     "doc-commit, затем pin-update; до этого действует запись "
                     "локального слоя")
# Символы, с которыми строка без кавычек читается `yamlmini` иначе или не
# читается вовсе (SPEC 01M5SCGSQN0AT0B07H7M9803RA, требование 10).
_QUOTE_MARKS = (": ", "#", '"', "'", "[", "]", ",")


class _Unwritable(Exception):
    """Значение поля подмножеством `yamlmini` не записать."""


def cmd_targets_migrate(name: str) -> None:
    """Перенос записи внешнего проекта из targets.yaml репозитория в
    локальный слой (SPEC 01M5SCGSQN0AT0B07H7M9803RA, требование 10).

    Файл пишется только после сверки: собранный текст разбирается тем же
    `yamlmini`, сводится загрузчиком и сравнивается с записью репозитория
    поле в поле — запись, которая читалась бы иначе, не появляется."""
    path = targets.local_path()
    if name == config.DEFAULT_TARGET:
        sys.exit(f"targets-migrate: запись {name} — только в targets.yaml "
                 f"репозитория, в локальный слой не переносится")
    try:
        repo, local = targets.layers()
    except targets.TargetsError as exc:
        sys.exit(f"targets-migrate: {exc}")
    if name not in repo:
        sys.exit(f"targets-migrate: записи {name} нет в {config.TARGETS}")
    if local is not None and name in local:
        sys.exit(f"targets-migrate: запись {name} уже есть в локальном слое "
                 f"{path} — файл не изменён")
    three, absolute = _split_entry(name, repo[name])
    if absolute:
        sys.exit(f"targets-migrate: абсолютные значения в записи {name}: "
                 f"{', '.join(absolute)} — в разделах description и policy "
                 f"их быть не может (каталог кэша — {targets.CACHE_MARK}, "
                 f"PATH — machine.path); файл не записан")
    try:
        entry_text = "".join(line + "\n"
                             for line in _render({name: three}, 2, ""))
    except _Unwritable as exc:
        sys.exit(f"targets-migrate: поле {exc} записи {name} не записать "
                 f"подмножеством YAML пульта; файл не записан")
    try:
        old = path.read_text(encoding="utf-8") if local is not None else ""
    except (OSError, UnicodeDecodeError) as exc:
        sys.exit(f"targets-migrate: {path} не прочитан: {exc}")
    if old and not old.endswith("\n"):
        old += "\n"
    text = (old or "targets:\n") + entry_text
    problems = _migrate_mismatches(text, name, repo[name], local or {}, path)
    if problems:
        sys.exit(f"targets-migrate: сверка не прошла — {'; '.join(problems)}; "
                 f"файл не записан")
    try:
        _write_atomic(path, text)
    except OSError as exc:
        sys.exit(f"targets-migrate: {path} не записан: {exc}")
    print(f"targets-migrate: запись {name} перенесена в локальный слой {path}")
    for section in targets.LOCAL_SECTIONS:
        print(f"  {section}: {', '.join(three[section])}")
    print(MIGRATE_NEXT_STEP.format(name=name))


def _split_fields(fields: dict, cache: str) -> tuple[dict, str | None]:
    """Профиль или компонент без PATH, с `<cache>` вместо каталога кэша;
    второе — снятый PATH или None."""
    fields = dict(fields)
    env = fields.get("env")
    if not isinstance(env, dict):
        return fields, None
    env = dict(env)
    path = env.pop("PATH", None)
    for key, value in env.items():
        if isinstance(value, str) and (
                value == cache or value.startswith(cache + "/")):
            env[key] = targets.CACHE_MARK + value[len(cache):]
    if env:
        fields["env"] = env
    else:
        del fields["env"]
    return fields, path


def _split_entry(name: str, flat: dict) -> tuple[dict, list[str]]:
    """Запись прежнего вида → три раздела; второе — поля `description`/
    `policy` с абсолютным значением."""
    cache = targets.cache_dir(name)
    placed = {"forge", "url", "token_slot", "base", "no_paths",
              "project_skills", "merge_gate", "sandbox", targets.WRAPPER_FIELD,
              targets.PROFILE_FIELD, targets.COMPONENTS_FIELD}
    description = {"base": flat["base"]}
    policy = {field: flat[field] for field in
              ("no_paths", "project_skills", "merge_gate", "sandbox",
               targets.WRAPPER_FIELD)
              if field in flat}
    machine = {field: flat[field] for field in ("forge", "url", "token_slot")}
    profile = flat.get(targets.PROFILE_FIELD)
    if isinstance(profile, dict):
        fields, path = _split_fields(profile, cache)
        for sub in targets.LOCAL_POLICY_SCOPES:
            if sub in fields:
                policy[sub] = fields.pop(sub)
        description[targets.PROFILE_FIELD] = fields
        if path is not None:
            machine["path"] = path
    comps = flat.get(targets.COMPONENTS_FIELD)
    if isinstance(comps, dict):
        described, scopes, paths = {}, {}, {}
        for comp, fields in comps.items():
            fields, paths[comp] = _split_fields(fields, cache)
            own = {sub: fields.pop(sub) for sub in targets.LOCAL_POLICY_SCOPES
                   if sub in fields}
            if own:
                scopes[comp] = own
            described[comp] = fields
        description[targets.COMPONENTS_FIELD] = described
        if scopes:
            policy[targets.COMPONENTS_FIELD] = scopes
        values = set(paths.values())
        if len(values) == 1 and None not in values:
            machine["path"] = values.pop()
        else:
            own_paths = {comp: {"path": path} for comp, path in paths.items()
                         if path is not None}
            if own_paths:
                machine[targets.COMPONENTS_FIELD] = own_paths
    # Прочие поля — в `description`: незнакомое загрузчику поле даст отказ
    # сверки с его именем, а не потеряется молча.
    for field, value in flat.items():
        if field not in placed:
            description[field] = value
    absolute = [field for section, body in (("description", description),
                                            ("policy", policy))
                for field, value in _strings(body, section)
                if value.startswith(("/", "~"))]
    return ({"description": description, "policy": policy,
             "machine": machine}, list(dict.fromkeys(absolute)))


def _strings(value: object, prefix: str):
    """(поле, строка) всех строк значения на любой глубине."""
    if isinstance(value, str):
        yield prefix, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _strings(item, f"{prefix}.{key}")
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item, prefix)


def _render(mapping: dict, indent: int, prefix: str) -> list[str]:
    """Строки блочного отображения подмножества `yamlmini`."""
    lines = []
    pad = " " * indent
    for key, value in mapping.items():
        field = f"{prefix}.{key}" if prefix else str(key)
        if (not isinstance(key, str) or not key or key != key.strip()
                or ":" in key or "\n" in key
                or key.startswith(("#", "- ", "[", '"', "'"))):
            raise _Unwritable(field)
        if isinstance(value, dict):
            if not value:
                raise _Unwritable(field)
            lines.append(f"{pad}{key}:")
            lines.extend(_render(value, indent + 2, field))
        elif isinstance(value, list):
            items = [_list_item(item, field) for item in value]
            lines.append(f"{pad}{key}: [{', '.join(items)}]")
        else:
            lines.append(f"{pad}{key}: {_scalar_text(value, field)}")
    return lines


def _list_item(item: object, field: str) -> str:
    """Элемент потокового списка — как есть (ANSWER-1, п. 2); прочтётся ли
    он тем же значением, решает сверка."""
    if isinstance(item, bool):
        return "true" if item else "false"
    if isinstance(item, (int, str)):
        return str(item)
    raise _Unwritable(field)


def _scalar_text(value: object, field: str) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if not isinstance(value, str) or "\n" in value or "\r" in value:
        raise _Unwritable(field)
    plain = (value and value == value.strip()
             and not any(mark in value for mark in _QUOTE_MARKS)
             and yamlmini.scalar(value) == value)
    if plain:
        return value
    if '"' not in value:
        return f'"{value}"'
    if "'" not in value:
        return f"'{value}'"
    raise _Unwritable(field)


def _differences(want: object, got: object, field: str) -> list[str]:
    """Поля, в которых `got` расходится с `want` (тип значения — тоже;
    порядок компонентов — тоже)."""
    if isinstance(want, dict) and isinstance(got, dict):
        found = []
        for key in [*want, *(k for k in got if k not in want)]:
            here = f"{field}.{key}"
            if key not in want or key not in got:
                found.append(here)
            else:
                found.extend(_differences(want[key], got[key], here))
        if (not found and field.endswith(f".{targets.COMPONENTS_FIELD}")
                and list(want) != list(got)):
            found.append(f"{field} (порядок)")
        return found
    if isinstance(want, list) and isinstance(got, list):
        if len(want) != len(got) or any(
                _differences(a, b, field) for a, b in zip(want, got)):
            return [field]
        return []
    return [] if type(want) is type(got) and want == got else [field]


def _migrate_mismatches(text: str, name: str, flat: dict, previous: dict,
                        path: Path) -> list[str]:
    """Расхождения собранного текста слоя с ожидаемым: новая запись — с
    записью репозитория, прежние — с их выдачей до переноса."""
    try:
        entries = yamlmini.mapping(text).get("targets")
    except yamlmini.YamlError as exc:
        return [f"собранный текст не разобран: {exc}"]
    if not isinstance(entries, dict):
        return ["в собранном тексте нет раздела 'targets:'"]
    if list(entries) != [*previous, name]:
        return [f"записи собранного текста — {', '.join(entries)}, ожидались "
                f"{', '.join([*previous, name])}"]
    problems = []
    for entry_name, want in [*previous.items(), (name, flat)]:
        try:
            got = targets.merge_local(entry_name, entries[entry_name], path)
        except targets.TargetsError as exc:
            problems.append(str(exc))
            continue
        problems.extend(_differences(want, got, entry_name))
    return problems


def _write_atomic(path: Path, text: str) -> None:
    """Временный файл в том же каталоге и замена: читатель видит либо
    прежний файл, либо новый целиком."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.",
                               suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except OSError:
        Path(tmp).unlink(missing_ok=True)
        raise


TARGET_SET_USAGE = ("target-set <проект> <путь поля> <значение> | "
                    "target-set --show <проект> [<путь>]")
TARGET_SET_ABSENT = "(нет)"
NO_COMPONENT = "компонента {comp} нет в записи; добавление компонентов не входит"
# Виды полей компонента, значение которых — отображение (`targets.
# COMPONENT_FIELDS`): лист такого поля командой не правится.
_MAPPING_KINDS = ("mapping", "tools", "depends_on", "paths_source")


def _backup_stamp() -> str:
    """Время UTC до секунд для имени копии прежнего файла — шов теста
    «две правки в одну секунду» (SPEC 01M6KBD9FC36WARWSY9Z0JDMG5,
    требование 6)."""
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def cmd_target_set(rest: list) -> None:
    """Правка одного поля записи внешнего проекта в локальном слое (SPEC
    01M6KBD9FC36WARWSY9Z0JDMG5).

    Новый текст собирается целиком из разобранного прежнего и пишется
    только после сверки в памяти: отличается ровно одним листом, сводится
    `targets.merge_local`, прочие записи сводятся как прежде. Перед записью
    прежний файл копируется в `config.LOGS`, после — запись журнала."""
    if rest[:1] in (["-h"], ["--help"]):
        print(TARGET_SET_USAGE)
        return
    if rest[:1] == ["--show"]:
        _target_set_show(rest[1:])
        return
    if len(rest) < 3:
        sys.exit(f"target-set: нужны проект, путь поля и значение\n"
                 f"{TARGET_SET_USAGE}")
    if len(rest) > 3:
        sys.exit(f"target-set: значение — ровно один аргумент, получено "
                 f"{len(rest) - 2}: {' '.join(rest[2:])} — возьми значение в "
                 f"кавычки, например '[a, b]'; файл не записан")
    name, field_path, raw = rest
    if name == config.DEFAULT_TARGET:
        sys.exit(f"target-set: запись {name} — в targets.yaml репозитория, "
                 f"правка — doc-commit; файл не записан")
    try:
        _repo, local = targets.layers()
    except targets.TargetsError as exc:
        sys.exit(f"target-set: {exc}; файл не записан")
    path = targets.local_path()
    if local is None or name not in local:
        sys.exit(f"target-set: записи {name} нет в локальном слое {path}; "
                 f"файл не записан")
    try:
        old = path.read_text(encoding="utf-8")
        data = yamlmini.mapping(old)
    except (OSError, UnicodeDecodeError, yamlmini.YamlError) as exc:
        sys.exit(f"target-set: {path} не прочитан: {exc}")
    comment = _comment_line(old)
    if comment is not None:
        sys.exit(f"target-set: в {path} комментарий (строка {comment}) — "
                 f"пересборка файла его сотрёт; убери комментарий вручную; "
                 f"файл не записан")
    entry = data["targets"][name]
    keys = _field_keys(entry, field_path)
    value = _argument_value(raw, field_path)
    try:
        new_text = _literal(value, field_path)
    except _Unwritable:
        sys.exit(f"target-set: значение {raw!r} поля {field_path} не записать "
                 f"подмножеством YAML пульта; файл не записан")
    found, current = _lookup(entry, keys)
    if found and not _differences(current, value, field_path):
        print(f"target-set: {name} {field_path}: без изменений ({new_text})")
        return
    try:
        was = _literal(current, field_path) if found else TARGET_SET_ABSENT
    except _Unwritable:
        was = repr(current)
    if not store.db_usable():
        sys.exit(f"target-set: {NO_JOURNAL}; файл не записан")
    edited = copy.deepcopy(data)
    _assign(edited["targets"][name], keys, value)
    try:
        text = "".join(line + "\n" for line in _render(edited, 0, ""))
    except _Unwritable as exc:
        sys.exit(f"target-set: поле {exc} файла {path} не записать "
                 f"подмножеством YAML пульта; файл не записан")
    problems = _target_set_mismatches(data, text, name, keys, value, path)
    if problems:
        sys.exit(f"target-set: сверка не прошла — {'; '.join(problems)}; "
                 f"файл не записан")
    try:
        backup = _backup_copy(path)
    except OSError as exc:
        sys.exit(f"target-set: копия {path} в {config.LOGS} не создана: "
                 f"{exc}; файл не записан")
    print(f"target-set: копия прежнего файла — {backup}")
    try:
        _write_atomic(path, text)
    except OSError as exc:
        sys.exit(f"target-set: {path} не записан: {exc}")
    detail = f"{field_path}: {was} → {new_text}"
    store.journal(store.db(), None, "operator", "target-set", detail,
                  target=name)
    print(f"target-set: {detail}")


def _target_set_show(rest: list) -> None:
    """`target-set --show <проект> [<путь>]`: значение поля или раздела
    записи локального слоя как оно записано; файл не пишется."""
    if not rest or len(rest) > 2:
        sys.exit(f"target-set --show: нужен проект и, возможно, путь\n"
                 f"{TARGET_SET_USAGE}")
    name = rest[0]
    path = targets.local_path()
    try:
        data = yamlmini.mapping(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        sys.exit(f"target-set --show: локального слоя {path} нет")
    except (OSError, UnicodeDecodeError, yamlmini.YamlError) as exc:
        sys.exit(f"target-set --show: {path} не прочитан: {exc}")
    entries = data.get("targets")
    if not isinstance(entries, dict) or name not in entries:
        sys.exit(f"target-set --show: записи {name} нет в локальном слое {path}")
    field_path = rest[1] if len(rest) == 2 else ""
    found, value = _lookup(entries[name], field_path.split(".")
                           if field_path else [])
    if not found:
        sys.exit(f"target-set --show: у записи {name} нет поля {field_path}")
    label = field_path or name
    try:
        if isinstance(value, dict):
            lines = [f"{label}:"] + _render(value, 2, label)
        else:
            lines = [f"{label}: {_literal(value, label)}"]
    except _Unwritable:
        lines = [f"{label}: {value!r}"]
    print("\n".join(lines))


def _comment_line(text: str) -> int | None:
    """Номер первой строки с комментарием по правилу `yamlmini` (строка с
    `#` первым непробельным символом; `#` в начале значения или после
    пробела; кавычки значения снимаются раньше комментария); None — нет."""
    for number, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if stripped.startswith("#"):
            return number
        _key, _sep, rest = stripped.partition(":")
        rest = rest.strip()
        if rest[:1] in ("'", '"'):
            end = rest.find(rest[0], 1)
            if end != -1:
                tail = rest[end + 1:].strip()
                if not tail:
                    continue
                if tail.startswith("#"):
                    return number
        if yamlmini.COMMENT.search(rest):
            return number
    return None


def _field_keys(entry: dict, field_path: str) -> list[str]:
    """Ключи пути поля от записи проекта; отказ — путь вне формы
    `<раздел>.<поле>` / `<раздел>.components.<к>.<поле>`, поле вне перечня
    раздела, вложенное отображение, компонент вне `description.components`."""
    keys = field_path.split(".")
    section = keys[0]
    if section not in targets.LOCAL_SECTIONS or len(keys) < 2 or not all(keys):
        sys.exit(f"target-set: путь {field_path!r} — не "
                 f"<раздел>.<поле> или <раздел>.{targets.COMPONENTS_FIELD}."
                 f"<компонент>.<поле>; разделы: "
                 f"{', '.join(targets.LOCAL_SECTIONS)}; файл не записан")
    if keys[1] == targets.COMPONENTS_FIELD and len(keys) >= 3:
        comp = keys[2]
        scope = f"{section}.{targets.COMPONENTS_FIELD}.{comp}"
        allowed = _component_fields(section)
        if len(keys) == 3:
            sys.exit(f"target-set: путь {field_path} — блок компонента, не "
                     f"поле; поля {scope}: {', '.join(allowed)}; файл не записан")
        comps = entry.get("description", {}).get(targets.COMPONENTS_FIELD)
        if not isinstance(comps, dict) or comp not in comps:
            sys.exit(f"target-set: {NO_COMPONENT.format(comp=comp)}; "
                     f"файл не записан")
        field = keys[3]
        if field not in allowed:
            sys.exit(f"target-set: поля {field} нет в {scope}; допустимые: "
                     f"{', '.join(allowed)}; файл не записан")
        nested = (len(keys) > 4 or (section == "description" and
                  targets.COMPONENT_FIELDS[field] in _MAPPING_KINDS))
    else:
        field = keys[1]
        allowed = list(targets.LOCAL_FIELDS[section])
        if field not in allowed:
            sys.exit(f"target-set: поля {field} нет в {section}; допустимые: "
                     f"{', '.join(allowed)}; файл не записан")
        nested = (len(keys) > 2 or field in (targets.COMPONENTS_FIELD,
                                             targets.PROFILE_FIELD))
    found, current = _lookup(entry, keys[:4] if len(keys) > 4 else keys)
    if nested or (found and isinstance(current, dict)):
        sys.exit(f"target-set: путь {field_path} ведёт во вложенное "
                 f"отображение — его поля командой не правятся; файл не записан")
    return keys


def _component_fields(section: str) -> list[str]:
    """Допустимые поля блока компонента раздела (требование 2)."""
    if section == "policy":
        return list(targets.LOCAL_POLICY_SCOPES)
    if section == "machine":
        return list(targets.LOCAL_MACHINE_COMPONENT_FIELDS)
    return [field for field in targets.COMPONENT_FIELDS
            if field not in targets.LOCAL_POLICY_SCOPES]


def _argument_value(raw: str, field_path: str) -> object:
    """Значение аргумента тем же разбором, каким его прочтёт файл; отказ —
    разбор не годен, теряет часть текста или даёт пустое значение."""
    text = raw.strip()
    if "\n" in raw or "\r" in raw:
        sys.exit(f"target-set: значение поля {field_path} — в одну строку; "
                 f"файл не записан")
    try:
        value = yamlmini.mapping(f"value: {text}\n").get("value")
    except yamlmini.YamlError as exc:
        sys.exit(f"target-set: значение {raw!r} не разобрано: {exc}; "
                 f"файл не записан")
    if _loses_text(text):
        sys.exit(f"target-set: значение {raw!r} читается как {value!r} — "
                 f"разбор теряет хвост комментария (`#` в начале или после "
                 f"пробела); файл не записан")
    if value is None or value == "":
        sys.exit(f"target-set: значение {raw!r} поля {field_path} пусто; "
                 f"файл не записан")
    return value


def _loses_text(text: str) -> bool:
    """Отбросит ли разбор `yamlmini` часть текста как комментарий."""
    if text.startswith("["):
        end = text.find("]")
        if end == -1:
            return False
        return bool(text[end + 1:].strip()) or any(
            yamlmini.COMMENT.search(item.strip())
            for item in text[1:end].split(","))
    if text[:1] in ("'", '"'):
        end = text.find(text[0], 1)
        if end != -1 and text[end + 1:].strip().startswith("#"):
            return True
        if end != -1 and not text[end + 1:].strip():
            return False
    return bool(yamlmini.COMMENT.search(text))


def _literal(value: object, field: str) -> str:
    """Литерал значения в той записи, что пишет `_render`."""
    if isinstance(value, list):
        return f"[{', '.join(_list_item(item, field) for item in value)}]"
    return _scalar_text(value, field)


def _lookup(mapping: dict, keys: list) -> tuple[bool, object]:
    """(есть ли значение по пути, значение)."""
    value = mapping
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            return False, None
        value = value[key]
    return True, value


def _assign(mapping: dict, keys: list, value: object) -> None:
    """Лист по пути; недостающие блоки (компонент в `policy`/`machine`)
    заводятся пустыми — существование компонента проверено раньше."""
    for key in keys[:-1]:
        mapping = mapping.setdefault(key, {})
    mapping[keys[-1]] = value


def _leaves(value: object, prefix: tuple = ()) -> dict:
    """Листья разобранного отображения: путь → значение (список — лист)."""
    if isinstance(value, dict):
        found = {}
        for key, item in value.items():
            found.update(_leaves(item, prefix + (key,)))
        return found
    return {prefix: value}


def _target_set_mismatches(data: dict, text: str, name: str, keys: list,
                           value: object, path: Path) -> list[str]:
    """Сверка нового текста до записи (требование 5): (а) разобранный текст
    отличается от прежнего ровно листом по пути; (б) сведение слоя на нём
    проходит, сведённые записи прочих проектов равны прежним."""
    try:
        new = yamlmini.mapping(text)
    except yamlmini.YamlError as exc:
        return [f"собранный текст не разобран: {exc}"]
    target = ("targets", name, *keys)
    old_leaves, new_leaves = _leaves(data), _leaves(new)
    changed = [".".join(map(str, key)) for key in
               dict.fromkeys([*old_leaves, *new_leaves])
               if key not in old_leaves or key not in new_leaves
               or _differences(old_leaves[key], new_leaves[key], "")]
    if changed != [".".join(target)]:
        return [f"изменились листы {', '.join(changed) or '(никакие)'}, "
                f"ожидался один — {'.'.join(target)}"]
    if _differences(value, new_leaves[target], ".".join(keys)):
        return [f"{'.'.join(keys)} читается как {new_leaves[target]!r}, "
                f"задано {value!r}"]
    entries = new.get("targets")
    if not isinstance(entries, dict) or list(entries) != list(data["targets"]):
        return ["записи собранного текста расходятся с прежними"]
    problems = []
    for entry_name, entry in entries.items():
        try:
            got = targets.merge_local(entry_name, entry, path)
        except targets.TargetsError as exc:
            problems.append(str(exc))
            continue
        if entry_name == name:
            continue
        try:
            want = targets.merge_local(entry_name, data["targets"][entry_name],
                                       path)
        except targets.TargetsError as exc:
            problems.append(str(exc))
            continue
        problems.extend(_differences(want, got, entry_name))
    return problems


def _backup_copy(path: Path) -> Path:
    """Копия прежнего файла в `config.LOGS` под новым именем
    `targets-<время>[-<n>].yaml`: создание без перезаписи — вторая правка в
    ту же секунду не затирает первую копию."""
    content = path.read_bytes()
    config.LOGS.mkdir(parents=True, exist_ok=True)
    stamp = _backup_stamp()
    number = 0
    while True:
        suffix = f"-{number}" if number else ""
        backup = config.LOGS / f"targets-{stamp}{suffix}.yaml"
        try:
            with open(backup, "xb") as handle:
                handle.write(content)
        except FileExistsError:
            number += 1
            continue
        return backup


def reference_summary(name: str, setting: dict | None, sha: str,
                      result: reference_cache.Reference) -> list[str]:
    """Сводка справочника ядра: состояние, sha, размер, предел, доля,
    порог с источником и вывод по формулам брифа (`brief.py`: размер —
    байты UTF-8 полного текста кэша, «больше предела» при `size > limit`,
    предупреждение при `size * 10 > limit * 9`)."""
    head = f"{REFERENCE_LABEL} {name}: {result.state}"
    if result.state == "off":
        return [f"{head} (нет поля {targets.REFERENCE_FIELD})"]
    lines = [f"{head} — {result.note}" if result.note else head, f"sha: {sha}"]
    if setting is not None:
        threshold, source = reference_cache.min_uses(setting)
        lines.append(f"порог использования: {threshold} ({source})")
    if result.state == "absent":
        return lines
    size = len(result.text.encode("utf-8"))
    limit = config.CORE_REFERENCE_MAX_BYTES
    if size > limit:
        verdict = "больше предела — в бриф не попадёт"
    elif size * 10 > limit * 9:
        verdict = "больше 90% предела — бриф поднимет предупреждение"
    else:
        verdict = "в пределе"
    lines += [f"размер: {size} байт, предел {limit} байт "
              f"({size * 100 / limit:.1f}%)", f"вывод: {verdict}"]
    return lines


def cmd_reference(rest: list) -> None:
    """Команда `reference <проект> [--sha <sha>]`: сборка справочника ядра
    проекта по требованию и сводка (SPEC 01M4TVBT9ZCRQDY669QV3S95MA,
    требование 4). Проверки до любых действий: имя проекта, клон, форма
    `--sha`, БД пульта; без `--sha` — коммит `refs/heads/<base>` клона без
    `fetch`. Код выхода ненулевой при `absent`; размер больше предела —
    сообщение, не ошибка."""
    if rest[:1] in (["-h"], ["--help"]):
        print(REFERENCE_USAGE)
        return
    if not rest or rest[0].startswith("-"):
        sys.exit(f"reference: не назван проект\n{REFERENCE_USAGE}")
    name, extra = rest[0], rest[1:]
    sha = None
    if extra:
        if extra[0] != "--sha" or len(extra) != 2:
            sys.exit(f"reference: нераспознанные аргументы {' '.join(extra)}\n"
                     f"{REFERENCE_USAGE}")
        sha = extra[1]
    try:
        entry = targets.target(name)
    except targets.TargetsError as exc:
        sys.exit(f"reference: {exc}")
    clone = repo_context.clone_path(name)
    if not clone.is_dir():
        sys.exit(f"reference: клона проекта {name} нет ({clone}) — сначала "
                 f"target-init {name}")
    if sha is not None and not reference_cache.SHA_FORM.fullmatch(sha):
        sys.exit(f"reference: --sha {sha!r} — не полный sha из 40 "
                 f"шестнадцатеричных знаков")
    if not store.db_usable():
        sys.exit(f"reference: {NO_JOURNAL}")
    if sha is None:
        sha, why = reference_cache.branch_commit(clone, entry["base"])
        if sha is None:
            sys.exit(f"reference: коммит базы refs/heads/{entry['base']} "
                     f"не узнан: {why}")
    result = reference_cache.get_reference_for_target(
        store.db(), name, reason=reference_cache.REFERENCE_REASON, sha=sha)
    lines = reference_summary(name, entry.get(targets.REFERENCE_FIELD), sha, result)
    print("\n".join(lines))
    if result.state not in ("off", "fresh", "cached"):
        sys.exit(1)
