"""Аудит SPEC — шаг роли `spec_auditor` между сдачей SPEC и гейтом SPEC
(ADR-0022 пп. 2-3, SPEC 01M4MQAGRWMWR0GFDM9086P3TD).

Здесь — всё, что о визите `spec_audit` знает пульт помимо самого перехода
(`orchestrator/fsm_advance.py::spec_audit`): вход с записью журнала (sha
содержимого SPEC.md и сигналы глубины), свежесть вердикта по последнему
коммиту `SPEC-AUDIT.md`, привязка вердикта к проверенной версии SPEC,
выход с записью вердикта и счёт возвратов аналитику.

Вердикт и счётчик живут в журнале задачи, не в колонках БД (требования
11, 14): `approve`, `show`, `status`, остановка `auto` и канарейка читают
последний вердикт отсюда, а не из файла, который на гейте мог поменяться.

Модуль лёгкий по импортам: его читают `catalog`, `auto`, `canary` и
`role_prompt` — `budget`/`fsm` сюда не тянутся.
"""
import hashlib
import re

from scripts import guard

from .. import artifact_branch, artifact_source, config, store, yamlmini
from . import mandate, refusal_classes

STATE = "spec_audit"
ROLE = "spec_auditor"
ARTIFACT = "SPEC-AUDIT.md"
ACCEPT_FAIL_FLAG = "--accept-audit-fail"

# Записи журнала визита аудита. Вход несёт sha содержимого SPEC.md и
# сигналы; выход — вердикт (`RETURN_ACTION` — возврат аналитику, по числу
# этих записей считается лимит возвратов); принятие `fail` — флаг
# Оператора на `approve`.
ENTRY_ACTION = "аудит SPEC: вход"
VERDICT_ACTION = "аудит SPEC: вердикт"
RETURN_ACTION = "аудит SPEC: возврат аналитику по fail"
ACCEPTED_FAIL_ACTION = "аудит SPEC: вердикт fail принят Оператором"

NOT_FRESH_REFUSAL_ACTION = refusal_classes.SPEC_AUDIT_NOT_FRESH_REFUSAL_ACTION
SPEC_CHANGED_REFUSAL_ACTION = refusal_classes.SPEC_AUDIT_SPEC_CHANGED_REFUSAL_ACTION
SPEC_SHA_REFUSAL_ACTION = refusal_classes.SPEC_AUDIT_SPEC_SHA_REFUSAL_ACTION

_SHA_RE = re.compile(r"[0-9a-f]{40}")
_ANSWER_NAME_RE = re.compile(r"ANSWER-(\d+)\.md")
_ADR_RE = re.compile(r"ADR-\d{4}")
_APPENDIX_RE = re.compile(r"приложени\w*\s+PLAN", re.I)
_SPEC_SHA_FIELD_RE = re.compile(r"^spec_sha:\s*[\"']?([0-9A-Fa-f]+)", re.M)
_ENTRY_RE = re.compile(
    r"^SPEC\.md (?P<sha>\S+) — сигналы: (?P<signals>.*); "
    r"разбор: (?P<depth>полный|краткий)$", re.S)
_VERDICT_RE = re.compile(r"\bвердикт (pass|concerns|fail)\b")
_MANDATE_MARKERS = (mandate._ZONES_MANDATE_MARKER,
                    mandate.TEST_WEAKENING_MANDATE_MARKER,
                    mandate.TEST_ID_MANDATE_MARKER)

NO_SIGNALS = "нет"


def _rel(task_id: str, name: str) -> str:
    return f"tasks/{task_id}/{name}"


def autocommit_prefix(task_id: str) -> str:
    """Префикс сообщения автокоммита шага роли `spec_auditor` в ссылке
    документов — тот же текст, что строит `checkpoint.
    _commit_external_step_artifacts` (`own_commit_marker`): сверка
    префиксом покрывает и формулировку «WIP после таймаута»."""
    return f"{task_id}: артефакты шага {ROLE} (автокоммит оркестратора"


