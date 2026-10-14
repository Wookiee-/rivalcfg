Things to do when releasing a new version
=========================================

This file is a memo for the maintainer.


0. Checks
---------

* Check SSDB is up to date (``nox -s update_ssdb``)
* Check copyright years in ``doc/conf.py``


1. Release
----------

* Update version number in ``pyproject.toml``
* Update version number in ``rivalcfg/version.py``
* Edit / update changelog in ``README.rst``
* Commit / tag (``git commit -m vX.Y.Z && git tag vX.Y.Z && git push && git push --tags``)


2. Publish PyPI package
-----------------------

Publish source dist and wheels on PyPI.

→ Automated :)


3. Publish Github Release
-------------------------

* Make a release on Github
* Add changelog
* Add standalone builds (Linux, macOS and Windows)

The Linux GUI release bundle can be built from the checkout with::

    ./scripts/build-packages.sh

This always creates the versioned source archive and then builds the Fedora
RPM, Arch package, and Debian package into ``dist/packages/``. Run it on the
corresponding distribution (or use ``--rpm``, ``--arch``, or ``--deb`` to
build one target). The RPM and Arch recipes must have the same version as
``pyproject.toml``; the runner checks this before building.


4. Update the website
---------------------

* Update the download page
* Update the devices page if required
* Publish release notes on rivalcfg.flozz.org


5. Misc
-------

* Flag ArchLinux AUR package as out of date:
  https://aur.archlinux.org/packages/rivalcfg
