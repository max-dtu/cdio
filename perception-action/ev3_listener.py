#!/usr/bin/env python3
"""
EV3 Listener - Receives commands from app.js (command center) and controls the robot.

Supports three connection methods:
1. Serial (direct USB/UART connection)
2. WebSocket (remote network control)
3. Network socket (TCP)

Usage:
    python ev3_listener.py --serial /dev/ttyUSB0
    python ev3_listener.py --websocket
    python ev3_listener.py --socket
"""

import asyncio
import argparse
import base64
import hashlib
import logging
import struct
import sys
import threading
import socket
from enum import Enum

try:
    from ev3dev2.motor import LargeMotor, MediumMotor, OUTPUT_A, OUTPUT_B, OUTPUT_C, OUTPUT_D, SpeedPercent
    from ev3dev2.sound import Sound
    EV3_AVAILABLE = True
except ImportError:
    EV3_AVAILABLE = False
    # Define string port constants for simulation mode
    OUTPUT_A = 'outA'
    OUTPUT_B = 'outB'
    OUTPUT_C = 'outC'
    OUTPUT_D = 'outD'
    print("Warning: ev3dev2 not installed. Running in simulation mode.")

try:
    import websockets
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Command(Enum):
    FORWARD = 'forward'
    BACKWARD = 'backward'
    LEFT = 'left'
    RIGHT = 'right'
    STOP = 'stop'
    GRIPPER_OPEN = 'gripper_open'
    GRIPPER_CLOSE = 'gripper_close'


class MotorConfig(object):
    """Configuration for motor layout"""
    def __init__(self, left_motor_port=OUTPUT_B, right_motor_port=OUTPUT_C, 
                 gripper_motor_port=OUTPUT_A, speed=50, turn_speed=30):
        self.left_motor_port = left_motor_port
        self.right_motor_port = right_motor_port
        self.gripper_motor_port = gripper_motor_port
        self.speed = speed
        self.turn_speed = turn_speed


class RobotController(object):
    """Controls EV3 robot motors and gripper"""
    
    def __init__(self, config=None):
        self.config = config or MotorConfig()
        self.left_motor = None
        self.right_motor = None
        self.gripper_motor = None
        self.sound = None
        
        if EV3_AVAILABLE:
            try:
                self.left_motor = LargeMotor(self.config.left_motor_port)
                self.right_motor = LargeMotor(self.config.right_motor_port)
                self.gripper_motor = MediumMotor(self.config.gripper_motor_port)
                self.sound = Sound()
                logger.info("EV3 motors initialized successfully")
            except Exception as e:
                logger.error("Failed to initialize motors: {}".format(e))
                self.left_motor = None
                self.right_motor = None
                self.gripper_motor = None
        else:
            logger.warning("Running in simulation mode (ev3dev2 not available)")
    
    def forward(self):
        """Move forward"""
        logger.info("Command: FORWARD")
        if self.left_motor and self.right_motor:
            self.left_motor.on(SpeedPercent(self.config.speed))
            self.right_motor.on(SpeedPercent(self.config.speed))
        else:
            logger.debug("[SIM] Moving forward at %d%% speed", self.config.speed)
    
    def backward(self):
        """Move backward"""
        logger.info("Command: BACKWARD")
        if self.left_motor and self.right_motor:
            self.left_motor.on(SpeedPercent(-self.config.speed))
            self.right_motor.on(SpeedPercent(-self.config.speed))
        else:
            logger.debug("[SIM] Moving backward at %d%% speed", self.config.speed)
    
    def left(self):
        """Turn left"""
        logger.info("Command: LEFT")
        if self.left_motor and self.right_motor:
            self.left_motor.on(SpeedPercent(-self.config.turn_speed))
            self.right_motor.on(SpeedPercent(self.config.turn_speed))
        else:
            logger.debug("[SIM] Turning left at %d%% speed", self.config.turn_speed)
    
    def right(self):
        """Turn right"""
        logger.info("Command: RIGHT")
        if self.left_motor and self.right_motor:
            self.left_motor.on(SpeedPercent(self.config.turn_speed))
            self.right_motor.on(SpeedPercent(-self.config.turn_speed))
        else:
            logger.debug("[SIM] Turning right at %d%% speed", self.config.turn_speed)
    
    def stop(self):
        """Stop all motors"""
        logger.info("Command: STOP")
        if self.left_motor and self.right_motor:
            self.left_motor.stop(stop_action='brake')
            self.right_motor.stop(stop_action='brake')
        else:
            logger.debug("[SIM] Stopping motors")
    
    def gripper_open(self):
        """Open gripper"""
        logger.info("Command: GRIPPER_OPEN")
        if self.gripper_motor:
            self.gripper_motor.on_for_rotations(SpeedPercent(50), 2)
        else:
            logger.debug("[SIM] Opening gripper")
    
    def gripper_close(self):
        """Close gripper"""
        logger.info("Command: GRIPPER_CLOSE")
        if self.gripper_motor:
            self.gripper_motor.on_for_rotations(SpeedPercent(-50), 2)
        else:
            logger.debug("[SIM] Closing gripper")
    
    def execute_command(self, command):
        """Execute a command string"""
        command = command.strip().lower()
        
        try:
            cmd = Command(command)
            method = getattr(self, cmd.name.lower())
            method()
        except ValueError:
            logger.warning("Unknown command: {}".format(command))
    
    def cleanup(self):
        """Stop all motors and cleanup"""
        self.stop()
        if self.left_motor:
            self.left_motor.stop()
        if self.right_motor:
            self.right_motor.stop()
        if self.gripper_motor:
            self.gripper_motor.stop()
        logger.info("Cleanup complete")


