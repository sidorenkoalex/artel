# Записка test_author

## Выяснено
- Планка (разовые, acceptance_tests/): test_ac6_artel_briefs_unchanged.py (AC-6 — пять точек артели на коде `_pult.DIFF_BASE` через `git archive` и на коде рабочей копии, сравнение побайтно; зелёный с рождения), test_ac12_target_onboarding_doc.py (AC-12, документ из `_pult.CODE_ROOT`; красен — документа нет).
- Долгоживущие: tests/test_01m5t18k1yfbya7mm1bbrv869a_conventions_brief.py (AC-1–5, 7, 14), tests/test_01m5t18k1yfbya7mm1bbrv869a_conventions_stamp.py (AC-8–11, 13). Все красны на текущем коде по верной причине.
- Сборка пяти точек — `role_prompt.mission_brief_package` (reviewer → `package["text"]`).
- `main` клона песочницы переставлен на коммит базы: иначе diff пакета ревьювера несёт CLAUDE.md базы.
- Бриф developer крупнее 64 КБ делится на части — AC-4 сверяет текст построчно.
- AC-5: `agent_wrapper` — плоское поле записи слоя репозитория (у соседки 01M5T19041 оно равнозначно `policy.agent_wrapper`); `make_project_repo` сам дописывает запись в слой репозитория.
- AC-9: сначала успешная отметка в исправном состоянии — иначе отказы «зелены», пока команды нет.
- Валидация стабом (brief, role_prompt, conventions.py, doctor/project_conventions.py, artel.py, docs) — всё зелёное, мутации ловятся; стаб удалён, `git status` — только два новых файла tests/.
- preflight — все проверки пройдены.

## Не сработало
- Долгоживущему файлу нельзя читать живой файл репозитория (`REPO_ROOT / "docs"…`) — AC-12 вынесен в разовый.
- `ls`/`rm` в оболочке нет; heredoc с `{"` блокируется — писать файлы через Write/Edit.

## Где остановился
- Готово к сдаче.

## Чего не хватило
- Формат поля `agent_wrapper` пришлось читать из SPEC соседки через `git show refs/artifacts/01M5T19041…`.
