#!/bin/env python3

"""Test devices profile (CLI option -> bytes sent to USB device)."""

import re

import os
import sys

from io import StringIO
from pathlib import Path
from collections.abc import Iterator
from typing import Any, TypeVar, Type

from rivalcfg.__main__ import main as rivalcfg_main


def list_device_spec_files() -> Iterator[Path]:
    """Lists device spec files in ``tests/devices/spec/``.

    >>> list(list_device_spec_files())
    [...Path(...)...]
    """
    root = Path(__file__).parent / "specs"
    return root.glob("*.txt")


def cleanup_line(line: str) -> str:
    """Remove comments and useless white char from given line.

    :param line: The line to clean.

    >>> cleanup_line(" \\t line \\t\\r\\n")
    'line'
    >>> cleanup_line(" foobar  # comment \\n")
    'foobar'
    >>> cleanup_line(" # XXX")
    ''
    """
    line = re.sub("#.*$", "", line)
    line = line.strip()
    return line


def parse_device_spec(spec_text: str) -> dict[str, Any]:
    spec: dict[str, Any] = {
        "vendor_id": 0x0000,
        "product_id": 0x0000,
        "device_name": "",
        "tests": [],
    }

    for line in spec_text.split("\n"):
        line = cleanup_line(line)
        if not line:
            continue

        # Device identification
        if line.startswith(":"):
            if spec["vendor_id"]:
                raise ValueError("Only one device definition is allowed per test file")
            match = re.match("^:([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})(.*)$", line)
            if match:
                vendor_id, product_id, device_name = match.groups()
                spec["vendor_id"] = int(vendor_id, 16)
                spec["product_id"] = int(product_id, 16)
                spec["device_name"] = device_name.strip()
            else:
                raise ValueError("Wrong format for device definition")
            continue

        # Tests
        if line.startswith("-"):
            spec["tests"].append(
                {
                    "command": [arg.strip() for arg in line.split(" ") if arg.strip()],
                    "_buff": "",
                    "packets": [],
                }
            )
        else:
            spec["tests"][-1]["_buff"] += line  # type: ignore

    # Generate expectd packets (bytes)
    for test in spec["tests"]:
        test["packets"] = [
            bytes.fromhex(p)
            for p in test["_buff"].replace("|", "").split("<")
            if p.strip()
        ]
        del test["_buff"]

    return spec


T = TypeVar("T", bound="DeviceProfileTest")


class UnexpectedExitError(Exception):
    pass


