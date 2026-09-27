"""AC-7 — карта исполнителей и локальный слой моделей в тесте, предмет
которого не сама карта, — фикстура сценария, не настоящий файл репозитория.

Источник — SPEC.md, «Критерии приёмки»:

AC-7. После применения приложения `skills/test-authoring.md` требует,
чтобы карта исполнителей (roles.yaml) и локальный слой моделей в тесте,
предмет которого не сама карта, были фикстурой сценария, а не настоящим
файлом репозитория.

Проверяется абзац скила после применения приложений PLAN к базе сравнения
(см. `_appendix`): критерий не называет раздела, поэтому ищется абзац про
`roles.yaml`.

Красен до реализации: приложения на `skills/test-authoring.md` ещё нет — в
базе сравнения `roles.yaml` не упоминается вовсе, правила о фикстуре
окружения в скиле нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _appendix  # noqa: E402

ROLES_MAP = "roles.yaml"


class RolesMapIsFixtureTest(unittest.TestCase):

    def setUp(self):
        self.state = _appendix.state()
        self.text = _appendix.applied_text(_appendix.TEST_AUTHORING)
        self.candidates = _appendix.paragraphs_with(self.text, ROLES_MAP)

    def test_ac7_roles_map_and_models_layer_are_scenario_fixtures(self):
        """Скил требует строить окружение теста на фикстуре: абзац про
        `roles.yaml` называет и локальный слой моделей, и саму фикстуру, и
        противопоставляет ей настоящий файл репозитория.

        Ловит мутацию: правка называет фикстурой только карту исполнителей и
        забывает локальный слой моделей (`.artel/models.yaml`) — вторую
        половину того же повода a6da0abe, от которого краснели три задачи —
        в абзаце не окажется слова о моделях, и проверка покраснеет.
        """
        self.assertTrue(
            self.text,
            f"текст `{_appendix.TEST_AUTHORING}` после применения приложений "
            f"пуст ({self.state.diagnosis()})")
        self.assertTrue(
            self.candidates,
            f"в `{_appendix.TEST_AUTHORING}` нет абзаца про `{ROLES_MAP}` "
            f"({self.state.diagnosis()})")
        needles = ("фикстур", "модел")
        with_fixture = [p for p in self.candidates
                        if not _appendix.missing(p, needles)
                        and (_appendix.has(p, "настоящ")
                             or _appendix.has(p, "реальн"))]
        self.assertTrue(
            with_fixture,
            f"абзац про `{ROLES_MAP}` не требует фикстуры сценария вместо "
            f"настоящего файла (ищутся «фикстур», «модел» и "
            f"«настоящ»/«реальн» в том же абзаце; недостающее по абзацам: "
            f"{[_appendix.missing(p, needles) for p in self.candidates]}) "
            f"({self.state.diagnosis()})")

    def test_ac7_rule_applies_when_the_map_is_not_the_subject(self):
        """Тот же абзац ограничивает правило тестом, ПРЕДМЕТ которого не
        сама карта: тест про саму карту исполнителей вправе читать настоящий
        файл.

        Ловит мутацию: правка запрещает настоящий файл любому тесту — тогда
        тест самой карты (проверка её схемы, существующие тесты
        `roles.yaml`) оказался бы вне правил скила — в абзаце не окажется
        оговорки о предмете теста, и проверка покраснеет.
        """
        self.assertTrue(
            self.candidates,
            f"абзаца про `{ROLES_MAP}` нет вовсе — оговорку о предмете теста "
            f"проверять не на чем ({self.state.diagnosis()})")
        scope_words = ("предмет", "не сама карта", "не о самой карте",
                       "не про саму карту")
        scoped = [p for p in self.candidates
                  if any(_appendix.has(p, w) for w in scope_words)]
        self.assertTrue(
            scoped,
            f"абзац про `{ROLES_MAP}` не оговаривает, что правило — про тест, "
            f"предмет которого не сама карта (ни одного из оборотов "
            f"{list(scope_words)} в абзаце нет) ({self.state.diagnosis()})")


if __name__ == "__main__":
    unittest.main()
