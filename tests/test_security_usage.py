"""Tests for non-blocking per-device traffic accounting."""
import unittest
from unittest import mock

from piscripts.security_usage import parse_neighbors, parse_rules, reconcile, tick, update_totals


MAC = "02:00:00:00:00:11"
IP = "192.0.2.10"
UP = "wpi-sec|up|%s|%s|123456abcdef" % (MAC, IP)
DOWN = "wpi-sec|down|%s|%s|123456abcdef" % (MAC, IP)


def snapshot(up, down):
    return (
        '[1:%d] -A WPI_SEC_U_52B7 -s %s/32 -i eth0 -o usb0 -m mac --mac-source %s -m comment --comment "%s"\n'
        '[1:%d] -A WPI_SEC_U_52B7 -d %s/32 -i usb0 -o eth0 -m comment --comment "%s"\n'
        % (up, IP, MAC, UP, down, IP, DOWN)
    )


class SecurityUsageTests(unittest.TestCase):
    def test_counts_only_increments_and_handles_reset(self):
        state = {"last_counters": {}, "devices": {}}
        update_totals(state, parse_rules(snapshot(100, 200)))
        update_totals(state, parse_rules(snapshot(130, 270)))
        self.assertEqual(state["devices"][MAC]["up_bytes"], 130)
        self.assertEqual(state["devices"][MAC]["down_bytes"], 270)
        update_totals(state, parse_rules(snapshot(10, 20)))
        self.assertEqual(state["devices"][MAC]["up_bytes"], 140)
        self.assertEqual(state["devices"][MAC]["down_bytes"], 290)

    def test_rejects_rules_that_could_change_forwarding(self):
        with self.assertRaises(RuntimeError):
            parse_rules(snapshot(1, 2).replace('-m comment --comment "' + UP + '"',
                                               '-m comment --comment "' + UP + '" -j DROP'))
        with self.assertRaises(RuntimeError):
            parse_rules(snapshot(1, 2) + snapshot(1, 2))

    def test_ignores_incomplete_and_other_interface_neighbors(self):
        arp = (
            "IP address HW type Flags HW address Mask Device\n"
            "%s 0x1 0x2 %s * eth0\n"
            "10.0.0.2 0x1 0x0 00:00:00:00:00:00 * eth0\n"
            "192.168.1.1 0x1 0x2 %s * usb0\n"
        ) % (IP, MAC, MAC)
        self.assertEqual(parse_neighbors(arp), {IP: MAC})

    @mock.patch("piscripts.security_usage.command")
    def test_ip_reassignment_replaces_old_rules_without_blocking(self, command):
        rules = parse_rules(snapshot(10, 20))
        reconcile({IP: "00:11:22:33:44:55"}, rules)
        calls = [call.args for call in command.call_args_list]
        self.assertEqual([call[0] for call in calls], ["-D", "-D", "-A", "-A"])
        self.assertTrue(all("-j" not in call for call in calls))

    @mock.patch("piscripts.security_usage.save_state")
    @mock.patch("piscripts.security_usage.reconcile", side_effect=RuntimeError("iptables failed"))
    @mock.patch("piscripts.security_usage.parse_neighbors", return_value={IP: "00:11:22:33:44:55"})
    @mock.patch("piscripts.security_usage.snapshot", return_value=snapshot(10, 20))
    @mock.patch("builtins.open", new_callable=mock.mock_open, read_data="")
    def test_failed_reconcile_does_not_mark_data_fresh(self, opened, get_snapshot, neighbors, reconcile_rules, save):
        state = {"last_counters": {}, "devices": {}, "updated_at": 123}
        with self.assertRaises(RuntimeError):
            tick(state)
        self.assertEqual(state["updated_at"], 123)
        save.assert_called_once()


if __name__ == "__main__":
    unittest.main()
