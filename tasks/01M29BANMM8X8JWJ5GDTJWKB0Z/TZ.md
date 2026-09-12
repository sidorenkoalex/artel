---
task: 01M29BANMM8X8JWJ5GDTJWKB0Z
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: прогоны тестов ролями и шаг CI на минимальной версии Python — через pytest с таймаутом, тем же раннером, что у пульта

Источник: вопрос Оператора 12.09 при разборе красного CI ветки lease
(01M290PS4Z): шаг CI «tests.test_invariants на минимальной объявленной
версии Python» до сих пор идёт через unittest, тогда как основной прогон
переведён на pytest (01M291M2Z7, pytest-xdist). Решение Оператора 12.09:
одна задача на два хвоста — шаг CI и инструкции ролям.

Факты:
- `.github/workflows/ci.yml`, задание `python`: основной прогон —
  `python3 -m pytest tests -n auto -p no:cacheprovider -p timeout -p
  xdist -o timeout=120` (строка 215); затем `actions/setup-python` меняет
  интерпретатор на минимальную версию из `scripts/stack_ci.py --min` и
  запускает `python3 -m unittest tests.test_invariants -v` (строка 236)
  без установки `requirements.lock` для этого интерпретатора, без
  таймаута на тест; `timeout-minutes` в ci.yml нет ни у одного задания —
  зависший тест держит раннер до общего лимита GitHub (6 часов).
- Пульт гоняет планку и полный набор через pytest:
  `orchestrator/acceptance.py::_pytest_command` — `[stack.
  pytest_python_executable(), "-m", "pytest", *args, "-p",
  "no:cacheprovider", "-p", "timeout", "-o", f"timeout={stack.
  PER_TEST_TIMEOUT_SEC}"]` (строки 19–38); `stack.PER_TEST_TIMEOUT_SEC =
  120` (`orchestrator/stack.py:77`).
- Ролям же велят unittest: миссия test_author в `orchestrator/
  role_prompt.py:63` — «Прогони `python3 -m unittest discover -s
  <task_ref>/acceptance_tests`»; `skills/test-authoring.md:151` — та же
  команда в разделе «Перед завершением»; `skills/coding-standards.md:78–79`
  — «тесты затронутых модулей (`python3 -m unittest tests.test_<модуль>`)».
  Роль проверяет планку одним раннером, пульт принимает другим; в
  docs/operator-session.md:193 записан случай, когда прогон через unittest
  завис и шаг ушёл в таймаут на $35 — pytest-timeout это ловит.
- Роль может звать pytest: `runner.role_env` ставит `<.artel/venv>/bin`
  первым в PATH (`_venv_interpreter_bin`, строки 519–542), белый список
  инструментов роли — `Bash(git:*),Bash(python3:*)` (`role_cmd`, строка
  705).
- `.github/`, `skills/` — защищённые пути (`config.PROTECTED_PATHS`):
  правит только Оператор коммитом в main, задача предлагает правку
  приложением к PLAN (unified-дифф) — текст отказа
  `fsm_advance._protected_path_refusal_detail`.

Требуется:
1. `orchestrator/role_prompt.py`: пункт 5 миссии test_author вместо `python3 -m unittest discover -s <task_ref>/acceptance_tests` даёт команду pytest той же формы, что `acceptance._pytest_command`: `python3 -m pytest <task_ref>/acceptance_tests -p no:cacheprovider -p timeout -o timeout=<stack.PER_TEST_TIMEOUT_SEC>`, значение таймаута подставляется из константы `stack.PER_TEST_TIMEOUT_SEC`, не литералом; остальной текст пункта (про автокоммит, про неприкосновенность кода и SPEC.md) без изменений.
2. Приложение к PLAN.md (unified-дифф, защищённый путь, коммит Оператора): в `.github/workflows/ci.yml` шаг «tests.test_invariants на минимальной объявленной версии Python (AC-2)» перед прогоном ставит зависимости `python3 -m pip install -r requirements.lock` для нового интерпретатора и запускает `python3 -m pytest tests/test_invariants.py -p no:cacheprovider -p timeout -o timeout=120` (литерал 120 дублирует `stack.PER_TEST_TIMEOUT_SEC` с тем же комментарием об известном ограничении, что у основного шага); заданию `python` добавляется `timeout-minutes: 40` с комментарием, что это страховка от зависшего раннера, а не рабочий ориентир.
3. То же приложение: `skills/test-authoring.md` раздел «Перед завершением» и `skills/coding-standards.md` раздел «Тесты» вместо команд unittest дают команды pytest той же формы (`python3 -m pytest tasks/<id>/acceptance_tests -p no:cacheprovider -p timeout -o timeout=120` и `python3 -m pytest tests/test_<модуль>.py -p no:cacheprovider -p timeout -o timeout=120`), с одной фразой, что это тот же раннер и таймаут, которыми пульт принимает планку; слова «в переднем плане с таймаутом» сохраняются.
4. Тесты в tests/: миссия test_author (`role_prompt.mission_brief_package` или функция, собирающая пункт 5) содержит `-m pytest`, `-p timeout` и `timeout=<PER_TEST_TIMEOUT_SEC>` и не содержит `unittest discover` (мутация «литерал 120 вместо константы» — красный при подмене `stack.PER_TEST_TIMEOUT_SEC` в тесте); существующие тесты role_prompt — без ослабления.

Зоны: orchestrator/role_prompt.py, tests/.

Приложением: orchestrator/acceptance.py (форма команды pytest), orchestrator/stack.py (константа таймаута), .github/workflows/ci.yml, skills/test-authoring.md, skills/coding-standards.md (защищённые пути — только предложение диффа).

Не входит: перевод прогонов пульта (acceptance.py) — уже на pytest; параллель xdist для шага на минимальной версии (один файл, не нужна); правка docs/operator-session.md; изменение `requirements.lock` и `stack.py`; переименование или перенос tests/test_invariants.py.

Рамка: $25.
