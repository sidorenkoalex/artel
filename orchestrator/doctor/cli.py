"""Пакет orchestrator/doctor -- команда doctor: all_checks, cmd_doctor, cmd_alert_ack.

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
    # Действующий тариф моделей (SPEC 01M300A14KRHCFB0DQXVCBJEKF,
    # требование 8) — сразу за слоями, по которым он и разрешается:
    # протухшая цена и смена модели мимо тарифа читаются вместе с
    # цепочкой роли, а не в конце списка, где их не связать с ней глазом.
    checks.append(doctor.check_model_tariff_freshness())
    checks.append(doctor.check_model_tariff_vs_model_change(conn))
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
    checks.append(doctor.check_git_hooks())
    checks.append(doctor.check_role_log_pool_leak(conn))
    checks.append(doctor.check_canary_pool_drift())
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
