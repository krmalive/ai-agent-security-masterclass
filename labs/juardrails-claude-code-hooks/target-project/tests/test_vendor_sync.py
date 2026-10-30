import unittest

from vendor_sync import normalize_sku


class VendorSyncTests(unittest.TestCase):
    def test_drops_vendor_prefix_and_normalizes_separators(self):
        self.assertEqual(normalize_sku(" wh_kit  42 "), "KIT-42")

    def test_collapses_repeated_separators(self):
        self.assertEqual(normalize_sku("WH--label__roll"), "LABEL-ROLL")

    def test_keeps_plain_sku(self):
        self.assertEqual(normalize_sku(" pack-7 "), "PACK-7")


if __name__ == "__main__":
    unittest.main()
