# Записка spec_auditor

## Выяснено
- Визит 10 (spec_sha 55121bcc, коммит 8b183c446): разница с 7028feb8 — только внесение №9.1 (треб. 14, 15, 17, AC-2, AC-3, Материалы). Д1/Д2 визита 9 сняты.
- Опыт: mock.patch.object(os,'killpg') с сигналом 0 → PermissionError действует на liveness._group_exists; счёт вызовов с сигналом 0 точен; SIGKILL уходит настоящей функции, группа исчезает.
- pyproject.toml:13 — pytest-timeout 120 с: бесконечный цикл проб в реализации даст красный, не вечное зависание.
- liveness.terminate_process_group (:118-155) — SIGTERM + sleep, форме треб. 14 не подходит (SPEC его не называет).

## Не сработало
- Голый `sh` в Popen не находится (PATH окружения роли) — нужен `/bin/sh`.

## Где остановился
- SPEC-AUDIT.md: status ready, verdict pass; наблюдение — сигнал SIGKILL назван в треб. 17/AC, не в треб. 14 (без отклонения).

## Чего не хватило
- Ничего; история SPEC — `git log refs/artifacts/<id> -- tasks/<id>/SPEC.md`.
