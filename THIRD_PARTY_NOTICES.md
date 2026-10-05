# Third-party components

CᵘPⁱ source is MIT licensed. Its Python runtime and dependencies retain
their own licenses. The release folder includes `licenses/` and
`dependency-manifest.json` with the installed package versions and metadata.

PySide6, Shiboken6 and the Qt modules used by CᵘPⁱ are distributed under
the LGPLv3 option. Qt is copyright The Qt Company Ltd. and other contributors.
The LGPLv3 and GPLv3 texts are included in `licenses/`. Qt includes additional
third-party components; preserve the upstream notices when rebuilding it.

The portable distribution uses shared libraries in `_internal/`. You may
replace the Qt/PySide6 libraries with compatible modified versions. Keep the
same architecture and Python/Qt ABI, and preserve the directory layout. No
CᵘPⁱ restriction prohibits reverse engineering to debug such changes.
The included `cupi-source.zip` lets you rebuild the application with
your chosen dependencies using `requirements.txt` and `packaging/` scripts.

Upstream library source and licensing information:

* Qt: https://download.qt.io/archive/qt/ and https://code.qt.io/cgit/qt/
* PySide6/Shiboken6: https://download.qt.io/official_releases/QtForPython/
  and https://code.qt.io/cgit/pyside/pyside-setup.git/
* Python: https://www.python.org/downloads/source/
* Other packages: project URLs in `dependency-manifest.json`.

Before publicly hosting binary releases, provide corresponding library source
for the exact bundled versions alongside the download, including any changes,
and verify all bundled native-library notices. Upstream links alone are not a
substitute for completing the distributor's source obligations. See Qt's
guidance: https://www.qt.io/development/open-source-lgpl-obligations.
