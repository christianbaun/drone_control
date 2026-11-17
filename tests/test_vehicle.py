# SPDX-License-Identifier: Apache-2.0
"""Test MAVLink state handling, flight checks, arming, and RC takeover without hardware.

File: tests/test_vehicle.py
Project: drone_control
Version: 0.1.0 (project version)
Header added: 2026-11-17
Authors: drone_control contributors
Development assistance: OpenAI Codex CLI
License: Apache License, Version 2.0; see LICENSE in the repository root.
"""

import time
import unittest
from unittest.mock import Mock, patch
from pymavlink import mavutil
from drone_control.vehicle import Vehicle, FlightError, CommandRejected, PilotOverride, GUIDED, LAND

M = mavutil.mavlink


def heartbeat(mode=GUIDED, system=1):
    msg = M.MAVLink_heartbeat_message(M.MAV_TYPE_QUADROTOR,
        M.MAV_AUTOPILOT_ARDUPILOTMEGA, M.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        mode, M.MAV_STATE_ACTIVE, 3)
    msg._header.srcSystem = system
    msg._header.srcComponent = 1
    return msg


class VehicleTests(unittest.TestCase):
    def setUp(self):
        self.transport = Mock()
        self.transport.recv_match.return_value = None
        with patch('drone_control.vehicle.mavutil.mavlink_connection', return_value=self.transport):
            self.vehicle = Vehicle('unused')
        self.vehicle.cache['HEARTBEAT'] = (heartbeat(), time.monotonic())
        self.vehicle.expected_mode = (GUIDED,)

    def test_override_is_latched(self):
        self.transport.recv_match.side_effect = [heartbeat(2), heartbeat(GUIDED)]
        self.vehicle.pump()
        self.vehicle.pump()
        with self.assertRaises(PilotOverride):
            self.vehicle.command(M.MAV_CMD_NAV_LAND)
        self.transport.mav.command_long_send.assert_not_called()

    def test_foreign_vehicle_does_not_override(self):
        self.transport.recv_match.return_value = heartbeat(2, system=42)
        self.vehicle.pump()
        self.vehicle.guard()
        self.assertFalse(self.vehicle.overridden)

    def test_stale_heartbeat_blocks_commands(self):
        self.vehicle.cache['HEARTBEAT'] = (heartbeat(), time.monotonic() - 10)
        with self.assertRaises(FlightError):
            self.vehicle.command(M.MAV_CMD_COMPONENT_ARM_DISARM, 1)
        self.transport.mav.command_long_send.assert_not_called()

    def test_rejected_command(self):
        ack = M.MAVLink_command_ack_message(M.MAV_CMD_COMPONENT_ARM_DISARM, M.MAV_RESULT_DENIED)
        ack._header.srcSystem, ack._header.srcComponent = 1, 1
        self.transport.recv_match.return_value = ack
        with self.assertRaisesRegex(FlightError, 'abgelehnt'):
            self.vehicle.command(M.MAV_CMD_COMPONENT_ARM_DISARM, 1)

    def test_land_transition_and_completion(self):
        ack = M.MAVLink_command_ack_message(M.MAV_CMD_NAV_LAND, M.MAV_RESULT_ACCEPTED)
        ack._header.srcSystem, ack._header.srcComponent = 1, 1
        self.transport.recv_match.side_effect = [ack, heartbeat(LAND), heartbeat(LAND)]
        self.vehicle.land(1)
        self.assertFalse(self.vehicle.overridden)
        self.assertEqual(self.vehicle.expected_mode, (LAND,))
        args = self.transport.mav.command_long_send.call_args.args
        self.assertEqual(args[:4], (1, 1, M.MAV_CMD_NAV_LAND, 0))

    def test_close_stops_heartbeat(self):
        self.vehicle.heartbeat_enabled = True
        self.vehicle.close()
        self.assertFalse(self.vehicle.heartbeat_enabled)
        self.transport.close.assert_called_once()

    def test_arm_only_has_no_takeoff_land_or_heartbeat(self):
        self.vehicle.parameter = Mock(return_value=1)
        state = Mock(landed_state=M.MAV_LANDED_STATE_ON_GROUND)
        self.vehicle.cache['EXTENDED_SYS_STATE'] = (state, time.monotonic())
        self.vehicle.arm = Mock()
        self.vehicle.wait = Mock()
        self.vehicle.arm_only()
        self.vehicle.arm.assert_called_once()
        calls = self.transport.mav.command_long_send.call_args_list
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].args[2], M.MAV_CMD_SET_MESSAGE_INTERVAL)
        self.transport.mav.heartbeat_send.assert_not_called()
        self.assertFalse(self.vehicle.heartbeat_enabled)

    def test_arm_only_rejects_airborne(self):
        self.vehicle.parameter = Mock(return_value=1)
        state = Mock(landed_state=M.MAV_LANDED_STATE_IN_AIR)
        self.vehicle.cache['EXTENDED_SYS_STATE'] = (state, time.monotonic())
        self.vehicle.arm = Mock()
        self.vehicle.wait = Mock()
        with self.assertRaisesRegex(FlightError, 'Bodenkontakt'):
            self.vehicle.arm_only()
        self.vehicle.arm.assert_not_called()

    def test_arm_reports_reason_arriving_after_rejected_ack(self):
        import itertools
        self.vehicle.command = Mock(side_effect=CommandRejected('MAV_RESULT_DENIED'))
        self.vehicle.guard = Mock()
        msg = M.MAVLink_statustext_message(2, b'PreArm: Battery 1 low voltage')
        msg._header.srcSystem, msg._header.srcComponent = 1, 1
        self.transport.recv_match.side_effect = itertools.chain([msg], itertools.repeat(None))
        with patch('drone_control.vehicle.time.monotonic', side_effect=itertools.count(0, 0.1)):
            with self.assertRaisesRegex(FlightError, 'PreArm: Battery 1 low voltage'):
                self.vehicle.arm()
        self.vehicle.command.assert_called_once_with(M.MAV_CMD_COMPONENT_ARM_DISARM, 1)
        self.assertFalse(self.vehicle.started)

    def test_old_prearm_reason_not_used_for_new_attempt(self):
        self.vehicle.cache['ARMING_MESSAGES'] = [('PreArm: Old error', 1)]
        self.assertIn('Keine konkrete', self.vehicle.arming_diagnostics(2))

    def test_custom_arming_mask_is_accepted_without_writing_parameters(self):
        self.vehicle.parameter = Mock(return_value=6)
        with self.assertLogs('drone_control.vehicle', level='WARNING') as logs:
            self.vehicle.check_arming_configuration()
        self.assertIn('ARMING_CHECK=6', '\n'.join(logs.output))
        self.transport.mav.param_set_send.assert_not_called()
        self.transport.mav.command_long_send.assert_not_called()

    def test_disabled_or_invalid_arming_checks_are_rejected(self):
        for value in [0, -1, 1.5, float('nan')]:
            with self.subTest(value=value):
                self.vehicle.parameter = Mock(return_value=value)
                with self.assertRaises(FlightError):
                    self.vehicle.check_arming_configuration()

    def test_arm_only_custom_mask_uses_normal_arm_method(self):
        self.vehicle.parameter = Mock(return_value=6)
        self.vehicle.cache['EXTENDED_SYS_STATE'] = (
            Mock(landed_state=M.MAV_LANDED_STATE_ON_GROUND), time.monotonic())
        self.vehicle.arm = Mock()
        self.vehicle.wait = Mock()
        with self.assertLogs('drone_control.vehicle', level='WARNING'):
            self.vehicle.arm_only()
        self.vehicle.arm.assert_called_once()
