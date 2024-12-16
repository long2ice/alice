from aerich.utils import get_dict_diff_by_key, import_py_file


def test_import_py_file() -> None:
    m = import_py_file("aerich/utils.py")
    assert getattr(m, "import_py_file", None)


class TestDiffFields:
    def test_the_same_through_order(self) -> None:
        old = [
            {"name": "users", "through": "users_group"},
            {"name": "admins", "through": "admins_group"},
        ]
        new = [
            {"name": "members", "through": "users_group"},
            {"name": "admins", "through": "admins_group"},
        ]
        diffs = list(get_dict_diff_by_key(old, new))
        assert type(get_dict_diff_by_key(old, new)).__name__ == "generator"
        assert len(diffs) == 1
        assert diffs == [("change", [0, "name"], ("users", "members"))]

    def test_same_through_with_different_orders(self) -> None:
        old = [
            {"name": "users", "through": "users_group"},
            {"name": "admins", "through": "admins_group"},
        ]
        new = [
            {"name": "admins", "through": "admins_group"},
            {"name": "members", "through": "users_group"},
        ]
        diffs = list(get_dict_diff_by_key(old, new))
        assert len(diffs) == 1
        assert diffs == [("change", [0, "name"], ("users", "members"))]

    def test_the_same_field_name_order(self) -> None:
        old = [
            {"name": "users", "through": "users_group"},
            {"name": "admins", "through": "admins_group"},
        ]
        new = [
            {"name": "users", "through": "user_groups"},
            {"name": "admins", "through": "admin_groups"},
        ]
        diffs = list(get_dict_diff_by_key(old, new))
        assert len(diffs) == 4
        assert diffs == [
            ("remove", "", [(0, {"name": "users", "through": "users_group"})]),
            ("remove", "", [(0, {"name": "admins", "through": "admins_group"})]),
            ("add", "", [(0, {"name": "users", "through": "user_groups"})]),
            ("add", "", [(0, {"name": "admins", "through": "admin_groups"})]),
        ]

    def test_same_field_name_with_different_orders(self) -> None:
        old = [
            {"name": "admins", "through": "admins_group"},
            {"name": "users", "through": "users_group"},
        ]
        new = [
            {"name": "users", "through": "user_groups"},
            {"name": "admins", "through": "admin_groups"},
        ]
        diffs = list(get_dict_diff_by_key(old, new))
        assert len(diffs) == 4
        assert diffs == [
            ("remove", "", [(0, {"name": "admins", "through": "admins_group"})]),
            ("remove", "", [(0, {"name": "users", "through": "users_group"})]),
            ("add", "", [(0, {"name": "users", "through": "user_groups"})]),
            ("add", "", [(0, {"name": "admins", "through": "admin_groups"})]),
        ]

    def test_drop_one(self) -> None:
        old = [
            {"name": "users", "through": "users_group"},
            {"name": "admins", "through": "admins_group"},
        ]
        new = [
            {"name": "admins", "through": "admins_group"},
        ]
        diffs = list(get_dict_diff_by_key(old, new))
        assert len(diffs) == 1
        assert diffs == [("remove", "", [(0, {"name": "users", "through": "users_group"})])]

    def test_add_one(self) -> None:
        old = [
            {"name": "admins", "through": "admins_group"},
        ]
        new = [
            {"name": "users", "through": "users_group"},
            {"name": "admins", "through": "admins_group"},
        ]
        diffs = list(get_dict_diff_by_key(old, new))
        assert len(diffs) == 1
        assert diffs == [("add", "", [(0, {"name": "users", "through": "users_group"})])]

    def test_drop_some(self) -> None:
        old = [
            {"name": "users", "through": "users_group"},
            {"name": "admins", "through": "admins_group"},
            {"name": "staffs", "through": "staffs_group"},
        ]
        new = [
            {"name": "admins", "through": "admins_group"},
        ]
        diffs = list(get_dict_diff_by_key(old, new))
        assert len(diffs) == 2
        assert diffs == [
            ("remove", "", [(0, {"name": "users", "through": "users_group"})]),
            ("remove", "", [(0, {"name": "staffs", "through": "staffs_group"})]),
        ]

    def test_add_some(self) -> None:
        old = [
            {"name": "staffs", "through": "staffs_group"},
        ]
        new = [
            {"name": "users", "through": "users_group"},
            {"name": "admins", "through": "admins_group"},
            {"name": "staffs", "through": "staffs_group"},
        ]
        diffs = list(get_dict_diff_by_key(old, new))
        assert len(diffs) == 2
        assert diffs == [
            ("add", "", [(0, {"name": "users", "through": "users_group"})]),
            ("add", "", [(0, {"name": "admins", "through": "admins_group"})]),
        ]

    def test_some_through_unchanged(self) -> None:
        old = [
            {"name": "staffs", "through": "staffs_group"},
            {"name": "admins", "through": "admins_group"},
        ]
        new = [
            {"name": "users", "through": "users_group"},
            {"name": "admins_new", "through": "admins_group"},
            {"name": "staffs_new", "through": "staffs_group"},
        ]
        diffs = list(get_dict_diff_by_key(old, new))
        assert len(diffs) == 3
        assert diffs == [
            ("change", [0, "name"], ("staffs", "staffs_new")),
            ("change", [0, "name"], ("admins", "admins_new")),
            ("add", "", [(0, {"name": "users", "through": "users_group"})]),
        ]

    def test_some_unchanged_without_drop_or_add(self) -> None:
        old = [
            {"name": "staffs", "through": "staffs_group"},
            {"name": "admins", "through": "admins_group"},
            {"name": "users", "through": "users_group"},
        ]
        new = [
            {"name": "users_new", "through": "users_group"},
            {"name": "admins_new", "through": "admins_group"},
            {"name": "staffs_new", "through": "staffs_group"},
        ]
        diffs = list(get_dict_diff_by_key(old, new))
        assert len(diffs) == 3
        assert diffs == [
            ("change", [0, "name"], ("staffs", "staffs_new")),
            ("change", [0, "name"], ("admins", "admins_new")),
            ("change", [0, "name"], ("users", "users_new")),
        ]
