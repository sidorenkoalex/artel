"""Красен до реализации: AC-2 падает для ВСЕХ четырёх ролей —
`role_prompt.mission_brief_package` пока не несёт буквальной строки
«рабочий каталог шага — <путь>; все пути ниже относительно него; запись
вне него недоступна» ни для одной из них (SPEC 01M1RQ12JVHE3PQYDFV1XPSTQ3,
требование 2) — эта строка ещё не существует в тексте промпта.

AC-1 красен для роли reviewer (не для analyst/test_author/developer —
их промпт уже сегодня называет SPEC.md/PLAN.md/REVIEW.md/acceptance_tests/
только относительным `tasks/<id>/...`): `orchestrator/review.py::
artifact_text` на отсутствующем PLAN.md/REVIEW.md (нет ни в ветке, ни в
рабочем дереве) падает в ветку `except (OSError, UnicodeDecodeError) as
exc: return None, f"(не показан: в ветке — {in_branch}; в дереве —
{exc})"` — текст `exc` (`FileNotFoundError`) несёт абсолютный путь под
`config.TASKS` буквально (`str(config.ROOT / rel)`, где `rel` начинается
с `tasks/<id>/...`, то есть содержит `str(config.TASKS)` целиком), и эта
строка уходит в ревью-пакет, а с ним и в промпт ревьювера.

Проверка ниже сверяет только `str(config.TASKS)` — БЕЗ параллельной
проверки на голый `str(config.ROOT)` (тот AC-1 тоже называет буквально) —
и это осознанный выбор, не недосмотр: критерий приёмки 2 (см.
`test_ac2_prompt_states_the_real_role_cwd_for_every_role` ниже) требует
буквальной строки с ФАКТИЧЕСКИМ `runner.role_cwd`, а тот для self/артели
(`workspace.path`) и для внешнего target (`config.PROJECTS/<target>/
workspace`) — ОБА пути `orchestrator/config.py` строит от `config.ROOT`
(`WORKTREES = ROOT / ".artel" / "worktrees"`, `PROJECTS = ROOT / ".artel"
/ "projects"`): голой `str(config.ROOT)` неизбежно окажется префиксом
ЛЮБОГО значения `role_cwd` в этой системе. Проверка «промпт не содержит
str(config.ROOT)» и требование 2 («промпт называет реальный role_cwd»)
поэтому взаимоисключающи буквально для каждой роли и любого target —
не только для reviewer и не только в этой песочнице (переубедиться:
добавить `self.assertNotIn(str(config.ROOT), prompt)` рядом с проверкой
ниже и прогнать против стаба AC-2 — упадёт для всех четырёх ролей
сразу). Собственная развёрнутая часть текста AC-1 — «все упоминания
SPEC.md, PLAN.md, REVIEW.md, ANSWER-*.md, acceptance_tests/ ... даны
путём вида tasks/<id>/...» — называет именно `config.TASKS`
(`tasks/<id>/...` — это и есть форма `config.TASKS`, только
относительная), и ровно она отличима от абсолютного `role_cwd` строкой:
`config.TASKS = config.ROOT / "tasks"` — путь-СОСЕД `role_cwd`
(`.artel/worktrees/...`/`.artel/projects/...`), не его префикс и не его
подстрока, так что проверка `config.TASKS` не конфликтует с обязательной
строкой AC-2 ни для одной роли — и при этом продолжает ловить дефект
`brief.py:466`/утечку `review.py`, показанные выше (обе используют
`config.TASKS`-подобный путь, не голый `config.ROOT`).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import RoleCwdSandbox  # noqa: E402
from orchestrator import config, workspace  # noqa: E402

# AC-8: skip — регрессия существующего набора (tests/test_brief.py,
# tests/test_agent_prompt.py и смежные) — это прогон УЖЕ СУЩЕСТВУЮЩИХ
# файлов после правки, а не новое проверяемое поведение; дублирующий их
# юнит-тест здесь не добавил бы покрытия. Регрессию проверяет разработчик
# прогоном этих файлов перед сдачей шага, и то же самое видит CI на любой
# коммит ветки.

ROLE_STATES = (
    ("analyst", "spec_writing", ("SPEC.md",)),
    ("test_author", "tests_writing", ("acceptance_tests/test_marker.py",)),
    ("developer", "in_dev", ("PLAN.md",)),
    ("reviewer", "review", ("REVIEW.md",)),
)


class Ac1NoAbsoluteTasksPathTest(RoleCwdSandbox):

    def setUp(self):
        super().setUp()
        # TZ.md делает роль analyst достижимой в состоянии spec_writing —
        # остальным трём ролям эта запись не мешает (`step_role` резолвит
        # их через `STATE_ROLE`, TZ.md не участвует).
        self.write_tz()

    def test_ac1_prompt_never_carries_the_absolute_tasks_path(self):
        """Промпт (миссия + бриф, у ревьювера — ещё и ревью-пакет) каждой
        из ролей analyst/test_author/developer/reviewer собирается и
        сверяется на отсутствие абсолютного `config.TASKS` — по разу на
        роль, каждый раз со своим состоянием задачи; см. докстринг модуля
        про то, почему параллельная проверка на голый `config.ROOT` здесь
        не ведётся (взаимоисключает требование 2 этой же SPEC).

        Ловит мутацию: кто-то вернёт в `orchestrator/brief.py` или
        `orchestrator/role_prompt.py` литеральный `str(config.TASKS /
        task_id / "SPEC.md")` вместо `f"tasks/{task_id}/SPEC.md"` —
        абсолютный путь этой же песочницы попадёт в промпт, и
        `assertNotIn` поймает совпадение (`config.TASKS` этой песочницы —
        заведомо непустая, уникальная для процесса строка, случайное
        совпадение с обычным текстом промпта исключено); та же проверка
        ловит и уже найденную утечку `orchestrator/review.py::
        artifact_text` (см. докстринг модуля) — `FileNotFoundError` на
        отсутствующем PLAN.md/REVIEW.md несёт `str(config.TASKS)` как
        часть своего текста.
        """
        task_ref = f"tasks/{self.TASK}"
        for role, state, artifacts in ROLE_STATES:
            with self.subTest(role=role):
                self.set_state(state)
                # Артефакт роли уже на месте — шаг укладывается в ОДНУ
                # попытку (критерий приёмки 7 этой же SPEC), промпт первой
                # и единственной попытки читается без побочного ретрая.
                for rel in artifacts:
                    self.seed_role_artifact(rel)
                self.run_agent((0, ["готово\n"]))
                prompt = self.prompt_text()

                self.assertNotIn(str(config.TASKS), prompt,
                                 f"{role}: абсолютный config.TASKS в промпте")
                self.assertIn(task_ref, prompt,
                             f"{role}: относительный {task_ref} не найден "
                             f"в промпте")


class Ac2CwdLineNamesTheActualRoleCwdTest(RoleCwdSandbox):

    def setUp(self):
        super().setUp()
        self.write_tz()

    def test_ac2_prompt_states_the_real_role_cwd_for_every_role(self):
        """Промпт каждой из четырёх ролей несёт буквальную строку
        «рабочий каталог шага — <путь>; все пути ниже относительно
        него; запись вне него недоступна» с фактическим значением,
        которое для этого шага вернул бы `runner.role_cwd` (для self/
        артели — `workspace.path(task_id)`, SPEC T045): критерий приёмки
        2 требует именно совпадения с реальным путём, не плейсхолдера.

        Ловит мутацию: кто-то заведёт строку с фиксированным текстом
        плейсхолдера («рабочий каталог шага — <путь>») вместо реального
        `cwd`, либо забудет добавить строку для одной из четырёх ролей —
        `assertIn` не найдёт точного совпадения (или найдёт для трёх из
        четырёх ролей, `subTest` укажет, для какой).
        """
        expected_cwd = str(workspace.path(self.TASK))
        expected_line = (
            f"рабочий каталог шага — {expected_cwd}; все пути ниже "
            f"относительно него; запись вне него недоступна")
        for role, state, artifacts in ROLE_STATES:
            with self.subTest(role=role):
                self.set_state(state)
                for rel in artifacts:
                    self.seed_role_artifact(rel)
                self.run_agent((0, ["готово\n"]))
                prompt = self.prompt_text()

                self.assertIn(expected_line, prompt,
                             f"{role}: строка рабочего каталога шага не "
                             f"найдена буквально в промпте")


if __name__ == "__main__":
    unittest.main()
