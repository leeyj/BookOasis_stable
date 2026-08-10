from unittest.mock import patch

from tools import repair_mariadb_admin


EMPTY_STATES = [
    {"db_type": "general", "user_count": 0, "admin_count": 0},
    {"db_type": "adult", "user_count": 0, "admin_count": 0},
    {"db_type": "audiobook", "user_count": 0, "admin_count": 0},
]


def test_known_seed_failure_requires_all_users_tables_to_be_empty():
    assert repair_mariadb_admin.is_known_seed_failure(EMPTY_STATES)

    partial_state = [dict(state) for state in EMPTY_STATES]
    partial_state[1]["user_count"] = 1
    partial_state[1]["admin_count"] = 1

    assert not repair_mariadb_admin.is_known_seed_failure(partial_state)


def test_dry_run_does_not_create_admin():
    with patch.object(repair_mariadb_admin.database, "is_mariadb_mode", return_value=True), patch.object(
        repair_mariadb_admin, "inspect_users", return_value=EMPTY_STATES
    ), patch.object(repair_mariadb_admin, "create_initial_admin") as create_initial_admin:
        result = repair_mariadb_admin.main([])

    assert result == 0
    create_initial_admin.assert_not_called()


def test_apply_creates_admin_for_known_failure():
    with patch.object(repair_mariadb_admin.database, "is_mariadb_mode", return_value=True), patch.object(
        repair_mariadb_admin, "inspect_users", return_value=EMPTY_STATES
    ), patch.object(
        repair_mariadb_admin,
        "create_initial_admin",
        return_value=["general", "adult", "audiobook"],
    ) as create_initial_admin:
        result = repair_mariadb_admin.main(["--apply"])

    assert result == 0
    create_initial_admin.assert_called_once_with()


def test_apply_refuses_to_touch_nonempty_users_tables():
    states = [dict(state) for state in EMPTY_STATES]
    states[0]["user_count"] = 1
    states[0]["admin_count"] = 1

    with patch.object(repair_mariadb_admin.database, "is_mariadb_mode", return_value=True), patch.object(
        repair_mariadb_admin, "inspect_users", return_value=states
    ), patch.object(repair_mariadb_admin, "create_initial_admin") as create_initial_admin:
        result = repair_mariadb_admin.main(["--apply"])

    assert result == 1
    create_initial_admin.assert_not_called()