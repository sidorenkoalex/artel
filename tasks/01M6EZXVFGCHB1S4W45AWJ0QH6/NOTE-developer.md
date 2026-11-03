# Записка developer — 01M6EZXVFGCHB1S4W45AWJ0QH6

## Выяснено
- Итерация 2 (REVIEW R1-F1): долгоживущие сторожа добавлены — `tests/test_push_hook_stand.py` (стенд `real_git`,
  17 тестов по пп. 1–4, 6 замечания) и 2 теста п. 5 в `tests/test_push_hook_units.py`. 32 passed; с соседями 98;
  test_invariants 88; plank-run 68. 20 временных мутаций — все красные. R1-F1 в реестре REVIEW.md размечен `fixed`.
- Мутация «`clone` убран из `HOSTING_SUBCOMMANDS`» выживает законно: `clone` разбирается раньше (`gitcmd.py:131-132`).
- Итерация 1: `ensure_clone` клонирует из `clone.parent` — проект клона ищется по url в argv (`_clone_project`).
  Хост записи для помощника — `ARTEL_HOSTING_HOST` (тест `test_appends_after_existing_git_config_entries`
  фиксирует 2 записи `GIT_CONFIG_*`). MR-стенды: адрес записи = путь bare-origin (ANSWER-1 п.1).

## Не сработало
- В стенде шпион `subprocess.Popen` перехватывает и `REAL_RUN` теста (run зовёт Popen модуля) — перед второй
  подготовкой проекта под шпионом нужен `Stand.unspy()`.
- Запись проекта без `token_slot` в targets.yaml отвергается схемой — убирать поле подменой `targets.load`.
- `scripts/guard.py` на файлах tests/ ищет frontmatter — гонять только на артефактах; заявки мутаций —
  `guard.test_functions_without_mutation_claim`.
- `pytest -n` в шаге отказывает сторож роли; Bash-инструмент отказывает командам с `$VAR`.

## Где остановился
- Шаг завершён, PLAN.md status: ready (шаг 7 добавлен). Карта перегенерирована.

## Чего не хватило
- Как планка помечает группы и почему всё «разовый» — из-за `scripts/guard.py::_GIT_MODULES` для долгоживущих.
