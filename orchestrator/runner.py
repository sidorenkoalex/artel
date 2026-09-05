"""Запуск агента шага: промпт роли, окружение, попытки, исход, стоимость.

Классификация ошибок попытки — `orchestrator/failure_classification.py`;
WIP-чекпоинты рабочего дерева — `orchestrator/checkpoint.py`; сборка
миссии/брифа/ревью-пакета роли — `orchestrator/role_prompt.py` (T091,
декомпозиция диспетчеров fsm/runner). Здесь остаются запуск процесса
агента, окружение/cwd/argv шага и сам цикл попыток `cmd_run`.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

from . import (agent_log, brief, budget, checkpoint, config, failure_classification,
              fixation, gitcmd, keychain, lease, parallel_limit, pause,
              review, role_prompt, roles, spend, store, workspace)

# Идентичность коммитера, которую роль обязана унести с собой в свой HOME.
# git читает эти переменные ПОВЕРХ конфига, поэтому перенос ровно двух пар
# возвращает шагу авторство, не втаскивая в него остальной user-слой
# Оператора: ни его алиасов, ни его хуков, ни его includeIf.
GIT_IDENTITY = (
    ("user.name", ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME")),
    ("user.email", ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL")),
)


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
    """
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
        sys.exit(f"[{task_id}] run отклонён: {detail}")

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
            return

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
        return

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
        return

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
        sys.exit(f"[{task_id}] состав скилов роли {role} не прочитан: {exc}")
    skills, reason = brief.skills_text(conn, task_id, role, skill_names)
    if skills is None:
        sys.exit(f"[{task_id}] скил роли {role} не прочитан: {reason}")
    mission, brief_text, package = role_prompt.mission_brief_package(
        conn, task_id, t, role)
    prompt = f"{mission}\n\n--- СКИЛЫ РОЛИ ---\n\n{skills}"
    if brief_text is not None:
        prompt = f"{prompt}\n\n{brief_text}"
    if package is not None:
        # Размер входа — в журнал до первой попытки: стоимость прогона потом
        # сопоставляется именно с ним (SPEC T011, 5).
        store.journal(conn, task_id, role, "ревью-пакет собран",
                      review.package_note(package))
        print(f"[{task_id}] ревью-пакет: {review.package_note(package)}")
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

    reason = ""
    failure_class = None
    for attempt in range(1, config.AGENT_ATTEMPTS + 1):
        outcome, reason, failure_class = run_agent_once(
            conn, task_id, role, prompt, attempt)
        # Потолок проверяем после каждой попытки, до решения о ретрае: иначе
        # три попытки подряд потратят бюджет, исчерпанный ещё первой.
        if budget.enforce_budget(conn, task_id, t["state"]):
            return
        if outcome != "failed":
            return
        if failure_class == "session_limit":
            # Требование 4/AC-9: класс 2 не расходует остаток попыток шага —
            # отказ сразу, без ретрая (в отличие от связки «транзиентное
            # системное» ниже, которую ретрай как раз должен пережидать).
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


