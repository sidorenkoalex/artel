"""Пакет orchestrator/doctor -- команда doctor: all_checks, cmd_doctor, cmd_alert_ack, cmd_alert_ack_bulk.

Коллаборанты читаются лениво через фасад doctor (см. докстринг
orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""
import sys

from orchestrator import doctor


# --- команда doctor -------------------------------------------------------

def all_checks(conn) -> list[doctor.Check]:
    """Требование 1: прогон всех проверок doctor.

    Проверки исполнителя роли (CLI найден, версия CLI, секрет, дом
    роли) приходят из `preflight()` провайдера КАЖДОЙ agent-роли (SPEC
    01M2ZNTHSNFYSTF904P6SZTPYF, требование 6): склейка без дублей — в
    `doctor.provider_preflight_checks`, порядок строк в выводе остаётся
    прежним (CLI, версия, токены ролей, git-идентичность, диск, дом
    роли). Версия CLI отсутствует в склейке, если CLI не нашёлся, —
    то же условие, что стояло здесь явным `if` до задачи, теперь внутри
    `preflight()` провайдера.

    Четыре сегодняшних имени разбираются поимённо — ради ПОРЯДКА строк,
    в котором они перемежаются общими проверками пульта; всё, что
    провайдер назвал иначе, печатается следом за ними, а не пропадает
    (REVIEW.md итерации 1, R1-F4): проверка секрета второго провайдера
    под своим именем (`api-key`) обязана дойти до Оператора, иначе
    `doctor` зеленел бы при отсутствующем ключе.
    """
    provider_checks = doctor.provider_preflight_checks()
    checks = [doctor.check_role_providers()]
    # Каталог моделей и локальный слой (SPEC 01M3009Y9AGGY6ZCFA7H1HJ1TD,
    # требование 11) — сразу за строкой цепочек ролей, до проверок CLI:
    # без разрешимой цепочки ни один агентный шаг не стартует, и причина
    # обязана стоять рядом с самой цепочкой, а не в конце списка.
    checks.append(doctor.check_models_catalog())
    checks.append(doctor.check_models_local())
    # Записи `role_models:` (SPEC 01M3PYMQ6N4SCAJ9WWTTKH6XNG, требование
    # 2) — сразу за слоем, которому принадлежат: роль, идущая мимо яруса,
    # читается рядом с ярусами, а не в конце списка.
    checks.extend(doctor.check_role_models())
    # Действующий тариф моделей (SPEC 01M300A14KRHCFB0DQXVCBJEKF,
    # требование 8) — сразу за слоями, по которым он и разрешается:
    # протухшая цена и смена модели мимо тарифа читаются вместе с
    # цепочкой роли, а не в конце списка, где их не связать с ней глазом.
    checks.append(doctor.check_model_tariff_freshness())
    checks.append(doctor.check_model_tariff_vs_model_change(conn))
    # Согласованность «провайдер роли ↔ провайдер её модели» и наличие
    # CLI востребованных провайдеров (REVIEW.md итерации 1, R1-F1) —
    # перед строками самих CLI: пара, разошедшаяся между `roles.yaml` и
    # ярусом локального слоя, до этой строки не была видна в `doctor`
    # вовсе, а шаг по ней уходил бы в чужой CLI за деньги.
    checks.append(doctor.check_model_provider_cli())
    checks.extend(provider_checks.pop("cli-found", []))
    checks.extend(provider_checks.pop("cli-version", []))
    checks.extend(provider_checks.pop("token", []))
    checks.append(doctor.check_git_identity())
    checks.append(doctor.check_disk_space())
    checks.extend(provider_checks.pop("role-home-reference", []))
    for remaining in provider_checks.values():
        checks.extend(remaining)
    checks.append(doctor.check_backup_age(conn))
    checks.append(doctor.check_task_counters(conn))
    checks.append(doctor.isolation_smoke())
    # Смоки изоляции провайдеров, у которых он свой (SPEC
    # 01M32NH6P053978AER66P0X4GN, требование 12) — сразу за общим: у них
    # один предмет («достаёт ли шаг то, чего не должен»), и читать их
    # Оператору удобнее рядом.
    checks.extend(doctor.provider_isolation_smokes())
    # Секреты чужих провайдеров в окружении шага (REVIEW.md итерации 1,
    # R1-F4) — рядом со смоками изоляции: предмет тот же («в шаге лежит
    # то, чего там быть не должно»), но лечится он не кодом шага, а
    # сужением общего белого списка манифеста.
    checks.append(doctor.check_foreign_provider_secrets())
    checks.append(doctor.live_smoke(conn))

    try:
        declared = doctor.targets.load()
    except doctor.targets.TargetsError as exc:
        checks.append(doctor.Check("targets-yaml", "fail", str(exc)))
        declared = {}
    for name, entry in declared.items():
        checks.append(doctor.check_target_layout(name))
        checks.append(doctor.check_target_wrapper(name))
        checks.append(doctor.check_remote_empty(name))
        checks.append(doctor.check_base_branch(name, entry))
        checks.extend(doctor.recovery_check(conn, name))

    checks.extend(doctor.check_pending_snapshots(conn))
    checks.extend(doctor.check_orphans(conn))
    checks.extend(doctor.check_leases(conn))
    checks.extend(doctor.check_merge_lock(conn))
    checks.extend(doctor.check_merge_queue(conn))
    checks.extend(doctor.check_hung_test_runs(conn))
    checks.extend(doctor.check_zone_waits(conn))
    checks.extend(doctor.check_branch_freshness(conn))
    checks.extend(doctor.check_artifact_branch_sync(conn))
    checks.extend(doctor.check_artifact_branch_ci(conn))
    checks.extend(doctor.check_artifact_branch_parent_ancestry(conn))
    checks.append(doctor.check_root_pin())
    checks.append(doctor.check_pin_unpushed())
    # Цвет CI main (SPEC 01M3SF7DPFGEZ7VYEGGXGTX49E, AC-3) — рядом с пином:
    # `pin-update` сверяет тот же цвет, и читать их Оператору вместе.
    checks.append(doctor.check_main_ci())
    checks.append(doctor.check_git_hooks())
    checks.append(doctor.check_role_log_pool_leak(conn))
    checks.append(doctor.check_canary_pool_drift())
    # Наборы ролей канарейки (SPEC 01M3FQ2Z2PY0E9T5F5WQ207NP5, требование
    # 9) — рядом с остальными строками канарейки: битая ссылка набора
    # обнаруживается иначе только на самом прогоне, то есть после того, как
    # за неё заплачено попыткой.
    checks.append(doctor.check_canary_sets())
    checks.append(doctor.check_canary_trigger(conn))
    checks.append(doctor.check_pending_notes())
    checks.extend(doctor.check_token_repo_scope())
    checks.extend(doctor.stack.check_stack())
    checks.extend(doctor.check_map_growth(conn))
    return checks


LABELS = {"ok": "ok", "warn": "WARN", "fail": "FAIL", "skip": "skip"}


def cmd_doctor(restore: bool = False, fix: bool = False) -> None:
    """SPEC 01M1REVP9WGRHDDNVEVE8BBH0Z, требования 3-6: `_orphan_artifact_
    branches(conn)` зовётся РОВНО ОДИН РАЗ за весь прогон (что в режиме
    предпросмотра, что под `--fix`, AC-3) — результат передаётся явно в
    `sweep_orphan_artifact_branches`, чтобы та не переспрашивала origin.

    Origin недоступен (`orphans is None`): без `--fix` — информационная
    строка вместо списка кандидатов (требование 6/AC-7, не FAIL — тем же
    приёмом деградации, что `check_root_pin`); под `--fix` — именованный
    `Check` со статусом `fail` вливается в общий список проверок (тот же
    механизм печати `[FAIL]`/подсчёта провалов/`sys.exit(1)`, что и у
    остальных доктор-проверок) — уборка веток при этом не запускается
    вовсе (требование 5/AC-6). Уборка игнорируемых файлов/мёртвых
    lease-групп/зависших тестов от origin не зависит и продолжает
    работать независимо от исхода сверки веток-сирот.
    """
    conn = doctor.store.db()
    # Стоп-кран волны, часть 2 (01M1THKRK8HPXA7Y2SRB0RFTN2, требование 3):
    # первым пунктом вывода, раньше остальных проверок — Оператор обязан
    # увидеть блокирующую причину, из-за которой `run`/`auto` self сейчас
    # отказывают, до любой другой диагностики.
    wave_breaker_alerts = doctor.runner.wave_breaker_alerts_open(conn)
    if wave_breaker_alerts:
        print("СТОП-КРАН ВОЛНЫ ОТКРЫТ — run/auto self не начинают новый "
             "агентный шаг:")
        for a in wave_breaker_alerts:
            print(f"  #{a['id']} {a['message']}")
        print(f"  `artel.py alert-ack <id> \"...\"` снимет блокировку\n")
    if restore:
        print("Recovery-сверка после восстановления .artel/ из бэкапа:")
        # SPEC 01M1NSR5M5THYRC0RFWPMVE2DW, требование 3/AC-6: тот же
        # вход восстановления пула, что `catalog.cmd_init()`.
        pool_restore_msg = doctor.pool_seal.restore_pool_if_missing(conn)
        if pool_restore_msg:
            print(pool_restore_msg)
    orphans = doctor._orphan_artifact_branches(conn)
    extra_checks = []
    if fix:
        if orphans is None:
            extra_checks.append(doctor.Check(
                "orphan-branches-origin", "fail",
                "origin недоступен (git ls-remote --heads origin "
                "'artifact/*' не ответил) — критерий сироты артефактных "
                "веток не вычислим, уборка artifact/*-веток не выполнена"))
        else:
            doctor._print_orphan_branch_candidates(orphans)
            removed = doctor.sweep_orphan_artifact_branches(conn, orphans)
            if removed:
                print(f"Осиротевшие артефактные ветки удалены ({len(removed)}):")
                for branch in removed:
                    print(f"  {branch}")
            elif orphans:
                # R1-F3 (ANSWER-3): найдены, но НИ ОДНО удаление не прошло —
                # честно об этом, не «не найдено» (расхождение с журналом
                # алертов, который sweep уже честно ведёт).
                print("Осиротевшие артефактные ветки найдены, но не удалены "
                     "— см. журнал алертов (doctor.cleanup.artifact_branches).")
            else:
                print("Осиротевших артефактных веток не найдено.")
        print("Уборка игнорируемых файлов артефактных веток живых задач:")
        doctor._fix_ignored_artifact_files(conn)
        doctor._fix_dead_lease_groups(conn)
        doctor._fix_hung_test_runs(conn)
        # Локальный слой моделей (SPEC 01M3009Y9AGGY6ZCFA7H1HJ1TD,
        # требование 7) — до `all_checks` ниже, чтобы проверка
        # «models-local» в том же прогоне уже видела положенный шаблон
        # (тот же приём, что у хуков защиты main ниже).
        doctor.fix_models_local()
        # Хуки защиты main (SPEC 01M2XMCC837R5CX9M58VARK85G, требование 4)
        # — до `all_checks` ниже, чтобы проверка «git-hooks» в том же
        # прогоне уже видела включённую защиту (AC-11).
        doctor._fix_git_hooks()
    else:
        if orphans is None:
            print("критерий не вычислим без origin")
        else:
            doctor._print_orphan_branch_candidates(orphans)
    checks = extra_checks + doctor.all_checks(conn)
    for c in checks:
        print(f"  [{doctor.LABELS[c.status]}] {c.name}: {c.detail}")

    triggers = doctor.alerts.open_alerts(conn, "trigger")
    if triggers:
        print("\nОткрытые триггеры (docs/triggers.md) — ack обязан нести решение:")
        for a in triggers:
            print(f"  #{a['id']} [{a['target'] or '-'}] {a['source']}: {a['message']}")

    failed = [c for c in checks if c.status == "fail"]
    if failed:
        print(f"\nDOCTOR: провалов {len(failed)} — чини по причинам выше")
        sys.exit(1)
    print("\nDOCTOR: ок")


def cmd_alert_ack(alert_id: str, resolution: str) -> None:
    conn = doctor.store.db()
    try:
        parsed_id = int(alert_id)
    except ValueError:
        sys.exit(f"alert-ack: '{alert_id}' — не номер алерта")
    error = doctor.alerts.ack(conn, parsed_id, "operator", resolution)
    if error is not None:
        sys.exit(f"alert-ack: {error}")
    print(f"alert #{parsed_id}: подтверждён")


def cmd_alert_ack_bulk(source: str | None, needle: str | None,
                       resolution: str | None, confirmed: bool) -> None:
    """`alert-ack --source <источник> --grep <подстрока> "<решение>" [--yes]`
    (SPEC 01M3YDHTY1Y67KB98FVSHREC4N, требования 4-7): открытые `incident`
    источника с подстрокой в тексте — перечнем без `--yes`, подтверждением
    каждого с `--yes`.

    `None` — аргумент не передан. Пустое или пробельное значение любого из
    трёх — отказ до чтения БД: пустая подстрока отобрала бы все `incident`
    источника, пустое решение закрыло бы пачку без следа «почему».

    Подтверждение — тот же `alerts.ack(..., "operator", resolution)`, что у
    одиночной формы: `ack_by` и текст решения совпадают байт-в-байт, отказ
    `ack` на одном алерте (его успели подтвердить между отбором и записью)
    не останавливает остальные, но даёт ненулевой код возврата.
    """
    for name, value in (("--source", source), ("--grep", needle),
                        ("текст решения", resolution)):
        if value is None or not value.strip():
            sys.exit(f"alert-ack: массовая форма требует непустой {name} — "
                     f'alert-ack --source <источник> --grep <подстрока> '
                     f'"<решение>" [--yes]')
    conn = doctor.store.db()
    incidents, skipped = doctor.alerts.bulk_ack_selection(conn, source, needle)
    print(f"alert-ack --source {source} --grep {needle!r}: отобрано открытых "
          f"incident: {len(incidents)}")
    if incidents:
        days = sorted(row["ts"][:10] for row in incidents)
        print(f"  диапазон дат: {days[0]} — {days[-1]}")
        print(f"  номера: {', '.join(str(row['id']) for row in incidents)}")
        for row in incidents:
            first_line = ((row["message"] or "").splitlines() or [""])[0]
            print(f"  #{row['id']} {row['ts']}  {first_line[:200]}")
    if skipped:
        kinds = {}
        for row in skipped:
            kinds[row["kind"]] = kinds.get(row["kind"], 0) + 1
        detail = ", ".join(f"{kind}: {n}" for kind, n in sorted(kinds.items()))
        print(f"  пропущено не-incident: {len(skipped)} ({detail}) — массовой "
              f"формой не подтверждаются, только одиночной alert-ack <id>")
    if not confirmed:
        print("предпросмотр: ничего не изменено; подтвердить — та же команда "
              "с --yes")
        return
    failures = []
    for row in incidents:
        error = doctor.alerts.ack(conn, row["id"], "operator", resolution)
        if error is not None:
            failures.append(error)
    print(f"подтверждено: {len(incidents) - len(failures)} из {len(incidents)}")
    if failures:
        sys.exit("alert-ack: не подтверждены — " + "; ".join(failures))
