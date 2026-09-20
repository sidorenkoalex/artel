"""Запуск агента шага: промпт роли, окружение, попытки, исход, стоимость.

Классификация ошибок попытки — `orchestrator/failure_classification.py`;
WIP-чекпоинты рабочего дерева — `orchestrator/checkpoint.py`; сборка
миссии/брифа/ревью-пакета роли — `orchestrator/role_prompt.py` (T091,
декомпозиция диспетчеров fsm/runner). Здесь остаются запуск процесса
агента, окружение/cwd/argv шага и сам цикл попыток `cmd_run`.
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import (agent_log, alerts, brief, budget, checkpoint, config,
              failure_classification, fixation, gitcmd, keychain, lease,
              liveness, parallel_limit, pause, review, role_prompt, roles,
              spend, stack, store, workspace, zone_lock)

# Идентичность коммитера, которую роль обязана унести с собой в свой HOME.
# git читает эти переменные ПОВЕРХ конфига, поэтому перенос ровно двух пар
# возвращает шагу авторство, не втаскивая в него остальной user-слой
# Оператора: ни его алиасов, ни его хуков, ни его includeIf.
GIT_IDENTITY = (
    ("user.name", ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME")),
    ("user.email", ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL")),
)


# Стоп-кран волны, часть 2 (01M1THKRK8HPXA7Y2SRB0RFTN2, требования 1, 5):
# текст action записи журнала, которым `auto._run_wave_breaker_refusal`
# узнаёт, что ИМЕННО этот вызов `_cmd_run` отказал по открытому алерту
# стоп-крана — не по одновременному отказу бюджета/лимита/паузы/занятости
# зоны (тот же приём отсечки, что уже несёт `pause.REFUSAL_ACTION`).
WAVE_BREAKER_REFUSAL_ACTION = "run отклонён: стоп-кран волны"


def wave_breaker_alerts_open(conn) -> list:
    """Открытые алерты `kind=incident` стоп-крана волны target self
    (`alerts.WAVE_BREAKER_SOURCE`, `target=config.DEFAULT_TARGET`) —
    заводит часть 1 (`alerts.check_wave_breaker_failure`/
    `check_wave_breaker_timeout`), читает часть 2 (это SPEC): отказ
    старта шага здесь (требование 1), первая строка вывода `doctor`
    (требование 3) и пометка `status` (требование 4) — один и тот же
    критерий «алерт открыт» в трёх разных командах, поэтому общая
    функция вместо трёх копий фильтра."""
    return [row for row in alerts.open_alerts(conn, "incident")
           if row["target"] == config.DEFAULT_TARGET
           and row["source"] == alerts.WAVE_BREAKER_SOURCE]


def _attempts_word(n: int) -> str:
    """Русское числительное «попытка» в форме, согласованной с {n} (ревью
    T082 итерации 1, замечание minor): класс 2 (session limit) обрывает
    цикл на attempt=1 (требование 4), и «за 1 попытки» — не по-русски."""
    if 11 <= n % 100 <= 14:
        return "попыток"
    last = n % 10
    if last == 1:
        return "попытку"
    if 2 <= last <= 4:
        return "попытки"
    return "попыток"


def spawn_agent(cmd: list[str], **kwargs) -> subprocess.Popen:
    """cli-вызов агента шага — тонкая обёртка над `subprocess.Popen`.

    По образцу `gitcmd.git`/`keychain.token`: отдельная точка мокинга в
    тестах вместо прямой подмены `subprocess.Popen` (модуль общий на
    процесс — подмена ловила бы и системные вызовы вне запуска агента,
    SPEC T037, требование 2).

    Новая сессия (SPEC 01M1PNBSHR2PMFECMP7C204MF1, AC-1): агентный
    процесс становится лидером собственной группы (`pgid == pid`), а не
    наследует pgid пульта — таймаут шага/`kill`/`pause --now`/`release`
    (требование 2) бьют её целиком (`os.killpg`), включая
    `pytest`/`unittest`, запущенные ролью и переходящие под launchd при
    обычном `subprocess.Popen` без своей группы (инцидент 04.09, SPEC
    «Контекст»). `setdefault` — явный `start_new_session` вызывающего
    кода (если он вообще появится) сильнее дефолта этой обёртки.
    """
    kwargs.setdefault("start_new_session", True)
    return subprocess.Popen(cmd, **kwargs)


def step_role(t) -> str | None:
    """Роль текущего шага задачи; None — состояние не агентское.

    `spec_writing` сознательно не входит в `config.STATE_ROLE` статически
    (SPEC T025, требование 1 — обратная совместимость): задача без
    `tasks/<id>/TZ.md` обязана жить прежним флоу («SPEC пишет Оператор»),
    и `run`/`auto` не имеют права ни разу попытаться запустить агента
    просто потому, что кто-то добавил запись в общий словарь состояний.
    Роль `analyst` подключается только когда `TZ.md` реально лежит
    в задаче; при отсутствии файла функция ведёт себя так же, как и до
    этой задачи (роли нет). Единственная точка резолвинга, которую зовут
    и `cmd_run`, и `auto.cmd_auto` (`STATE_ROLE`/`AUTO_STOP` как словари
    при этом не трогаются — их читают `test_invariants.FsmStatesCoverTheCodeTest`
    и `test_auto_cycle.*` буквально по ключам).

    Наличие `TZ.md` определяется ветко-корректно (SPEC T048, требование 7
    — тот же класс, что уже закрыт для статусов SPEC/REVIEW/QUESTIONS,
    T031/T047): `cmd_new` с этой задачи коммитит TZ.md сразу в ветку, не
    на диск main (требование 4), так что на чужой ветке (`gitcmd.
    on_foreign_branch`) файл ищется В НЕЙ (`gitcmd.show`), а не в
    `config.TASKS` — иначе только что заведённая ролью задача выглядела
    бы так, будто ТЗ не было вовсе. Иначе (своя ветка уже выписана; ветка
    ещё не создана; git не ответил) — прежнее поведение, диск: тот же
    вырожденный случай, на котором стоит весь стенд заглушек `gitcmd.git`.

    ДОБАВЛЕНО (SPEC 01M1KT0792125J9ZNJNZJ86E9Q, требование 1): проверка
    выше не видит TZ.md, лежащий в АРТЕФАКТНОЙ ветке пульта
    (`artifact_source.resolve`) — у задачи, заведённой `cmd_new --tz`
    после A7, кодовой ветки `t["branch"]` в git ещё нет вовсе (первый шаг
    роли её ещё не создал), и старая проверка молчит «ТЗ не заведён»,
    хотя `cmd_new` реально закоммитил TZ.md в артефактную ветку. Читается
    ПЕРВОЙ, поверх старой проверки (не вместо неё) — задача прежнего
    флоу, чей TZ.md лежит только в кодовой ветке (AC-2), обязана
    по-прежнему находиться старым путём ниже.
    """
    role = config.STATE_ROLE.get(t["state"])
    if role is not None:
        return role
    if t["state"] != "spec_writing":
        return None
    from . import artifact_source
    artifact_branch_name, foreign = artifact_source.resolve(store.db(), t["id"])
    if foreign:
        tz_text, _ = gitcmd.show(artifact_branch_name, f"tasks/{t['id']}/TZ.md")
        if tz_text is not None:
            return "analyst"
    branch = t["branch"]
    if gitcmd.on_foreign_branch(branch):
        tz_text, _ = gitcmd.show(branch, f"tasks/{t['id']}/TZ.md")
        has_tz = tz_text is not None
    else:
        has_tz = (config.TASKS / t["id"] / "TZ.md").exists()
    return "analyst" if has_tz else None


def cmd_run(task_id: str, session_id: str | None = None) -> None:
    """Запуск агента текущего шага (claude CLI, headless).

    Берёт lease задачи перед работой (SPEC T044, требование 2) — обёртка
    вокруг `_cmd_run`, см. `orchestrator/lease.py`.

    Префикс -> полный id (SPEC T094, требование 3, AC-3) резолвится ЗДЕСЬ,
    до lease (REVIEW T094 итерация 1, замечание 1).
    """
    conn = store.db()
    task_id = store.resolve_task_id(conn, task_id)
    lease.run_locked(conn, task_id, session_id,
                     lambda sid: _cmd_run(conn, task_id))


def _cmd_run(conn, task_id: str) -> None:
    t = store.get_task(conn, task_id)
    # Бюджет проверяем до всего остального: потраченные деньги не зависят от
    # состояния задачи, а из escalated Оператор её вернуть уже мог.
    blocked = budget.budget_block(t)
    if blocked is not None:
        sys.exit(blocked)

    # Лимитер параллельных задач (SPEC T060, требования 2-4): общесистемный
    # потолок слотов, не зависящий от состояния/роли этой задачи — той же
    # природы, что и бюджет выше, поэтому проверяется тем же местом, до
    # резолвинга роли. В отличие от budget_block (журналируется только
    # изнутри auto.auto_stop), отказ журналируется здесь явно: требование
    # 3 обязывает журнал и для одиночного `run`, не только для `auto`.
    limit_refusal = parallel_limit.refusal(conn, task_id)
    if limit_refusal is not None:
        store.journal(conn, task_id, "fsm",
                      "run отклонён: лимит параллельных задач", limit_refusal)
        sys.exit(limit_refusal)

    role = step_role(t)
    if role is None:
        if t["state"] == "spec_writing":
            sys.exit(f"[{task_id}] SPEC пишет Оператор — TZ.md не заведён "
                     f"(`new \"...\" --tz <файл>` заведёт роль analyst)")
        sys.exit(f"[{task_id}] в состоянии {t['state']} агент не запускается")

    # Занятость зоны на старте кода (SPEC 01M1P9QAG65GVF69YJEV0V18D9,
    # требование 1): `STATE_ROLE` отображает `in_dev` исключительно на
    # `developer` (`config.py`), поэтому `role == "developer"` здесь
    # эквивалентно `t["state"] == "in_dev"` — единственная фаза, где
    # действует этот отказ. Тот же `sys.exit`, что и бюджет/лимит
    # параллельных задач выше: `auto` ловит `SystemExit` немедленно.
    #
    # Проверка и захват — одной транзакцией (SPEC 01M28NWPS3PJHJAT4APXRY7MF7,
    # требование 1, AC-1): `zone_lock.claim` журналирует `zone claimed` ДО
    # того, как эта функция дойдёт до сборки промпта/окружения и запуска
    # агента — закрывает гонку двух параллельных `cmd_run`, раньше
    # проверявших конфликт секундами раньше фактической записи занятости
    # (SPEC «Контекст»). `claim_pending` — записан ли захват ИМЕННО этим
    # вызовом (не унаследован от уже идущей занятости этой же задачи в
    # текущем пребывании) — используется ниже, чтобы решить, снимать ли
    # его (требование 2, AC-2/AC-3).
    claim_pending = False
    if role == "developer":
        zone_refusal, claim_pending = zone_lock.claim(conn, task_id, t)
        if zone_refusal is not None:
            store.journal(conn, task_id, role, zone_lock.REFUSAL_ACTION,
                          zone_refusal)
            sys.exit(zone_refusal)

    try:
        _run_developer_step(conn, task_id, t, role)
    finally:
        # Захват снимается, только если он записан ЭТИМ вызовом и шаг не
        # довёл дело до фактического старта агента (требование 2, AC-2/
        # AC-3) — покрывает ЛЮБОЙ путь возврата ниже (sys.exit паузы/
        # стоп-крана, return workspace/pre-flight/фиксации, sys.exit
        # несобранных скилов, «skipped»-исход run_agent_once до записи
        # «agent run started»), не требуя чинить каждый путь отдельно.
        # Задача, уже занимавшая зону раньше в этом пребывании
        # (`claim_pending is False`), не трогается — её occupancy не от
        # этого захвата, снимать нечего.
        if claim_pending and zone_lock.claimed_but_not_started(conn, task_id):
            zone_lock.release_claim(conn, task_id)


def _run_developer_step(conn, task_id: str, t, role: str) -> None:
    """Тело шага ПОСЛЕ прохождения занятости зоны — пауза, стоп-кран
    волны, workspace, pre-flight, фиксация, сборка промпта, попытки
    агента. Вынесено из `_cmd_run` отдельной функцией (SPEC
    01M28NWPS3PJHJAT4APXRY7MF7, требование 2), чтобы та могла обернуть
    вызов `try/finally` и снять атомарный захват зоны (`zone_lock.
    release_claim`), если шаг вернётся отсюда, не запустив агента —
    независимо от конкретного места возврата ниже.

    Разбито на фазы `_refuse_before_start`/`_build_prompt`/`_run_attempts`/
    `_escalate_after_attempts` (SPEC 01M2CN3ZCSZ54TFJGTDCXTDHXD, AC-4):
    `sys.exit`/`return` отказов до старта остаются текстом здесь же
    (AC-5) — `_refuse_before_start` только вычисляет, какой из них нужен.
    """
    action, payload = _refuse_before_start(conn, task_id, t, role)
    if action == "exit":
        sys.exit(payload)
    if action == "return":
        return
    target, skills, model_id = payload

    prompt = _build_prompt(conn, task_id, t, role, target, skills)

    attempt, reason, failure_class = _run_attempts(conn, task_id, t, role,
                                                    prompt)
    if attempt is None:
        return

    if failure_class == failure_classification.MODEL_UNSUPPORTED_CLASS:
        # Тот же именованный отказ, что у предполётной сверки (SPEC
        # 01M2XJKV84SQ9VEVR0VNVKDNGJ, требование 4): задача остаётся в
        # своём состоянии, `auto` останавливается текстом с подсказкой.
        sys.exit(_model_unsupported_after_attempt(conn, task_id, role,
                                                  model_id, reason))

    _escalate_after_attempts(conn, task_id, t, role, target, attempt,
                             reason, failure_class)


def _refuse_before_start(conn, task_id: str, t, role: str):
    """Отказы шага до старта агента: пауза, стоп-кран волны, чужая ветка
    worktree, pre-flight, инцидент целостности, скилы и модель роли (SPEC
    01M2CN3ZCSZ54TFJGTDCXTDHXD, AC-5; SPEC 01M2DTT96FS25SHXP0HDTWARQH,
    требования 1-2, 4). Журнал/консоль/`set_state` — те же побочные
    эффекты, что раньше стояли прямо в `_run_developer_step`; сам
    `sys.exit`/`return` остаётся за вызывающим кодом — эта функция
    возвращает признак: `("exit", message)`, `("return", None)` или
    `("continue", (target, skills, model_id))`."""
    # Штатная пауза (SPEC T070, требование 2): пометка стоит — шаг не
    # начинается, но уже идущий шаг (эта же функция, стартовавшая раньше)
    # эта проверка не трогает — она стоит строго до всего, что реально
    # запускает агента (workspace, pre-flight, spawn), поэтому не может
    # оборвать процесс, стартовавший до постановки паузы (AC-3). Отказ —
    # `sys.exit`, тем же приёмом, что и бюджет/лимит параллельных задач
    # выше: `auto` ловит `SystemExit` и останавливает цикл немедленно,
    # вместо того чтобы прокручивать шаги до `AUTO_MAX_STEPS`, принимая
    # отказ паузы за «шаг ещё не готов, продолжай».
    if pause.is_paused(t):
        detail = (f"задача на паузе — следующий агентный шаг не "
                  f"начинается; `artel.py resume {task_id}` снимет пометку")
        store.journal(conn, task_id, role, pause.REFUSAL_ACTION, detail)
        return "exit", f"[{task_id}] run отклонён: {detail}"

    # Стоп-кран волны, часть 2 (01M1THKRK8HPXA7Y2SRB0RFTN2, требования 1,
    # 5): тем же приёмом, что и штатная пауза выше — стоит строго до
    # workspace/pre-flight/spawn, уже идущий шаг не трогает (AC-1). Только
    # target self — задачи любого другого target не блокируются вовсе
    # (требование 5, AC-7): `wave_breaker_alerts_open` уже фильтрует по
    # `target=config.DEFAULT_TARGET` со стороны алерта, здесь проверяем
    # ЭТУ задачу тем же критерием, чтобы внешний target не заходил в блок.
    if (t["target"] or config.DEFAULT_TARGET) == config.DEFAULT_TARGET:
        wave_breaker_alerts = wave_breaker_alerts_open(conn)
        if wave_breaker_alerts:
            names = "; ".join(f"#{a['id']} {a['message']}"
                              for a in wave_breaker_alerts)
            detail = (f"открыт алерт(ы) стоп-крана волны ({names}) — новый "
                      f"агентный шаг не начинается; "
                      f"`artel.py alert-ack <id> \"...\"` снимет блокировку")
            store.journal(conn, task_id, role,
                          WAVE_BREAKER_REFUSAL_ACTION, detail)
            return "exit", f"[{task_id}] run отклонён: {detail}"

    target = t["target"] or config.DEFAULT_TARGET

    # Рабочая поверхность агентного шага (SPEC T045, требование 3, AC-8,
    # сценарий 1): worktree задачи уже есть, но стоит не на её ветке —
    # кто-то переключил его руками. Отказ до старта агента вместо попытки
    # самому починить рабочую поверхность или молча стартовать на чужой
    # ветке. Worktree ещё не заведён (`None`) — сверять не с чем: его
    # заведёт `role_cwd` через `workspace.ensure` на правильной ветке.
    if target == config.DEFAULT_TARGET:
        on_branch = workspace.on_task_branch(task_id, t["branch"])
        if on_branch is False:
            wt = workspace.path(task_id)
            detail = (f"{wt} стоит не на ветке задачи {t['branch']} — шаг "
                      f"не начат; перейди в worktree на свою ветку либо "
                      f"разберись, кто её переключил, и повтори run")
            store.journal(conn, task_id, role,
                          "run отклонён: чужая ветка worktree", detail)
            print(f"[{task_id}] run отклонён: {detail}")
            return "return", None

    # Pre-flight перед стартом шага (SPEC T022, требование 2): быстрые
    # проверки окружения (CLI найден, токен роли добыт, диск, layout
    # внешнего target'а) — до git-сверки и до попыток агента, отдельным
    # модулем (ADR-0003 3ж — «одна проверка, одно место»; отложенный
    # импорт по тому же приёму, что store.record_fixation берёт fixation:
    # doctor читает runner по имени, runner не должен знать о doctor
    # на уровне модуля). Провал — шаг не начат, без ретрая, с именованной
    # причиной. Версия CLI ≠ пин — предупреждение, не блок (требование 5).
    from . import doctor
    preflight = doctor.preflight_checks(role, target)
    for check in preflight:
        if check.status == "warn":
            detail = f"{check.name}: {check.detail}"
            store.journal(conn, task_id, role, "pre-flight WARNING", detail)
            print(f"[{task_id}] ВНИМАНИЕ: {detail}")
    failed = [c for c in preflight if c.status == "fail"]
    if failed:
        reason = "; ".join(f"{c.name}: {c.detail}" for c in failed)
        store.journal(conn, task_id, role, "pre-flight FAILED", reason)
        print(f"[{task_id}] pre-flight провален — шаг не начат: {reason}")
        return "return", None

    # Сверка при старте каждого шага (ADR-0003 п.17, SPEC T021 требование
    # 5): вход шага сравнивается с sha, зафиксированным на последнем
    # переходе FSM. Расхождение или грязная копия артефактов — инцидент
    # целостности, задача останавливается эскалацией, агент не стартует
    # (закрытие TOCTOU между approve и стартом шага).
    incident = fixation.check_integrity(conn, task_id)
    if incident is not None:
        store.update_task(conn, task_id, escalated_from=t["state"])
        store.set_state(conn, task_id, "escalated", "fsm",
                        expected_state=t["state"],
                        detail=f"инцидент целостности: {incident}")
        print(f"[{task_id}] СТОП: инцидент целостности — {incident}")
        # Sha, перефиксированный только что этим же set_state (SPEC
        # «approve: полный sha в подсказках», требование 1) — готовое к
        # копированию значение вместо литерального плейсхолдера `<sha>`,
        # который Оператору иначе пришлось бы искать самому.
        sha_hint = fixation.approve_sha_hint(task_id, target)
        print(f"  разберись и: artel.py approve {task_id}{sha_hint}")
        return "return", None

    # Состав скилов роли — из roles.yaml, а не из константы рядом с кодом:
    # правка карты исполнителей меняет промпт без правки кода (T017,
    # требование 1). Отказы обеих чтений называются причиной: шаг не
    # начинается, но Оператор видит, что именно чинить.
    #
    # Текст самих скилов — с ГОЛОВЫ ветки `main`, не с диска рабочей копии
    # `config.ROOT` (tasks/01M1K7KP0D8ZKRM9KTE75DCCYR, AC-1/AC-6): скилы —
    # правило системы, роль обязана видеть версию, действующую в `main`
    # СЕЙЧАС, а не ту, что была на момент отведения ветки задачи (ADR-0012,
    # замечание R1-F3) — `brief.skills_text`, тот же приём, что инвариант
    # 28 применяет к артефактам задачи, с обратным адресом.
    try:
        skill_names = roles.skills(role)
    except roles.RolesError as exc:
        return "exit", (f"[{task_id}] состав скилов роли {role} не "
                        f"прочитан: {exc}")
    skills, reason = brief.skills_text(conn, task_id, role, skill_names)
    if skills is None:
        return "exit", f"[{task_id}] скил роли {role} не прочитан: {reason}"

    # Модель роли из roles.yaml (SPEC 01M2DTT96FS25SHXP0HDTWARQH, требования
    # 1-2, 4): тем же приёмом отказа, что skills выше — нечитаемое значение
    # поля (не строка/пустая строка) останавливает шаг, вместо того чтобы
    # молча дотянуть до попытки агента. Поле не задано (`None`) — не отказ:
    # ровно одна запись предупреждения в журнал ЭТОГО шага (не на попытку —
    # `run_agent_once` резолвит модель заново для argv/журнала записей
    # попытки, но не журналирует предупреждение повторно), команда идёт без
    # `--model` (требование 3).
    try:
        model_id = roles.model(role)
    except roles.RolesError as exc:
        return "exit", f"[{task_id}] модель роли {role} не прочитана: {exc}"
    if model_id is None:
        store.journal(conn, task_id, role, "model WARNING",
                      "модель роли не задана — дефолт CLI")
    else:
        # Предполётная сверка модели с версией CLI (SPEC
        # 01M2XJKV84SQ9VEVR0VNVKDNGJ, требование 3, AC-6..AC-8) — ДО
        # сборки промпта и первой попытки: отказ детерминирован, повторы и
        # эскалация его не лечат (инцидент 19.09 — три попытки по 120 с за
        # 0 токенов). `claude --version` зовётся только для модели из
        # таблицы: модели вне её версия не нужна — одна запись
        # предупреждения на шаг и запуск как сегодня. `sys.exit` — тем же
        # приёмом, что пауза/стоп-кран выше: `auto` ловит `SystemExit`,
        # печатает текст (с подсказкой из самого отказа) и останавливает
        # цикл, не прокручивая шаги до `AUTO_MAX_STEPS`.
        installed = (stack.installed_cli_version()
                     if model_id in stack.MODEL_MIN_CLI_VERSION else None)
        verdict = stack.model_cli_verdict(model_id, installed)
        if verdict.status == "fail":
            return "exit", _model_refusal_exit(conn, task_id, role,
                                               verdict.detail)
        if verdict.status == "warn":
            # Только журнал, без консоли — тем же приёмом, что «модель
            # роли не задана» выше: модели вне таблицы — штатный случай
            # (таблицу пополняет Оператор), строка на каждый шаг в stdout
            # была бы шумом раньше пути лога шага.
            store.journal(conn, task_id, role, "model WARNING",
                          f"{model_id}: {verdict.detail}")

    return "continue", (target, skills, model_id)


# Действие записи журнала отказа «модель не поддерживается CLI» (SPEC
# 01M2XJKV84SQ9VEVR0VNVKDNGJ, требования 3-4): одно и то же для
# предполётного отказа и отказа после попытки — тот же приём именованного
# отказа, что `pause.REFUSAL_ACTION`/`WAVE_BREAKER_REFUSAL_ACTION`.
MODEL_UNSUPPORTED_REFUSAL_ACTION = "run отклонён: модель не поддерживается CLI"


def _model_refusal_exit(conn, task_id: str, role: str, detail: str) -> str:
    """Журнал + текст `sys.exit` именованного отказа шага по модели роли:
    `detail` уже несёт префикс `stack.MODEL_UNSUPPORTED_PREFIX`, модель,
    обе версии и подсказку `stack.CLI_UPGRADE_HINT` — `auto` печатает
    ровно этот текст, останавливая цикл (AC-7)."""
    store.journal(conn, task_id, role, MODEL_UNSUPPORTED_REFUSAL_ACTION, detail)
    return f"[{task_id}] run отклонён: {detail}"


def _model_unsupported_after_attempt(conn, task_id: str, role: str,
                                     model_id: str | None,
                                     reason: str) -> str:
    """Отказ шага после попытки класса «модель не поддерживается CLI»
    (SPEC 01M2XJKV84SQ9VEVR0VNVKDNGJ, требование 4, AC-9) — тот же
    именованный исход, что и у предполётной сверки, для модели, которой
    в таблице нет (или чья запись занижена): требуемая версия — из
    текста попытки («version X or newer is required»), установленная —
    тем же `claude --version`, что и предполёт."""
    required = failure_classification.required_cli_version(reason)
    installed = stack.installed_cli_version()
    detail = (f"{stack.MODEL_UNSUPPORTED_PREFIX}: "
              f"{_model_journal_label(model_id)} — CLI отверг модель в "
              f"попытке агента («{failure_classification.MODEL_UNSUPPORTED_SIGNATURE}»)")
    if required is not None:
        detail += f", требует claude ≥ {required}"
    if installed is not None:
        detail += f", установлен {stack.version_text(installed)}"
    detail += f"; {stack.CLI_UPGRADE_HINT}"
    if model_id is not None and model_id not in stack.MODEL_MIN_CLI_VERSION:
        detail += (f"; {stack.MODEL_NOT_IN_TABLE_WARNING} — запись в "
                   f"stack.MODEL_MIN_CLI_VERSION остановит следующий такой "
                   f"шаг до запуска агента")
    return _model_refusal_exit(conn, task_id, role, detail)


def _build_prompt(conn, task_id: str, t, role: str, target: str,
                  skills: str) -> str:
    """Сборка промпта шага: бриф/миссия/ревью-пакет и история отказов
    advance (SPEC 01M2CN3ZCSZ54TFJGTDCXTDHXD, AC-4) — перенесённое
    дословно тело `_run_developer_step` между чтением скилов и циклом
    попыток."""
    cwd_for_prompt = role_cwd_path(task_id, target)
    mission, brief_text, package = role_prompt.mission_brief_package(
        conn, task_id, t, role, cwd_for_prompt)
    prompt = f"{mission}\n\n--- СКИЛЫ РОЛИ ---\n\n{skills}"
    if brief_text is not None:
        prompt = f"{prompt}\n\n{brief_text}"
    if package is not None:
        # Размер входа — в журнал до первой попытки: стоимость прогона потом
        # сопоставляется именно с ним (SPEC T011, 5).
        store.journal(conn, task_id, role, "ревью-пакет собран",
                      review.package_note(package))
        print(f"[{task_id}] ревью-пакет: {review.package_note(package)}")
        # Требование 3 (tasks/01M1P9RJVYHTAC087J4B2CAR44): «diff не
        # собран» на итерации > 1 — алерт Оператору, не тихая строка
        # журнала; на итерации 1 `not_collected` штатно пуст (полный diff
        # всегда собирается), алерт не заводится и не трогается вовсе.
        if package["iteration"] > 1:
            if package["not_collected"]:
                alerts.raise_diff_not_collected_alert(
                    conn, task_id, package["not_collected"])
            else:
                alerts.close_diff_not_collected_alerts(conn, task_id)
        prompt = f"{prompt}\n\n--- РЕВЬЮ-ПАКЕТ ---\n\n{package['text']}"

    # Отказ advance доносится до следующего запуска роли (SPEC T078):
    # одна точка для всех ролей — механика не зависит от того, какая
    # роль читает бриф в этом состоянии, только от того, есть ли у
    # ТЕКУЩЕГО визита состояния своя история отказов (пусто — прежний
    # промпт без изменений, требование 5).
    refusal_block = brief.advance_refusal_history(conn, task_id, role,
                                                   t["state"])
    if refusal_block:
        prompt = f"{prompt}\n\n--- ОТКАЗ ADVANCE (история) ---\n\n{refusal_block}"

    return prompt


def _run_attempts(conn, task_id: str, t, role: str, prompt: str):
    """Цикл попыток агента: `run_agent_once` + бэкофф между попытками
    (SPEC 01M2CN3ZCSZ54TFJGTDCXTDHXD, AC-4/AC-6). Возвращает `(attempt,
    reason, failure_class)`; `attempt is None` — шаг обязан завершиться
    без эскалации (потолок бюджета либо исход, отличный от "failed") —
    тот же ранний `return`, что раньше стоял прямо в теле
    `_run_developer_step`; иначе `attempt` — номер последней попытки, как
    в прежнем теле цикла (AC-6)."""
    reason = ""
    failure_class = None
    for attempt in range(1, config.AGENT_ATTEMPTS + 1):
        outcome, reason, failure_class = run_agent_once(
            conn, task_id, role, prompt, attempt)
        # Потолок проверяем после каждой попытки, до решения о ретрае: иначе
        # три попытки подряд потратят бюджет, исчерпанный ещё первой.
        if budget.enforce_budget(conn, task_id, t["state"]):
            return None, None, None
        if outcome != "failed":
            return None, None, None
        if failure_class == "session_limit":
            # Требование 4/AC-9: класс 2 не расходует остаток попыток шага —
            # отказ сразу, без ретрая (в отличие от связки «транзиентное
            # системное» ниже, которую ретрай как раз должен пережидать).
            break
        if failure_class == failure_classification.MODEL_UNSUPPORTED_CLASS:
            # «Модель не поддерживается CLI» (SPEC 01M2XJKV84SQ9VEVR0VNVKDNGJ,
            # требование 4, AC-9): отказ детерминирован — следующая попытка
            # не запускается, паузы нет; исход решает `_run_developer_step`
            # (именованный отказ, не эскалация).
            break
        if attempt < config.AGENT_ATTEMPTS:
            if failure_class in failure_classification.TRANSIENT_SYSTEM_CLASSES:
                # Требование 3/AC-7: связка 1а/1б/«системный кандидат» —
                # минутный бэкофф, не секундный; число попыток не меняется.
                backoff_sec = (config.TRANSIENT_SYSTEM_BACKOFF_SEC
                              * 2 ** (attempt - 1))
            else:
                backoff_sec = config.RETRY_BACKOFF_SEC * 2 ** (attempt - 1)
            detail = (f"пауза {backoff_sec} с перед попыткой "
                      f"{attempt + 1}/{config.AGENT_ATTEMPTS}")
            store.journal(conn, task_id, role, "agent run retry", detail)
            print(f"[{task_id}] {detail}")
            time.sleep(backoff_sec)
    return attempt, reason, failure_class


def _escalate_after_attempts(conn, task_id: str, t, role: str, target: str,
                             attempt: int, reason: str,
                             failure_class: str | None) -> None:
    """Эскалация задачи после исчерпания попыток шага (SPEC
    01M2CN3ZCSZ54TFJGTDCXTDHXD, AC-4) — хвостовое тело
    `_run_developer_step`, перенесённое без изменений."""
    # Шаг, на котором упал агент, запоминаем: чинить надо его, а не задачу
    # целиком. Без этого approve увёл бы упавшее ревью в in_dev и поднял
    # разработчика на ветке, где всё уже сделано.
    note = ""
    if failure_class == "session_limit":
        # AC-10: причина — лимит сессии подписки, нужно дождаться reset
        # (текст печатается тем же `set_state` ниже, что и в журнал).
        note = (" — лимит сессии подписки исчерпан (класс 2), дождись "
                "сброса (reset) лимита и повтори")
    store.update_task(conn, task_id, escalated_from=t["state"])
    store.set_state(conn, task_id, "escalated", "fsm",
                    expected_state=t["state"],
                    detail=f"агент не отработал за {attempt} "
                    f"{_attempts_word(attempt)}{note}: "
                    f"{reason}")
    # Sha, зафиксированный этим же set_state (SPEC «approve: полный sha
    # в подсказках», требование 1) — тот же приём, что и у отказа
    # инцидента целостности выше.
    sha_hint = fixation.approve_sha_hint(task_id, target)
    print(f"  разберись по логам и: artel.py approve {task_id}{sha_hint}  "
          f"(вернёт в {t['state']}, шаг повторится)")


def git_identity() -> dict:
    """Имя и почта коммитера из git-конфига — готовыми переменными окружения.

    Смена HOME уводит из-под роли не только user-слой Оператора, но и его
    `~/.gitconfig`, а в этом репозитории `user.email` задан только
    глобально. Без переноса `git commit` внутри шага падает с rc=128
    («Author identity unknown»), то есть предписанный роли коммит
    (миссия разработчика выше, skills/conventions-core) не проходит,
    и ветка задачи остаётся пустой при отработавшем агенте.

    Читается `git config --get` в окружении Оператора, то есть с его
    ~/.gitconfig, — до подмены HOME. Значение не прочиталось (git молчит,
    идентичность не задана) — переменной нет, и это видно в журнале:
    молча уводить шаг в rc=128 нельзя.
    """
    identity = {}
    for option, names in GIT_IDENTITY:
        res = gitcmd.git("config", "--get", option)
        value = res.stdout.strip() if res.returncode == 0 else ""
        if value:
            identity.update(dict.fromkeys(names, value))
    return identity


def role_token(role: str | None) -> str | None:
    """Подписочный токен роли из keychain — по слотам roles.yaml."""
    try:
        slots = roles.token_slots(role)
    except roles.RolesError:
        return None
    for slot in slots:
        token = keychain.token(slot)
        if token:
            return token
    return None


def _resolve_declared_tools() -> dict[str, str]:
    """Абсолютные пути объявленных в манифесте инструментов (SPEC
    01M1RDCEF0JZ4AVQRE43JFH8TN, требования 1, 3, AC-1, AC-2, AC-6):
    `shutil.which` вызывается ровно один раз на инструмент, в окружении
    Оператора (эта функция не трогает `os.environ`, только читает его через
    `which`). Отсутствие ЛЮБОГО объявленного инструмента — `OSError`,
    называющий его по имени, вместо тихой сборки окружения без него.
    """
    resolved = {}
    missing = []
    for name in stack.DECLARED_TOOLS:
        path = shutil.which(name)
        if path is None:
            missing.append(name)
        else:
            resolved[name] = path
    if missing:
        raise OSError(
            f"объявленный инструмент не найден в PATH: {', '.join(missing)}")
    return resolved


def _role_path_dirs(resolved: dict[str, str]) -> list[str]:
    """PATH роли — каталоги объявленных инструментов, в порядке манифеста
    (SPEC, AC-1, AC-3): для `python3` — каталог `sys.executable` пульта, а
    не which-результат (тот каталог в PATH вообще не попадает), — иначе
    первый `python3` на PATH мог бы оказаться pyenv-шимом Оператора, а не
    интерпретатором пульта.
    """
    dirs = []
    for name in stack.DECLARED_TOOLS:
        directory = (str(Path(sys.executable).parent) if name == "python3"
                    else str(Path(resolved[name]).parent))
        if directory not in dirs:
            dirs.append(directory)
    return dirs


def _allowlisted_env(source) -> dict:
    """Копия `source`, суженная до белого списка манифеста (SPEC,
    требования 2, 5, AC-4/AC-5): переменные Оператора вне списка (и вне
    префиксов вроде `LC_*`) в окружение роли не попадают.
    """
    prefixes = tuple(stack.ROLE_ENV_ALLOWLIST_PREFIXES)
    return {name: value for name, value in source.items()
           if name in stack.ROLE_ENV_ALLOWLIST or name.startswith(prefixes)}


def _venv_interpreter_bin() -> str:
    """Требование 4 (SPEC 01M1REVEZ1HESMJ7AFD5A9MEJ8, AC-12/AC-13): каталог
    `<.artel/venv>/bin` — интерпретатор роли, если `.artel/venv` существует
    и согласован с файлом закреплённых версий (та же проверка, что
    `stack.check_stack()` уже даёт AC-7/AC-8 — не отдельная копия логики).

    Зовёт ПОЛНЫЙ `check_stack()`, а не более узкую `stack.venv_checks()`,
    хотя интересна только пара venv-проверок (REVIEW.md итерация 1,
    R1-F2 — три лишних subprocess-вызова к `git`/`gh`/`claude` на каждый
    шаг роли): планка приёмки (`tasks/01M1REVEZ1HESMJ7AFD5A9MEJ8/
    acceptance_tests/test_ac12_ac13_role_env_venv_interpreter.py`, залочена
    T023) мокает именно `runner.stack.check_stack` — сужение вызова здесь
    без правки планки оставило бы мок без эффекта и уронило бы приёмку
    реальным отсутствием venv по временному пути теста. Риск принят,
    описан в PLAN.md «Риски».
    """
    checks = stack.check_stack()
    warn = [c for c in checks if "venv" in c.name.lower() and c.status == "warn"]
    if warn:
        detail = "; ".join(c.detail for c in warn)
        raise OSError(f"venv не готов для роли: {detail}")
    return str(config.VENV_DIR / "bin")


def role_env(role: str | None = None, task_id: str | None = None) -> dict:
    """Окружение процесса роли: PATH и переменные — из манифеста, не копия
    `os.environ` Оператора (SPEC 01M1RDCEF0JZ4AVQRE43JFH8TN, требования 1-3).

    `ARTEL_ROLE`/`ARTEL_TASK` (SPEC 01M2B6K3EM7F2J72RC2F520Y2K, требование
    1) — признак процесса роли, читаемый самим CLI (`conftest.py`,
    `artel.py`) вместо клиентского PreToolUse-хука: ставятся, только если
    значение передано — вызовы без `task_id` (`orchestrator/doctor/*`,
    часть тестов) продолжают работать без правки и просто не несут
    `ARTEL_TASK` в результате.

    Роль не наследует user-слой Оператора (ADR-0003 п.14): его
    ~/.claude/CLAUDE.md, хуки его плагинов и его MCP исполнялись бы
    внутри шага — конфиг-инъекция, и заодно недетерминированное
    окружение, зависящее от того, что Оператор поставил себе вчера. То же
    самое верно для PATH (pyenv/shim'ы Оператора — сегодняшняя причина
    217 логов шагов с чужим `pytest`, «Контекст» SPEC) и для остальных
    переменных `os.environ`: роль видит только каталоги/переменные,
    объявленные манифестом (`orchestrator.stack`), а не весь мир
    Оператора. Курируемый слой живёт в .artel/ пульта: что в нём лежит,
    решает Оператор, но адрес слоя решает пульт.

    Резолвинг инструментов (`_resolve_declared_tools`) — ПЕРВАЯ операция
    функции и единственное место, где вообще читается `os.environ`
    Оператора (через `shutil.which`, до того, как PATH/HOME роли
    подставлены хоть в один словарь) — AC-2. Отсутствие инструмента
    останавливает сборку целиком (`OSError` наружу, без частичного
    результата) — AC-6/AC-8: тихого отката на PATH/переменные Оператора
    нет, `run_agent_once` ловит это исключение и не запускает агента.

    Курируемый слой обязан нести то, без чего шаг не выполним, — отсюда
    git-идентичность (см. `git_identity`). Ставится через `setdefault`:
    git предпочитает переменную окружения конфигу, поэтому уже заданная
    Оператором должна остаться сильнее — так роль видит ровно ту
    идентичность, которую увидел бы git в его HOME.

    Каталог создаётся здесь же: CLI, не нашедший CLAUDE_CONFIG_DIR,
    создал бы его сам — и это был бы каталог, о котором пульт не знает.

    Интерпретатор роли — `.artel/venv` (SPEC 01M1REVEZ1HESMJ7AFD5A9MEJ8,
    требование 4), если он согласован с файлом закреплённых версий
    (`_venv_interpreter_bin`, вызывается сразу после резолвинга
    инструментов манифеста — тот же принцип «отказ до частичного
    результата», что и у `_resolve_declared_tools` выше): его `bin/`
    встаёт ПЕРВЫМ в PATH роли, раньше каталога `sys.executable` пульта —
    голый `python3`/`pytest` внутри шага роли резолвится в venv.
    """
    resolved = _resolve_declared_tools()
    venv_bin = _venv_interpreter_bin()
    config.ROLE_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    env = _allowlisted_env(os.environ)
    env["HOME"] = str(config.ROLE_HOME)
    env["CLAUDE_CONFIG_DIR"] = str(config.ROLE_CONFIG_DIR)
    env["PATH"] = os.pathsep.join([venv_bin] + _role_path_dirs(resolved))
    if role:
        env[config.ARTEL_ROLE_ENV] = role
    if task_id:
        env[config.ARTEL_TASK_ENV] = task_id
    for name, value in git_identity().items():
        env.setdefault(name, value)
    # Аутентификация CLI живёт в user-слое Оператора (~/.claude.json +
    # keychain-запись аккаунта) и вместе с ним из-под роли уходит — чистый
    # HOME отвечает «Not logged in» (фактура T020, вопрос 18 ADR-0003 п.14).
    # Токен подписки (`claude setup-token`) кладётся Оператором в слот
    # keychain и приходит роли переменной окружения. setdefault — заданный
    # Оператором CLAUDE_CODE_OAUTH_TOKEN/ANTHROPIC_API_KEY сильнее слота.
    if not env.get("CLAUDE_CODE_OAUTH_TOKEN") and not env.get(
            "ANTHROPIC_API_KEY"):
        token = role_token(role)
        if token:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = token
    return env


def in_role_environment() -> bool:
    """Верно, если ТЕКУЩИЙ процесс сам исполняется в окружении роли —
    те же два маркера, что `role_env()` ставит процессу роли (HOME/
    CLAUDE_CONFIG_DIR на курируемый слой): единственное в кодовой базе
    определение «окружения роли» читается здесь же, симметрично записи,
    не задаётся заново (SPEC 01M1NSR5M5THYRC0RFWPMVE2DW, требование 5,
    AC-15 — второй, независимый от `permissions.deny` рубеж отказа
    расшифровки пула канарейки, если она вызвана из-под роли)."""
    return (os.environ.get("HOME") == str(config.ROLE_HOME) and
            os.environ.get("CLAUDE_CONFIG_DIR") == str(config.ROLE_CONFIG_DIR))


def role_cwd_path(task_id: str, target: str) -> Path:
    """Путь `role_cwd` этого шага без побочных эффектов (без `workspace.
    ensure`/материализации `tasks/<id>/`) — та же формула, что и внутри
    `role_cwd` ниже (SPEC 01M1RQ12JVHE3PQYDFV1XPSTQ3, требование 2):
    промпт обязан назвать рабочий каталог шага буквальной строкой ДО
    первой попытки агента, раньше первого реального вызова `role_cwd`
    внутри `run_agent_once`."""
    if target == config.DEFAULT_TARGET:
        return workspace.path(task_id)
    return config.PROJECTS / target / "workspace"


def role_cwd(conn, task_id: str, target: str) -> Path:
    """Рабочий каталог роли: worktree задачи для self/артели, workspace
    target'а — иначе.

    Пересмотр планки решением Оператора 03.09 (вариант A по блокеру
    R1-F1 ревью итерации 1 задачи A7; канал ADR-0012): требование 2
    SPEC A7 («первичка артефактов вне git пульта») относится к
    АРТЕФАКТАМ, не к коду. Self/артель (`config.DEFAULT_TARGET`) с
    T045 — не общая рабочая копия пульта (`config.ROOT`), а собственный
    git worktree задачи в стандартном месте (`workspace.ensure`, SPEC
    T045 требования 1-2): агентный шаг исполняется там, рабочая копия
    пульта остаётся территорией оркестратора и не переключается
    запуском роли (инцидент 26–27.08, из-за которого решение и
    принято). Draft-MR, merge_gate, гейт ёмкости и WIP-чекпоинты
    работают только с кодовой веткой, физически связанной с
    `config.ROOT` — именно этот worktree, не внешний артефактный
    каталог.

    Внешний target по ADR-0003 §4 обязан видеть только свой workspace:
    `.artel/projects/<target>/workspace/`, не дерево пульта с его
    CLAUDE.md, `.claude/`, `.mcp.json` (та же конфиг-инъекция, от
    которой T019 увёл HOME/CLAUDE_CONFIG_DIR, — здесь другой вектор,
    cwd, а не окружение); этот путь T045 не меняет. Каталог workspace
    внешнего target создаётся здесь же, как и курируемый слой ролей: до
    git-первички (A2b) он пуст, но роль обязана стартовать в НЁМ, а не
    тихо съехать на ROOT из-за отсутствия каталога.

    Материализация `tasks/<id>/` из артефактной ветки (SPEC
    01M1NKTF173WV5CPDZ1C3WW69K, требование 1, AC-1/AC-2, AC-8): на
    каждом вызове каталог задачи здесь же перезаписывается ГОЛОВОЙ
    артефактной ветки — правка Оператора на гейте между шагами доезжает
    до диска следующего шага, а не остаётся стухшей копией с прошлого
    (инцидент 04.09, «Контекст» SPEC). sha использованной головы —
    baseline конфликт-гварда автокоммита (`checkpoint.
    _commit_external_step_artifacts`, AC-6/AC-7), в колонку БД, не в
    файл диска — переживает `shutil.rmtree` каталога, которым автокоммит
    убирает `tasks/<id>/` после переноса. `task_id is None` — офлайн-смоук
    изоляции (`doctor.isolation_smoke`, синтетический target без реальной
    задачи) — материализация здесь бессмысленна, пропускается тихо, той
    же деградацией, что и отсутствие артефактной ветки.
    """
    if target == config.DEFAULT_TARGET:
        branch = store.task_branch(conn, task_id)
        wt_path, error = workspace.ensure(task_id, branch)
        if error is not None:
            raise OSError(error)
        path = wt_path
    else:
        path = role_cwd_path(task_id, target)
        path.mkdir(parents=True, exist_ok=True)
    if task_id is not None:
        from . import artifact_branch
        materialized_sha = artifact_branch.materialize_task_dir(task_id, path)
        store.update_task(conn, task_id,
                          materialized_artifact_sha=materialized_sha or None)
    return path


def role_cmd() -> list[str]:
    """Argv шага роли: сборка без побочных эффектов, один источник истины
    для реального запуска (`run_agent_once`) и для офлайн-сверки
    `doctor.isolation_smoke` (SPEC T069, требование 2) — вместо двух
    списков флагов, синхронизируемых руками.

    `--strict-mcp-config` без курируемого `--mcp-config` (пульт его пока
    не заводит, SPEC T069 требование 1) резолвит шагу ноль MCP-серверов
    независимо от `.mcp.json` рабочего каталога — конфиг-инъекция через
    MCP тем же вектором, что уже закрыт `--setting-sources` для
    project-/local-хуков (SPEC T058, инцидент T046).
    """
    # argv[0] — абсолютный путь из резолва манифеста (SPEC
    # 01M2XJKV84SQ9VEVR0VNVKDNGJ, требование 1, AC-1/AC-3): тот же
    # `_resolve_declared_tools`, из которого `role_env` собирает PATH роли.
    # Литерал `claude` искался бы по PATH роли в момент запуска, где
    # каталог другого объявленного инструмента стоит раньше и может нести
    # одноимённый бинарник (инцидент 06.09: подставной `claude` планки
    # затенён настоящим из каталога `gh`). Резолв здесь, а не параметром:
    # `role_cmd()` заперта на нулевой список параметров (AC-4). Обе точки
    # вызова стоят после успешного `role_env()` — `OSError` резолва там уже
    # отработал бы раньше.
    claude = _resolve_declared_tools()["claude"]
    return [
        # `claude -p` без аргумента читает промпт со стандартного входа.
        claude, "-p", "--permission-mode", "acceptEdits",
        # stream-json — единственный режим, где строки приходят по ходу
        # шага: text и json отдают всё одним куском в конце (замер в
        # PLAN.md T017). --verbose при нём обязателен, иначе CLI выходит
        # с rc=1.
        "--output-format", "stream-json", "--verbose",
        # белый список вместо полного Bash: только git и запуск тестов/guard
        "--allowedTools", "Bash(git:*),Bash(python3:*)",
        # изоляция от project-/local-слоя клиентских настроек репозитория
        # (хуки, MCP) — SPEC T058, инцидент T046
        "--setting-sources", config.AGENT_SETTING_SOURCES,
        # изоляция MCP-вектора: ambient `.mcp.json` рабочего каталога не
        # резолвится — SPEC T069
        "--strict-mcp-config",
    ]


def _missing_required_artifact(role: str, cwd: Path, task_id: str) -> str | None:
    """Имя обязательного артефакта роли, отсутствующего в РЕАЛЬНОМ рабочем
    каталоге шага (`cwd`, где роль пишет инструментом Write) — `None`,
    если артефакт на месте либо роль не несёт обязательного выхода этого
    шага (SPEC 01M1RQ12JVHE3PQYDFV1XPSTQ3, требование 3).

    Проверяется диск рабочего каталога роли, не артефактная ветка: rc=0
    без файла на диске — тот же класс отказа, что и rc != 0 (два
    инцидента 05.09, «Контекст» SPEC) — headless-шаг не получает
    подтверждения записи вне рабочего каталога и молча ничего не
    оставляет там, где реально смотрит эта проверка."""
    task_dir = cwd / "tasks" / task_id
    if role == "reviewer":
        return None if (task_dir / "REVIEW.md").is_file() else "REVIEW.md"
    if role == "developer":
        return None if (task_dir / "PLAN.md").is_file() else "PLAN.md"
    if role == "analyst":
        if (task_dir / "SPEC.md").is_file() or (task_dir / "QUESTIONS.md").is_file():
            return None
        return "SPEC.md/QUESTIONS.md"
    if role == "test_author":
        acc = task_dir / "acceptance_tests"
        if acc.is_dir() and any(p.is_file() for p in acc.rglob("*")):
            return None
        return "acceptance_tests/"
    return None


def _resolved_role_model(role: str) -> str | None:
    """`roles.model(role)`, деградируя к `None` на `RolesError` (SPEC
    01M2DTT96FS25SHXP0HDTWARQH, требование 2) — защитный повтор: значение,
    нечитаемое `roles.model`, уже остановило бы шаг раньше, в
    `_refuse_before_start`, ДО первой попытки. Повтор здесь нужен только
    потому, что `run_agent_once` (AC-7 `tasks/01M2CN3ZCSZ54TFJGTDCXTDHXD`
    — 101 патч по имени модуля) не вправе принять новый параметр — модель
    попытки резолвится тем же вызовом заново, а не передаётся аргументом."""
    try:
        return roles.model(role)
    except roles.RolesError:
        return None


def _model_journal_label(model_id: str | None) -> str:
    """`<идентификатор>` либо `дефолт CLI` — общий текст поля `model=` для
    записей журнала шага (SPEC 01M2DTT96FS25SHXP0HDTWARQH, требования
    5-6)."""
    return model_id if model_id is not None else "дефолт CLI"


def _numbered_with_model(numbered: str, model_id: str | None) -> str:
    """`numbered`, дополненный `model=` — источник для записей «agent cost
    KNOWN»/«agent cost PARTIAL», журналируемых `spend.py` (вне зоны этой
    задачи, требования 5-6): тот же приём, что и «agent run started» в
    `_prepare_step`, применённый к параметру, который `spend.charge_step`/
    `charge_missing_result` дословно вставляют в начало своей записи."""
    return f"{numbered}, model={_model_journal_label(model_id)}"


def _cost_partial_expected(role: str, pump) -> bool:
    """Верно — ровно то же условие, при котором `spend.
    charge_missing_result` заведёт «agent cost PARTIAL», а не «agent cost
    LOST»/«agent cost ESTIMATED» (SPEC 01M2DTT96FS25SHXP0HDTWARQH,
    требование 6): usage-события в потоке были, и курс роли считает
    частичную сумму без `ValueError`. Условие читается ОТСЮДА (не
    правкой `spend.py`, вне зоны этой задачи) вызовом её же публичной
    `partial_cost_usd` — дублируется только ветвление, не арифметика
    курса."""
    if not pump.saw_usage_event:
        return False
    try:
        return spend.partial_cost_usd(role, pump.partial_tokens) is not None
    except ValueError:
        return False


def run_agent_once(conn, task_id: str, role: str, prompt: str,
                   attempt: int) -> tuple[str, str, str | None]:
    """Один запуск агента: исход попытки, пояснение и класс отказа.

    Исход — "ok" | "failed" | "timeout" | "skipped"; ретраится в `cmd_run`
    только "failed" (ненулевой rc). Таймаут не ретраится: три подряд — это
    полтора часа до возврата управления Оператору. Отсутствие CLI — тоже:
    повторный запуск ничего не изменит, промпт уже сохранён для ручного
    прогона. Класс отказа (SPEC T082, требования 1-2) — `None` вне
    "failed" и для нераспознанного текста; иначе решает `cmd_run` —
    бэкофф связки «транзиентное системное» или немедленный отказ класса 2.

    Разбит на фазы `_prepare_step`/`_spawn_and_wait`/`_account_step` и
    функции исходов `_finish_*` (SPEC 01M2CN3ZCSZ54TFJGTDCXTDHXD, AC-1) —
    значение и тип возврата не меняются.
    """
    model_id = _resolved_role_model(role)

    skip, ctx = _prepare_step(conn, task_id, role, prompt, attempt, model_id)
    if skip is not None:
        return skip
    log_path, prompt_path, env, cwd, numbered = ctx

    skip, spawn_ctx = _spawn_and_wait(
        conn, task_id, role, log_path, prompt_path, cwd, env, numbered,
        model_id)
    if skip is not None:
        return skip
    proc, pump, rc, timed_out, killed_group = spawn_ctx

    spent = _account_step(conn, task_id, role, pump, timed_out, numbered,
                          model_id)
    agent_pid = getattr(proc, "pid", None)

    if timed_out:
        return _finish_timeout(conn, task_id, role, numbered, spent,
                               killed_group, agent_pid)

    if rc != 0:
        return _finish_failed(conn, task_id, role, rc, numbered, spent,
                              log_path)

    missing_artifact = _missing_required_artifact(role, cwd, task_id)
    if missing_artifact is not None:
        return _finish_missing_artifact(conn, task_id, role,
                                        missing_artifact, cwd, numbered,
                                        spent)

    return _finish_ok(conn, task_id, role, pump, rc, numbered, spent)


def _prepare_step(conn, task_id: str, role: str, prompt: str, attempt: int,
                  model_id: str | None):
    """Подготовка попытки шага: лог/промпт на диске, окружение и рабочий
    каталог роли (SPEC 01M2CN3ZCSZ54TFJGTDCXTDHXD, AC-2/AC-3) — три из
    пяти исходов SKIPPED (промпт не записан; окружение роли не создано;
    рабочий каталог роли не создан), с прежними текстами возврата и
    записями журнала. Возвращает `(skip, ctx)`: `skip` — то, что
    `run_agent_once` обязан вернуть немедленно (`None` при успехе); `ctx`
    — `(log_path, prompt_path, env, cwd, numbered)` для
    `_spawn_and_wait`."""
    numbered = f"попытка {attempt}/{config.AGENT_ATTEMPTS}"
    log_path = agent_log.new_agent_log(task_id, role)
    # Промпт уходит агенту файлом на stdin, а не аргументом командной строки
    # (SPEC T017, требование 4): в argv он упирается в предел ядра, режется
    # по длине и целиком виден в `ps` любому процессу машины. Файл рядом
    # с логом заодно делает шаг воспроизводимым руками — раньше промпт
    # сохранялся только в ветке «CLI не найден» (T011, ревью 1).
    prompt_path = log_path.with_suffix(".prompt.txt")
    try:
        prompt_path.write_text(prompt, encoding="utf-8")
    except OSError as exc:
        store.journal(conn, task_id, role, "agent run SKIPPED",
                      f"промпт не записан в {prompt_path}: {exc}")
        print(f"[{task_id}] промпт шага не записан ({exc}) — шаг не начат")
        return ("skipped", f"промпт не записан: {exc}", None), None

    # Окружение готовится до запуска и без запасного пути: не создался
    # каталог курируемого слоя — шаг не начинается. Тихо откатиться на HOME
    # Оператора было бы молчаливой сменой периметра (ADR-0003 п.14).
    try:
        env = role_env(role, task_id)
    except OSError as exc:
        store.journal(conn, task_id, role, "agent run SKIPPED",
                      f"каталог окружения роли не создан: {exc}")
        print(f"[{task_id}] окружение роли не подготовлено ({exc}) — "
              f"шаг не начат")
        return (("skipped", f"окружение роли не подготовлено: {exc}", None),
                None)

    # Тот же принцип, что у окружения выше: рабочий каталог roли не создался —
    # шаг не стартует, тихого отката на ROOT нет (ADR-0003 §4).
    try:
        cwd = role_cwd(conn, task_id, store.task_target(conn, task_id))
    except OSError as exc:
        store.journal(conn, task_id, role, "agent run SKIPPED",
                      f"рабочий каталог роли не создан: {exc}")
        print(f"[{task_id}] рабочий каталог роли не подготовлен ({exc}) — "
              f"шаг не начат")
        return (("skipped", f"рабочий каталог роли не подготовлен: {exc}",
                 None), None)

    # Отсутствие идентичности — не повод не запускать шаг (агент делает не
    # только коммит), но повод сказать об этом до запуска: иначе Оператор
    # узнает о ней из хвоста лога упавшего `git commit` получасом позже.
    # Полный набор GIT_IDENTITY (author И committer), не только пара
    # GIT_AUTHOR_* (SPEC T034, требование 5, ревью T019): committer-часть
    # молча проходила бы мимо предупреждения, хотя коммит роли одинаково
    # падает с rc=128 без неё («committer identity unknown»).
    absent = [name for _, names in GIT_IDENTITY for name in names
              if not env.get(name)]
    if absent:
        detail = (f"git-идентичность роли не задана ({', '.join(absent)}) — "
                  f"коммит шага упадёт; чинится "
                  f"`git config --global user.name/user.email`")
        store.journal(conn, task_id, role, "agent env WARNING", detail)
        print(f"[{task_id}] ВНИМАНИЕ: {detail}")

    # Отсутствие токена теперь блокирует шаг раньше, в pre-flight
    # `cmd_run` (SPEC T022, требование 2) — до этой точки код не доходит,
    # если токена нет ни в keychain, ни в ambient-окружении.

    print(f"[{task_id}] лог шага: {log_path}  (наблюдать: tail -f {log_path})")
    store.journal(conn, task_id, role, "agent run started",
                  f"{numbered}, model={_model_journal_label(model_id)}, "
                  f"лог: {log_path}, промпт: {prompt_path}, "
                  f"окружение: {agent_log.environment_fingerprint()}")
    return None, (log_path, prompt_path, env, cwd, numbered)


def _spawn_and_wait(conn, task_id: str, role: str, log_path: Path,
                    prompt_path: Path, cwd: Path, env: dict, numbered: str,
                    model_id: str | None):
    """Запуск агента и ожидание завершения: открытие промпта, `spawn_
    agent`, перекачка вывода, таймаут и снятие группы процессов (SPEC
    01M2CN3ZCSZ54TFJGTDCXTDHXD, AC-3) — оставшиеся два из пяти исходов
    SKIPPED (промпт не прочитан; claude CLI не найден). Возвращает
    `(skip, ctx)`: `skip` — то, что `run_agent_once` обязан вернуть
    немедленно (`None` при успехе); `ctx` — `(proc, pump, rc, timed_out,
    killed_group)`."""
    # Открытие файла держится вне `try` вокруг Popen: там ловится
    # FileNotFoundError, и пропавший промпт (ручная уборка `.artel/logs`,
    # внешний tmp-reaper) отчитывался бы Оператору как «claude CLI не найден» —
    # он пошёл бы чинить установку CLI вместо диска.
    try:
        prompt_file = open(prompt_path, encoding="utf-8")
    except OSError as exc:
        store.journal(conn, task_id, role, "agent run SKIPPED",
                      f"промпт не прочитан из {prompt_path}: {exc}")
        print(f"[{task_id}] промпт шага не прочитан ({exc}) — шаг не начат")
        return ("skipped", f"промпт не прочитан: {exc}", None), None

    # Файл открыт только на время запуска: у процесса свой дескриптор,
    # а держать его открытым в оркестраторе незачем.
    with prompt_file:
        # Модель роли — довеском к argv `role_cmd()`, а не внутри неё:
        # `role_cmd()` заперта на нулевой список параметров (AC-7 `tasks/
        # 01M2CN3ZCSZ54TFJGTDCXTDHXD`, 101 патч по имени модуля), а флаг
        # `--model` — per-role, известен только здесь (SPEC
        # 01M2DTT96FS25SHXP0HDTWARQH, требование 3). Довесок в конец
        # списка не переставляет существующие флаги.
        cmd = role_cmd()
        if model_id is not None:
            cmd = cmd + ["--model", model_id]
        try:
            proc = spawn_agent(
                # Промпт — файлом на стандартном входе, им и отдаётся
                # `prompt_file` (см. `role_cmd`, флаги — там).
                cmd,
                cwd=cwd, env=env, text=True, bufsize=1,
                stdin=prompt_file, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        except FileNotFoundError:
            # Промпт уже на диске, и это весь смысл ветки: ручной прогон роли
            # делается тем же текстом, из скроллбэка его было бы не скопировать.
            store.journal(conn, task_id, role, "agent run SKIPPED",
                          f"claude CLI не найден, промпт: {prompt_path}")
            print(f"claude CLI не найден. Промпт шага целиком записан в "
                  f"{prompt_path} — запусти роль вручную с ним.")
            return ("skipped", "claude CLI не найден", None), None

    # pgid агентного процесса — рядом с существующим pid держателя lease
    # (SPEC 01M1PNBSHR2PMFECMP7C204MF1, AC-2): `spawn_agent` спавнит его
    # лидером собственной сессии (AC-1), поэтому pgid всегда равен его
    # же pid — запрос `os.getpgid` не нужен. Лизы может не быть вовсе
    # (шаг запущен в обход `lease.acquire`, тесты) — `update_lease_pgid`
    # тогда тихо не меняет ни одной строки. `agent_pid` — не всегда `int`:
    # существующие тесты (T005/T007/…) мокают `spawn_agent` фейковым
    # объектом БЕЗ реального OS-процесса (`FakeProc`/`mock.Mock`) — `pid`
    # такого объекта либо отсутствует, либо сам `Mock`, и группу
    # процессов, которой нет, снимать/записывать некуда и незачем
    # (реальный `subprocess.Popen` продакшена таким никогда не бывает).
    agent_pid = getattr(proc, "pid", None)
    if isinstance(agent_pid, int):
        store.update_lease_pgid(conn, task_id, agent_pid)

    # Перекачка в потоке: чтение строк блокируется, пока агент молчит, а
    # таймаут шага должен срабатывать и на замолчавшем агенте.
    pump = agent_log.OutputPump(proc.stdout, log_path)
    pump.start()
    timed_out = False
    killed_group = None
    try:
        rc = proc.wait(timeout=config.AGENT_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        if isinstance(agent_pid, int):
            # Группа целиком (AC-3), не только сам процесс — потомок,
            # заведённый ролью (`pytest`/`unittest`), иначе переживает
            # завершение шага и виснет под launchd (инцидент 04.09, SPEC
            # «Контекст»). `agent_pid` — pgid этой же группы (AC-1),
            # запрос `os.getpgid` не нужен.
            killed_group = liveness.terminate_process_group(agent_pid)
        else:
            proc.kill()
        rc = proc.wait()
        timed_out = True

    close_pump(conn, task_id, role, pump, proc)
    return None, (proc, pump, rc, timed_out, killed_group)


def _account_step(conn, task_id: str, role: str, pump, timed_out: bool,
                  numbered: str, model_id: str | None) -> str:
    """Учёт шага: трение, стоимость и потолок программы (SPEC
    01M2CN3ZCSZ54TFJGTDCXTDHXD, AC-3) — без изменения вызовов и их
    порядка. Возвращает `spent` — хвост строки для журналов и печати
    исхода."""
    # Трение шага (tasks/T095/SPEC.md, вариант 4б — точка завершения
    # шага, обоснование в tasks/T095/PLAN.md): журналируется сразу по
    # завершении перекачки, независимо от исхода попытки — провалившийся
    # или оборвавшийся шаг тоже тратит вызовы инструментов вхолостую, и
    # это не менее интересное число, чем у успешного. Из ЖИВОГО потока
    # (`pump.friction`), не из персистентного лога: тот несёт рендер, не
    # сырой JSON (см. `agent_log.step_friction`, докстринг).
    store.journal(conn, task_id, role, agent_log.FRICTION_JOURNAL_ACTION,
                  f"{pump.friction:.4f}")
    # Деньги сжигает любая попытка, а не только успешная: провалившаяся стоит
    # столько же, и не учитывать её значило бы обходить потолок ретраями.
    # Финального события потока нет ИМЕННО из-за таймаута или обрыва
    # stdout-пайпа (tasks/T040) — отдельная ветка учёта, без изменений
    # `charge_step` (её сигнатуру напрямую зовут другие тесты, SPEC T040
    # требование 4). Признак обрыва пайпа — тот же `pump.error`, что уже
    # заводит «agent log INCOMPLETE» в `close_pump`; новый способ его
    # обнаружить не заводится.
    # `model=` в «agent cost KNOWN»/«agent cost PARTIAL» (SPEC
    # 01M2DTT96FS25SHXP0HDTWARQH, требование 6) — без правки `spend.py`
    # (вне зоны этой задачи): условие «эта попытка заведёт именно ТУ
    # запись» читается здесь тем же приёмом, что и выбор между веткой
    # `charge_missing_result`/`charge_step` уже ниже, и `numbered`
    # достаётся `spend.py` с довеском ТОЛЬКО когда ветка внутри неё и
    # правда журналирует KNOWN/PARTIAL — иначе «agent cost UNKNOWN»/
    # «agent cost LOST»/«agent cost ESTIMATED» получили бы `model=` по
    # ошибке, хотя требование 6 называет только KNOWN и PARTIAL.
    if pump.cost is None and (timed_out or pump.error is not None):
        cause = "таймаут шага" if timed_out else "обрыв stdout-пайпа"
        numbered_for_cost = (_numbered_with_model(numbered, model_id)
                             if _cost_partial_expected(role, pump)
                             else numbered)
        spent = spend.charge_missing_result(
            conn, task_id, role, numbered_for_cost, cause,
            pump.partial_tokens, pump.saw_usage_event)
    else:
        numbered_for_cost = (_numbered_with_model(numbered, model_id)
                             if pump.cost and pump.cost.get("tokens_by_type")
                             else numbered)
        spent = spend.charge_step(conn, task_id, role, pump.cost,
                                  numbered_for_cost)
    # Порог программы считается сразу после учёта: сумма по всем задачам
    # всех target'ов сдвинулась именно этим шагом (roadmap §5).
    budget.check_program_spend(conn, task_id, pump.cost)
    return spent


def _finish_timeout(conn, task_id: str, role: str, numbered: str,
                    spent: str, killed_group, agent_pid):
    """Исход «таймаут шага» (SPEC 01M2CN3ZCSZ54TFJGTDCXTDHXD, AC-1) —
    перенесённая без изменений ветка `run_agent_once`."""
    # Чекпоинт — до журнала таймаута, чтобы рестарт, начатый сразу по
    # этой записи, уже видел чистое дерево (SPEC T041, требования 1–4).
    checkpoint.commit_timeout_checkpoint(conn, task_id, role)
    # «без ретрая» — чтобы читающий журнал не ждал попыток 2 и 3.
    timeout_min = f"{config.AGENT_TIMEOUT_SEC // 60} мин"
    detail = f"{timeout_min}, {numbered} (без ретрая){spent}"
    if killed_group is not None:
        # Только когда группа реально снята (AC-7) — `agent_pid`
        # тестового дубля выше не участвовал в group-kill вовсе.
        detail = f"{detail}; {liveness.group_kill_detail(agent_pid, killed_group)}"
    store.journal(conn, task_id, role, "agent run TIMEOUT", detail)
    # Стоп-кран волны (01M1THKPNZ11DBZAQDMJ33EMJR, требование 3, вторая
    # точка вызова): считает только СЕЙЧАС записанное событие и все
    # прежние в пределах окна — журнал выше уже несёт эту попытку.
    alerts.check_wave_breaker_timeout(conn)
    print(f"[{task_id}] таймаут шага ({timeout_min}) — разберись и "
          f"перезапусти run")
    return "timeout", f"таймаут шага ({timeout_min})", None


def _finish_failed(conn, task_id: str, role: str, rc: int, numbered: str,
                   spent: str, log_path: Path):
    """Исход «агент упал» (rc != 0) (SPEC 01M2CN3ZCSZ54TFJGTDCXTDHXD,
    AC-1) — перенесённая без изменений ветка `run_agent_once`."""
    # Чекпоинт — до журнала провала, тем же доводом, что и у таймаута
    # выше (SPEC T074, требование 3 — расширение правила T041: провал
    # по коду возврата тоже аварийное завершение шага, не только
    # таймаут). Сам провал/ретрай/эскалация ниже не меняются.
    checkpoint.commit_abnormal_checkpoint(conn, task_id, role, f"rc={rc}")
    reason = (f"rc={rc}, {numbered}{spent}; "
              f"хвост {log_path}:\n{agent_log.log_tail(log_path)}")
    store.journal(conn, task_id, role, "agent run FAILED", reason)
    # Эвристики ошибок агента (SPEC T082): классификация по ПОЛНОМУ
    # тексту попытки (не по усечённому хвосту выше) — журналирует
    # сырой текст структурно и заводит алерты классов «обрыв
    # потока»/2, решение о бэкоффе/немедленном отказе — за `cmd_run`.
    failure_class = failure_classification._record_failure_classification(
        conn, task_id, role, numbered,
        failure_classification._attempt_output_text(log_path))
    # Стоп-кран волны (01M1THKPNZ11DBZAQDMJ33EMJR, требование 3, первая
    # точка вызова): без действия для классов вне TRANSIENT_SYSTEM_
    # CLASSES (в т.ч. failure_class=None) — фильтр внутри check_wave_
    # breaker_failure.
    alerts.check_wave_breaker_failure(conn, failure_class)
    # В консоли хвост не повторяем: эти строки Оператор только что видел
    # вживую (перекачка пишет и в stdout, и в лог). В журнале он нужен —
    # `log <id>` читают потом, когда вывода на экране уже нет.
    print(f"[{task_id}] {role}: агент упал (rc={rc}, {numbered}), "
          f"причина в {log_path}")
    return "failed", reason, failure_class


def _finish_missing_artifact(conn, task_id: str, role: str,
                             missing_artifact: str, cwd: Path,
                             numbered: str, spent: str):
    """Исход «rc=0, но обязательный артефакт роли не оставлен» (SPEC
    01M2CN3ZCSZ54TFJGTDCXTDHXD, AC-1) — перенесённая без изменений ветка
    `run_agent_once`."""
    # Требование 3: rc=0, но роль не оставила обязательный артефакт в
    # своём рабочем каталоге — тот же класс отказа, что rc != 0 выше
    # (чекпоинт WIP, ретрай/эскалацию решает `cmd_run`), а не штатное
    # «agent run finished» (иначе цикл ретраев съедает попытку и
    # бюджет впустую — оба инцидента 05.09, «Контекст» SPEC).
    checkpoint.commit_abnormal_checkpoint(
        conn, task_id, role, f"без артефакта {missing_artifact}")
    reason = (f"rc=0, {numbered}{spent}; шаг завершён без артефакта "
              f"{missing_artifact} в рабочем каталоге роли {cwd}")
    store.journal(conn, task_id, role, "agent run FAILED", reason)
    print(f"[{task_id}] {role}: шаг завершён без артефакта "
          f"{missing_artifact} (rc=0, {numbered})")
    return "failed", reason, None


def _finish_ok(conn, task_id: str, role: str, pump, rc: int,
              numbered: str, spent: str):
    """Исход «шаг завершён» (rc=0, обязательный артефакт на месте) (SPEC
    01M2CN3ZCSZ54TFJGTDCXTDHXD, AC-1) — перенесённая без изменений ветка
    `run_agent_once`."""
    if pump.error is not None:
        # Обрыв stdout-пайпа без таймаута (rc=0, но перекачка сама поймала
        # исключение) — тоже аварийное завершение (SPEC T074, требование 3):
        # безусловный `commit_step_artifacts` ниже закоммитил бы тот же WIP
        # сообщением обычного успешного автокоммита, неотличимым от штатного
        # завершения шага (см. `commit_abnormal_checkpoint`, докстринг).
        checkpoint.commit_abnormal_checkpoint(conn, task_id, role, "обрыв потока")
    else:
        # WIP-коммит кода пультом за роль developer, если рабочее дерево
        # вне tasks/<id>/ осталось грязным после обычного успешного шага
        # (SPEC 01M283NC4JJXK7QS68Y9ET8TBK, требования 1-3) — до
        # артефактного автокоммита ниже, тем же порядком, что у трёх
        # аварийных WIP-чекпоинтов (код сначала, перенос tasks/<id>/
        # потом).
        checkpoint.commit_success_checkpoint(conn, task_id, role)
        # Автокоммит — до журнала завершения шага и до advance-логики
        # (SPEC T059, требование 1): роль может не успеть закоммитить свой
        # артефакт, а `advance` уже проверяет чистоту рабочей копии.
        checkpoint.commit_step_artifacts(conn, task_id, role)
    store.journal(conn, task_id, role, "agent run finished",
                  f"rc={rc}, {numbered}{spent}, "
                  f"окружение: {agent_log.environment_fingerprint()}")
    print(f"[{task_id}] {role} завершил (rc={rc}{spent}); "
          f"дальше: artel.py advance {task_id}")
    return "ok", "", None


def close_pump(conn, task_id: str, role: str, pump: agent_log.OutputPump,
               proc) -> None:
    """Дожидается перекачки и отмечает в журнале, если лог неполный.

    Join с таймаутом: процесс агента уже мёртв, но EOF на пайпе приходит,
    только когда его закрыли все унаследовавшие — фоновый процесс, оставленный
    агентом, держал бы `run` вечно. Пайп закрываем лишь после успешного join:
    `close()` при живом читателе ждёт лок буфера, то есть меняет одно вечное
    ожидание на другое.
    """
    pump.join(config.PUMP_JOIN_TIMEOUT_SEC)
    if pump.is_alive():
        detail = (f"перекачка не завершилась за "
                  f"{config.PUMP_JOIN_TIMEOUT_SEC} с "
                  f"(пайп держит чужой процесс) — лог неполный")
    elif pump.error is not None:
        proc.stdout.close()
        detail = f"лог не записан: {pump.error}"
    else:
        proc.stdout.close()
        return
    store.journal(conn, task_id, role, "agent log INCOMPLETE", detail)
    print(f"[{task_id}] {detail}")