class DeviceProfileTest:
    """Contains tests for a device profile

    :param vendor_id: Vendor ID of the USB device.
    :param product_id: Product ID of the USB device.
    :param product_name: Product name of the USB device.
    :param tests: Things to test::

        [
            {
                "option": "--sensitivity1 1500",  # Option(s) to test
                "packets": [                      # Expected USB packets (prefixed with wValue)
                    bytes.fromhex("02 00 03 01 05"),  # Packet 1
                    bytes.fromhex("02 00 09 00"),     # Packet 2
                ]
            },
        ]
    """

    def __init__(
        self,
        vendor_id: int = 0x0000,
        product_id: int = 0x0000,
        device_name: str = "",
        tests: list[dict[str, Any]] = [],
    ) -> None:
        self._vendor_id = vendor_id
        self._product_id = product_id
        self._device_name = device_name
        self._tests = tests
        self.errors: list[str] = []
        self._real_stdout = sys.stdout
        self._real_stderr = sys.stderr
        self._rivalcfg_stdout = StringIO()
        self._rivalcfg_stderr = StringIO()
        self._real_exit = sys.exit

    @classmethod
    def from_file(Cls: Type[T], test_file_path: Path) -> T:
        """Create a device profile test from a file.

        :param test_file_path: The path of the test file.

        :returns: an instance of DeviceProfileTest
        """
        with open(test_file_path, "r") as test_file:
            return Cls.from_string(test_file.read())

    @classmethod
    def from_string(Cls: Type[T], spec_text: str) -> T:
        """Create a device profile test from a string.

        :param spec_text: The profile test.

        :returns: an instance of DeviceProfileTest
        """
        spec = parse_device_spec(spec_text)
        profile_test = Cls(**spec)
        return profile_test

    def run(self) -> bool:
        """Run tests of the device profile.

        :returns: ``True`` on success, ``False`` on failure.
        """
        os.environ["RIVALCFG_DRY"] = "1"
        os.environ["RIVALCFG_DEBUG_NO_COMMAND_DELAY"] = "1"
        os.environ["RIVALCFG_DEBUG_PRINT_HID_REPORT"] = "1"
        os.environ["RIVALCFG_PROFILE"] = "%04X:%04X" % (
            self._vendor_id,
            self._product_id,
        )

        def _dummy_exit(status: str | int | None = None, /):
            raise UnexpectedExitError("Rivalcfg exited with status: %s" % str(status))

        for test in self._tests:
            self._rivalcfg_stdout.seek(0)
            self._rivalcfg_stderr.seek(0)

            # Redirect stdout/stderr to read logged packets and errors
            sys.stdout = self._rivalcfg_stdout
            sys.stderr = self._rivalcfg_stderr
            # Avoid rivalcfg to exit the tests
            sys.exit = _dummy_exit

            try:
                rivalcfg_main(test["command"])
                rivalcfg_packets = self._read_logged_packets()
            except UnexpectedExitError as error:
                self._add_error(test["command"], "Unexpected exit", str(error))
            except Exception as error:
                self._add_error(
                    test["command"], "An unexpected error occurred", str(error)
                )
            else:
                if len(rivalcfg_packets) != len(test["packets"]):
                    self._add_error(
                        test["command"],
                        "%i packet(s) expected but %i emitted"
                        % (
                            len(test["packets"]),
                            len(rivalcfg_packets),
                        ),
                        "Expected: %s\nEmitted:  %s"
                        % (
                            "\n          ".join([p.hex(" ") for p in test["packets"]]),
                            "\n          ".join([p.hex(" ") for p in rivalcfg_packets]),
                        ),
                    )
                for i in range(len(test["packets"])):
                    if rivalcfg_packets[i] != test["packets"][i]:
                        self._add_error(
                            test["command"],
                            "Emitted packet #%i does not match the expected one" % i,
                            "Expected: %s\nEmitted:  %s"
                            % (
                                test["packets"][i].hex(" "),
                                rivalcfg_packets[i].hex(" "),
                            ),
                        )
            finally:
                sys.stdout = self._real_stdout
                sys.stderr = self._real_stderr
                sys.exit = self._real_exit

        return len(self.errors) == 0

    def _add_error(
        self, command: list[str], message: str, detail: str | None = None
    ) -> None:
        """Add an error to the error list.

        :param command: The command that caused the error.
        :param message: A single-line error message.
        :param detail: A more detailed error description. Multi-line allowed.
        """
        error_message = "  %s -> %s" % (" ".join(command), message)
        if detail:
            error_message += ":\n"
            for line in detail.split("\n"):
                error_message += "    %s\n" % line
        self.errors.append(error_message)

    def _read_logged_packets(self) -> list[bytes]:
        """Read packets Rivalcfg logged to stdout.

        :returns: The list of packets.
        """
        packets = []
        self._rivalcfg_stdout.seek(0)
        for line in self._rivalcfg_stdout.readlines():
            if not line.startswith("[USBHID]<"):
                continue
            packets.append(
                bytes.fromhex(line.replace("[USBHID]<", "").replace("|", ""))
            )
        return packets

    def __repr__(self) -> str:
        return "<DeviceProfileTest '%s' (%04X:%04X)>" % (
            self._device_name,
            self._vendor_id,
            self._product_id,
        )

    def __str__(self) -> str:
        return "%s (%04X:%04X)" % (
            self._device_name,
            self._vendor_id,
            self._product_id,
        )


def main() -> None:
    failed = False

    print("=" * 80)
    print("End to End Devices Tests")
    print("=" * 80)

    for spec_file in list_device_spec_files():
        device_test = DeviceProfileTest.from_file(spec_file)
        sys.stdout.write("\nTesting %s..." % str(device_test))
        sys.stdout.flush()
        success = device_test.run()
        if success:
            print("  -> OK")
        else:
            failed = True
            print("  -> FAILED!")
            for err in device_test.errors:
                print(err)

    if failed:
        print("\nSome device tests failed!")
        print("=" * 80)
        sys.exit(1)
    else:
        print("\nAll devices behave as expected! :)")
        print("=" * 80)


if __name__ == "__main__":
    main()
