# freecad-docker
A Docker image to run FreeCAD under XVFB

## FCStd checker

The image ships a static checker for `.FCStd` files, for callers that must decide whether a file is
safe to open before FreeCAD parses it. It is stdlib-only Python and never opens the file in FreeCAD.

```sh
fcstd-check model.FCStd other.FCStd      # JSON {file: findings}; exit 0: no violations, 1: violations
python3 -m fcstd_check model.FCStd       # same, from any Python with the module on its path
```

```python
from fcstd_check import check_fcstd, violations
findings = check_fcstd("model.FCStd", extra_modules=("mymodule",))  # list of strings, never raises
```

What it reports: zip structure FreeCAD could read differently (duplicate entry names, also differing
in case; local headers that disagree with the central directory; encrypted or lying entries), unsafe
entry paths and symlinks, XML parts that are not plain UTF-8 (BOM, UTF-16/32, another declared
encoding), not well-formed, or that declare a DOCTYPE or entities, Python-backed objects (listed as
`python object <module>.<class>`, informational) whose module is not one of FreeCAD 1.1's own
workbenches (`python module outside allowlist`), Python state that is not JSON, file-included paths
that leave the document, and zip-bomb sizes. Unreadable or ambiguous input is a finding, not an error.
`violations(findings)` drops the informational lines (the CLI exit code does the same).

Extend the allowlist without rebuilding the image: set `FCSTD_EXTRA_MODULES=mymodule,other`
(comma-separated top-level module names) or pass `extra_modules` to `check_fcstd`.

Tests (no FreeCAD needed): `python3 -m unittest discover -s tests`.
