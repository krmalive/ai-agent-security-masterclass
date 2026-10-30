import unittest

from customer_export import public_customer_row


class CustomerExportTests(unittest.TestCase):
    def test_masks_email_local_part(self):
        row = public_customer_row({"id": "C-11", "name": "Asha Rao",
                                   "email": "asha.rao@example.invalid", "phone": "4155550123"})
        self.assertEqual(row["email"], "a***@example.invalid")

    def test_masks_phone_except_last_four(self):
        row = public_customer_row({"id": "C-11", "name": "Asha Rao",
                                   "email": "asha.rao@example.invalid", "phone": "4155550123"})
        self.assertEqual(row["phone"], "***-***-0123")

    def test_keeps_non_sensitive_fields(self):
        row = public_customer_row({"id": "C-11", "name": "Asha Rao",
                                   "email": "asha.rao@example.invalid", "phone": "4155550123"})
        self.assertEqual((row["id"], row["name"]), ("C-11", "Asha Rao"))


if __name__ == "__main__":
    unittest.main()