def blob_sha(text: str) -> str:
    """sha объекта git, которым `text` лежит в дереве коммита."""
    data = text.encode("utf-8")
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def content_sha(task_id: str, branch: str, name: str = "SPEC.md") -> str:
    """sha содержимого `tasks/<id>/<name>` в ссылке документов
    (`git rev-parse <ссылка>:<путь>`, требование 13) — не sha коммита её
    головы. git не дал sha — тот же sha считается по тексту файла, прочитанному
    с той же ссылки; файла нет — пустая строка."""
    rel = _rel(task_id, name)
    res = artifact_branch.git(task_id, "rev-parse", f"{branch}:{rel}")
    out = res.stdout.strip() if res is not None and res.returncode == 0 else ""
    if _SHA_RE.fullmatch(out):
        return out
    text, _ = artifact_branch.show(task_id, branch, rel)
    return blob_sha(text) if text is not None else ""


def _answer_texts(task_id: str, branch: str) -> list[tuple[str, str]]:
    """(имя, текст) каждого `ANSWER-n.md` задачи по возрастанию `n`."""
    paths = artifact_branch.ls_tree(task_id, branch, f"tasks/{task_id}") or []
    numbered = []
    for path in paths:
        found = _ANSWER_NAME_RE.fullmatch(path.rsplit("/", 1)[-1])
        if found:
            numbered.append((int(found.group(1)), found.group(0)))
    texts = []
    for _, name in sorted(numbered):
        text, _ = artifact_branch.show(task_id, branch, _rel(task_id, name))
        if text is not None:
            texts.append((name, text))
    return texts


def signals(spec_text: str, meta: dict, tz_text: str,
            answers: list[str]) -> list[str]:
    """Сработавшие сигналы глубины (требование 7) — строки с буквой
    сигнала и тем, что именно сработало; пустой список — сигналов нет."""
    from .. import budget
    found = []
    if guard.section_body(spec_text, "Меняемое поведение").strip():
        found.append("а) раздел «Меняемое поведение» непуст")
    if guard.section_body(spec_text, guard.REPLACED_TESTS_SECTION).strip():
        found.append(f"а) раздел «{guard.REPLACED_TESTS_SECTION}» непуст")
    mandates = sorted({line.strip() for text in answers
                       for line in text.splitlines()
                       if any(mandate.line_elements(line, marker) is not None
                              for marker in _MANDATE_MARKERS)})
    if mandates:
        found.append(f"б) мандат в ANSWER: {' / '.join(mandates)}")
    named = "\n".join(guard.section_body(spec_text, name)
                      for name in ("Требования", "Критерии приёмки"))
    paths = guard.zone_items(meta.get("zones")) | set(
        guard.PATH_MENTION.findall(named))
    for category, prefixes in config.SPEC_AUDIT_SIGNAL_PATHS.items():
        hits = sorted(p for p in paths if config.is_protected_path(p, prefixes))
        if hits:
            found.append(f"в) пути-признаки ({category}): {', '.join(hits)}")
    protected = guard.protected_zones(paths)
    if protected:
        found.append(f"в) защищённые пути: {', '.join(protected)}")
    if _APPENDIX_RE.search(spec_text):
        found.append("в) SPEC требует приложения PLAN")
    amount, _reason = budget.spec_budget(meta)
    if amount is not None and amount >= config.SPEC_AUDIT_BUDGET_SIGNAL_USD:
        found.append(f"г) budget_usd {amount:g} ≥ "
                     f"{config.SPEC_AUDIT_BUDGET_SIGNAL_USD}")
    adrs = sorted(set(_ADR_RE.findall(tz_text)))
    if adrs:
        found.append(f"д) ТЗ ссылается на ADR: {', '.join(adrs)}")
    return found


def record_entry(conn, task_id: str) -> dict:
    """Запись журнала входа в `spec_audit` (требования 7, 13): sha
    содержимого SPEC.md в ссылке документов на момент входа, сработавшие
    сигналы и глубина разбора. Зовётся сразу после перехода в
    `spec_audit` — любым из путей входа."""
    branch, _ = artifact_source.resolve(conn, task_id)
    spec_text, _ = artifact_branch.show(task_id, branch, _rel(task_id, "SPEC.md"))
    tz_text, _ = artifact_branch.show(task_id, branch, _rel(task_id, "TZ.md"))
    spec_text = spec_text or ""
    meta = yamlmini.frontmatter(spec_text) or {}
    answers = [text for _, text in _answer_texts(task_id, branch)]
    found = signals(spec_text, meta, tz_text or "", answers)
    sha = content_sha(task_id, branch)
    depth = "полный" if found else "краткий"
    listed = "; ".join(found) if found else NO_SIGNALS
    detail = f"SPEC.md {sha or '(не прочитан)'} — сигналы: {listed}; разбор: {depth}"
    store.journal(conn, task_id, "fsm", ENTRY_ACTION, detail)
    print(f"[{task_id}] аудит SPEC: SPEC.md {sha or '(не прочитан)'}, "
          f"сигналы: {listed}")
    return {"sha": sha, "signals": listed, "full": bool(found)}


