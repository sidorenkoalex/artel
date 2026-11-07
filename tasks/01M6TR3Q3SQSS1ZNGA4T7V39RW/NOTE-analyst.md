# Записка analyst

## Выяснено
- Шаг 2 (после аудита fail): вместо правки SPEC — батч QUESTIONS.md, 7 вопросов, guard ок. SPEC.md не тронут.
- Факты аудита подтверждены по коду: artel.py:2797-2798 (plank-run теряет минуты --wait); снятие стенда только finally acceptance.py:1464-1473, забытые стенды — doctor/orphans.py:385-410; deferrable закрыт (suite_lock.py:200-222); suite-run --wait — suite_run.py:824-857; Codex пишет только suite_lock.directory() (providers/codex.py:416-440); ACCEPTANCE_TIMEOUT_SEC 300 + COMPOSE_UP_DOWN_SEC 300 > SUITE_RUN_MAX_WAIT_MIN 9.
- Дефолты батча: 1A (зона artel.py, иначе B), 2A+B, 3A (время запроса ≥ начало шага; ждущие в конце шага — отказ), 4A (поля вид/файл/id/время), 5A, 6A (журнал пишет исполнитель напрямую, suite_lock.py из зон уходит), 7A (suite_lock.directory()).
- Сам поправлю в SPEC после ответа: Б3 (узел планки — путь cmd_plank_run целиком), Д2 (без poll/pid FakeProc), Е4 (оба признака роли в AC прямого отказа), безопасность AC-3 (подмена config.LOGS, снятие отвязанного фона по pid из run.json).

## Не сработало
- `ls` в оболочке нет (command not found) — каталог смотреть через Read/Glob.

## Где остановился
- QUESTIONS.md сдан (status ready). После ANSWER: переписать SPEC по решениям, удалить QUESTIONS.md через task-rm.

## Чего не хватило
- Ничего.
