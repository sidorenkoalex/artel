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


