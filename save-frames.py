import cv2
import os
from datetime import datetime

# ==========================================
# CONFIG
# ==========================================

CAMERA_INDEX = 0

# Create a new folder for each run
RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
SAVE_DIR = f"dataset_{RUN_ID}"

# ==========================================
# SETUP
# ==========================================

os.makedirs(SAVE_DIR, exist_ok=True)

cap = cv2.VideoCapture(CAMERA_INDEX)

if not cap.isOpened():
    print("Camera failed to open")
    raise SystemExit(1)

print(f"Saving dataset to: {SAVE_DIR}")
print("Press 'q' to quit")

frame_count = 0

# ==========================================
# LOOP
# ==========================================

while True:

    ret, frame = cap.read()
    if not ret:
        continue

    cv2.imshow("Capture", frame)

    frame_count += 1

    # Only save every 20th frame
    if frame_count % 20 == 0:
        filename = os.path.join(
            SAVE_DIR,
            f"frame_{frame_count:06d}.jpg"
        )
        cv2.imwrite(filename, frame)

    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):
        break

# ==========================================
# CLEANUP
# ==========================================

cap.release()
cv2.destroyAllWindows()

print(f"Saved {frame_count} frames in {SAVE_DIR}")