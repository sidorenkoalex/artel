"""AC-1 — 01M3H3JRBD544GQ10SS3DBGEVP: источник перечня ролей предполёта.

Источник — SPEC.md, «Критерии приёмки»:

AC-1. Перечень ролей doctor включает все роли карты исполнителей с
`executor: agent`, в том числе analyst, и не формируется из
`config.STATE_ROLE`; `config.STATE_ROLE` и его читатели не изменены.

Красен до реализации: `doctor.agent_roles()` собран из
`config.STATE_ROLE.values()` — analyst в перечень не попадает вовсе.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, doctor, roles  # noqa: E402
from tests.sandbox import TmpDirTest  # noqa: E402

from _analyst import ANALYST, roles_text  # noqa: E402

#: Состояния FSM, за которыми `config.STATE_ROLE` закрепляет роль сегодня.
#: Литерал здесь — предмет критерия, а не предпосылка сценария: AC-1
#: требует, чтобы словарь остался нетронутым, и сверять «не изменён» не с
#: чем, кроме его сегодняшнего состава.
STATE_ROLE_KEYS = {"tests_writing", "in_dev", "review"}

#: Состояние, на котором работает analyst. В `STATE_ROLE` его нет
#: намеренно (`orchestrator/runner.py`, докстринг `role_for_state`) —
#: именно туда потянется рука, чтобы «добавить analyst в перечень», не
#: меняя источник.
ANALYST_STATE = "spec_writing"


def map_agent_roles() -> list:
    """Отсортированные роли карты исполнителей с `executor: agent` —
    прочитанные из того же файла, что читает `doctor`, без предположений
    о его сегодняшнем содержимом."""
    return sorted(name for name, entry in roles.load().items()
                  if isinstance(entry, dict)
                  and entry.get("executor") == "agent")


class AgentRolesSourceTest(TmpDirTest):
    """Перечень ролей предполёта — из карты исполнителей, не из FSM."""

    def use_roles(self, text: str) -> None:
        """Карта исполнителей под тестом (`config.ROLES` — файл с этим
        текстом); патч снимается штатным cleanup."""
        path = self.tdir / "roles-under-test.yaml"
        path.write_text(text, encoding="utf-8")
        patcher = mock.patch.object(config, "ROLES", path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_ac1_list_covers_every_executor_agent_role_including_analyst(self):
        """Перечень ролей `doctor` совпадает с составом agent-ролей карты
        исполнителей пульта, и analyst в нём есть.

        Ловит мутацию: источник перечня оставлен прежним
        (`config.STATE_ROLE.values()`) — analyst, у которого нет своего
        состояния в этом словаре, не получает ни одной зависимой от роли
        строки предполёта, и вход его провайдера по-прежнему проверяется
        руками.
        """
        expected = map_agent_roles()

        self.assertIn(ANALYST, expected,
                      f"{config.ROLES}: analyst обязан быть agent-ролью — "
                      f"иначе сверять нечего")
        self.assertEqual(doctor.agent_roles(), expected)

    def test_ac1_list_follows_the_map_not_state_role(self):
        """На карте, где единственная agent-роль — analyst, перечень
        `doctor` равен `['analyst']`.

        Сценарий развязывает два источника: карта говорит «одна роль»,
        `config.STATE_ROLE` — «три другие». Перечень обязан слушать карту.

        Ловит мутацию: перечень собран объединением карты и
        `config.STATE_ROLE` («так надёжнее, ничего не потеряется») — роли,
        снятой с агента в карте, продолжают считать токен и вход, и
        `doctor` печатает строки предполёта для роли, которая шагов больше
        не делает.
        """
        demoted = [role for role in map_agent_roles() if role != ANALYST]
        self.assertTrue(demoted, "в карте одна agent-роль — сценарий вырожден")
        self.use_roles(roles_text({role: {"executor": "none"}
                                   for role in demoted}))

        self.assertEqual(doctor.agent_roles(), [ANALYST])

    def test_ac1_state_role_and_its_readers_are_untouched(self):
        """`config.STATE_ROLE` не получил ни состояния analyst, ни самой
        роли, а перечень `doctor` шире его значений.

        Ловит мутацию: analyst «добавлен в перечень» дописыванием
        `spec_writing: analyst` в `config.STATE_ROLE` вместо смены
        источника — тогда КАЖДЫЙ читатель словаря (`runner.cmd_run`,
        `auto`, `pause`, `doctor.leases`) начинает считать `spec_writing`
        обычным рабочим состоянием роли, и FSM меняет поведение там, где
        задача обещала не трогать ничего.
        """
        self.assertNotIn(ANALYST, set(config.STATE_ROLE.values()))
        self.assertNotIn(ANALYST_STATE, config.STATE_ROLE)
        self.assertEqual(set(config.STATE_ROLE), STATE_ROLE_KEYS)
        self.assertNotEqual(doctor.agent_roles(),
                            sorted(set(config.STATE_ROLE.values())))


if __name__ == "__main__":
    unittest.main()
