# Redistribution notices and release gate

LightMq source is MIT, copyright PRANATHEESH S. Python is PSF licensed;
openpyxl and et-xmlfile are MIT licensed. PySide6, shiboken6, and Qt include
LGPL/GPL/commercial terms. Qt WebEngine bundles Chromium and many libraries
with their own notices. Read the exact distribution license texts under this
directory. No standalone Chromium third-party HTML notice file was found in
the installed wheels; obtaining and bundling the exact matching notices is
an outstanding public-release gate.

The currently installed 6.12 wheels contain `LicenseRef-Qt-Commercial.txt`.
No commercial redistribution entitlement has been verified. These artifacts
are internal test candidates, not cleared for public redistribution. Do not
assume LGPL terms apply to these specific binaries solely because Qt has
open-source editions. Obtain the applicable authorization or rebuild with
appropriately licensed packages before public release.

For an LGPL distribution, keep the DLLs replaceable; do not
prohibit reverse engineering for debugging LGPL library modifications. A public
release needs a corresponding-source/access mechanism for the exact LGPL Qt
libraries, including any modifications, and installation/relinking information
where applicable. Source: https://code.qt.io/cgit/ and
https://download.qt.io/official_releases/QtForPython/ . Verify the exact 6.12.0
source and Chromium third-party notice coverage before public distribution.
Do not treat this inventory as legal clearance or a source offer.

Build tooling (PyInstaller, pytest, Inno Setup) is not bundled as application
Python modules. PyInstaller's bootloader exception permits distribution of the
generated application under its own license. Review tool license terms for
commercial use. Public release remains gated on a full third-party license
and source-availability review.
