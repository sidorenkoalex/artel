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
    if check.status != "ok":
        doctor.alerts.raise_alert(conn, None, "incident", "doctor.live_smoke", check.detail)
    doctor._auto_ack_gone(conn, "doctor.live_smoke", lambda _msg: check.status != "ok")
    return check


def _live_smoke_run(role: str) -> doctor.Check:
    try:
        env = doctor.runner.role_env(role)
    except OSError as exc:
        return doctor.Check("live-smoke", "fail",
                     f"окружение роли не подготовлено: {exc}")
    try:
        proc = doctor.subprocess.Popen(
            ["claude", "-p", doctor.LIVE_SMOKE_PROMPT,
             "--output-format", "stream-json", "--verbose"],
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


