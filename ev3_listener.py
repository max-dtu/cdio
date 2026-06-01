from ev3dev2.motor import (
    LargeMotor,
    MediumMotor,
    OUTPUT_A,
    OUTPUT_B,
    OUTPUT_D,
    SpeedPercent
)

import asyncio
import websockets


# --------------------------------------------------
# MOTOR SETUP
# --------------------------------------------------

def safe_motor(cls, port, name):
    try:
        motor = cls(port)
        print("{} OK: {}".format(name, port))
        return motor
    except Exception as e:
        print("{} FAIL: {} -> {}".format(name, port, e))
        return None


left_motor = safe_motor(LargeMotor, OUTPUT_A, "left_motor")
right_motor = safe_motor(LargeMotor, OUTPUT_B, "right_motor")
gripper_motor = safe_motor(MediumMotor, OUTPUT_D, "gripper_motor")


# --------------------------------------------------
# SETTINGS
# --------------------------------------------------

BASE_SPEED = 40
TURN_SPEED = 25

GRIPPER_SPEED = 10

ACCEL_STEP = 1
UPDATE_INTERVAL = 0.02


# --------------------------------------------------
# CURRENT / TARGET SPEEDS
# --------------------------------------------------

current_left_speed = 0
current_right_speed = 0

target_left_speed = 0
target_right_speed = 0


# --------------------------------------------------
# DRIVE COMMANDS
# --------------------------------------------------

def forward():
    global target_left_speed
    global target_right_speed

    target_left_speed = -BASE_SPEED
    target_right_speed = -BASE_SPEED


def backward():
    global target_left_speed
    global target_right_speed

    target_left_speed = BASE_SPEED
    target_right_speed = BASE_SPEED


def stop():
    global target_left_speed
    global target_right_speed

    target_left_speed = 0
    target_right_speed = 0


def left():
    global target_left_speed
    global target_right_speed

    target_left_speed = -TURN_SPEED
    target_right_speed = 0


def right():
    global target_left_speed
    global target_right_speed

    target_left_speed = 0
    target_right_speed = -TURN_SPEED


# --------------------------------------------------
# GRIPPER
# --------------------------------------------------

def gripper_open():
    if gripper_motor:
        gripper_motor.on_for_seconds(
            SpeedPercent(GRIPPER_SPEED),
            0.3,
            block=False
        )


def gripper_close():
    if gripper_motor:
        gripper_motor.on_for_seconds(
            SpeedPercent(-GRIPPER_SPEED),
            0.3,
            block=False
        )


# --------------------------------------------------
# SMOOTH MOTOR CONTROL
# --------------------------------------------------

@asyncio.coroutine
def motor_loop():

    global current_left_speed
    global current_right_speed

    while True:

        # LEFT MOTOR RAMP
        if current_left_speed < target_left_speed:
            current_left_speed = min(
                current_left_speed + ACCEL_STEP,
                target_left_speed
            )

        elif current_left_speed > target_left_speed:
            current_left_speed = max(
                current_left_speed - ACCEL_STEP,
                target_left_speed
            )

        # RIGHT MOTOR RAMP
        if current_right_speed < target_right_speed:
            current_right_speed = min(
                current_right_speed + ACCEL_STEP,
                target_right_speed
            )

        elif current_right_speed > target_right_speed:
            current_right_speed = max(
                current_right_speed - ACCEL_STEP,
                target_right_speed
            )

        try:

            if left_motor:
                left_motor.on(
                    SpeedPercent(current_left_speed)
                )

            if right_motor:
                right_motor.on(
                    SpeedPercent(current_right_speed)
                )

        except Exception as e:
            print("Motor error:", e)

        yield from asyncio.sleep(
            UPDATE_INTERVAL
        )


# --------------------------------------------------
# COMMAND PROCESSING
# --------------------------------------------------

def process_command(cmd):

    cmd = cmd.strip()

    print("Received:", cmd)

    if cmd == "forward":
        forward()

    elif cmd == "backward":
        backward()

    elif cmd == "left":
        left()

    elif cmd == "right":
        right()

    elif cmd == "stop":
        stop()

    elif cmd == "gripper_open":
        gripper_open()

    elif cmd == "gripper_close":
        gripper_close()

    else:
        print("Unknown command:", cmd)


# --------------------------------------------------
# WEBSOCKET HANDLER
# --------------------------------------------------

@asyncio.coroutine
def handler(websocket, path):

    print("Client connected")

    try:

        while True:

            message = yield from websocket.recv()

            process_command(message)

    except Exception as e:

        print("Connection closed:", e)

    finally:

        stop()

        print("Client disconnected")


# --------------------------------------------------
# MAIN
# --------------------------------------------------

@asyncio.coroutine
def main():

    asyncio.ensure_future(
        motor_loop()
    )

    server = yield from websockets.serve(
        handler,
        "0.0.0.0",
        8765
    )

    print("")
    print("===================================")
    print("EV3 WebSocket Server Running")
    print("Port: 8765")
    print("===================================")
    print("")

    yield from server.wait_closed()


# --------------------------------------------------
# STARTUP
# --------------------------------------------------

if __name__ == "__main__":

    loop = asyncio.get_event_loop()

    try:

        loop.run_until_complete(
            main()
        )

    except KeyboardInterrupt:

        print("Stopping server...")

    finally:

        stop()

        if left_motor:
            left_motor.stop()

        if right_motor:
            right_motor.stop()

        if gripper_motor:
            gripper_motor.stop()

        loop.close()