def role_env(role: str | None = None) -> dict:
    """Окружение процесса роли: HOME и CLAUDE_CONFIG_DIR задаёт пульт.

    Роль не наследует user-слой Оператора (ADR-0003 п.14): его
    ~/.claude/CLAUDE.md, хуки его плагинов и его MCP исполнялись бы
    внутри шага — конфиг-инъекция, и заодно недетерминированное
    окружение, зависящее от того, что Оператор поставил себе вчера.
    Курируемый слой живёт в .artel/ пульта: что в нём лежит, решает
    Оператор, но адрес слоя решает пульт.

    Курируемый слой обязан нести то, без чего шаг не выполним, — отсюда
    git-идентичность (см. `git_identity`). Ставится через `setdefault`:
    git предпочитает переменную окружения конфигу, поэтому уже заданная
    Оператором должна остаться сильнее — так роль видит ровно ту
    идентичность, которую увидел бы git в его HOME.

    Каталог создаётся здесь же: CLI, не нашедший CLAUDE_CONFIG_DIR,
    создал бы его сам — и это был бы каталог, о котором пульт не знает.
    """
    config.ROLE_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["HOME"] = str(config.ROLE_HOME)
    env["CLAUDE_CONFIG_DIR"] = str(config.ROLE_CONFIG_DIR)
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
        path = config.PROJECTS / target / "workspace"
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
    return [
        # `claude -p` без аргумента читает промпт со стандартного входа.
        "claude", "-p", "--permission-mode", "acceptEdits",
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
    """
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
        return "skipped", f"промпт не записан: {exc}", None

    # Окружение готовится до запуска и без запасного пути: не создался
    # каталог курируемого слоя — шаг не начинается. Тихо откатиться на HOME
    # Оператора было бы молчаливой сменой периметра (ADR-0003 п.14).
    try:
        env = role_env(role)
    except OSError as exc:
        store.journal(conn, task_id, role, "agent run SKIPPED",
                      f"каталог окружения роли не создан: {exc}")
        print(f"[{task_id}] окружение роли не подготовлено ({exc}) — "
              f"шаг не начат")
        return "skipped", f"окружение роли не подготовлено: {exc}", None

    # Тот же принцип, что у окружения выше: рабочий каталог roли не создался —
    # шаг не стартует, тихого отката на ROOT нет (ADR-0003 §4).
    try:
        cwd = role_cwd(conn, task_id, store.task_target(conn, task_id))
    except OSError as exc:
        store.journal(conn, task_id, role, "agent run SKIPPED",
                      f"рабочий каталог роли не создан: {exc}")
        print(f"[{task_id}] рабочий каталог роли не подготовлен ({exc}) — "
              f"шаг не начат")
        return "skipped", f"рабочий каталог роли не подготовлен: {exc}", None

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
                  f"{numbered}, лог: {log_path}, промпт: {prompt_path}, "
                  f"окружение: {agent_log.environment_fingerprint()}")
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
        return "skipped", f"промпт не прочитан: {exc}", None

    # Файл открыт только на время запуска: у процесса свой дескриптор,
    # а держать его открытым в оркестраторе незачем.
    with prompt_file:
        try:
            proc = spawn_agent(
                # Промпт — файлом на стандартном входе, им и отдаётся
                # `prompt_file` (см. `role_cmd`, флаги — там).
                role_cmd(),
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
            return "skipped", "claude CLI не найден", None

    # Перекачка в потоке: чтение строк блокируется, пока агент молчит, а
    # таймаут шага должен срабатывать и на замолчавшем агенте.
    pump = agent_log.OutputPump(proc.stdout, log_path)
    pump.start()
    timed_out = False
    try:
        rc = proc.wait(timeout=config.AGENT_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        proc.kill()
        rc = proc.wait()
        timed_out = True

    close_pump(conn, task_id, role, pump, proc)
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
    if pump.cost is None and (timed_out or pump.error is not None):
        cause = "таймаут шага" if timed_out else "обрыв stdout-пайпа"
        spent = spend.charge_missing_result(
            conn, task_id, role, numbered, cause,
            pump.partial_tokens, pump.saw_usage_event)
    else:
        spent = spend.charge_step(conn, task_id, role, pump.cost, numbered)
    # Порог программы считается сразу после учёта: сумма по всем задачам
    # всех target'ов сдвинулась именно этим шагом (roadmap §5).
    budget.check_program_spend(conn, task_id, pump.cost)

    if timed_out:
        # Чекпоинт — до журнала таймаута, чтобы рестарт, начатый сразу по
        # этой записи, уже видел чистое дерево (SPEC T041, требования 1–4).
        checkpoint.commit_timeout_checkpoint(conn, task_id, role)
        # «без ретрая» — чтобы читающий журнал не ждал попыток 2 и 3.
        timeout_min = f"{config.AGENT_TIMEOUT_SEC // 60} мин"
        store.journal(conn, task_id, role, "agent run TIMEOUT",
                      f"{timeout_min}, {numbered} (без ретрая){spent}")
        print(f"[{task_id}] таймаут шага ({timeout_min}) — разберись и "
              f"перезапусти run")
        return "timeout", f"таймаут шага ({timeout_min})", None

    if rc != 0:
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
        # В консоли хвост не повторяем: эти строки Оператор только что видел
        # вживую (перекачка пишет и в stdout, и в лог). В журнале он нужен —
        # `log <id>` читают потом, когда вывода на экране уже нет.
        print(f"[{task_id}] {role}: агент упал (rc={rc}, {numbered}), "
              f"причина в {log_path}")
        return "failed", reason, failure_class

    if pump.error is not None:
        # Обрыв stdout-пайпа без таймаута (rc=0, но перекачка сама поймала
        # исключение) — тоже аварийное завершение (SPEC T074, требование 3):
        # безусловный `commit_step_artifacts` ниже закоммитил бы тот же WIP
        # сообщением обычного успешного автокоммита, неотличимым от штатного
        # завершения шага (см. `commit_abnormal_checkpoint`, докстринг).
        checkpoint.commit_abnormal_checkpoint(conn, task_id, role, "обрыв потока")
    else:
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
