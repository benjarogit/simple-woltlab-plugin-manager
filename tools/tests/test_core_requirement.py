import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('requirements', Path(__file__).resolve().parents[1] / 'package-core-requirement.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RequirementsTests(unittest.TestCase):
    def read(self, xml):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'package.xml'
            path.write_text(xml)
            return module.read_requirement(path)

    def test_addon_dependency_precedes_core(self):
        self.assertEqual(self.read('''<package xmlns="http://www.woltlab.com"><requiredpackages>
        <requiredpackage minversion="1.0.0">com.vendor.base</requiredpackage>
        <requiredpackage minversion="6.3.0 dev 1">com.woltlab.wcf</requiredpackage>
        </requiredpackages></package>'''), '6.3.0 dev 1')

    def test_single_quotes_and_attribute_order(self):
        self.assertEqual(self.read("<package><requiredpackages><requiredpackage optional='0' minversion='6.2.0'>com.woltlab.wcf</requiredpackage></requiredpackages></package>"), '6.2.0')

    def test_other_package_is_not_core(self):
        self.assertEqual(self.read('<package><requiredpackages><requiredpackage minversion="9.0.0">com.vendor.base</requiredpackage></requiredpackages></package>'), '')


if __name__ == '__main__':
    unittest.main()