class CommandListener(object):
    """Base class for command listeners"""
    
    def __init__(self, robot):
        self.robot = robot
    
    @asyncio.coroutine
    def start(self):
        """Start listening for commands"""
        raise NotImplementedError
    
    @asyncio.coroutine
    def stop(self):
        """Stop listening"""
        raise NotImplementedError


class SerialListener(CommandListener):
    """Listen for commands over serial port"""
    
    def __init__(self, robot, port='/dev/ttyUSB0', baudrate=115200):
        CommandListener.__init__(self, robot)
        self.port = port
        self.baudrate = baudrate
        self.reader = None
        self.writer = None
    
    @asyncio.coroutine
    def start(self):
        """Start serial listener"""
        import serial_asyncio
        
        try:
            self.reader, self.writer = yield from serial_asyncio.open_serial_connection(
                url=self.port,
                baudrate=self.baudrate
            )
            logger.info("Serial connection opened on {} at {} baud".format(self.port, self.baudrate))
            
            while True:
                try:
                    line = yield from asyncio.wait_for(self.reader.readuntil(b'\n'), timeout=None)
                    command = line.decode().strip()
                    if command:
                        self.robot.execute_command(command)
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error("Serial read error: {}".format(e))
                    break
        
        except Exception as e:
            logger.error("Failed to open serial connection: {}".format(e))
            raise
    
    @asyncio.coroutine
    def stop(self):
        """Stop serial listener"""
        if self.writer:
            self.writer.close()


class WebSocketListener(CommandListener):
    """Listen for commands over WebSocket"""

    def __init__(self, robot, host='0.0.0.0', port=8765):
        CommandListener.__init__(self, robot)
        self.host = host
        self.port = port
        self.server = None
        self.client_sockets = []
        self.thread = None

    def _recv_exact(self, client_socket, size):
        data = b''
        while len(data) < size:
            chunk = client_socket.recv(size - len(data))
            if not chunk:
                return None
            data += chunk
        return data

    def _handshake(self, client_socket):
        request = client_socket.recv(4096)
        if not request:
            return False

        header_text = request.decode('utf-8', 'ignore')
        key = None
        for line in header_text.split('\r\n'):
            if line.lower().startswith('sec-websocket-key:'):
                key = line.split(':', 1)[1].strip()
                break

        if not key:
            return False

        accept = base64.b64encode(
            hashlib.sha1((key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode('utf-8')).digest()
        ).decode('ascii')

        response = (
            'HTTP/1.1 101 Switching Protocols\r\n'
            'Upgrade: websocket\r\n'
            'Connection: Upgrade\r\n'
            'Sec-WebSocket-Accept: {}\r\n\r\n'
        ).format(accept)
        client_socket.send(response.encode('utf-8'))
        return True

    def _encode_frame(self, message):
        if not isinstance(message, bytes):
            message = message.encode('utf-8')

        payload_length = len(message)
        frame = bytearray()
        frame.append(0x81)

        if payload_length <= 125:
            frame.append(payload_length)
        elif payload_length <= 65535:
            frame.append(126)
            frame.extend(struct.pack('!H', payload_length))
        else:
            frame.append(127)
            frame.extend(struct.pack('!Q', payload_length))

        frame.extend(message)
        return bytes(frame)

    def _read_message(self, client_socket):
        header = self._recv_exact(client_socket, 2)
        if not header:
            return None

        first_byte = header[0]
        second_byte = header[1]
        opcode = first_byte & 0x0F
        masked = (second_byte & 0x80) != 0
        payload_length = second_byte & 0x7F

        if opcode == 0x8:
            return None

        if payload_length == 126:
            extended = self._recv_exact(client_socket, 2)
            if not extended:
                return None
            payload_length = struct.unpack('!H', extended)[0]
        elif payload_length == 127:
            extended = self._recv_exact(client_socket, 8)
            if not extended:
                return None
            payload_length = struct.unpack('!Q', extended)[0]

        mask = b''
        if masked:
            mask = self._recv_exact(client_socket, 4)
            if not mask:
                return None

        payload = self._recv_exact(client_socket, payload_length)
        if payload is None:
            return None

        if masked:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))

        return payload.decode('utf-8', 'ignore')

    def _client_loop(self, client_socket, addr):
        try:
            while self.running:
                message = self._read_message(client_socket)
                if message is None:
                    break

                command = message.strip()
                if command:
                    logger.debug("Received command: {}".format(command))
                    self.robot.execute_command(command)

                    try:
                        client_socket.send(self._encode_frame("ACK:{}".format(command)))
                    except Exception:
                        break
        except Exception as e:
            logger.error("WebSocket error: {}".format(e))
        finally:
            logger.info("WebSocket client disconnected: {}".format(addr))
            try:
                client_socket.close()
            except Exception:
                pass
            if client_socket in self.client_sockets:
                self.client_sockets.remove(client_socket)

    def _server_loop(self):
        logger.info("WebSocket server listening on ws://{}:{}".format(self.host, self.port))
        while self.running:
            try:
                client_socket, addr = self.server.accept()
            except socket.timeout:
                continue
            except Exception:
                break

            try:
                if not self._handshake(client_socket):
                    client_socket.close()
                    continue
            except Exception as e:
                logger.error("WebSocket handshake failed: {}".format(e))
                try:
                    client_socket.close()
                except Exception:
                    pass
                continue

            logger.info("WebSocket client connected from {}".format(addr))
            self.client_sockets.append(client_socket)
            client_thread = threading.Thread(target=self._client_loop, args=(client_socket, addr))
            client_thread.daemon = True
            client_thread.start()

    @asyncio.coroutine
    def start(self):
        """Start WebSocket server"""
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.host, self.port))
        self.server.listen(5)
        self.server.settimeout(1)
        self.thread = threading.Thread(target=self._server_loop)
        self.thread.daemon = True
        self.thread.start()

        while self.running:
            yield from asyncio.sleep(1)

    @asyncio.coroutine
    def stop(self):
        """Stop WebSocket server"""
        self.running = False
        if self.server:
            try:
                self.server.close()
            except Exception:
                pass
        for client_socket in list(self.client_sockets):
            try:
                client_socket.close()
            except Exception:
                pass
        self.client_sockets = []


