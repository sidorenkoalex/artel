## Выяснено
- Код уже реализует ANSWER-1 пп. 1–4; прошлый отказ advance — инвариант 35: адреса `*.example` в tests/test_doctor_gitlab_ci_file.py.
- Хосты заменены: `git.example` → `localhost`, `other.example` → `127.0.0.1`; проверка — `guard.network_address_errors_from_files([(путь, текст)])` даёт [].
- Bash шага ограничен: ls/wc/cp отказаны; работают python3, git, pytest.
## Где остановился
- Шаг завершён: 24 passed в файле, plank-run 1 passed, карта перегенерирована, PLAN ready.
## Не сработало
- —
## Чего не хватило
- Правило «в tests/ только localhost/127.0.0.1» (инвариант 35) всплыло только отказом advance; в скиле coding-standards его нет.
