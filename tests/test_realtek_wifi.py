"""Tests for Realtek Wi-Fi station statistics."""
import unittest

from piscripts.realtek_wifi import parse_stations


class StationParserTests(unittest.TestCase):
    def test_reads_per_radio_station_counters(self):
        output = (
            "__wlan0__\r\n-- STA info table -- (active: 0)\r\n"
            "__wlan1__\r\n-- STA info table -- (active: 1)\r\n"
            " 1: stat_info...\r\n    hwaddr: 020000000011\r\n"
            "    tx_bytes: 123\r\n    rx_bytes: 456\r\n__END__\r\n"
        )
        self.assertEqual(parse_stations(output), [{
            "radio": "wlan1", "mac": "02:00:00:00:00:11",
            "tx_bytes": 123, "rx_bytes": 456,
        }])

    def test_rejects_missing_or_incomplete_counters(self):
        samples = (
            "__wlan0__\n-- STA info table -- (active: 0)\n__END__\n",
            "__wlan0__\n-- STA info table -- (active: 1)\n__wlan1__\n"
            "-- STA info table -- (active: 0)\n__END__\n",
        )
        for sample in samples:
            with self.subTest(sample=sample), self.assertRaises(ValueError):
                parse_stations(sample)


if __name__ == "__main__":
    unittest.main()
