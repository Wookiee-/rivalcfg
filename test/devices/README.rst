End to End Devices Tests
========================

The ``tests/devices/`` folder contains end to end tests for devices (from CLI options to bytes sent over the USB bus).


Work in Progress
----------------

The end to end devices tests replace previous Pytest devices tests. The ``old_specs/`` folder contains the remaining Pytests modules that have not been converted yet, the ``sepcs/`` folder contains new tests.


Spec Format
-----------

Devices test files are named "device spec". Device spec files must be placed in the ``test/devices/specs/`` folder and named ``<device_internal_name>.txt`` (e.g. ``rival100.txt``).

General format::

    :vendor_id:product_id Product Name

    # This is a comment

    --cli-option VALUE
    < Expected USB packet 1 (hex)
    < Expected USB packet 2 (hex)

    --cli-option2 VALUE2
    < Expected USB packet 1 (hex)

    -a VALUE3
    < Expected USB packet 1 (hex)


Device Identification Line
~~~~~~~~~~~~~~~~~~~~~~~~~~

::

    :vendor_id:product_id Product Name

* Device identification line MUST start with a colon (``:``).
* Device identification line MUST be the first non-blank/comment line of the file.
* the file MUST contain only ONE device identification line.


CLI Option Lines
~~~~~~~~~~~~~~~~

::

    --cli-option VALUE

* CLI option lines MUST start with a dash (``-``),
* CLI option lines MUST be written on a single line.
* CLI option lines MAY contain multiple options.
* CLI option lines MUST be followed by one or more expected packet line(s).

Expected Packet Lines
~~~~~~~~~~~~~~~~~~~~~

::

    < 02 00 | 00 00 00 00 00 00

      -----   -----------------
      wValue   USB Packet Data

* Expected packet lines MUST follow CLI option line or an other expected packet line.
* Expected packet lines MUST start with a chevron (``<``).
* Expected packet lines MUST be writen as hexadecimal Bytes.
* Expected packet data MUST be prefixed by the wValue (report type and report ID).
* Expected packet lines MAY be writen on muliple lines.
* Expected packet lines MAY contain a pipe character (``|``) to separate wValue from the data.
* Expected packet lines MAY contain white spaces to separates bytes (parsed by ``bytes.fromhex()``).


Blank Lines, White Spaces and Comments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Everything from a hash (``#``) to the end of a line is a comment.
* Blank lines are ignored.
* White spaces at the start and end of lines (a.k.a. indentation) are ignored.


Example
~~~~~~~

Here is a (partial) example for the Rival 100 mouse (``rival100.txt``)::

    :1038:1702 SteelSeries Rival 100

    # Test 1st sensitity preset

    --sensitivity1 250
    < 02 00 |
      03 01
      08

    < 02 00 |
      09 00

    --sensitivity1 500
    < 02 00 | 03 01 07
    < 02 00 | 09 00

    -s 1000
    < 0200 0301 06
    < 0200 0900

For more examples, look at the ``tests/devices/specs/*.txt`` files.
