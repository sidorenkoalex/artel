"""Пакет orchestrator/doctor -- живой смоук CLI.

Коллаборанты читаются лениво через фасад doctor (см. докстринг
orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""

from orchestrator import doctor


# --- живой смоук CLI (требование 3) -------------------------------------

def live_smoke(conn, role: str = "developer") -> doctor.Check:
    """Минимальный реальный вызов `claude`: код возврата и стоимость в потоке.

    НЕ вызывается из pre-flight (дорого); часть `doctor`, обязателен после
    изменения runner/config/roles/пина (SPEC требование 3). Тесты подменяют
    `subprocess.Popen` — настоящий прогон делает Оператор вручную (критерий
    приёмки 8, manual).

    Провал заводит `alerts` (kind=incident, требование 3: «результат в
    журнал») — тем же способом, что и соседние дорогие/разовые проверки
    (`recovery_check`, `check_orphans`, `check_backup_age`): вывод `doctor`
    в терминале, не сохранённый Оператором, иначе теряет провал живого
    смоука бесследно.

    Авто-ack (SPEC T088, требование 1) зовётся на каждом прогоне, не
    только при провале — тем же приёмом, что `check_leases`/
    `check_merge_lock`: иначе алерт прошлого провала не закроется в
    прогоне, где очередной вызов уже вернул `status="ok"`, но новых
    находок (по построению) нет.
    """
    check = doctor._live_smoke_run(role)
    # Инцидент заводит РОВНО провал (SPEC 01M32NH6P053978AER66P0X4GN,
    # требование 12). Для провайдера по умолчанию это тождественная
    # замена прежнему `!= "ok"` — `_live_smoke_run` отдаёт ему только
    # `ok` и `fail`; отличать их понадобилось из-за третьего исхода
    # `skip`, которым отвечает провайдер, чей живой смок обычный прогон
    # `doctor` не запускает: «проверка не выполнялась» инцидентом не
    # является, и алерт по ней открывался бы на каждом прогоне.
    if check.status == "fail":
        doctor.alerts.raise_alert(conn, None, "incident", "doctor.live_smoke", check.detail)
    doctor._auto_ack_gone(conn, "doctor.live_smoke", lambda _msg: check.status == "fail")
    return check


def _live_smoke_run(role: str) -> doctor.Check:
    """Argv и окружение — у провайдера роли (SPEC
    01M2ZNTHSNFYSTF904P6SZTPYF, требование 6): смок обязан проверять
    живость ТОГО САМОГО CLI и того окружения, которыми реально пойдёт
    шаг, а не собственной копии списка флагов. Окружение роли уже несёт
    провайдерскую часть (`runner.role_env`), argv даёт
    `live_smoke_command` того же провайдера.

    Сборка argv стоит ПОСЛЕ `role_env`: обе тянут резолв инструментов
    манифеста, и `OSError` отсутствующего инструмента отрабатывает
    здесь один раз, первой же строкой.

    Провайдер вправе объявить, что обычный прогон `doctor` его живой смок
    не запускает (`live_smoke_in_doctor`, SPEC
    01M32NH6P053978AER66P0X4GN, требование 12) — тогда исход `skip` ДО
    сборки argv и до единого системного вызова: диагностика не обязана
    платить деньги за CLI, на который ещё не переведена ни одна роль.
    Сам смок при этом остаётся доступен Оператору явным запуском
    (`live_smoke_command` провайдера).
    """
    try:
        provider = doctor.providers.for_role(role)
    except doctor.providers.UnknownProviderError as exc:
        return doctor.Check("live-smoke", "fail", str(exc))
    if not provider.live_smoke_in_doctor:
        return doctor.Check(
            "live-smoke", "skip",
            f"живой смок провайдера {provider.name} роли {role} — только по "
            f"явному запуску Оператора, обычный прогон doctor за него не "
            f"платит")
    try:
        env = doctor.runner.role_env(role)
    except OSError as exc:
        return doctor.Check("live-smoke", "fail",
                     f"окружение роли не подготовлено: {exc}")
    try:
        proc = doctor.subprocess.Popen(
            provider.live_smoke_command(doctor.LIVE_SMOKE_PROMPT),
            cwd=doctor.config.ROOT, env=env, text=True,
            stdout=doctor.subprocess.PIPE, stderr=doctor.subprocess.STDOUT)
    except FileNotFoundError:
        return doctor.Check("live-smoke", "fail", "claude CLI не найден")

    try:
        output, _ = proc.communicate(timeout=doctor.LIVE_SMOKE_TIMEOUT_SEC)
    except doctor.subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        return doctor.Check("live-smoke", "fail",
                     f"таймаут живого смоука ({doctor.LIVE_SMOKE_TIMEOUT_SEC} с)")

    rc = proc.returncode
    cost = None
    for line in output.splitlines():
        parsed = doctor.spend.parse_cost_event(line)
        if parsed is not None:
            cost = parsed
    if rc != 0:
        return doctor.Check("live-smoke", "fail", f"rc={rc}; хвост: {output[-500:]}")
    if cost is None:
        return doctor.Check("live-smoke", "fail",
                     "нет события со стоимостью в финальном ответе потока")
    return doctor.Check("live-smoke", "ok", f"rc=0, стоимость ${cost['usd']:.4f}")


