"""
Static check of an FCStd file, run without opening it in FreeCAD (stdlib only).

An FCStd is a zip of XML parts that FreeCAD trusts when it opens the file: a Python object stores the
module and class it re-imports (`<Python module=".." class=".."/>`) and its state, and file-included
properties name a file inside the archive. `check_fcstd(path)` returns the list of findings (strings,
empty when the file looks clean); it never raises: a bad, unreadable or ambiguous file is a finding.

    python -m fcstd_check <file>...     prints {file: findings} as JSON; exit code 0 when no file has a
                                        violation, 1 otherwise

Findings:
- zip structure FreeCAD could read differently from this checker: duplicate entry names (also when they
  differ only in case), a local header that disagrees with the central directory, encrypted entries,
  unsupported compression, sizes that lie;
- zip entries with `.`/`..` components, absolute, backslash or drive paths, or symlinks;
- an XML part that is not plain UTF-8 (BOM, UTF-16/32, another declared encoding), not well-formed, or
  with a DOCTYPE or entity declaration (never expanded). Checked parts: `Document.xml`,
  `GuiDocument.xml` (the two FreeCAD parses when restoring a document) and, to fail closed, every other
  `*.xml` entry;
- every Python-backed object: `python object <module>.<class>` (informational, not a violation) and
  `python module outside allowlist: <module>` for a module that is not a FreeCAD workbench's nor one
  added by the caller; a state that is not JSON (FreeCAD would unpickle it);
- file-included properties whose path leaves the document folder;
- zip-bomb limits.

Extending the allowlist: `check_fcstd(path, extra_modules=("mymodule",))` or the environment variable
`FCSTD_EXTRA_MODULES=mymodule,other` (top-level module names, comma-separated).
"""

import base64, json, os, re, struct, sys, zipfile, zlib
from xml.parsers import expat

CORE_PARTS = ("Document.xml", "GuiDocument.xml")
MAX_PART_BYTES = 256 * 1024 * 1024  # an XML part inflating past this is not parsed (zip bomb)
MAX_RATIO = 1000
MAX_ENTRIES = 100_000
INFO_MARKER = ": python object "  # informational findings: not violations

# Top-level modules FreeCAD 1.1's own workbenches use for Python objects and view providers (plus every
# `Arch*` one). Anything else is flagged unless the caller adds it.
ALLOWED_MODULES = {
  "Draft", "draftobjects", "draftviewproviders", "draftutils", "draftmake", "draftguitools", "WorkingPlane",
  "femobjects", "femviewprovider", "femguiobjects", "femsolver", "femtools",
  "Path", "PathScripts", "PathPythonGui",
  "BasicShapes", "BOPTools", "JoinFeatures", "CompoundTools", "AttachmentEditor",
  "InvoluteGearFeature", "SprocketFeature", "fcgear", "fcsprocket",
  "OpenSCADFeatures", "JointObject", "Show", "MeasureCOM", "importFCMat", "materialtools",
  "freecad",
}


def _unsafe_path(path):
  parts = re.split(r"[\\/]", path)
  return bool(path.startswith("/") or "\\" in path or re.match(r"[A-Za-z]:", path) or ".." in parts)


def _check_zip(zf):
  findings = []
  infos = zf.infolist()
  if len(infos) > MAX_ENTRIES:
    return [f"too many zip entries: {len(infos)}"]
  seen = {}
  for info in infos:
    name = info.filename
    if _unsafe_path(name) or "." in name.split("/") or "" in name.split("/")[:-1]:
      findings.append(f"zip entry with unsafe path: {name!r}")
    if (info.external_attr >> 16) & 0o170000 == 0o120000:
      findings.append(f"zip entry is a symlink: {name!r}")
    if info.flag_bits & 0x1:
      findings.append(f"zip entry is encrypted: {name!r}")
    if "\x00" in name:
      findings.append(f"zip entry name with NUL: {name!r}")
    key = name.lower()
    if key in seen:
      findings.append(f"duplicate zip entry name: {name!r} and {seen[key]!r}")
    seen.setdefault(key, name)
  return findings


def _raw_part(path, info):
  """Bytes of one entry, read the way a streaming reader would (local header, then the data until the
  compressed stream ends). Raises ValueError if it disagrees with the central directory."""
  with open(path, "rb") as f:
    f.seek(info.header_offset)
    header = f.read(30)
    if len(header) < 30 or header[:4] != b"PK\x03\x04":
      raise ValueError("no local header at the offset the central directory gives")
    flags, method = struct.unpack("<HH", header[6:10])
    nlen, elen = struct.unpack("<HH", header[26:30])
    if f.read(nlen) != info.filename.encode("utf-8" if info.flag_bits & 0x800 else "cp437"):
      raise ValueError("local header name differs from the central directory")
    if method != info.compress_type or method not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
      raise ValueError(f"unsupported or inconsistent compression method {method}")
    if not flags & 0x8:
      csize, usize = struct.unpack("<II", header[18:26])
      if (csize, usize) != (info.compress_size, info.file_size) and 0xFFFFFFFF not in (csize, usize):
        raise ValueError("local header sizes differ from the central directory")
    f.seek(elen, 1)
    data = f.read(info.compress_size)
  if method == zipfile.ZIP_STORED:
    out = data
  else:
    inflater = zlib.decompressobj(-15)
    out = inflater.decompress(data, MAX_PART_BYTES + 1)
    if inflater.unconsumed_tail or not inflater.eof or inflater.unused_data:
      raise ValueError("compressed stream does not end where the central directory says")
  if len(out) != info.file_size:
    raise ValueError("inflated size differs from the central directory")
  return out


