#!/usr/bin/env python3
"""EV3 websocket listener for app.js commands.

Install dependencies on the EV3:
    pip3 install ev3dev2 websockets

Run:
    python3 ev3_listener.py --host 0.0.0.0 --port 8765
"""

import argparse
import asyncio
import logging

try:
    import websockets
except ImportError:
    websockets = None

try:
    from ev3dev2.motor import LargeMotor, MediumMotor, OUTPUT_A, OUTPUT_B, OUTPUT_C, SpeedPercent
except ImportError:
    LargeMotor = MediumMotor = SpeedPercent = None
    OUTPUT_A = 'outA'
    OUTPUT_B = 'outB'
    OUTPUT_C = 'outC'


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)


COMMANDS = {
    'forward': 'forward',
    'backward': 'backward',
    'left': 'left',
    'right': 'right',
    'stop': 'stop',
    'gripper_open': 'gripper_open',
    'gripper_close': 'gripper_close',
}


class Robot(object):
    def __init__(self, left_port=OUTPUT_B, right_port=OUTPUT_C, gripper_port=OUTPUT_A, drive_speed=50):
        self.drive_speed = drive_speed
        self.left_motor = None
        self.right_motor = None
        self.gripper_motor = None

        if LargeMotor is None or MediumMotor is None:
            log.warning('ev3dev2 is not installed; running in simulation mode')
            return

        try:
            self.left_motor = LargeMotor(left_port)
            self.right_motor = LargeMotor(right_port)
            self.gripper_motor = MediumMotor(gripper_port)
            log.info('Motors initialized: left=%s right=%s gripper=%s', left_port, right_port, gripper_port)
        except Exception as exc:
            log.error('Motor initialization failed: %s', exc)

    def _drive(self, left_speed, right_speed):
        if self.left_motor and self.right_motor:
            self.left_motor.on(SpeedPercent(left_speed))
            self.right_motor.on(SpeedPercent(right_speed))
        else:
            log.info('[SIM] drive left=%s right=%s', left_speed, right_speed)

    def forward(self):
        self._drive(self.drive_speed, self.drive_speed)

    def backward(self):
        self._drive(-self.drive_speed, -self.drive_speed)

    def left(self):
        self._drive(-self.drive_speed, self.drive_speed)

    def right(self):
        self._drive(self.drive_speed, -self.drive_speed)

    def stop(self):
        if self.left_motor and self.right_motor:
            self.left_motor.stop(stop_action='brake')
            self.right_motor.stop(stop_action='brake')
        else:
            log.info('[SIM] stop')

    def gripper_open(self):
        if self.gripper_motor:
            self.gripper_motor.on_for_rotations(SpeedPercent(40), 1)
        else:
            log.info('[SIM] gripper_open')

    def gripper_close(self):
        if self.gripper_motor:
            self.gripper_motor.on_for_rotations(SpeedPercent(-40), 1)
        else:
            log.info('[SIM] gripper_close')

    def handle(self, command):
        command = command.strip().lower()
        if not command:
            return

        action = COMMANDS.get(command)
        if not action:
            log.warning('Unknown command: %s', command)
            return

        getattr(self, action)()

    def cleanup(self):
        self.stop()
        if self.left_motor:
            self.left_motor.stop()
        if self.right_motor:
            self.right_motor.stop()
        if self.gripper_motor:
            self.gripper_motor.stop()


async def serve_client(websocket, path, robot):
    peer = getattr(websocket, 'remote_address', None)
    log.info('Client connected: %s', peer)
    try:
        async for message in websocket:
            for command in message.splitlines():
                command = command.strip()
                if not command:
                    continue
                log.info('Command: %s', command)
                robot.handle(command)
                await websocket.send('ACK {}'.format(command))
    except websockets.ConnectionClosed:
        pass
    finally:
        log.info('Client disconnected: %s', peer)
        robot.stop()


async def main(host, port, drive_speed):
    if websockets is None:
        raise RuntimeError('Missing dependency: websockets. Install with: pip3 install websockets')

    robot = Robot(drive_speed=drive_speed)
    server = await websockets.serve(lambda ws, path: serve_client(ws, path, robot), host, port)
    log.info('Listening on ws://%s:%s', host, port)

    try:
        await asyncio.Future()
    finally:
        server.close()
        await server.wait_closed()
        robot.cleanup()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='EV3 websocket listener for app.js')
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--speed', type=int, default=50)
    args = parser.parse_args()

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main(args.host, args.port, args.speed))
    except KeyboardInterrupt:
        log.info('Stopped by user')
    finally:
        loop.close()
