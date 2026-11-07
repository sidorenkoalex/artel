# Записка spec_auditor

## Выяснено
- tests/test_01m6ezxvfgxc6wbda9qjesazrw_hosting_registry.py:32-33,114-117: WITHOUT_REPORT пустеет, когда у _GitHub появится job_test_report → оба варианта test_ac15_* из passed становятся skipped; гейт исходов (outcome_integrity.compare :226 BECAME_SKIPPED) на in_dev→verifying артели (targets.yaml:51 report: junit-xml) откажет — мандата на этот файл нет.
- parse_junit (reporters/outcome.py:163-201) отдаёт список CaseResult с id компонента и исходом passed, не «classname::name → success»; ТЗ/SPEC требование 2 о нём неверно.
- ci.gh (ci.py:91-93) text=True: бинарный zip даёт UnicodeDecodeError (опыт), не пойман — нужен отдельный бинарный вызов gh.
- Требование 1 «последний по времени завершения» против ci._last_job/outcome_integrity._ci_report (max Job.id) — расхождение ТЗ и ANSWER-1 п.2.
- Отображение заключений GitHub в статусы GitLab не задано (JOB_FINISHED ci.py:1339; _CI_FIT_STATUSES outcome_integrity.py:1045).
- zipfile.extractall сам чистит '..' и '/' (опыт) — отказа не даёт, AC-3 это ловит.
## Не сработало
- `cd W && grep` отклоняется песочницей — абсолютные пути.
## Где остановился
- SPEC-AUDIT.md написан, verdict concerns.
## Чего не хватило
- Поиск тестов, которые станут skip (не red) от реализации — нигде не описан как класс.
