## Выяснено
После возврата аудита сдан QUESTIONS.md, status ready, два вопроса: (1) машинный мандат только на общий запрет true в tests/test_providers_codex.py::CuratedHomeTest::test_every_disabled_feature_is_false_in_the_curated_config; (2) адресная подготовка доверенного контекста положительных fixtures. ANSWER-1 требует эскалации общих helpers; ANSWER-3 не содержит машинной строки для provider assertions. UNKNOWN/socket и потолок $45 повторно не согласуются.
Инвентаризация F2: SuiteRunSandbox в старом suite_run, SuiteRunStand в readonly_db, LockTest в test_suite_run.py, BaseReuseTest в base_reuse, ProgressCountTest в subtest_failures. Четыре дополнительные точные зоны; readonly_db уже в SPEC. Нужны изолированный broker/регистрации/cleanup до команды, без fallback, внешнего broker, зависимости от порядка, изменения assertions или общего ROLES. Пять старых смен области developer не расширяются.
F3: QUESTIONS содержит раздельную пятиколоночную матрицу. Прежние parity/argv-тесты не доказывают эффективные approvals/файловые права; новые проверки обязательны по AC-17/19. Матрица готова для переноса после ответа.
ADR-0024/0025 прочитаны из main через git show; PLAN и NOTE-developer подтверждают EPERM прежней пробы, а не готовность канала.

## Не сработало
В PATH нет cat (exit 127); чтение продолжено pathlib через штатный python3. apply_patch отказал delete+add одного пути; записка записана pathlib. Полный набор и IPC-пробы не запускались.

## Где остановился
QUESTIONS.md: GUARD ок (1 файлов), exit 0. SPEC не менялся: SHA 4a08c32089ebd79a1fc35f620cc5983340c49254 совпал до/после. git status --short пуст. Только собственные QUESTIONS и NOTE-analyst записаны; код/PLAN/чужие записки не менялись, коммитов нет. Требуется штатный ответ Оператора; после него пересмотр SPEC и независимый аудит.
БД show: spec_writing, нужная ветка, $28.85/$45; остаток $16.15 до этого шага меньше прежней оценки ~$19.6 без аудита/live. Риск назван, потолок не поднят.

## Чего не хватило
Машинного мандата на конфигурационный assertion и явного разрешения подготовки общих fixtures. Поиск полного набора положительных вызывателей выявил ещё три файла помимо двух в аудите.

## Предложения системе
Содержательное разрешение ANSWER-3 не совпало с машинным форматом test_integrity._answer_mandate; нужна сверка до developer. При новом обязательном контексте нужно учитывать setup старых положительных тестов. В PATH роли отсутствует cat; чтение доступно через штатный python3.