def _check_encoding(part, data):
  """Findings if `data` is not plain UTF-8 text (FreeCAD's XML parser and ours could disagree)."""
  head = data[:4]
  if head[:3] == b"\xef\xbb\xbf" or head[:2] in (b"\xfe\xff", b"\xff\xfe") or head[:4] in (b"\x00\x00\xfe\xff", b"\xff\xfe\x00\x00"):
    return [f"{part}: byte order mark"]
  if b"\x00" in data:
    return [f"{part}: contains NUL bytes (UTF-16/32 or binary)"]
  try:
    data.decode("utf-8")
  except UnicodeDecodeError:
    return [f"{part}: not valid UTF-8"]
  return []


def _check_xml(part, data, extra):
  findings = _check_encoding(part, data)
  if findings:
    return findings
  parser = expat.ParserCreate()

  def xml_decl(version, encoding, standalone):
    if encoding is not None and encoding.lower().replace("_", "-") not in ("utf-8", "utf8"):
      findings.append(f"{part}: XML encoding {encoding!r} is not UTF-8")

  parser.XmlDeclHandler = xml_decl
  parser.StartDoctypeDeclHandler = lambda *a: findings.append(f"{part}: DOCTYPE declaration")
  parser.EntityDeclHandler = lambda name, *a: findings.append(f"{part}: entity declaration {name!r}")
  parser.SkippedEntityHandler = lambda name, *a: findings.append(f"{part}: entity reference {name!r}")

  def start(tag, attrs):
    if tag == "Python":
      module, cls = attrs.get("module", ""), attrs.get("class", "")
      if not module:  # an empty proxy slot: nothing to import
        return
      findings.append(f"{part}{INFO_MARKER}{module}.{cls}")
      if not _allowed(module, extra):
        findings.append(f"{part}: python module outside allowlist: {module}")
      try:
        value = attrs.get("value", "")
        json.loads(base64.b64decode(value, validate=True) if attrs.get("encoded") == "yes" else value)
      except Exception:
        findings.append(f"{part}: python state of {module}.{cls} is not JSON")
    elif tag == "FileIncluded" and _unsafe_path(attrs.get("file", "")):
      findings.append(f"{part}: file-included path leaves the document: {attrs.get('file')!r}")

  parser.StartElementHandler = start
  try:
    parser.Parse(data, True)
  except expat.ExpatError as error:
    findings.append(f"{part}: not well-formed XML ({error})")
  return findings


def _allowed(module, extra):
  root = module.split(".")[0]
  return root in ALLOWED_MODULES or root in extra or root.startswith("Arch")


def _extra_modules(extra_modules):
  names = list(extra_modules) + os.environ.get("FCSTD_EXTRA_MODULES", "").split(",")
  return frozenset(n.strip() for n in names if n.strip())


def _check(path, extra):
  with zipfile.ZipFile(path) as zf:
    findings = _check_zip(zf)
    if findings and findings[0].startswith("too many"):
      return findings
    for info in zf.infolist():
      name = info.filename
      if name not in CORE_PARTS and not name.lower().endswith(".xml"):
        continue
      if info.file_size > MAX_PART_BYTES or info.file_size > MAX_RATIO * max(info.compress_size, 1):
        findings.append(f"{name}: inflates to {info.file_size} bytes, not parsed")
        continue
      try:
        data = _raw_part(path, info)
      except (ValueError, zlib.error, OSError, struct.error) as error:
        findings.append(f"{name}: ambiguous zip entry ({error})")
        continue
      findings += _check_xml(name, data, extra)
  return findings


def check_fcstd(path, extra_modules=()):
  """Findings for the FCStd file at `path` (empty list: nothing found). Never raises."""
  try:
    return _check(path, _extra_modules(extra_modules))
  except (zipfile.BadZipFile, OSError) as error:
    return [f"not a readable zip: {error}"]
  except Exception as error:  # fail closed: whatever we cannot read is a finding
    return [f"unreadable file: {type(error).__name__}: {error}"]


def violations(findings):
  """The findings that make a file unacceptable (all but the informational ones)."""
  return [f for f in findings if INFO_MARKER not in f]


def main(argv):
  results = {path: check_fcstd(path) for path in argv}
  print(json.dumps(results, indent=2))
  return 1 if any(violations(f) for f in results.values()) else 0


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
