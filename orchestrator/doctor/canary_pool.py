"""Пакет orchestrator/doctor -- изоляция пула канарейки от ролей и охват токена.

Коллаборанты читаются лениво через фасад doctor (см. докстринг
orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""
import os
import re

from orchestrator import doctor


# --- изоляция пула канарейки от ролей (SPEC 01M1NEEWH5K1XPFRDGRMPYSBXJ,
#     требование 13) ---------------------------------------------------

# Лог шага роли — `<task_id>-<role>-<N>.log` (`agent_log.new_agent_log`,
# один адрес на весь пульт). Отбор по ФОРМЕ имени, а не по маске ролей и
# не по формату идентификатора задачи (SPEC 01M3F7BYE82S9AQCBSP1RTQQTR,
# требование 7): роль появляется в `roles.yaml`, id задачи сменил формат
# один раз (T0NN -> ULID) и сменит ещё, а тройка «задача-роль-номер» в
# имени лога не менялась ни разу. Номер прогона — последняя часть, и
# только она обязана быть числом: имя роли само содержит `_`, а бывало бы
# и с дефисом.
_ROLE_LOG_STEM = re.compile(r"^[^-]+-.+-\d+$")

# Запись сессии Оператора — `<что-то>.session.log`
# (docs/backlog.md, строка 3 копилки 21.09: ложные срабатывания шли именно
# с них). Исключается ЯВНО и ДО чтения файла, а не отбрасыванием
# совпадения после: «прочитали и промолчали» — не то же, что «не читаем»,
# и первая же правка условия вернула бы ложные срабатывания.
_SESSION_LOG_SUFFIX = ".session.log"


def _is_role_step_log(name: str) -> bool:
    """Имя файла — лог шага роли, а не запись сессии Оператора и не
    посторонний файл каталога логов."""
    if name.endswith(_SESSION_LOG_SUFFIX):
        return False
    return bool(_ROLE_LOG_STEM.match(name[:-len(".log")]))


def check_role_log_pool_leak(conn) -> doctor.Check:
    """Требование 13б: логи шагов ролей проверяются на упоминание
    каталога пула канарейки — совпадение поднимает incident-алерт
    (AC-15). «На каждом doctor» — буквально из требования; второй
    триггер требования 13б («после каждого прогона канарейки») — часть
    механики `canary`, покрытой отдельно (AC-1..12), не этой проверки.

    Из трёх сигналов утечки, названных требованием 13б (каталог пула,
    имя его репозитория, GUID шаблона), проверяются каталог пула и GUID
    шаблонов (SPEC 01M5KNXGEMBAC1QRNHY3KC14JR): голое имя каталога —
    только в строке вызова инструмента, в прочем тексте — путь в пул
    домашнего каталога; значения меток `canary-guid:` читаются из
    открытого пула вне процесса роли. Имя репозитория пула не
    проверяется.

    Не заводит `_auto_ack_gone`, в отличие от `check_orphans`: утечка
    контекста роли — инцидент, требующий разбора Оператором, а не
    состояние, самоустраняющееся ротацией логов (`prune`) без его
    внимания.

    Читаются ЛОГИ ШАГОВ РОЛЕЙ обоих провайдеров и только они
    (`_is_role_step_log`, SPEC 01M3F7BYE82S9AQCBSP1RTQQTR, требование 7):
    формат содержимого значения не имеет — и строки лога Claude, и JSONL
    `codex exec --json` проверяются одной подстрокой, — а записи сессий
    Оператора (`*.session.log`) не читаются вовсе. До этой правки читался
    каждый `*.log` каталога, и упоминание пула в записи сессии Оператора,
    который пул и заводит, давало ложное срабатывание (docs/backlog.md,
    строка 3 копилки 21.09). Задача, чьи зоны или SPEC называют пул, из
    проверки по-прежнему НЕ исключается (требование 8): предмет отбора —
    имя файла, не задача.
    """
    if not doctor.config.LOGS.is_dir():
        return doctor.Check("canary-pool-leak", "ok", "логов ролей ещё нет")
    marker = doctor.config.CANARY_POOL_DIRNAME
    guids, untagged, guid_note = _pool_template_guids()
    home_sign = _home_path_sign_re()
    leaking, guid_leaking = [], []
    for path in sorted(doctor.config.LOGS.glob("*.log")):
        if not _is_role_step_log(path.name):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if home_sign.search(text) or _tool_call_sign(text):
            leaking.append(path.name)
        if any(value in text for value in guids):
            guid_leaking.append(path.name)
    for name in leaking:
        doctor.alerts.raise_alert(
            conn, None, "incident", "doctor.canary-pool-leak",
            f"лог роли {name} упоминает каталог пула канарейки ({marker}) "
            f"— утечка контекста роли (SPEC 01M1NEEWH5K1XPFRDGRMPYSBXJ, "
            f"требование 13б)")
    for name in guid_leaking:
        doctor.alerts.raise_alert(
            conn, None, "incident", "doctor.canary-pool-leak",
            f"лог роли {name} несёт GUID шаблона пула канарейки ({marker}) "
            f"— утечка контекста роли (SPEC 01M1NEEWH5K1XPFRDGRMPYSBXJ, "
            f"требование 13б)")
    parts = []
    if leaking:
        parts.append(f"логи ролей упоминают каталог пула: {', '.join(leaking)}")
    if guid_leaking:
        parts.append(f"логи ролей несут GUID шаблона пула канарейки: "
                     f"{', '.join(guid_leaking)}")
    if not parts:
        parts.append("логи ролей не упоминают каталог пула канарейки")
    if untagged:
        parts.append(f"шаблоны пула без метки canary-guid: "
                     f"{', '.join(untagged)}")
    if guid_note:
        parts.append(guid_note)
    status = ("fail" if leaking or guid_leaking
              else "warn" if untagged else "ok")
    return doctor.Check("canary-pool-leak", status, "; ".join(parts))


# Признаки утечки по поправке Оператора к ADR-0017 от 23.10.2026 (SPEC
# 01M5KNXGEMBAC1QRNHY3KC14JR, требование 1): голое имя каталога пула несут
# код и документы пульта, поэтому вне строк вызовов инструментов признак —
# только путь именно в пул домашнего каталога.

_GUID_TAG = re.compile(r"canary-guid:[ \t]*(\S*)")
_GUID_TAG_END = "-->"


def _home_path_sign_re() -> re.Pattern:
    """Признаки 1а и 1б одним выражением. Дом берётся в момент проверки:
    `Path.home()` под процессом роли — дом роли (требование 2)."""
    marker = re.escape(doctor.config.CANARY_POOL_DIRNAME)
    home = re.escape(str(doctor.Path.home()))
    pool = re.escape(str(doctor.Path.home() / doctor.config.CANARY_POOL_DIRNAME))
    inside = rf"(?:~|\$HOME|\$\{{HOME\}}|{home})/{marker}/[A-Za-z0-9_]"
    return re.compile(rf"{inside}|{pool}(?![A-Za-z0-9_.-])")


def _tool_call_sign(text: str) -> bool:
    """Признак 1г: имя каталога пула в строке вызова инструмента роли —
    только в строке, НАЧИНАЮЩЕЙСЯ с префикса вызова провайдера."""
    prefixes = tuple({doctor.providers.claude.TOOL_CALL_LINE_PREFIX,
                      doctor.codex_provider.TOOL_CALL_LINE_PREFIX})
    bare = re.compile(re.escape(doctor.config.CANARY_POOL_DIRNAME)
                      + r"(?![A-Za-z0-9_-])")
    return any(line.startswith(prefixes) and bare.search(line)
               for line in text.splitlines())


def _pool_template_guids() -> tuple[list[str], list[str], str]:
    """(значения меток `canary-guid:` шаблонов открытого пула, имена
    шаблонов без непустой метки, пояснение «GUID не сверялись» или "").

    Под процессом роли пул не открывается вовсе — ветка стоит до любого
    обращения к нему (требование 2). Значения наружу не выходят: ими
    только сверяются логи (требование 3)."""
    if doctor.runner.in_role_environment():
        return [], [], "GUID шаблонов не сверялись: процесс роли"
    pool = doctor.Path.home() / doctor.config.CANARY_POOL_DIRNAME
    if not pool.is_dir():
        return [], [], "GUID шаблонов не сверялись: открытый пул не развёрнут"
    guids, untagged = set(), []
    for path in sorted(pool.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        values = {m.group(1).split(_GUID_TAG_END, 1)[0]
                  for m in _GUID_TAG.finditer(text)} - {""}
        if values:
            guids |= values
        else:
            untagged.append(path.name)
    return sorted(guids), untagged, ""


def check_canary_pool_drift() -> doctor.Check:
    """AC-8 (SPEC 01M1NSR5M5THYRC0RFWPMVE2DW, требование 3): предупреждает,
    если открытый пул `~/.artel-canary` разошёлся с запечатанным
    `canary/pool.sealed` — незапечатанные правки Оператора."""
    warning = doctor.pool_seal.pool_drift_warning()
    if warning is None:
        return doctor.Check("canary-pool-drift", "ok",
                     "открытый пул канарейки не расходится с запечатанным "
                     "(либо пул/pool.sealed не развёрнуты)")
    return doctor.Check("canary-pool-drift", "warn", warning)


def check_token_repo_scope() -> list[doctor.Check]:
    """Требование 13в: предупреждает, если токен роли (слот keychain)
    виден более чем в одном репозитории GitHub (AC-16).

    Best-effort: единственный источник истины — реальный охват PAT на
    GitHub прямо сейчас — недетерминирован и недоступен offline
    (`markers.py`, AC-16 этой задачи, тот же класс зависимости, что и
    `check_token_repo_scope`'s собственный сетевой поход) — `gh`/сеть
    недоступны или токен не найден — честный `skip`, не блок доктора.
    Токены дедуплицируются по значению: сегодня (Фаза 0, roles.yaml
    `token_fallback`) все роли падают в один и тот же PAT — опрашивать
    его охват от каждой роли отдельно значило бы платить одним и тем же
    сетевым походом N раз.
    """
    if doctor.shutil.which("gh") is None:
        return [doctor.Check("token-repo-scope", "skip", "gh CLI не найден")]
    try:
        role_names = sorted(
            name for name, entry in doctor.roles.load().items()
            if isinstance(entry, dict) and entry.get("executor") == "agent")
    except doctor.roles.RolesError as exc:
        return [doctor.Check("token-repo-scope", "skip", str(exc))]
    seen: dict = {}
    results = []
    for role in role_names:
        token = doctor.runner.role_token(role)
        if not token or token in seen:
            continue
        seen[token] = role
        try:
            res = doctor.subprocess.run(
                ["gh", "api", "user/repos", "--paginate", "-q",
                 ".[].full_name"],
                env={**os.environ, "GH_TOKEN": token},
                capture_output=True, text=True, timeout=20)
        except (OSError, doctor.subprocess.TimeoutExpired) as exc:
            results.append(doctor.Check("token-repo-scope", "skip",
                                f"роль {role}: {exc}"))
            continue
        if res.returncode != 0:
            results.append(doctor.Check(
                "token-repo-scope", "skip",
                f"роль {role}: область токена не опрошена — "
                f"{res.stderr.strip()[:150]}"))
            continue
        repos = {line.strip() for line in res.stdout.splitlines() if line.strip()}
        if len(repos) > 1:
            results.append(doctor.Check(
                "token-repo-scope", "warn",
                f"роль {role}: токен виден в {len(repos)} репозиториях "
                f"({', '.join(sorted(repos))}) — рекомендуется "
                f"fine-grained токен на один репозиторий (SPEC "
                f"01M1NEEWH5K1XPFRDGRMPYSBXJ, требование 13в)"))
        else:
            results.append(doctor.Check(
                "token-repo-scope", "ok",
                f"роль {role}: токен виден в {len(repos)} репозитории(ях)"))
    return results or [doctor.Check("token-repo-scope", "skip",
                             "ни у одной agent-роли не нашлось токена")]


# --- триггер устаревшего зелёного прогона канарейки (tasks/
#     01M1NGFK3N6MRMYGCC09H975V3/SPEC.md, требования 2-3) -----------------

def check_canary_trigger(conn) -> doctor.Check:
    """AC-3, AC-4 (tasks/01M1NGFK3N6MRMYGCC09H975V3/SPEC.md): триггер
    `kind=trigger, source=canary`, когда число мержей main с последнего
    ЗЕЛЁНОГО прогона канарейки достигает `config.
    CANARY_MAX_MERGES_SINCE_GREEN` (та же арифметика и тот же порог, что
    у guard'а `pin.cmd_pin_update`, AC-1/AC-2 — `canary.
    merges_since_last_green_run`).

    Возраст считается относительно головы `origin/<config.MAIN_BRANCH>`
    (`doctor.fetch_origin_main_sha`, тот же источник, что `canary` по
    умолчанию — SPEC 01M2B6K02YVJBWE1JDWP85EJH0, требование 3/AC-7), НЕ
    относительно `gitcmd.head_sha()` главной копии (пина) — до этой
    задачи было наоборот (ANSWER-1 п.3, «без обращения к сети»,
    инвариант 35 остаётся про сеть в ТЕСТАХ, не про doctor в проде):
    пин мог отставать от `origin/main`, из-за чего этот триггер и
    `pin.cmd_pin_update` сверяли возраст с разными точками истории.
    `fetch` не удался (нет origin, сеть недоступна) — `warn` с текстом
    «сверка с origin невозможна» (тот же приём, что соседний `check_
    pin_unpushed`), НЕ триггер: недоступность origin — это «сверка не
    проведена», не «канарейка устарела».

    Пустой журнал зелёных прогонов — тот же порог, вырожденно всегда
    достигнутый: «канарейка ни разу не прогонялась» (AC-3, второй
    сценарий). Дедуп открытого алерта — заботa `alerts.raise_alert`
    (не дублирует, пока прежний не подтверждён).

    Текст алерта (`alert_message`), участвующий в дедупе, ФИКСИРОВАН —
    не несёт ни текущее число мержей, ни сам sha (REVIEW.md итерации 1,
    R1-F2): `store.open_alert_exists` дедупит строгим совпадением
    `message`, а и возраст, и голова `origin/<MAIN_BRANCH>` меняются с
    каждым следующим мержем main после срабатывания порога — несли бы
    их в тексте, каждый такой мерж заводил бы НОВЫЙ алерт вместо одного,
    ждущего ack Оператора. Конкретные число мержей и sha остаются в
    `Check.detail` (требование 3, AC-7: «текст проверки называет сам
    sha»), который в алерт не идёт.

    Статус `warn`, не `fail` (docs/triggers.md: триггер требует решения
    Оператора с ack'ом, не блокирует прогон doctor как инцидент) — тем же
    приёмом, что и `check_root_pin`: `cmd_doctor` завершается ненулевым
    кодом только на `fail`, а триггер без прогнанной канарейки иначе
    держал бы КАЖДЫЙ прогон doctor красным до первого прогона.
    """
    target_sha, fetch_reason = doctor.fetch_origin_main_sha()
    if not target_sha:
        detail = "сверка с origin невозможна"
        if fetch_reason:
            detail += f": {fetch_reason}"
        return doctor.Check("canary-trigger", "warn", detail)
    age = doctor.canary.merges_since_last_green_run(conn, target_sha)
    if age is None:
        alert_message = ("канарейка ни разу не прогонялась — обновление "
                         "пина заблокировано до первого зелёного прогона "
                         "(tasks/01M1NGFK3N6MRMYGCC09H975V3/SPEC.md)")
        detail = f"{alert_message} (целевой sha {target_sha})"
    elif age >= doctor.config.CANARY_MAX_MERGES_SINCE_GREEN:
        alert_message = ("последний зелёный прогон канарейки устарел (порог "
                         f"{doctor.config.CANARY_MAX_MERGES_SINCE_GREEN} мержей "
                         "main) — пора перепрогнать: artel.py canary --k 1")
        detail = (f"последний зелёный прогон канарейки на sha {target_sha} — "
                 f"{age} мержей main назад (порог "
                 f"{doctor.config.CANARY_MAX_MERGES_SINCE_GREEN}) — пора "
                 f"перепрогнать: artel.py canary --k 1 --sha {target_sha}")
    else:
        return doctor.Check("canary-trigger", "ok",
                     f"последний зелёный прогон канарейки на sha {target_sha} "
                     f"— {age} мержей main назад (порог "
                     f"{doctor.config.CANARY_MAX_MERGES_SINCE_GREEN})")
    doctor.alerts.raise_alert(conn, None, "trigger", "canary", alert_message)
    return doctor.Check("canary-trigger", "warn", detail)


# --- реестр живого прогона канарейки (SPEC 01M5FA4NR91PCF47SZT6V0Q9HS,
#     требование 4) -------------------------------------------------------

CANARY_LIVE_CHECK = "canary-live"


def check_canary_live() -> doctor.Check:
    """Живые прогоны канарейки по реестру. Реестр только читается
    (`canary.registry_view`): мёртвое убирает `doctor --fix`
    (`_fix_canary_live`) или `canary live --drop`, не эта проверка — без
    `--fix` файлы остаются и журнал не растёт. Запись или метка без записи
    старше `CANARY_DRIVE_TIMEOUT_SEC` — `warn`: ведение одной задачи дольше
    не идёт, такой прогон, скорее всего, завис."""
    canary = doctor.canary
    timeout = canary.CANARY_DRIVE_TIMEOUT_SEC
    records, marks = canary.registry_view()
    live, warns = [], []

    def drop_hint(stamp: str) -> str:
        return f'canary live --drop {stamp} "<основание>"'

    for path, entry, why in records:
        stamp = path.name.split("-", 1)[0]
        if why is not None:
            warns.append(f"{path.name}: {why} — убрать: doctor --fix или "
                         f"{drop_hint(stamp)}")
            continue
        age = canary.record_age(entry)
        line = (f"{stamp} на {str(entry.get('sha') or '')[:7]}, "
                f"pid {entry.get('pid')}, возраст {canary.hours_text(age)}")
        if age >= timeout:
            warns.append(f"{line} — дольше {timeout // 3600} ч, снять "
                         f"зависший: {drop_hint(stamp)}")
        else:
            live.append(line)
    for mark in marks:
        stamp = mark["run_stamp"]
        if mark["why"] is not None:
            warns.append(f"{mark['path'].name}: {mark['why']} — убрать: "
                         f"doctor --fix или {drop_hint(stamp)}")
            continue
        line = (f"{stamp} {canary.LIVE_MARK_ABSENT_NOTE}, pid {mark['pid']}, "
                f"возраст {canary.hours_text(mark['age'])}")
        if mark["age"] >= timeout:
            warns.append(f"{line} — дольше {timeout // 3600} ч, снять "
                         f"зависший: {drop_hint(stamp)}")
        else:
            live.append(line)
    if warns:
        return doctor.Check(CANARY_LIVE_CHECK, "warn", "; ".join(warns + live))
    if not live:
        return doctor.Check(CANARY_LIVE_CHECK, "ok",
                            "живых прогонов канарейки нет")
    return doctor.Check(CANARY_LIVE_CHECK, "ok",
                        "живые прогоны канарейки: " + "; ".join(live))


def _fix_canary_live() -> None:
    """`doctor --fix`: мёртвые записи и метки реестра — прежним путём
    чтения реестра (`live_runs`, затем `live_marks`), со строкой журнала
    `LIVE_RUN_SWEPT_ACTION` на каждую."""
    doctor.canary.live_runs()
    doctor.canary.live_marks()


