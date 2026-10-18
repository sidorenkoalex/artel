# Записка analyst — 01M574A6YQHAPASS9716Z11G4Q

## Выяснено
- Итерация 2 (возврат аудита 1 из 2): SPEC переписан, guard — ок, status: ready, 12 AC, budget 35 (класс ~45 — отмечено в «Оценке объёма»).
- Закрытие отклонений аудита:
  1. Разборщики note: verifying_is_red (ci.py:835; auto.py:485, ci_rerun.py:89, watch.py:219), red_status_sha (ci.py:848; ci_rerun.py:90), status_kind (ci.py:1014; fsm_merge_gate.py:363) — требование 5, AC-2/3/4/6.
  2. Триггер = событие `pull_request` запуска Actions (основание: Draft-MR fsm_advance.py:356/:624 и CI_WAIT_WARNING project_checks.py:18), без чтения клона. Запуски других событий остаются в вердикте (красный — красный, идущий — идёт); зелёный требует ≥1 завершённого pull_request. Только push-зелёные без pull_request — как «нет запусков». failed_check_names — без фильтра события и ветки (паритет с check-runs ci.py:899) → вершина main (push) работает (AC-7).
  3. Отбор по head_branch как _other_branch — требование 2, AC-5.
  4. AC-4 фиксирует оба ответа gh run list (пусто → NONE, есть → RUNNING).
  5. AC-9 называет 403 «API rate limit exceeded».
  6. doctor: имя project-ci-token-<проект>, ROLE_SKIP в роли, NOT_APPLICABLE артели, gh_env-авторизация, нет gh/слот — skip, check-runs 401/404/5xx — fail.
- Ссылки fsm_merge_gate исправлены на :591/:630 (охрана :583/:626).

## Не сработало
- `ls`/`cat` в Bash нет (command not found) — читать Read-инструментом.

## Где остановился
SPEC.md готов (ready), guard ок. Решения по п.6 (имя проверки, fail на 401/404/5xx) и бюджет — материал для правки Оператора на гейте.

## Чего не хватило
Карты потребителей текста note статуса CI — нашёл grep'ом по verifying_is_red|red_status_sha|status_kind.