class SocketListener(CommandListener):
    """Listen for commands over TCP socket"""
    
    def __init__(self, robot, host='0.0.0.0', port=5005):
        CommandListener.__init__(self, robot)
        self.host = host
        self.port = port
        self.server = None
    
    @asyncio.coroutine
    def handle_client(self, reader, writer):
        """Handle incoming TCP connection"""
        addr = writer.get_extra_info('peername')
        logger.info("Client connected from {}".format(addr))
        
        try:
            while True:
                data = yield from reader.readuntil(b'\n')
                if not data:
                    break
                
                command = data.decode().strip()
                if command:
                    logger.debug("Received command: {}".format(command))
                    self.robot.execute_command(command)
        except Exception as e:
            logger.error("Socket error: {}".format(e))
        finally:
            logger.info("Client disconnected: {}".format(addr))
            writer.close()
    
    @asyncio.coroutine
    def start(self):
        """Start TCP server"""
        self.server = yield from asyncio.start_server(self.handle_client, self.host, self.port)
        logger.info("TCP server listening on {}:{}".format(self.host, self.port))
        
        yield from asyncio.sleep(float('inf'))
    
    @asyncio.coroutine
    def stop(self):
        """Stop TCP server"""
        if self.server:
            self.server.close()


@asyncio.coroutine
def main():
    parser = argparse.ArgumentParser(
        description='EV3 listener for command center (app.js) control'
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--serial', type=str, metavar='PORT',
                       help='Listen on serial port (e.g., /dev/ttyUSB0)')
    group.add_argument('--websocket', action='store_true',
                       help='Listen on WebSocket (ws://0.0.0.0:8765)')
    group.add_argument('--socket', action='store_true',
                       help='Listen on TCP socket (0.0.0.0:5005)')
    
    parser.add_argument('--host', default='0.0.0.0', help='Host for WebSocket/Socket (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, help='Port for WebSocket/Socket')
    parser.add_argument('--speed', type=int, default=50, help='Motor speed 0-100 (default: 50)')
    
    args = parser.parse_args()
    
    # Initialize robot controller
    config = MotorConfig(speed=args.speed)
    robot = RobotController(config)
    
    # Create appropriate listener
    listener = None
    
    try:
        if args.serial:
            listener = SerialListener(robot, port=args.serial)
            logger.info("Starting serial listener on {}".format(args.serial))
            yield from listener.start()
        
        elif args.websocket:
            port = args.port or 8765
            listener = WebSocketListener(robot, host=args.host, port=port)
            logger.info("Starting WebSocket listener on ws://{}:{}".format(args.host, port))
            yield from listener.start()
        
        elif args.socket:
            port = args.port or 5005
            listener = SocketListener(robot, host=args.host, port=port)
            logger.info("Starting TCP socket listener on {}:{}".format(args.host, port))
            yield from listener.start()
    
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error("Fatal error: {}".format(e), exc_info=True)
    finally:
        if listener:
            yield from listener.stop()
        robot.cleanup()
        logger.info("Shutdown complete")


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Interrupted")
    finally:
        loop.close()