"""Пакет orchestrator/doctor -- изоляция пула канарейки от ролей и охват токена.

Коллаборанты читаются лениво через фасад doctor (см. докстринг
orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""
import os

from orchestrator import doctor


# --- изоляция пула канарейки от ролей (SPEC 01M1NEEWH5K1XPFRDGRMPYSBXJ,
#     требование 13) ---------------------------------------------------

def check_role_log_pool_leak(conn) -> doctor.Check:
    """Требование 13б: логи шагов ролей проверяются на упоминание
    каталога пула канарейки — совпадение поднимает incident-алерт
    (AC-15). «На каждом doctor» — буквально из требования; второй
    триггер требования 13б («после каждого прогона канарейки») — часть
    механики `canary`, покрытой отдельно (AC-1..12), не этой проверки.

    Из трёх сигналов утечки, названных требованием 13б (каталог пула,
    имя его репозитория, GUID шаблона), проверяется только каталог пула
    (`config.CANARY_POOL_DIRNAME`) — единственный, зафиксированный кодом
    самого SPEC (требование 1); имя репозитория пула и GUID шаблонов —
    содержимое пула, ручная настройка Оператора («Не входит» SPEC), не
    значение, которое код мог бы знать заранее.

    Не заводит `_auto_ack_gone`, в отличие от `check_orphans`: утечка
    контекста роли — инцидент, требующий разбора Оператором, а не
    состояние, самоустраняющееся ротацией логов (`prune`) без его
    внимания.
    """
    if not doctor.config.LOGS.is_dir():
        return doctor.Check("canary-pool-leak", "ok", "логов ролей ещё нет")
    marker = doctor.config.CANARY_POOL_DIRNAME
    leaking = []
    for path in sorted(doctor.config.LOGS.glob("*.log")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if marker in text:
            leaking.append(path.name)
    if not leaking:
        return doctor.Check("canary-pool-leak", "ok",
                     "логи ролей не упоминают каталог пула канарейки")
    for name in leaking:
        doctor.alerts.raise_alert(
            conn, None, "incident", "doctor.canary-pool-leak",
            f"лог роли {name} упоминает каталог пула канарейки ({marker}) "
            f"— утечка контекста роли (SPEC 01M1NEEWH5K1XPFRDGRMPYSBXJ, "
            f"требование 13б)")
    return doctor.Check("canary-pool-leak", "fail",
                f"логи ролей упоминают каталог пула: {', '.join(leaking)}")


def check_canary_pool_drift() -> doctor.Check:
    """AC-8 (SPEC 01M1NSR5M5THYRC0RFWPMVE2DW, требование 3): предупреждает,
    если открытый пул `~/.artel-canary` разошёлся с запечатанным
    `canary/pool.sealed` — незапечатанные правки Оператора."""
    warning = doctor.canary.pool_drift_warning()
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


