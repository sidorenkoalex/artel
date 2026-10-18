# Записка test_author — 01M56TNX1WWKV8PVQ94FT4ZJQB

## Выяснено
- Прошлая попытка сдала шаг без единого теста (отказ трассируемости AC-1…AC-10).
- Образец песочницы — tests/test_01m56tnty7hec85mc940kzr1zj_helper_scope.py (часть 1): RealGitSandbox + make_project_repo, учебный backend (workdir: backend), вход — test_integrity.merge_gate_escalates.
- Находка пропуска — сегмент detail эскалации «<путь>: <маркер> на <имя>» (Finding.line, разделитель «; »); проход условного пропуска — запись журнала TEST_INTEGRITY_CONDITIONAL_SKIP_ACTION «<путь>::<имя> — <причина>».
- Приложения PLAN разбирает guard.plan_appendices (разделы «## Приложение…», блоки ```diff).

## Файлы (написаны)
- tests/test_01m56tnx1wwkv8pvq94ft4zjqb_skip_labels.py — AC-1…AC-8 (все сценарии меток и модульных пропусков; вход — merge_gate_escalates; 11 задач песочницы, ~14 с).
- tests/test_01m56tnx1wwkv8pvq94ft4zjqb_async_test_method.py — AC-9 (модульный, TEST_METHOD.findall).
- acceptance_tests/test_ac10_invariants_attachment.py — AC-10 (разовый, _pult + guard.plan_appendices, наложение на DIFF_BASE во временном индексе).
- Валидация стабом: временная реализация в test_integrity._compare (метки/pytestmark/модульные вызовы + поиск импортёров изменённой метки) — все 10 методов зелёные; мутации «нет поиска импортёров вне диффа» и «послабление и методам базы» — красные. Стаб откатан git checkout. AC-9 — стаб регулярки `^\s*(?:async\s+)?def` зелёный. AC-10 — фикстура PLAN зелёная/красная как ожидалось.
- Форма находки, на которую опирается планка: элемент детали «<файл>: <маркер> на <имя>» (имя — Класс::метод, функция модуля или Класс), маркер — любой текст.

## Не сработало
- Bash: ls/cat/find недоступны или просят подтверждения — Read/grep/git.

## Где остановился
- Всё написано; plank-run: AC-10 красна (PLAN.md нет) — ожидаемо; долгоживущие красны до реализации; preflight — все проверки «пройдена».
- docs/codebase-map.md не регенерировал: правка вне tests/ у test_author откатывается пультом — карту обновит developer.

## Чего не хватило
- Формы текста находки пропуска пришлось вычитывать из test_integrity._file_findings/Finding.line — публичного описания «вида находки» нет.
