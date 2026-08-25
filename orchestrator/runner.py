"""Запуск агента шага: промпт роли, окружение, попытки, исход, стоимость."""
import os
import subprocess
import sys
import time
from pathlib import Path

from . import (agent_log, brief, budget, config, fixation, gitcmd, keychain,
              review, roles, spend, store)

# Идентичность коммитера, которую роль обязана унести с собой в свой HOME.
# git читает эти переменные ПОВЕРХ конфига, поэтому перенос ровно двух пар
# возвращает шагу авторство, не втаскивая в него остальной user-слой
# Оператора: ни его алиасов, ни его хуков, ни его includeIf.
GIT_IDENTITY = (
    ("user.name", ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME")),
    ("user.email", ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL")),
)


def step_role(t) -> str | None:
    """Роль текущего шага задачи; None — состояние не агентское.

    `spec_writing` сознательно не входит в `config.STATE_ROLE` статически
    (SPEC T025, требование 1 — обратная совместимость): задача без
    `tasks/<id>/TZ.md` обязана жить прежним флоу («SPEC пишет Оператор»),
    и `run`/`auto` не имеют права ни разу попытаться запустить агента
    просто потому, что кто-то добавил запись в общий словарь состояний.
    Роль `analyst` подключается только когда `TZ.md` реально лежит
    в каталоге задачи; при отсутствии файла функция ведёт себя так же,
    как и до этой задачи (роли нет). Единственная точка резолвинга,
    которую зовут и `cmd_run`, и `auto.cmd_auto` (`STATE_ROLE`/
    `AUTO_STOP` как словари при этом не трогаются — их читают
    `test_invariants.FsmStatesCoverTheCodeTest` и `test_auto_cycle.*`
    буквально по ключам).
    """
    role = config.STATE_ROLE.get(t["state"])
    if role is not None:
        return role
    if t["state"] == "spec_writing" and (
            config.TASKS / t["id"] / "TZ.md").exists():
        return "analyst"
    return None


def cmd_run(task_id: str) -> None:
    """Запуск агента текущего шага (claude CLI, headless)."""
    conn = store.db()
    t = store.get_task(conn, task_id)
    # Бюджет проверяем до всего остального: потраченные деньги не зависят от
    # состояния задачи, а из escalated Оператор её вернуть уже мог.
    blocked = budget.budget_block(t)
    if blocked is not None:
        sys.exit(blocked)
    role = step_role(t)
    if role is None:
        if t["state"] == "spec_writing":
            sys.exit(f"[{task_id}] SPEC пишет Оператор — TZ.md не заведён "
                     f"(`new \"...\" --tz <файл>` заведёт роль analyst)")
        sys.exit(f"[{task_id}] в состоянии {t['state']} агент не запускается")

    # Pre-flight перед стартом шага (SPEC T022, требование 2): быстрые
    # проверки окружения (CLI найден, токен роли добыт, диск, layout
    # внешнего target'а) — до git-сверки и до попыток агента, отдельным
    # модулем (ADR-0003 3ж — «одна проверка, одно место»; отложенный
    # импорт по тому же приёму, что store._record_fixation берёт fixation:
    # doctor читает runner по имени, runner не должен знать о doctor
    # на уровне модуля). Провал — шаг не начат, без ретрая, с именованной
    # причиной. Версия CLI ≠ пин — предупреждение, не блок (требование 5).
    from . import doctor
    preflight = doctor.preflight_checks(role, t["target"] or config.DEFAULT_TARGET)
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
                        f"инцидент целостности: {incident}")
        print(f"[{task_id}] СТОП: инцидент целостности — {incident}")
        print(f"  разберись и: artel.py approve {task_id} <sha>")
        return

    # Состав скилов роли — из roles.yaml, а не из константы рядом с кодом:
    # правка карты исполнителей меняет промпт без правки кода (T017,
    # требование 1). Отказы обеих чтений называются причиной: шаг не
    # начинается, но Оператор видит, что именно чинить.
    try:
        skill_names = roles.skills(role)
    except roles.RolesError as exc:
        sys.exit(f"[{task_id}] состав скилов роли {role} не прочитан: {exc}")
    try:
        skills = "\n\n".join(
            (config.ROOT / "skills" / f"{s}.md").read_text(encoding="utf-8")
            for s in skill_names
        )
    except (OSError, UnicodeDecodeError) as exc:
        sys.exit(f"[{task_id}] скил роли {role} не прочитан: {exc}")
    task_ref = f"tasks/{task_id}"
    package = None
    brief_text = None
    if role == "analyst":
        mission = (
            f"Роль: аналитик. Задача {task_id}, ветка {t['branch']}. "
            f"Основной вход — ТЗ Оператора, разработчик увидит задачу "
            f"только после тебя. Карта кодовой базы — в БРИФЕ РОЛИ ниже.\n"
            f"1) Прочитай {task_ref}/TZ.md. 2) Создай ветку от main, если "
            f"её ещё нет.\n"
            f"3) ТЗ достаточно — напиши {task_ref}/SPEC.md по "
            f"templates/SPEC.md: критерии приёмки размечены AC-n строго "
            f"из формулировок ТЗ, «не входит» — из его же границ, "
            f"budget_usd по классу задачи и только вниз от дефолта, "
            f"status: ready.\n"
            f"4) ТЗ неясно или неполно — не домысливай: один батч всех "
            f"вопросов в {task_ref}/QUESTIONS.md по templates/QUESTIONS.md, "
            f"отсортированный по блокирующести, каждый — с вариантами "
            f"и дефолтом. SPEC.md в этом случае не трогай — сам файл "
            f"эскалирует задачу.\n"
            f"5) Прогони scripts/guard.py на своём файле, закоммить в "
            f"ветку. Код репозитория не трогай."
        )
        brief_text = brief.analyst_map_component(conn, task_id)
    elif role == "test_author":
        mission = (
            f"Роль: автор приёмочных тестов. Задача {task_id}, ветка "
            f"{t['branch']}. Разработчик увидит задачу только после тебя —\n"
            f"1) Прочитай {task_ref}/SPEC.md, раздел «Критерии приёмки» "
            f"(AC-1, AC-2, …). 2) Создай ветку от main, если её ещё нет.\n"
            f"3) Для каждого AC-n напиши unittest в "
            f"{task_ref}/acceptance_tests/test_*.py, метод test_ac<n>_... — "
            f"ТОЛЬКО из формулировки критерия.\n"
            f"4) Критерий нельзя проверить тестом напрямую — пометь "
            f"`# AC-n: manual — <причина>` (Оператор проверит на приёмке) "
            f"или `# AC-n: skip — <причина>`.\n"
            f"5) Критерий в принципе неисполним тестом — не изобретай "
            f"компромисс: `# AC-n: escalate — <вопрос Оператору>`.\n"
            f"6) Прогони `python3 -m unittest discover -s "
            f"{task_ref}/acceptance_tests`, закоммить каталог в ветку. "
            f"Код репозитория и SPEC.md НЕ трогай."
        )
    elif role == "developer":
        mission = (
            f"Роль: разработчик. Задача {task_id}, ветка {t['branch']}. "
            f"SPEC задачи, карта кодовой базы и конвенции проекта — целиком "
            f"в БРИФЕ РОЛИ ниже, отдельно их читать не нужно.\n"
            f"1) Изучи бриф. 2) Создай ветку от main.\n"
            f"3) Напиши {task_ref}/PLAN.md по templates/PLAN.md.\n"
            f"4) Реализуй по плану + юнит-тесты. Если есть {task_ref}/REVIEW.md "
            f"со статусом changes_requested — сначала закрой замечания. Если "
            f"есть {task_ref}/acceptance_tests/ — они залочены (tasks/T023): "
            f"код чинится под них, их правка — эскалация, не правка.\n"
            f"5) Прогони scripts/guard.py на своих артефактах, закоммить всё "
            f"в ветку, поставь PLAN.md status: ready. НЕ мержи."
        )
        brief_text = brief.developer_brief(conn, task_id)
    else:
        mission = (
            f"Роль: ревьювер. Задача {task_id}, ветка {t['branch']}. Свежий "
            f"контекст: всё нужное для ревью уже собрано в РЕВЬЮ-ПАКЕТЕ ниже "
            f"(SPEC, PLAN, прошлый REVIEW, форма вердикта, список изменённых "
            f"файлов, diff). "
            f"Работай от пакета, а не от обхода репозитория.\n"
            f"Файлы сверх пакета читай точечно и только когда без них не "
            f"проверить конкретное замечание; причину чтения называй в самом "
            f"замечании. Права не сужены: тесты, guard и другие исполняемые "
            f"проверки запускай, когда они доказывают или опровергают "
            f"замечание.\n"
            f"Проведи обе фазы review-checklist (гейт плана + ревью MR) и "
            f"заполни {task_ref}/REVIEW.md по форме из пакета "
            # номер, которого ждёт FSM: вердикт с прежним iteration он уже учёл
            f"(iteration: {t['reviewed_iter'] + 1}). Код НЕ правь — только "
            f"REVIEW.md в ветке задачи."
        )
        package = review.review_package(task_id, t["title"], t["branch"])
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

    reason = ""
    for attempt in range(1, config.AGENT_ATTEMPTS + 1):
        outcome, reason = run_agent_once(conn, task_id, role, prompt, attempt)
        # Потолок проверяем после каждой попытки, до решения о ретрае: иначе
        # три попытки подряд потратят бюджет, исчерпанный ещё первой.
        if budget.enforce_budget(conn, task_id, t["state"]):
            return
        if outcome != "failed":
            return
        if attempt < config.AGENT_ATTEMPTS:
            pause = config.RETRY_BACKOFF_SEC * 2 ** (attempt - 1)
            detail = (f"пауза {pause} с перед попыткой "
                      f"{attempt + 1}/{config.AGENT_ATTEMPTS}")
            store.journal(conn, task_id, role, "agent run retry", detail)
            print(f"[{task_id}] {detail}")
            time.sleep(pause)

    # Шаг, на котором упал агент, запоминаем: чинить надо его, а не задачу
    # целиком. Без этого approve увёл бы упавшее ревью в in_dev и поднял
    # разработчика на ветке, где всё уже сделано.
    store.update_task(conn, task_id, escalated_from=t["state"])
    store.set_state(conn, task_id, "escalated", "fsm",
                    f"агент не отработал за {config.AGENT_ATTEMPTS} попытки: "
                    f"{reason}")
    print(f"  разберись по логам и: artel.py approve {task_id}  "
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


def role_cwd(target: str) -> Path:
    """Рабочий каталог роли: ROOT для догфуда, workspace target'а — иначе.

    Догфуд (`config.DEFAULT_TARGET`) держит артефакты в `tasks/` пульта
    до A7 (ADR-0003 3д, «особый случай») — рабочий каталог как и был,
    `ROOT`. Внешний target по ADR-0003 §4 обязан видеть только свой
    workspace: `.artel/projects/<target>/workspace/`, не дерево пульта
    с его CLAUDE.md, `.claude/`, `.mcp.json` (та же конфиг-инъекция,
    от которой T019 увёл HOME/CLAUDE_CONFIG_DIR, — здесь другой вектор,
    cwd, а не окружение). Каталог создаётся здесь же, как и курируемый
    слой ролей: до git-первички (A2b) он пуст, но роль обязана
    стартовать в НЁМ, а не тихо съехать на ROOT из-за отсутствия
    каталога.
    """
    if target == config.DEFAULT_TARGET:
        return config.ROOT
    path = config.PROJECTS / target / "workspace"
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_agent_once(conn, task_id: str, role: str, prompt: str,
                   attempt: int) -> tuple[str, str]:
    """Один запуск агента: исход попытки и пояснение к нему.

    Исход — "ok" | "failed" | "timeout" | "skipped"; ретраится в `cmd_run`
    только "failed" (ненулевой rc). Таймаут не ретраится: три подряд — это
    полтора часа до возврата управления Оператору. Отсутствие CLI — тоже:
    повторный запуск ничего не изменит, промпт уже сохранён для ручного
    прогона.
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
        return "skipped", f"промпт не записан: {exc}"

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
        return "skipped", f"окружение роли не подготовлено: {exc}"

    # Тот же принцип, что у окружения выше: рабочий каталог roли не создался —
    # шаг не стартует, тихого отката на ROOT нет (ADR-0003 §4).
    try:
        cwd = role_cwd(store.task_target(conn, task_id))
    except OSError as exc:
        store.journal(conn, task_id, role, "agent run SKIPPED",
                      f"рабочий каталог роли не создан: {exc}")
        print(f"[{task_id}] рабочий каталог роли не подготовлен ({exc}) — "
              f"шаг не начат")
        return "skipped", f"рабочий каталог роли не подготовлен: {exc}"

    # Отсутствие идентичности — не повод не запускать шаг (агент делает не
    # только коммит), но повод сказать об этом до запуска: иначе Оператор
    # узнает о ней из хвоста лога упавшего `git commit` получасом позже.
    absent = [name for name in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL")
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
                  f"{numbered}, лог: {log_path}, промпт: {prompt_path}")
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
        return "skipped", f"промпт не прочитан: {exc}"

    # Файл открыт только на время запуска: у процесса свой дескриптор,
    # а держать его открытым в оркестраторе незачем.
    with prompt_file:
        try:
            proc = subprocess.Popen(
                # `claude -p` без аргумента читает промпт со стандартного
                # входа — им и отдаётся файл.
                ["claude", "-p", "--permission-mode", "acceptEdits",
                 # stream-json — единственный режим, где строки приходят по
                 # ходу шага: text и json отдают всё одним куском в конце
                 # (замер в PLAN.md). --verbose при нём обязателен, иначе
                 # CLI выходит с rc=1.
                 "--output-format", "stream-json", "--verbose",
                 # белый список вместо полного Bash: только git и запуск
                 # тестов/guard
                 "--allowedTools", "Bash(git:*),Bash(python3:*)"],
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
            return "skipped", "claude CLI не найден"

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
    # Деньги сжигает любая попытка, а не только успешная: провалившаяся стоит
    # столько же, и не учитывать её значило бы обходить потолок ретраями.
    spent = spend.charge_step(conn, task_id, role, pump.cost, numbered)
    # Порог программы считается сразу после учёта: сумма по всем задачам
    # всех target'ов сдвинулась именно этим шагом (roadmap §5).
    budget.check_program_spend(conn, task_id, pump.cost)

    if timed_out:
        # «без ретрая» — чтобы читающий журнал не ждал попыток 2 и 3.
        store.journal(conn, task_id, role, "agent run TIMEOUT",
                      f"30 мин, {numbered} (без ретрая){spent}")
        print(f"[{task_id}] таймаут шага (30 мин) — разберись и перезапусти run")
        return "timeout", "таймаут шага (30 мин)"

    if rc != 0:
        reason = (f"rc={rc}, {numbered}{spent}; "
                  f"хвост {log_path}:\n{agent_log.log_tail(log_path)}")
        store.journal(conn, task_id, role, "agent run FAILED", reason)
        # В консоли хвост не повторяем: эти строки Оператор только что видел
        # вживую (перекачка пишет и в stdout, и в лог). В журнале он нужен —
        # `log <id>` читают потом, когда вывода на экране уже нет.
        print(f"[{task_id}] {role}: агент упал (rc={rc}, {numbered}), "
              f"причина в {log_path}")
        return "failed", reason

    store.journal(conn, task_id, role, "agent run finished",
                  f"rc={rc}, {numbered}{spent}")
    print(f"[{task_id}] {role} завершил (rc={rc}{spent}); "
          f"дальше: artel.py advance {task_id}")
    return "ok", ""


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
