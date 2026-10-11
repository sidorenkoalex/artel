"""AC-1 (tasks/01M1GV6H5DDDCWW4G3GW1D3A1X/SPEC.md): каждый компонент
недоверенного содержимого, сегодня включаемый в бриф роли
(`brief.developer_brief`, `brief.analyst_map_component`,
`brief.test_author_answer_component`, `brief.advance_refusal_history`) и
в ревью-пакет (`review.review_package`), обёрнут парой граничных
маркеров с общим для этого запуска непредсказуемым идентификатором.

Формат самого маркера SPEC не задаёт — тесты ищут его структурно
(`_sandbox.marker_id_for`): общий токен-кандидат вплотную ДО и ПОСЛЕ
тела компонента. См. докстринг `_sandbox.py`.

Красен до реализации: маркеров сегодня нет вовсе — `marker_id_for`
бросает `AssertionError` («не найден ровно один общий идентификатор»),
потому что кандидатов ноль.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (BriefSandbox, CONVENTIONS_SMALL, FakeGitDiff,  # noqa: E402
                      MAP_FRESH, PLAN_MD, REVIEW_MD, SPEC_MD, SPEC_SMALL,
                      TASK, build_review_package, marker_id_for,
                      standard_files)

from orchestrator import store  # noqa: E402


class Ac1DeveloperBriefTest(BriefSandbox):

    def test_ac1_developer_brief_wraps_spec_map_and_conventions(self):
        """Каждый из трёх компонентов брифа разработчика (SPEC, карта,
        конвенции) несёт свою пару маркеров с ОДНИМ и тем же
        идентификатором запуска.

        Ловит мутацию: маркеры добавлены только вокруг одного компонента
        (например только SPEC), а карта/конвенции остаются голыми — тест
        краснеет на `marker_id_for` для непокрытого компонента.
        """
        text = self.build_developer_brief()

        spec_id = marker_id_for(text, SPEC_SMALL.strip())
        map_id = marker_id_for(text, MAP_FRESH.strip())
        conv_id = marker_id_for(text, CONVENTIONS_SMALL.strip())

        self.assertEqual(spec_id, map_id,
                         "SPEC и карта одного и того же запуска обязаны "
                         "нести общий идентификатор границы")
        self.assertEqual(map_id, conv_id,
                         "карта и конвенции одного и того же запуска "
                         "обязаны нести общий идентификатор границы")

    def test_ac1_advance_refusal_history_is_wrapped_when_present(self):
        """Блок «история отказов advance» — тоже недоверенное содержимое
        (SPEC требование 1 прямо называет `brief.
        advance_refusal_history` источником «логов») и обязан нести пару
        маркеров с тем же идентификатором, что и остальные компоненты
        БРИФА РАЗРАБОТЧИКА этого запуска — `advance_refusal_history`
        вызывается отдельно от `developer_brief`, но оба принадлежат
        одному запуску шага роли.

        Ловит мутацию: `advance_refusal_history` продолжает возвращать
        текст без обвязки маркерами вовсе.
        """
        from orchestrator import brief as brief_mod

        store.journal(self.conn, TASK, "fsm",
                      "переход отклонён: трассируемость AC",
                      "МАРКЕР-ДЕТАЛЬ-ОТКАЗА-AC-2")

        text = brief_mod.advance_refusal_history(
            self.conn, TASK, "developer", "in_dev")

        self.assertNotEqual(text, "", "история отказов обязана быть непустой")
        marker_id_for(text, "МАРКЕР-ДЕТАЛЬ-ОТКАЗА-AC-2")


class Ac1AnalystBriefTest(BriefSandbox):

    def test_ac1_analyst_brief_wraps_the_map_component(self):
        """Единственный всегда присутствующий компонент брифа analyst —
        карта кодовой базы — обёрнут парой маркеров.

        Ловит мутацию: `analyst_map_component` продолжает склеивать карту
        в текст без обвязки маркерами.
        """
        text = self.build_analyst_brief()

        marker_id_for(text, MAP_FRESH.strip())

    def test_ac1_analyst_brief_wraps_questions_and_answer_with_one_id(self):
        """QUESTIONS.md и ANSWER-n.md — тоже недоверенные компоненты
        брифа analyst (SPEC требование 1: «включая историю отказов... —
        это и есть логи источника», тот же принцип касается любого
        текста, попавшего в репозиторий не от оркестратора) — оба несут
        маркеры с общим идентификатором вместе с картой.

        Ловит мутацию: QUESTIONS/ANSWER подмешиваются в бриф analyst
        текстом как есть, без обвязки.
        """
        self.write_questions("МАРКЕР-ВОПРОСА-AC1")
        self.write_answer(1, "МАРКЕР-ОТВЕТА-AC1")

        text = self.build_analyst_brief()

        map_id = marker_id_for(text, MAP_FRESH.strip())
        q_id = marker_id_for(text, "МАРКЕР-ВОПРОСА-AC1")
        a_id = marker_id_for(text, "МАРКЕР-ОТВЕТА-AC1")

        self.assertEqual(map_id, q_id)
        self.assertEqual(map_id, a_id)


class Ac1TestAuthorBriefTest(BriefSandbox):

    def test_ac1_test_author_brief_wraps_the_answer_component(self):
        """Единственный компонент брифа test_author — ANSWER-n.md
        последней эскалации — обёрнут маркерами.

        Ловит мутацию: `test_author_answer_component` продолжает
        возвращать `ANSWER` текстом как есть.
        """
        self.write_answer(1, "МАРКЕР-ОТВЕТА-TEST-AUTHOR")

        text = self.build_test_author_brief()

        self.assertIsNotNone(text)
        marker_id_for(text, "МАРКЕР-ОТВЕТА-TEST-AUTHOR")


class Ac1ReviewPackageTest(unittest.TestCase):

    def test_ac1_review_package_wraps_spec_plan_and_previous_review(self):
        """SPEC, PLAN и REVIEW.md прошлой итерации ревью-пакета — каждый
        несёт свою пару маркеров с общим для пакета идентификатором.

        Ловит мутацию: обвязка добавлена только вокруг diff'а (AC-2), а
        SPEC/PLAN/прошлый REVIEW остаются без маркеров.
        """
        files = standard_files(with_prev_review=True)
        git = FakeGitDiff(files=files)

        package = build_review_package(git, iteration=2, prev_sha="deadbeef")
        text = package["text"]

        spec_marker = "Маркер-тела-SPEC-ревью-пакета."
        plan_marker = "Маркер-тела-PLAN-ревью-пакета."
        prev_review_marker = "Маркер-тела-прошлого-REVIEW."
        self.assertIn(spec_marker, text)
        self.assertIn(plan_marker, text)
        self.assertIn(prev_review_marker, text)

        spec_id = marker_id_for(text, spec_marker)
        plan_id = marker_id_for(text, plan_marker)
        prev_id = marker_id_for(text, prev_review_marker)

        self.assertEqual(spec_id, plan_id)
        self.assertEqual(plan_id, prev_id)


if __name__ == "__main__":
    unittest.main()
