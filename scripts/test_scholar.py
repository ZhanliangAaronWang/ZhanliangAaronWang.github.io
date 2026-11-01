import importlib.util
import json
import pathlib
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("scholar", pathlib.Path(__file__).with_name("scholar.py"))
scholar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scholar)

PAGE = """<table id="gsc_rsb_st">
<tr><td class="gsc_rsb_std">1,234</td><td class="gsc_rsb_std">900</td></tr>
<tr><td class="gsc_rsb_std">12</td><td class="gsc_rsb_std">10</td></tr>
<tr><td class="gsc_rsb_std">8</td><td class="gsc_rsb_std">7</td></tr></table>
<tr class="gsc_a_tr"><td><a class="gsc_a_at">Test: AI &amp; Math</a></td>
<td><a class="gsc_a_ac">42</a></td></tr>
<button id="gsc_bpf_more" disabled>More</button>"""

class ScholarTests(unittest.TestCase):
    def test_profile(self):
        self.assertEqual(scholar.parse_page(PAGE), ([1234, 12, 8], {"testaimath": 42}, False))

    def test_block_keeps_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            out = pathlib.Path(directory) / "scholar.json"
            out.write_text('{"citations": 1234}')
            with self.assertRaises(RuntimeError):
                scholar.refresh(out, lambda url: "<html>CAPTCHA</html>")
            self.assertEqual(out.read_text(), '{"citations": 1234}')

    def test_complete_pagination(self):
        pages = iter([PAGE.replace(" disabled", ""), PAGE.replace("Test: AI &amp; Math", "Second paper")])
        with tempfile.TemporaryDirectory() as directory:
            out = pathlib.Path(directory) / "scholar.json"
            scholar.refresh(out, lambda url: next(pages))
            self.assertEqual(len(json.loads(out.read_text())["papers"]), 2)

    def test_incomplete_stats_rejected(self):
        with self.assertRaises(RuntimeError):
            scholar.parse_page(PAGE.replace('<td class="gsc_rsb_std">8</td>', "<td>8</td>").replace('<td class="gsc_rsb_std">7</td>', "<td>7</td>"))

if __name__ == "__main__":
    unittest.main()
