#!/usr/bin/env python3
"""
EV3 Listener - Receives commands from app.js (command center) and controls the robot.

Supports three connection methods:
1. Serial (direct USB/UART connection)
2. WebSocket (remote network control)
3. Network socket (TCP)

Usage:
    python3 ev3_listener.py --serial /dev/ttyUSB0
    python3 ev3_listener.py --websocket
    python3 ev3_listener.py --socket
"""

import asyncio
import argparse
import logging
import sys
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
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

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


class RobotController:
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


class CommandListener:
    """Base class for command listeners"""
    
    def __init__(self, robot):
        self.robot = robot
    
    async def start(self):
        """Start listening for commands"""
        raise NotImplementedError
    
    async def stop(self):
        """Stop listening"""
        raise NotImplementedError


class SerialListener(CommandListener):
    """Listen for commands over serial port"""
    
    def __init__(self, robot, port='/dev/ttyUSB0', baudrate=115200):
        super().__init__(robot)
        self.port = port
        self.baudrate = baudrate
        self.reader = None
        self.writer = None
    
    async def start(self):
        """Start serial listener"""
        import serial_asyncio
        
        try:
            self.reader, self.writer = await serial_asyncio.open_serial_connection(
                url=self.port,
                baudrate=self.baudrate
            )
            logger.info("Serial connection opened on {} at {} baud".format(self.port, self.baudrate))
            
            while True:
                try:
                    line = await asyncio.wait_for(self.reader.readuntil(b'\n'), timeout=None)
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
    
    async def stop(self):
        """Stop serial listener"""
        if self.writer:
            self.writer.close()


class WebSocketListener(CommandListener):
    """Listen for commands over WebSocket"""
    
    def __init__(self, robot, host='localhost', port=8765):
        super().__init__(robot)
        self.host = host
        self.port = port
        self.server = None
    
    async def handle_client(self, websocket, path):
        """Handle incoming WebSocket connection"""
        logger.info("Client connected from {}".format(websocket.remote_address))
        try:
            async for message in websocket:
                command = message.strip()
                if command:
                    logger.debug("Received command: {}".format(command))
                    self.robot.execute_command(command)
                    # Optionally send acknowledgment
                    await websocket.send("ACK:{}".format(command))
        except Exception as e:
            logger.error("WebSocket error: {}".format(e))
        finally:
            logger.info("Client disconnected: {}".format(websocket.remote_address))
    
    async def start(self):
        """Start WebSocket server"""
        if not WEBSOCKETS_AVAILABLE:
            raise ImportError("websockets library not installed. Install with: pip3 install websockets")
        
        self.server = await websockets.serve(self.handle_client, self.host, self.port)
        logger.info("WebSocket server listening on ws://{}:{}".format(self.host, self.port))
        
        # Keep the server running
        await asyncio.Future()
    
    async def stop(self):
        """Stop WebSocket server"""
        if self.server:
            self.server.close()


class SocketListener(CommandListener):
    """Listen for commands over TCP socket"""
    
    def __init__(self, robot, host='localhost', port=5005):
        super().__init__(robot)
        self.host = host
        self.port = port
        self.server = None
    
    async def handle_client(self, reader, writer):
        """Handle incoming TCP connection"""
        addr = writer.get_extra_info('peername')
        logger.info("Client connected from {}".format(addr))
        
        try:
            while True:
                data = await reader.readuntil(b'\n')
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
    
    async def start(self):
        """Start TCP server"""
        self.server = await asyncio.start_server(self.handle_client, self.host, self.port)
        logger.info("TCP server listening on {}:{}".format(self.host, self.port))
        
        async with self.server:
            await self.server.serve_forever()
    
    async def stop(self):
        """Stop TCP server"""
        if self.server:
            self.server.close()


async def main():
    parser = argparse.ArgumentParser(
        description='EV3 listener for command center (app.js) control',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 ev3_listener.py --serial /dev/ttyUSB0
  python3 ev3_listener.py --websocket
  python3 ev3_listener.py --socket
        """
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--serial', type=str, metavar='PORT',
                       help='Listen on serial port (e.g., /dev/ttyUSB0)')
    group.add_argument('--websocket', action='store_true',
                       help='Listen on WebSocket (ws://localhost:8765)')
    group.add_argument('--socket', action='store_true',
                       help='Listen on TCP socket (localhost:5005)')
    
    parser.add_argument('--host', default='localhost', help='Host for WebSocket/Socket (default: localhost)')
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
            await listener.start()
        
        elif args.websocket:
            port = args.port or 8765
            listener = WebSocketListener(robot, host=args.host, port=port)
            logger.info("Starting WebSocket listener on ws://{}:{}".format(args.host, port))
            await listener.start()
        
        elif args.socket:
            port = args.port or 5005
            listener = SocketListener(robot, host=args.host, port=port)
            logger.info("Starting TCP socket listener on {}:{}".format(args.host, port))
            await listener.start()
    
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error("Fatal error: {}".format(e), exc_info=True)
    finally:
        if listener:
            await listener.stop()
        robot.cleanup()
        logger.info("Shutdown complete")


if __name__ == '__main__':
    asyncio.run(main())