# Записка analyst — 01M53B45XW3J56RJHGD70TD8A2 (D2)

## Выяснено
- Шаг 2 (после ANSWER-1, все ответы — дефолты): написан SPEC.md, status ready, guard ок; QUESTIONS.md удалён.
- SPEC: 12 требований, AC-1..AC-11, budget_usd 45 (рамка ТЗ). Сигнал объёма — 9 зон вне общих; заявлено деление на 2 части:
  D2-1 (brief.py, runner.py, providers/claude.py; скилы + меры роли; $25, первая) и
  D2-2 (gitcmd, ci, github_adapter, repo_context, projects, doctor/; токен + doctor; $45, после части 1 — doctor переиспользует проверку project_skills части 1).
- Сумма рамок частей $70 > рамки ТЗ $45 (калибровка монолита на 9 файлов ~$85) — вынесено Оператору в «Оценке объёма».
- Все git-вызовы пульта идут через `gitcmd.pult_env` (orchestrator/gitcmd.py:22) — токен п.1 укладывается в зону gitcmd.py.
- Белый список: `providers/claude.py:45` `ALLOWED_TOOLS`.

## Не сработало
- `rm` в Bash шага недоступен (command not found) — файл удалял через `python3 -c "os.remove(...)"`.
- guard отказывает SPEC за упомянутые пути вне зон (`../`, role_prompt.py, knowledge_cards.py) — назвал их в «Не входит».

## Где остановился
- SPEC сдан, шаг завершён.

## Чего не хватило
- Нет готового перечня всех вызовов `python3` ролями — собирал grep по skills/ и orchestrator/role_prompt.py (шаг 1).