def entry(conn, task_id: str) -> dict | None:
    """Последняя запись входа в `spec_audit`: `{"sha", "signals", "full"}`;
    `None` — задача в аудит не входила."""
    for row in reversed(store.task_steps(conn, task_id)):
        if row["action"] != ENTRY_ACTION:
            continue
        found = _ENTRY_RE.match(row["detail"] or "")
        if found is None:
            return None
        sha = found["sha"]
        return {"sha": sha if _SHA_RE.fullmatch(sha) else "",
                "signals": found["signals"],
                "full": found["depth"] == "полный"}
    return None


def _last_entry_id(rows) -> int:
    ids = [row["id"] for row in rows if row["action"] == f"state -> {STATE}"]
    return ids[-1] if ids else 0


def freshness_refusal(conn, task_id: str, branch: str) -> tuple[str, str] | None:
    """(действие, текст) отказа, если `SPEC-AUDIT.md` ссылки документов не
    свежий вердикт этого визита (требование 12); `None` — свежий.

    Свежий — последний коммит файла в ссылке есть автокоммит шага
    `spec_auditor` (префикс сообщения) и подтверждён событием автокоммита
    артефактной ветки после последнего входа задачи в `spec_audit`: файл
    прошлого визита и файл, записанный любой другой ролью, задачу не
    продвигают."""
    rel = _rel(task_id, ARTIFACT)
    res = artifact_branch.git(task_id, "log", "-1", "--format=%H %s",
                              branch, "--", rel)
    if res is None or res.returncode != 0:
        return (refusal_classes.BRANCH_UNREAD_REFUSAL_ACTION,
                f"git не ответил на историю {rel} ссылки {branch} — "
                f"свежесть вердикта аудита не проверить")
    line = res.stdout.strip()
    sha, _, subject = line.partition(" ")
    if not sha:
        return (NOT_FRESH_REFUSAL_ACTION,
                f"у {rel} нет коммита в ссылке {branch} — вердикт аудитора "
                f"ещё не записан")
    if not subject.startswith(autocommit_prefix(task_id)):
        return (NOT_FRESH_REFUSAL_ACTION,
                f"последний коммит {ARTIFACT} ({sha}) — не автокоммит шага "
                f"{ROLE}: «{subject}» — вердикт ждёт шага аудитора")
    rows = store.task_steps(conn, task_id)
    since = _last_entry_id(rows)
    # Формат checkpoint._commit_step_artifacts_to_branch: SHA только в
    # поле коммита, а не в произвольном тексте или списке удалённых файлов.
    witness = re.compile(
        re.escape(autocommit_prefix(task_id))
        + r"(?:, WIP после таймаута)?\)"
        + re.escape(f" (артефактная ветка, sha {sha})")
        + r"(?:; удалено: .+)?", re.S)
    if not any(row["id"] > since and row["actor"] == "orchestrator"
               and row["action"] == "автокоммит артефактов шага (артефактная ветка)"
               and witness.fullmatch(row["detail"] or "") for row in rows):
        return (NOT_FRESH_REFUSAL_ACTION,
                f"{ARTIFACT} ({sha}) записан до последнего входа задачи в "
                f"{STATE} — вердикт прошлого визита, ждёт шага аудитора")
    return None


def binding_refusal(conn, task_id: str, branch: str,
                    audit_text: str) -> tuple[str, str] | None:
    """(действие, текст) отказа, если вердикт не относится к SPEC, взятому
    на аудит (требование 13): содержимое SPEC.md в ссылке сменилось после
    входа либо `spec_sha` файла не равен sha входа. Текст называет оба
    sha; `None` — привязка сошлась."""
    recorded = entry(conn, task_id)
    entry_sha = recorded["sha"] if recorded else ""
    if not entry_sha:
        return (SPEC_CHANGED_REFUSAL_ACTION,
                f"sha SPEC.md входа в {STATE} в журнале не найден — вердикт "
                f"не с чем сверить")
    current = content_sha(task_id, branch)
    if current != entry_sha:
        return (SPEC_CHANGED_REFUSAL_ACTION,
                f"SPEC.md сменился за визит аудита: sha входа {entry_sha}, "
                f"сейчас {current or '(не прочитан)'} — вердикт относится к "
                f"другой версии SPEC")
    found = _SPEC_SHA_FIELD_RE.search(_frontmatter_block(audit_text))
    spec_sha = found.group(1).lower() if found else ""
    if spec_sha != entry_sha:
        return (SPEC_SHA_REFUSAL_ACTION,
                f"spec_sha {spec_sha or '(нет)'} в {ARTIFACT} не равен sha "
                f"SPEC.md входа {entry_sha}")
    return None


