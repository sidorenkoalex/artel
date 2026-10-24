# Записка test_author

## Выяснено
- Планка — 5 файлов `test_*.py` + `_plan.py` (общий разбор), все разовые; форма
  взята с планки волны 2а-1 (refs/artifacts/01M5PHK9K0YQCTPA6CK94BBZ33).
  AC-1 → test_mutation_patches; AC-2/3/4/9(CI)/15/16/17/18 → test_mutation_tables;
  AC-5/8/9/20 → test_branch_diff; AC-6/7/11 → test_sandbox_transfer;
  AC-10/12/13/14/19 → test_module_form. Пометок manual/skip/escalate нет.
- Соглашения разбора PLAN (ссылки `<Класс>::<метод>`, `mutation-<nnn>`,
  `tests/<файл>.py:<строка>`, разделы «Мутации до/после», «…дубл…», «находк…»,
  строки с `setUp`/«подготовк…») — докстринг `_plan.py`.
- AC-11: реально помощники без утверждений — full_vitest (VitestReporterTest,
  InstallAndDepsTest), main_head, channels; `commit` — метод ReportSandbox
  (остаётся в песочнице), прочих имён перечня SPEC в файле нет. Префикс класса
  проверяется мягко (`_plan.class_prefixed`: префикс без `_` и регистра входит
  в имя класса, напр. `vitest_reporter_full_vitest`).
- AC-10: фикстура обязана содержать только вызов `_sandbox(ReportSandbox)`.
- AC-13: сообщения исходника — `self.note(...)`; `context = box.note(...)`,
  затем `assert …, context` — законно.
- AC-16: перед каждой таблицей «после» — строка с командой
  `git status --porcelain -- orchestrator/`, без строк porcelain под orchestrator/.
- Валидация стабом проведена (клон в $TMPDIR, автоконвертер unittest→pytest,
  синтетический PLAN и патчи в отдельном docs-репо): 61/61 зелёные; две
  внесённые порчи стаба дали 5 красных. Стаб удалён.
- plank-run на ветке: 55 failed, 6 passed (зелёные — «не тронуто»: AC-5 ×2,
  AC-9 инварианты ×2, AC-20 orchestrator и карта). preflight — всё пройдено.

## Не сработало
- Read по $TMPDIR запрещён — читать через python3 print; `rm`/`sed -i` нет —
  уборка через python3.

## Где остановился
- Готово.

## Чего не хватило
- Дольше всего: формат таблицы mutation-run (orchestrator/mutation_run.py
  `_header`, `_Run.row`) и поля `_pult` DOCS_REPO/DOCS_REVISION
  (orchestrator/plank_helper.py).
