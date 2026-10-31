"""Состояние `awaiting_human` вне перечней «нужен sha», «смена моделей» и ролей шага.

Группа: долгоживущий
Зелёный с рождения: состояния `awaiting_human` сегодня нет ни в одном из трёх перечней — тест держит, чтобы, вводя состояние, его не занесли в `fsm.APPROVE_NEEDS_SHA`, `fsm.SET_MODELS_STATES` или ключи `config.STATE_ROLE`.

Свойство — состав констант модулей, без песочницы.
"""
from orchestrator import config, fsm

STATE = "awaiting_human"


def test_ac3_awaiting_human_not_in_approve_needs_sha():
    """`approve` по задаче в `awaiting_human` не требует sha: состояния нет в `fsm.APPROVE_NEEDS_SHA`.

    Ловит мутацию: `awaiting_human` добавлен в `APPROVE_NEEDS_SHA` рядом
    с `merge_gate` (копия перечня гейтов) — утверждение покраснеет.
    """
    assert STATE not in fsm.APPROVE_NEEDS_SHA, fsm.APPROVE_NEEDS_SHA


def test_ac3_awaiting_human_not_in_set_models_states():
    """Смена набора моделей в `awaiting_human` не предусмотрена: состояния нет в `fsm.SET_MODELS_STATES`.

    Ловит мутацию: `awaiting_human` дописан в `SET_MODELS_STATES` вместе
    с прочими гейтовыми состояниями — утверждение покраснеет.
    """
    assert STATE not in fsm.SET_MODELS_STATES, fsm.SET_MODELS_STATES


def test_ac3_awaiting_human_has_no_step_role():
    """У состояния `awaiting_human` нет роли шага: его нет среди ключей `config.STATE_ROLE`.

    Ловит мутацию: `awaiting_human` сопоставлен роли (например
    `developer`) в `STATE_ROLE` — `run`/`auto` запустили бы агента в
    ожидании людей проекта; утверждение покраснеет.
    """
    assert STATE not in config.STATE_ROLE, sorted(config.STATE_ROLE)
