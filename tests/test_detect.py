import unittest

from pi_kiosk.detect import looks_like_raspberry_pi


class LooksLikeRaspberryPiTests(unittest.TestCase):
    def test_device_tree_model_is_enough(self):
        self.assertTrue(
            looks_like_raspberry_pi(
                model="Raspberry Pi 5 Model B Rev 1.0",
                has_rpi_issue=False,
            )
        )

    def test_rpi_issue_file_is_enough(self):
        self.assertTrue(
            looks_like_raspberry_pi(model=None, has_rpi_issue=True)
        )

    def test_generic_linux_box_is_rejected(self):
        self.assertFalse(
            looks_like_raspberry_pi(
                model="QEMU Virtual CPU",
                has_rpi_issue=False,
            )
        )
