"""The static FCStd check: stdlib only, small crafted archives. Run: python3 -m unittest discover -s tests"""

import base64, os, random, struct, sys, tempfile, unittest, zipfile
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fcstd_check"))
import fcstd_check
from fcstd_check import check_fcstd

def read(path):
  with open(path, "rb") as f:
    return f.read()


def write(path, data):
  with open(path, "wb") as f:
    f.write(data)


CLEAN = '<Document><Object type="Part::Feature" name="Box"/></Document>'


def python_object(module, cls, state=b"{}"):
  value = base64.b64encode(state).decode()
  return f'<Document><Property name="Proxy" type="App::PropertyPythonObject"><Python value="{value}" encoded="yes" module="{module}" class="{cls}"/></Property></Document>'


class CheckTest(unittest.TestCase):
  def setUp(self):
    self.dir = tempfile.TemporaryDirectory()
    self.addCleanup(self.dir.cleanup)

  def fcstd(self, document=CLEAN, extra=(), gui=None, name="t.FCStd"):
    path = os.path.join(self.dir.name, name)
    with zipfile.ZipFile(path, "w") as zf:
      zf.writestr("Document.xml", document)
      if gui:
        zf.writestr("GuiDocument.xml", gui)
      for entry in extra:
        zf.writestr(entry, "x")
    return path

  def test_clean(self):
    self.assertEqual(check_fcstd(self.fcstd()), [])

  def test_unsafe_zip_entries(self):
    findings = check_fcstd(self.fcstd(extra=["../evil", "/abs", "a\\b", "C:x"]))
    self.assertEqual(len(findings), 4)

  def test_symlink_entry(self):
    path = self.fcstd()
    with zipfile.ZipFile(path, "a") as zf:
      info = zipfile.ZipInfo("link")
      info.external_attr = 0o120777 << 16
      zf.writestr(info, "/etc/passwd")
    self.assertTrue(any("symlink" in f for f in check_fcstd(path)))

  def test_doctype_and_entity(self):
    doc = '<?xml version="1.0"?><!DOCTYPE d [<!ENTITY x "y">]><Document>&x;</Document>'
    findings = check_fcstd(self.fcstd(doc))
    self.assertTrue(any("DOCTYPE" in f for f in findings))
    self.assertTrue(any("entity declaration" in f for f in findings))

  def test_gui_document_is_checked(self):
    findings = check_fcstd(self.fcstd(gui="<!DOCTYPE d><Document/>"))
    self.assertTrue(any(f.startswith("GuiDocument.xml") for f in findings))

  def test_other_xml_entries_are_checked(self):
    path = self.fcstd()
    with zipfile.ZipFile(path, "a") as zf:
      zf.writestr("Extra.XML", "<!DOCTYPE d><d/>")
    self.assertTrue(any(f.startswith("Extra.XML") and "DOCTYPE" in f for f in check_fcstd(path)))

  def test_own_workbench_module_is_reported_not_flagged(self):
    findings = check_fcstd(self.fcstd(python_object("draftobjects.wire", "Wire")))
    self.assertEqual(findings, ["Document.xml: python object draftobjects.wire.Wire"])
    self.assertEqual(fcstd_check.violations(findings), [])

  def test_foreign_module_is_flagged(self):
    findings = check_fcstd(self.fcstd(python_object("evilmod", "X")))
    self.assertIn("Document.xml: python module outside allowlist: evilmod", findings)

  def test_extra_modules_argument_and_env(self):
    path = self.fcstd(python_object("mymod.sub", "X"))
    self.assertEqual(fcstd_check.violations(check_fcstd(path, extra_modules=("mymod",))), [])
    with mock.patch.dict(os.environ, {"FCSTD_EXTRA_MODULES": "other, mymod"}):
      self.assertEqual(fcstd_check.violations(check_fcstd(path)), [])
    self.assertEqual(len(fcstd_check.violations(check_fcstd(path))), 1)

  def test_non_json_state(self):
    findings = check_fcstd(self.fcstd(python_object("Draft", "X", b"\x80\x04N.")))
    self.assertTrue(any("not JSON" in f for f in findings))

  def test_plain_json_state_is_not_flagged(self):
    doc = '<Document><Python value="{}" module="Draft" class="X"/></Document>'
    self.assertEqual(check_fcstd(self.fcstd(doc)), ["Document.xml: python object Draft.X"])

  def test_zip_bomb_is_not_parsed(self):
    path = os.path.join(self.dir.name, "b.FCStd")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
      zf.writestr("Document.xml", "<Document>" + " " * (5 * 1024 * 1024) + "</Document>")
    self.assertTrue(any("not parsed" in f for f in check_fcstd(path)))

  def test_file_included_leaving_the_document(self):
    doc = '<Document><FileIncluded file="../../etc/passwd"/><FileIncluded file="ok.txt"/></Document>'
    self.assertEqual(len(check_fcstd(self.fcstd(doc))), 1)

  def test_not_a_zip(self):
    path = os.path.join(self.dir.name, "n.FCStd")
    write(path, b"nope")
    self.assertTrue(check_fcstd(path)[0].startswith("not a readable zip"))

  def test_missing_file_is_a_finding(self):
    self.assertTrue(check_fcstd(os.path.join(self.dir.name, "none"))[0].startswith("not a readable zip"))

  def test_duplicate_entry_names(self):
    path = os.path.join(self.dir.name, "d.FCStd")
    with zipfile.ZipFile(path, "w") as zf:
      zf.writestr("Document.xml", CLEAN)
      with self.assertWarns(UserWarning):
        zf.writestr("Document.xml", "<Document/>")
    self.assertTrue(any("duplicate zip entry" in f for f in check_fcstd(path)))

  def test_duplicate_entry_names_differing_in_case(self):
    findings = check_fcstd(self.fcstd(extra=["document.xml"]))
    self.assertTrue(any("duplicate zip entry" in f for f in findings))

  def test_dot_and_empty_path_components(self):
    self.assertEqual(len(check_fcstd(self.fcstd(extra=["./a", "b//c"]))), 2)

  def test_declared_encoding_other_than_utf8(self):
    doc = '<?xml version="1.0" encoding="ISO-8859-1"?><Document/>'
    self.assertTrue(any("not UTF-8" in f for f in check_fcstd(self.fcstd(doc))))
    ok = '<?xml version="1.0" encoding="utf-8"?><Document/>'
    self.assertEqual(check_fcstd(self.fcstd(ok)), [])

  def test_bom_and_utf16(self):
    for data in (b"\xef\xbb\xbf<Document/>", "<Document/>".encode("utf-16"), "<Document/>".encode("utf-16-le"), "<Document/>".encode("utf-32")):
      path = os.path.join(self.dir.name, "e.FCStd")
      with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("Document.xml", data)
      self.assertEqual(len(check_fcstd(path)), 1, data)

  def test_invalid_utf8(self):
    path = os.path.join(self.dir.name, "e.FCStd")
    with zipfile.ZipFile(path, "w") as zf:
      zf.writestr("Document.xml", b"<Document a='\xff'/>")
    self.assertTrue(any("not valid UTF-8" in f for f in check_fcstd(path)))

  def test_local_header_name_differs_from_central_directory(self):
    path = self.fcstd()
    raw = bytearray(read(path))
    raw[30:30 + 12] = b"Documenx.xml"  # local header name only
    write(path, raw)
    self.assertTrue(any("ambiguous" in f for f in check_fcstd(path)))

  def test_lying_central_directory_size(self):
    path = os.path.join(self.dir.name, "l.FCStd")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
      zf.writestr("Document.xml", CLEAN + " " * 200)
    raw = bytearray(read(path))
    central = raw.rindex(b"PK\x01\x02")
    raw[central + 24:central + 28] = struct.pack("<I", 10)  # claimed uncompressed size
    write(path, raw)
    self.assertTrue(any("ambiguous" in f or "not parsed" in f or "unreadable" in f for f in check_fcstd(path)))

  def test_cli_exit_code(self):
    clean = self.fcstd(python_object("Draft", "X"))
    bad = self.fcstd(python_object("evilmod", "X"), name="bad.FCStd")
    with mock.patch("builtins.print"):
      self.assertEqual(fcstd_check.main([clean]), 0)
      self.assertEqual(fcstd_check.main([clean, bad]), 1)

  def test_fuzz_mutations_never_raise(self):
    path = os.path.join(self.dir.name, "z.FCStd")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
      zf.writestr("Document.xml", python_object("Draft", "X"))
      zf.writestr("GuiDocument.xml", CLEAN)
    original = read(path)
    rng = random.Random(1234)
    target = os.path.join(self.dir.name, "m.FCStd")
    for _ in range(500):
      data = bytearray(original)
      for _ in range(rng.randint(1, 8)):
        kind = rng.choice(["flip", "cut", "insert"])
        pos = rng.randrange(len(data))
        if kind == "flip":
          data[pos] = rng.randrange(256)
        elif kind == "cut":
          del data[pos:]
        else:
          data[pos:pos] = bytes(rng.randrange(256) for _ in range(rng.randint(1, 16)))
        if not data:
          data = bytearray(b"x")
      write(target, data)
      self.assertIsInstance(check_fcstd(target), list)


if __name__ == "__main__":
  unittest.main()
