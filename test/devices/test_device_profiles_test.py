import pytest

from .device_profiles_test import parse_device_spec


class TestParseDeviceSpec:

    @pytest.fixture
    def device_spec_ok(self):
        return (
            ":1038:BAAD Dummy Test Device\n"
            "\n"
            "# This is a comment\n"
            " \t # This is a comment too \t \n"
            "--option1 123\n"
            "< 03 00 | 01 02 03 04\n"
            "< 02 00 | 05 06\n"
            " \t --option2 \t ABCDEF \t \n"
            " \t < 02 00 |\n"
            "\n"
            "\t 01 02\n"
            "03 04\n"
            "--option3\n"
            "< 02 00 AA BB\n"
            "--option4\n"
            "< 02 00\n"
            "CD EF\n"
            "12 34  # This is a comment\n"
            "56 78"
        )

    def test_spec_device_id(self, device_spec_ok):
        spec = parse_device_spec(device_spec_ok)
        assert spec["vendor_id"] == 0x1038
        assert spec["product_id"] == 0xBAAD
        assert spec["device_name"] == "Dummy Test Device"

    def test_spec_tests(self, device_spec_ok):
        spec = parse_device_spec(device_spec_ok)
        assert len(spec["tests"]) == 4

        assert spec["tests"][0]["command"] == ["--option1", "123"]
        assert spec["tests"][0]["packets"] == [
            bytes.fromhex("03 00 01 02 03 04"),
            bytes.fromhex("02 00 05 06"),
        ]

        assert spec["tests"][1]["command"] == ["--option2", "ABCDEF"]
        assert spec["tests"][1]["packets"] == [
            bytes.fromhex("02 00 01 02 03 04"),
        ]

        assert spec["tests"][2]["command"] == ["--option3"]
        assert spec["tests"][2]["packets"] == [
            bytes.fromhex("02 00 AA BB"),
        ]

        assert spec["tests"][3]["command"] == ["--option4"]
        assert spec["tests"][3]["packets"] == [
            bytes.fromhex("02 00 CD EF 12 34 56 78"),
        ]

    def test_spec_wrong_device_id_line(self):
        with pytest.raises(ValueError):
            parse_device_spec(":XX:BAAD Dummy device")

    def test_spec_multiple_id(self):
        with pytest.raises(ValueError):
            parse_device_spec("""
                :1038:BAAD Dummy device
                :1038:F000 Foo
            """)

    def test_spec_device_id_without_name(self):
        spec = parse_device_spec(""" :1038:BAAD  """)
        assert spec["vendor_id"] == 0x1038
        assert spec["product_id"] == 0xBAAD
        assert spec["device_name"] == ""
