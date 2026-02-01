"""Unit tests for the KeyValueStore backend."""

from __future__ import annotations

from pytest_aitest.testing.store import KeyValueStore


class TestKeyValueStoreBasics:
    """Test basic key-value operations."""

    def test_get_nonexistent_key(self):
        store = KeyValueStore()
        result = store.get("missing")
        assert not result.success
        assert "not found" in result.error.lower()

    def test_set_and_get(self):
        store = KeyValueStore()
        store.set("key1", "value1")
        result = store.get("key1")
        assert result.success
        assert result.value == "value1"

    def test_delete(self):
        store = KeyValueStore()
        store.set("key1", "value1")
        result = store.delete("key1")
        assert result.success
        result = store.get("key1")
        assert not result.success

    def test_list_keys(self):
        store = KeyValueStore()
        store.set("a", "1")
        store.set("b", "2")
        store.set("c", "3")
        result = store.list_keys()
        assert result.success
        assert sorted(result.value) == ["a", "b", "c"]


class TestKeyValueStoreCalculation:
    """Test math calculation."""

    def test_simple_addition(self):
        store = KeyValueStore()
        result = store.calculate("2+3")
        assert result.success
        assert result.value == 5

    def test_order_of_operations(self):
        store = KeyValueStore()
        result = store.calculate("2+3*4")
        assert result.success
        assert result.value == 14

    def test_parentheses(self):
        store = KeyValueStore()
        result = store.calculate("(2+3)*4")
        assert result.success
        assert result.value == 20

    def test_floats(self):
        store = KeyValueStore()
        result = store.calculate("1.5 * 2")
        assert result.success
        assert result.value == 3.0

    def test_invalid_expression(self):
        store = KeyValueStore()
        result = store.calculate("2 + foo")
        assert not result.success
        assert "invalid" in result.error.lower()


class TestKeyValueStoreCompare:
    """Test value comparison."""

    def test_greater(self):
        store = KeyValueStore()
        result = store.compare("10", "5")
        assert result.success
        assert result.value == "greater"

    def test_less(self):
        store = KeyValueStore()
        result = store.compare("3", "7")
        assert result.success
        assert result.value == "less"

    def test_equal(self):
        store = KeyValueStore()
        result = store.compare("5", "5")
        assert result.success
        assert result.value == "equal"

    def test_string_comparison(self):
        store = KeyValueStore()
        result = store.compare("banana", "apple")
        assert result.success
        assert result.value == "greater"  # b > a


class TestKeyValueStoreSearch:
    """Test regex search."""

    def test_prefix_search(self):
        store = KeyValueStore()
        store.set("user_1", "a")
        store.set("user_2", "b")
        store.set("item_1", "c")
        result = store.search("^user_")
        assert result.success
        assert sorted(result.value) == ["user_1", "user_2"]

    def test_no_match(self):
        store = KeyValueStore()
        store.set("foo", "bar")
        result = store.search("^xyz")
        assert result.success
        assert result.value == []

    def test_invalid_regex(self):
        store = KeyValueStore()
        result = store.search("[invalid")
        assert not result.success
        assert "invalid" in result.error.lower()


class TestKeyValueStoreTransform:
    """Test value transformations."""

    def test_uppercase(self):
        store = KeyValueStore()
        store.set("key", "hello")
        result = store.transform("key", "uppercase")
        assert result.success
        assert result.value == "HELLO"
        assert store.get("key").value == "HELLO"

    def test_lowercase(self):
        store = KeyValueStore()
        store.set("key", "HELLO")
        result = store.transform("key", "lowercase")
        assert result.success
        assert result.value == "hello"

    def test_reverse(self):
        store = KeyValueStore()
        store.set("key", "hello")
        result = store.transform("key", "reverse")
        assert result.success
        assert result.value == "olleh"

    def test_length(self):
        store = KeyValueStore()
        store.set("key", "hello")
        result = store.transform("key", "length")
        assert result.success
        assert result.value == "5"

    def test_trim(self):
        store = KeyValueStore()
        store.set("key", "  hello  ")
        result = store.transform("key", "trim")
        assert result.success
        assert result.value == "hello"

    def test_unknown_operation(self):
        store = KeyValueStore()
        store.set("key", "hello")
        result = store.transform("key", "explode")
        assert not result.success
        assert "unknown" in result.error.lower()


class TestKeyValueStoreFail:
    """Test intentional failure tool."""

    def test_fail_returns_error(self):
        store = KeyValueStore()
        result = store.fail("Something went wrong")
        assert not result.success
        assert result.error == "Something went wrong"


class TestKeyValueStoreToolDispatch:
    """Test the call_tool dispatcher."""

    def test_dispatch_get(self):
        store = KeyValueStore()
        store.set("key", "value")
        result = store.call_tool("get", {"key": "key"})
        assert result.success
        assert result.value == "value"

    def test_dispatch_unknown_tool(self):
        store = KeyValueStore()
        result = store.call_tool("explode", {})
        assert not result.success
        assert "unknown" in result.error.lower()

    def test_dispatch_missing_arg(self):
        store = KeyValueStore()
        result = store.call_tool("get", {})
        assert not result.success
        assert "missing" in result.error.lower()


class TestKeyValueStoreSchemas:
    """Test tool schema generation."""

    def test_schemas_have_required_fields(self):
        schemas = KeyValueStore.get_tool_schemas()
        assert len(schemas) == 10

        for schema in schemas:
            assert "name" in schema
            assert "description" in schema
            assert "inputSchema" in schema

    def test_schema_names(self):
        schemas = KeyValueStore.get_tool_schemas()
        names = [s["name"] for s in schemas]
        expected = [
            "get",
            "set",
            "delete",
            "list_keys",
            "calculate",
            "compare",
            "search",
            "transform",
            "fail",
            "slow",
        ]
        assert names == expected
