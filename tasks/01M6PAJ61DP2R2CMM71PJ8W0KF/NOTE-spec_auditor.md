# Записка spec_auditor

## Выяснено
- Визит 3 (spec_sha 0de2b3a3): решения гейта №2.1–2.7 внесены в SPEC; вердикт concerns, Д1–Д9.
- Якоря верны: runner.py:1186/1246/1364/1819-1827, doctor/cli.py:221-226/305-331, __init__.py:152-155, lease.py:399/414, acceptance.py:156; sandbox.py — подмена config на 1639-1641 (в SPEC 1638-1641).
- SPEC части 1 и родителя читаются `git show refs/artifacts/<id>:tasks/<id>/SPEC.md` из worktree.
- Главные: Д2 — гонка `doctor --fix` с собираемой версией `.v<нс>` (нет метки владельца); Д7 — `process_alive`=False для чужого хоста (lease.py:409) при общем демоне → снятие чужих живых стендов; Д1 — AC-4 без живой tmp-ссылки; Д3 — AC-5 не ловит неснятый `v` и сравнение по major.minor; Д4 — красная фаза AC-1 доходит до spawn_agent; Д5 — DOCKER_CONFIG пульта не задан; Д6 — cwd у `down` без `-f`; Д8 — строка в составе check_orphans уронит test_doctor.py:1040-1043.

## Не сработало
- docker в шаге не запускается (требует подтверждения) — опыт с CLI невозможен.

## Где остановился
- SPEC-AUDIT.md готов (status: ready), guard ок, временные файлы убраны.

## Чего не хватило
- Опыта с Docker CLI в шаге (`context inspect --format`, `down` без `-f`).
