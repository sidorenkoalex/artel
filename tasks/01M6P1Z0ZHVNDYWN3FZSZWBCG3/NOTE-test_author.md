# NOTE test_author

## Выяснено
- AC-1..AC-8 — долгоживущий файл tests/test_01m6p1z0zhvndywn3fzszwbcg3_submodule_tokens.py
  (61 случай); AC-9 — разовый acceptance_tests/test_ac9_untouched.py (шесть файлов не в
  `changed_paths()`; их зелёность держит полный прогон tests/ пультом — шесть файлов идут
  131 с, это больше предела 120 с на тест планки).
- Публичные входы тестов: `workspace.ensure_clone` (к `_clone_submodules`; клон — ответ
  песочницы на `git clone`), `repo_context.git`, `doctor.project_entry_checks`,
  `doctor.misc_checks.gh_env`, `ci.gh(repo=)`, `gitlab_adapter.token_user`.
- Инвариант 35 (guard): в tests/ адреса `http(s)://` только на localhost/127.0.0.1, сверка хоста
  точная, ловит и шаблоны `{host}`. Хост записи — `localhost`, другой — `127.0.0.1`, регистр —
  `LocalHost`, порт — 8443; схемы собираются как `"https" + "://"`, адреса — через `fmt()`.
- Ход AC-6 к `_clone_submodules` в процессе роли: признак ARTEL_ROLE ставится сразу после
  ответа песочницы на `git clone`.
- Валидация стабом (targets/gitcmd/workspace/doctor): 61/61 зелёные; 6 мутаций стаба ловятся.
  Стаб откачен `git checkout --`; рабочая копия — только новый файл tests/.
- На коде main: 51 красный (поле неизвестно), 10 зелёных (AC-2 без поля ×6, AC-4 без поля,
  AC-5 operator без поля, AC-3 «другой порт»/«другой хост» — тривиально).

## Не сработало
- Первая редакция с `git.example.test` — отказ предпроверки по инварианту 35.

## Где остановился
- Готово: plank-run 6 passed; preflight — все проверки пройдены.

## Чего не хватило
- Правило инварианта 35 (сетевые адреса в tests/) не упомянуто в test-authoring — нашёл только
  отказом preflight (scripts/guard.py::network_address_hits).
