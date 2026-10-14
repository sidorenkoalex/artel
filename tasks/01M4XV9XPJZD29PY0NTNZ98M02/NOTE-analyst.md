## Выяснено

SPEC.md готов, status: ready, AC-1–AC-8, budget_usd: 40 при рамке $50. Включены точная таблица всех исходов acquire и пятиколоночная матрица неослабления. Guard: «ок (1 файлов)». Код не менялся, git status --short пуст.

Дефект подтверждён в sqlite3.connect(":memory:") со schema.SCHEMA: строка remote-host.invalid, своя session_id, os.getpid(), свежий heartbeat штатного формата. При обоих same_host_ok исходный acquire возвращает (None, False) и меняет hostname/heartbeat_ts. Проверка живости подменена исключением — не вызывалась; второго хоста и процессов не было.

Remote same_host_ok без мутации уже закреплён тестом tests/test_lease.py:285, класс OwnSessionLiveOtherPidTest (в ТЗ имя класса неточно). Его явно приняло REVIEW итерации 2 задачи 01M2B6JWGS9HMR9XZJBASXVNSY, R1-F1. Старый SPEC 01M1VBEDGM описывал общий remote отказ, ANSWER-1..3 его касались FSM; позднейшее принятое исключение своей сессии сохраняется. Коллизия PID исправляется без смены ожиданий старых тестов.

Сверены все вызовы acquire/run_locked: same_host_ok=True только budget, force=True только kill, остальные — дефолтные. TTL сейчас относится только к другой сессии; F приоритетнее S; у чужой local свежей сессии S приоритетнее перехвата dead PID. Kill сначала проверяет живой цикл/--yes. Подробности и исторические refs находятся в SPEC.

Узкий прогон: python3 -m pytest -q tests/test_lease.py::OwnSessionLiveOtherPidTest tests/test_budget_live_lease_and_escalation.py::AcquireSameHostOkTest — 10 passed.

## Не сработало

cat отсутствует в PATH (command not found); чтение через pathlib штатного python3. Аномалия записана в «Предложения системе» SPEC.

## Где остановился

Сдан SPEC, исправление не реализовывалось. Документы задачи не коммитились. show читает прежний draft из ссылки документов до автокоммита шага; файл каталога документов имеет ready.

## Чего не хватило

Для точной границы remote same_host_ok понадобился исторический REVIEW R1-F1, не только старый SPEC budget. Ссылки доступны локально в refs/artifacts, выгрузка не потребовалась.
