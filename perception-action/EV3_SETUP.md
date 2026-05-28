# EV3 Listener Setup Guide

This guide explains how to deploy and run `ev3_listener.js` on a Lego EV3 running ev3dev.

## Prerequisites

1. **EV3 running ev3dev** - Download from [https://www.ev3dev.org](https://www.ev3dev.org)
2. **SSH access to EV3** or direct keyboard/monitor
3. **Node.js** installed on EV3

## Connection Options

The listener uses WebSocket only. Commands are newline-delimited strings from app.js.

### WebSocket (recommended)
- **Best for**: Remote control over network/WiFi
- **Command**: `node ev3_listener.js --host 0.0.0.0 --port 8765`
- **app.js URL**: `ws://EV3_IP_ADDRESS:8765`

## Installation Steps

### Step 1: Copy to EV3

Via SSH (recommended):
```bash
scp perception-action/ev3_listener.js robot@ev3dev.local:~/cdio/perception-action/
```

Or manually via USB/SFTP.

### Step 2: Install Dependencies

SSH into EV3:
```bash
ssh robot@ev3dev.local
```

Install the WebSocket package if you use npm on the EV3:
```bash
cd ~/cdio
npm install
```

### Step 3: Test Connection

```bash
node ev3_listener.js --host 0.0.0.0 --port 8765
```

You should see:
```text
Listening on ws://0.0.0.0:8765
```

### Step 4: Update app.js

Modify the WebSocket URL in app.js to point to your EV3:
```javascript
// In the connection form handler:
const url = 'ws://YOUR_EV3_IP:8765';  // Replace with EV3's IP
```

Find your EV3's IP:
```bash
# On EV3
hostname -I

# Or on your computer
ssh robot@ev3dev.local "hostname -I"
```

## Motor Layout

By default, the listener looks for EV3 motors on:
- **LEFT motor**: `outB`
- **RIGHT motor**: `outC`
- **GRIPPER motor**: `outA`

If your ports differ, edit the `MOTORS` map in `ev3_listener.js`.

## Supported Commands

The listener responds to these commands from app.js:

| Command | Action |
|---------|--------|
| `forward` | Both motors forward |
| `backward` | Both motors backward |
| `left` | Left motor reverse, right forward (pivot left) |
| `right` | Left motor forward, right reverse (pivot right) |
| `stop` | Brake both motors |
| `gripper_open` | Open gripper (2 rotations) |
| `gripper_close` | Close gripper (2 rotations) |

## Running as a Service

To run automatically on startup:

### Create systemd service file

```bash
sudo nano /etc/systemd/system/ev3_listener.service
```

Add:
```ini
[Unit]
Description=EV3 Command Listener
After=network.target

[Service]
Type=simple
User=robot
WorkingDirectory=/home/robot
ExecStart=/usr/bin/node /home/robot/cdio/perception-action/ev3_listener.js --host 0.0.0.0 --port 8765
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable ev3_listener.service
sudo systemctl start ev3_listener.service
```

Check status:
```bash
sudo systemctl status ev3_listener.service
```

View logs:
```bash
sudo journalctl -u ev3_listener.service -f
```

## Troubleshooting

### Motors not detected
- Verify motors are properly connected to EV3 ports
- Check the `MOTORS` map in `ev3_listener.js`
- Confirm the EV3 sysfs motor paths exist under `/sys/class/tacho-motor`

### Connection refused
- Ensure EV3 is running (`sudo systemctl status ev3_listener.service`)
- Check firewall allows port 8765 (or your custom port)
- Verify EV3 IP address: `ssh robot@ev3dev.local "hostname -I"`

### WebSocket connection timeout from app.js
- Ping EV3: `ping YOUR_EV3_IP`
- Check listener is running: `ps aux | grep ev3_listener`
- Verify network connectivity

## References

- [ev3dev](https://www.ev3dev.org)
- [WebSocket Protocol](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)
