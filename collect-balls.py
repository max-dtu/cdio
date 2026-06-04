import cv2
import asyncio
from websocket import create_connection
from ultralytics import YOLO

# =====================================================
# CONFIG
# =====================================================

EV3_WS_URL = "ws://10.255.110.18:8765"

CAMERA_INDEX = 0

# Using pretrained COCO model
MODEL_PATH = "yolov8n.pt"

# COCO class IDs
BALL_CLASS = 32  # sports ball

CONF_THRESH = 0.40

# =====================================================
# WEBSOCKET
# =====================================================

ws = None
ws_connected = False


async def connect_ev3():
    global ws
    global ws_connected

    try:
        print(f"Connecting to {EV3_WS_URL}")

        ws = create_connection(
            EV3_WS_URL,
            timeout=10
        )

        ws_connected = True

        print("Connected to EV3")

        return True

    except Exception as e:
        print("Connection failed:", e)

        ws_connected = False

        return False


async def send(cmd):
    global ws
    global ws_connected

    if not ws_connected:
        return

    try:
        ws.send(cmd)

    except Exception as e:
        print("Send error:", e)

        ws_connected = False


# =====================================================
# MODEL
# =====================================================

print("Loading YOLO model...")
model = YOLO(MODEL_PATH)

print("\nCOCO Classes:\n")
print(model.names)
print("\n====================\n")

# =====================================================
# DETECTION
# =====================================================

def detect(frame):
    """
    Runs YOLO on a frame.

    Returns:
        detections
        results
    """

    results = model(frame, verbose=False)[0]

    detections = []

    for box in results.boxes:

        conf = float(box.conf[0])

        if conf < CONF_THRESH:
            continue

        cls = int(box.cls[0])

        x1, y1, x2, y2 = map(
            int,
            box.xyxy[0]
        )

        detections.append(
            [x1, y1, x2, y2, conf, cls]
        )

    return detections, results


# =====================================================
# BALL EXTRACTION
# =====================================================

def get_balls(detections):
    """
    Extract only sports balls.
    """

    balls = []

    for det in detections:

        x1, y1, x2, y2, conf, cls = det

        if cls == BALL_CLASS:

            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2

            balls.append(
                {
                    "center": (cx, cy),
                    "conf": conf
                }
            )

    return balls


# =====================================================
# DECISION LOGIC
# =====================================================

def decide(frame_width, balls):

    if len(balls) == 0:
        return "stop"

    ball = balls[0]

    bx, by = ball["center"]

    center_x = frame_width // 2

    error = bx - center_x

    # Ball near center
    if abs(error) < 30:
        return "forward"

    # Ball left
    if error < 0:
        return "left"

    # Ball right
    return "right"


# =====================================================
# MAIN LOOP
# =====================================================

async def loop():

    cap = cv2.VideoCapture(CAMERA_INDEX)

    if not cap.isOpened():
        print("Camera failed to open")
        return

    print("Camera opened")

    await connect_ev3()

    last_cmd = None

    while True:

        ret, frame = cap.read()

        if not ret:
            continue

        # -------------------------------------------------
        # Run YOLO
        # -------------------------------------------------

        detections, results = detect(frame)

        # -------------------------------------------------
        # Draw all detections automatically
        # -------------------------------------------------

        annotated = results.plot()

        # -------------------------------------------------
        # Print detections
        # -------------------------------------------------

        if len(detections) > 0:

            print("\nDetected objects:")

            for det in detections:

                x1, y1, x2, y2, conf, cls = det

                print(
                    f"  {model.names[cls]}"
                    f" ({conf:.2f})"
                )

        # -------------------------------------------------
        # Find balls
        # -------------------------------------------------

        balls = get_balls(detections)

        print(
            f"Balls detected: {len(balls)}"
        )

        # -------------------------------------------------
        # Draw ball centers
        # -------------------------------------------------

        for ball in balls:

            cx, cy = ball["center"]

            cv2.circle(
                annotated,
                (cx, cy),
                10,
                (0, 0, 255),
                3
            )

        # -------------------------------------------------
        # Decide robot action
        # -------------------------------------------------

        cmd = decide(
            frame.shape[1],
            balls
        )

        # Only print/send if changed
        if cmd != last_cmd:

            print(
                f"Robot command -> {cmd}"
            )

            await send(cmd)

            last_cmd = cmd

        # -------------------------------------------------
        # Show video
        # -------------------------------------------------

        cv2.imshow(
            "YOLO Debug",
            annotated
        )

        key = cv2.waitKey(1)

        if key == ord("q"):
            break

        await asyncio.sleep(0.05)

    cap.release()

    cv2.destroyAllWindows()


# =====================================================
# MAIN
# =====================================================

async def main():
    await loop()


if __name__ == "__main__":
    asyncio.run(main())