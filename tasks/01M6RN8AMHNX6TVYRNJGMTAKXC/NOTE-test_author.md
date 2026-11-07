# Записка test_author

## Выяснено
- Долгоживущий `tests/test_01m6rn8amhnx6tvyrnjgmtakxc_commit_trailer.py`: AC-2 (загрузка `""` в запись), AC-4 (9 значений из файла слоя + две строки через `merge_local`), AC-5 (`target-set` через `artel.main`).
- Планка `acceptance_tests/test_commit_message.py` (Группа: разовый — вынужденно): AC-1, AC-2 (текст сообщения), AC-3 — всё через `gitcmd.pult_message`. guard (`scripts/guard.py::_GIT_MODULES`, признак «git-модуль») закрывает долгоживущему файлу импорт `orchestrator.gitcmd`, а `pult_message` живёт там.
- Красная фаза: всё красное с «раздел 'policy': неизвестное поле 'commit_trailer'», AC-3 (3 варианта) зелёный с рождения.
- Стаб (поле в LOCAL_FIELDS.policy и DELIVERY_POLICY_FIELDS; `[A-Za-z0-9-]+: .*\S.*` без `\n`, либо `""`, в `_check_delivery`; `pult_message` берёт `entry.get("commit_trailer", PULT_ACTOR_TRAILER)`, пустое — без абзаца): планка 8/8, долгоживущий + signature + entry_checks 41/41. Стаб снят, дерево чистое.
- preflight: всё «пройдена».

## Не сработало
- Первый вариант — всё в долгоживущем файле — preflight отклонил («git-модуль»).
- Прогон rewrite_flow не уложился в 5 минут, его не гонял.

## Где остановился
- Шаг готов к сдаче.

## Чего не хватило
- Правило «долгоживущему файлу нельзя импортировать gitcmd» конфликтует со свойствами кода, которые живут в gitcmd (`pult_message`); пришлось ставить группу «разовый» на свойство кода.
