
## Requirements 
pip install -r requirements.txt

## Run localhost
Make sure you are inside perception-action and then run: 
python3 -m http.server 8000


## Robot connections
- Bluetooth uses Web Bluetooth in Chromium on localhost or HTTPS.
- USB Serial uses the Web Serial API in Chromium-based browsers.
- WiFi uses the WebSocket URL in the UI; the robot should expose a WebSocket endpoint on its WiFi network.


## Other info

ws://10.255.110.18:8765

But Testing if sensors are detected
by Runing :
ls /sys/class/lego-sensor/


We get: sensor0  sensor1
off by 1
sensor0 is color


ws://10.255.110.18:8765

## Models
```python
from ultralytics import YOLO

model = YOLO("yolov8n.pt")

results = model("image.jpg")

