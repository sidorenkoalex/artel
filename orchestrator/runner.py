"""Запуск агента шага: промпт роли, попытки, исход, стоимость, журнал."""
import subprocess
import sys
import time

from . import agent_log, budget, config, review, roles, spend, store


def cmd_run(task_id: str) -> None:
    """Запуск агента текущего шага (claude CLI, headless)."""
    conn = store.db()
    t = store.get_task(conn, task_id)
    # Бюджет проверяем до всего остального: потраченные деньги не зависят от
    # состояния задачи, а из escalated Оператор её вернуть уже мог.
    blocked = budget.budget_block(t)
    if blocked is not None:
        sys.exit(blocked)
    role = config.STATE_ROLE.get(t["state"])
    if role is None:
        sys.exit(f"[{task_id}] в состоянии {t['state']} агент не запускается")

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
    if role == "developer":
        mission = (
            f"Роль: разработчик. Задача {task_id}, ветка {t['branch']}.\n"
            f"1) Прочитай {task_ref}/SPEC.md. 2) Создай ветку от main.\n"
            f"3) Напиши {task_ref}/PLAN.md по templates/PLAN.md.\n"
            f"4) Реализуй по плану + юнит-тесты. Если есть {task_ref}/REVIEW.md "
            f"со статусом changes_requested — сначала закрой замечания.\n"
            f"5) Прогони scripts/guard.py на своих артефактах, закоммить всё "
            f"в ветку, поставь PLAN.md status: ready. НЕ мержи."
        )
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
    conn.execute("UPDATE tasks SET escalated_from=? WHERE id=?",
                 (t["state"], task_id))
    conn.commit()
    store.set_state(conn, task_id, "escalated", "fsm",
                    f"агент не отработал за {config.AGENT_ATTEMPTS} попытки: "
                    f"{reason}")
    print(f"  разберись по логам и: artel.py approve {task_id}  "
          f"(вернёт в {t['state']}, шаг повторится)")


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

    print(f"[{task_id}] лог шага: {log_path}  (наблюдать: tail -f {log_path})")
    store.journal(conn, task_id, role, "agent run started",
                  f"{numbered}, лог: {log_path}, промпт: {prompt_path}")
    try:
        # Файл открыт только на время запуска: у процесса свой дескриптор,
        # а держать его открытым в оркестраторе незачем.
        with open(prompt_path, encoding="utf-8") as prompt_file:
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
                cwd=config.ROOT, text=True, bufsize=1, stdin=prompt_file,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
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