def _frontmatter_block(text: str) -> str:
    found = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
    return found.group(1) if found else ""


def return_count(conn, task_id: str) -> int:
    """Число возвратов `spec_audit -> spec_writing` по `fail` за всю жизнь
    задачи — ни `reject` на гейте, ни повторный аудит его не сбрасывают."""
    return sum(1 for row in store.task_steps(conn, task_id)
               if row["action"] == RETURN_ACTION)


def leave(conn, task_id: str, state: str, verdict: str, audit_text: str) -> None:
    """Выход из аудита по готовому вердикту (требования 11, 14): `pass`/
    `concerns` — гейт SPEC; `fail` — возврат аналитику с отклонениями в
    записи перехода (её читает раздел «Причина возврата» брифа), пока
    возвраты не исчерпаны, затем гейт SPEC с этим вердиктом."""
    recorded = entry(conn, task_id)
    listed = recorded["signals"] if recorded else NO_SIGNALS
    limit = config.SPEC_AUDIT_FAIL_RETURNS
    if verdict == "fail":
        returns = return_count(conn, task_id)
        if returns < limit:
            number = returns + 1
            deviations = (guard.section_body(audit_text, "Вердикт").strip()
                          or "(раздел «Вердикт» пуст)")
            store.set_state(
                conn, task_id, "spec_writing", "fsm", expected_state=state,
                detail=f"аудит SPEC: вердикт fail, возврат {number} из "
                       f"{limit} — отклонения {ARTIFACT}:\n{deviations}")
            store.journal(conn, task_id, "fsm", RETURN_ACTION,
                          f"вердикт fail; возврат по fail {number} из {limit}; "
                          f"сигналы: {listed}")
            print(f"[{task_id}] аудит SPEC: fail — возврат аналитику "
                  f"{number} из {limit}")
            return
        detail = (f"вердикт fail; возвраты по fail исчерпаны ({limit} из "
                  f"{limit}) — на гейт SPEC с этим вердиктом; сигналы: {listed}")
    else:
        detail = f"вердикт {verdict}; сигналы: {listed}"
    store.set_state(conn, task_id, "spec_gate", "fsm", expected_state=state,
                    detail=f"аудит SPEC: вердикт {verdict} — SPEC ждёт approve")
    store.journal(conn, task_id, "fsm", VERDICT_ACTION, detail)
    print(f"[{task_id}] аудит SPEC: вердикт {verdict} — гейт SPEC")


def last_verdict(conn, task_id: str) -> str | None:
    """Последний вердикт аудита из журнала (требование 14); `None` —
    вердикта нет либо после него задача снова вошла в `spec_audit`."""
    verdict = None
    for row in store.task_steps(conn, task_id):
        if row["action"] in (VERDICT_ACTION, RETURN_ACTION):
            found = _VERDICT_RE.search(row["detail"] or "")
            verdict = found.group(1) if found else None
        elif row["action"] == f"state -> {STATE}":
            verdict = None
    return verdict


def summary(conn, task_id: str) -> str | None:
    """Строка `show` об аудите (требование 16): последний вердикт, число
    возвратов по `fail` и сигналы последнего входа; `None` — задача в аудит
    не входила."""
    recorded = entry(conn, task_id)
    if recorded is None:
        return None
    verdict = last_verdict(conn, task_id) or "ещё нет"
    return (f"  аудит SPEC: последний вердикт {verdict}; возвратов по fail: "
            f"{return_count(conn, task_id)} из {config.SPEC_AUDIT_FAIL_RETURNS}; "
            f"сигналы: {recorded['signals']}")


def status_suffix(conn, t) -> str:
    """Добавка строки `status` задачи на гейте SPEC — последний вердикт."""
    if t["state"] != "spec_gate":
        return ""
    verdict = last_verdict(conn, t["id"])
    return f"  [аудит SPEC: {verdict}]" if verdict else ""
