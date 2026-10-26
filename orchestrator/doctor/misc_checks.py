"""Пакет orchestrator/doctor -- разрозненные проверки: бэкап, счётчики, base-branch, срок токена хостинга.

Коллаборанты читаются лениво через фасад doctor (см. докстринг
orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""
import datetime
import os
import time

from orchestrator import doctor


# --- прочие проверки (требование 9) --------------------------------------

def check_backup_age(conn) -> doctor.Check:
    """Деградировано до информационной строки (SPEC T049, требование 6;
    легализовано ADR-0005 п.3: отдельный бэкап `.artel/` не ведётся —
    сохранность определяется уровнем target'а, не бэкапом пульта).
    Больше не заводит `incident`: маркер, если Оператор всё же его ведёт
    по своей воле, остаётся диагностической строкой, не гейтом. Любой
    открытый алерт этого источника, заведённый ДО этой правки,
    авто-ack'ается — условие, которое его подняло, снято настоящей
    задачей, не наблюдением doctor.
    """
    doctor._auto_ack_gone(conn, "doctor.backup_age", lambda _msg: False)
    marker = doctor.config.BACKUP_MARKER
    if not marker.exists():
        return doctor.Check("backup-age", "ok",
                     "бэкап .artel/ отдельно не ведётся (ADR-0005 п.3) — "
                     "информационно, не гейт")
    age_days = (time.time() - marker.stat().st_mtime) / 86400
    return doctor.Check("backup-age", "ok",
                 f"маркер найден, {age_days:.1f} дн. назад — информационно "
                 f"(ADR-0005 п.3, бэкап .artel/ не обязателен)")


def check_pending_notes() -> doctor.Check:
    """Требование 6 SPEC 01M1VBEHTDYPK3E4RRFHWYYYW3: заметки `note`,
    удержанные из-за сетевого отказа push либо исчерпания повторов
    non-fast-forward (`notes.pending_notes()`), — предупреждение, пока
    Оператор/следующий вызов `note`/`note --flush` не допушит их."""
    pending = doctor.notes.pending_notes()
    if not pending:
        return doctor.Check("pending-notes", "ok", "нет удержанных заметок note")
    return doctor.Check("pending-notes", "warn",
                 f"{len(pending)} удержанных заметок note — "
                 f"artel.py note --flush отправит их в origin")


def check_task_counters(conn) -> doctor.Check:
    """Контур счётчика номеров задач — замороженный legacy (SPEC T094,
    требование 6; ADR-0005 п.5 правки этой же задачи): генератором id
    стал ULID (`orchestrator/idgen.py`), `cmd_new` больше не расходует
    `store.next_task_number` ни для одного target — коллизия номеров,
    которую эта проверка когда-то ловила, для ULID структурно не
    существует. Сверка деградирована до информационной (AC-7): статус
    никогда не `fail`, алерт `doctor.task_counter` не заводится — только
    дословная формулировка «счётчик не движется» в detail.

    Полное удаление самого контура (`task_counters`, `seed_task_counters`,
    `next_task_number`/`peek_task_number`) — отдельная мелочь после M1
    (SPEC «Не входит»); эта функция лишь перестаёт его блокирующе
    сверять. Прежний incident-алерт мог остаться открытым от прогона
    до этой задачи — авто-ack безусловно закрывает его (условие
    «ещё живо» теперь всегда `False`).
    """
    try:
        declared = doctor.targets.load()
    except doctor.targets.TargetsError:
        declared = {}
    checked_targets = ({doctor.config.DEFAULT_TARGET} | doctor.store.counter_targets(conn)
                       | set(declared))
    for target in sorted(checked_targets):
        doctor._auto_ack_gone(conn, "doctor.task_counter", lambda _msg: False,
                      target=target)
    return doctor.Check("task-counters", "ok",
                 "счётчик номеров задач заморожен как legacy (ULID — "
                 "основной генератор, SPEC T094) — счётчик не движется")


def gh_env(name: str, entry: dict) -> tuple[dict | None, str | None]:
    """(окружение, отказ) прямого вызова `gh` проекта `name`: `None`
    окружения — окружение процесса, прежняя авторизация (артель, запись
    без `token_slot`); иначе — с `GH_TOKEN` слота проекта."""
    token, refusal = doctor.gitcmd.hosting_token(name, entry)
    if refusal is not None or token is None:
        return None, refusal
    return dict(os.environ, GH_TOKEN=token), None


def check_base_branch(name: str, entry: dict) -> doctor.Check:
    """Сверка базовой ветки/merge-политики — по возможностям forge, иначе
    честный skip с причиной (SPEC требование 9 явно это допускает).
    Единая логика для ЛЮБОГО объявленного target, включая артель (A7,
    требование 2, AC-2).

    `gh` внешнего проекта — с токеном слота `token_slot` его записи
    (`gh_env`, SPEC 01M545EDTHS47HSB59AKC1EZ9C, требование 1).

    Реализация хостинга — из реестра `forge` по полю `forge` записи (SPEC
    01M5WCXBR9K8CN586W1AP3ZN6Q, требование 1): у реализации со сведениями
    проекта (`project_info`) база сверяется с её `default_branch`, у
    реализации без них — прежним `gh repo view`."""
    implementation = _forge_implementation(entry)
    if implementation is None:
        return doctor.Check("base-branch", "skip",
                     f"forge {entry.get('forge')} — сверка не реализована")
    if hasattr(implementation, "project_info"):
        return _base_branch_by_project_info(name, entry)
    gh = doctor.shutil.which("gh")
    if gh is None:
        return doctor.Check("base-branch", "skip", "gh CLI не найден — сверка пропущена")
    env, refusal = gh_env(name, entry)
    if refusal is not None:
        return doctor.Check("base-branch", "skip", refusal)
    try:
        res = doctor.subprocess.run(
            ["gh", "repo", "view", entry["url"], "--json", "defaultBranchRef",
             "-q", ".defaultBranchRef.name"],
            capture_output=True, text=True, timeout=doctor.config.GH_TIMEOUT_SEC,
            env=env)
    except (OSError, doctor.subprocess.TimeoutExpired) as exc:
        return doctor.Check("base-branch", "skip", f"gh не ответил: {exc}")
    if res.returncode != 0:
        return doctor.Check("base-branch", "skip",
                     f"gh repo view отказал: {res.stderr.strip()[:200]}")
    remote_base = res.stdout.strip()
    if not remote_base:
        return doctor.Check("base-branch", "skip", "gh не вернул defaultBranchRef")
    if remote_base != entry["base"]:
        return doctor.Check("base-branch", "warn",
                     f"targets.yaml base={entry['base']!r}, у форджа "
                     f"{remote_base!r}")
    return doctor.Check("base-branch", "ok", f"база сходится: {remote_base}")


def _forge_implementation(entry: dict):
    """Реализация хостинга записи из реестра `forge`; `None` — значения
    поля `forge` в реестре нет."""
    return doctor.forge.IMPLEMENTATIONS.get(entry.get("forge"))


def _base_branch_by_project_info(name: str, entry: dict) -> doctor.Check:
    """Сверка базы записи с `default_branch` проекта у хостинга; причина
    адаптера (нет токена, ошибка HTTP, сеть, адрес) — `skip` с ней."""
    info = doctor.forge.project_info(name)
    if info.reason:
        return doctor.Check("base-branch", "skip",
                            f"сверка базы пропущена: {info.reason}")
    if not info.default_branch:
        return doctor.Check("base-branch", "skip",
                            "хостинг не вернул ветку проекта по умолчанию")
    if info.default_branch != entry.get("base"):
        return doctor.Check("base-branch", "warn",
                            f"targets.yaml base={entry.get('base')!r}, у форджа "
                            f"{info.default_branch!r}")
    return doctor.Check("base-branch", "ok", f"база сходится: {info.default_branch}")


def check_token_expiry(conn, name: str, entry: dict) -> doctor.Check | None:
    """Строка `token-expiry-<проект>` — срок токена хостинга (SPEC
    01M5WCXBR9K8CN586W1AP3ZN6Q, требование 2); `None` — у реализации
    хостинга записи срока токена нет, строки нет вовсе.

    Срок через `TOKEN_EXPIRY_WARN_DAYS` дней реализации или раньше —
    `warn`. Токен без срока — информационная строка, пока задач проекта в
    БД пульта (кроме `killed`) меньше `TOKEN_NO_EXPIRY_TASKS_WARN`, затем
    `warn`: бессрочный токен с правом записи — тем больший риск, чем
    больше проект ведётся пультом. Нет токена или запрос не удался —
    `skip` с причиной адаптера (Н-4 родительской задачи): строка
    диагностическая и не должна краснеть от сети."""
    implementation = _forge_implementation(entry)
    if not hasattr(implementation, "token_expiry"):
        return None
    check_name = f"token-expiry-{name}"
    expiry = doctor.forge.token_expiry(name)
    if expiry.reason:
        return doctor.Check(check_name, "skip",
                            f"проект {name}: срок токена не прочитан — {expiry.reason}")
    if expiry.expires_at is None:
        tasks = sum(1 for row in doctor.store.project_tasks(conn, name)
                    if row["state"] != "killed")
        limit = implementation.TOKEN_NO_EXPIRY_TASKS_WARN
        status = "warn" if tasks >= limit else "ok"
        return doctor.Check(check_name, status,
                            f"проект {name}: токен без срока; задач проекта "
                            f"{tasks} (порог {limit}) — бессрочный токен "
                            f"стоит заменить токеном со сроком")
    days = (expiry.expires_at - datetime.date.today()).days
    limit = implementation.TOKEN_EXPIRY_WARN_DAYS
    if days < 0:
        return doctor.Check(check_name, "warn",
                            f"проект {name}: срок токена истёк "
                            f"{expiry.expires_at.isoformat()}")
    if days <= limit:
        return doctor.Check(check_name, "warn",
                            f"проект {name}: токен истекает "
                            f"{expiry.expires_at.isoformat()}, через {days} дн. "
                            f"(порог {limit}) — выпусти новый")
    return doctor.Check(check_name, "ok",
                        f"проект {name}: токен действует до "
                        f"{expiry.expires_at.isoformat()}, через {days} дн.")
