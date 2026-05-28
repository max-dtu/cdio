#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const WebSocket = require('ws');

const args = process.argv.slice(2);
const host = getArg('--host', '0.0.0.0');
const port = Number(getArg('--port', '8765'));
const speed = Number(getArg('--speed', '50'));

const MOTORS = {
  left: findMotor(['outB', 'motor1']),
  right: findMotor(['outC', 'motor2']),
  gripper: findMotor(['outA', 'motor0']),
};

const commands = {
  forward: () => drive(speed, speed),
  backward: () => drive(-speed, -speed),
  left: () => drive(-speed, speed),
  right: () => drive(speed, -speed),
  stop: () => stop(),
  gripper_open: () => moveGripper(90),
  gripper_close: () => moveGripper(-90),
};

function getArg(flag, fallback) {
  const index = args.indexOf(flag);
  return index >= 0 ? args[index + 1] : fallback;
}

function findMotor(candidates) {
  for (const name of candidates) {
    const base = path.join('/sys/class/tacho-motor', name);
    if (fs.existsSync(base)) return base;
  }
  return null;
}

function drive(leftSpeed, rightSpeed) {
  setMotor(MOTORS.left, leftSpeed);
  setMotor(MOTORS.right, rightSpeed);
}

function stop() {
  setMotorCommand(MOTORS.left, 'stop');
  setMotorCommand(MOTORS.right, 'stop');
}

function moveGripper(position) {
  if (!MOTORS.gripper) return;
  writeFile(path.join(MOTORS.gripper, 'speed_sp'), '200');
  writeFile(path.join(MOTORS.gripper, 'position_sp'), String(position));
  writeFile(path.join(MOTORS.gripper, 'command'), 'run-to-rel-pos');
}

function setMotor(base, dutyCycle) {
  if (!base) {
    console.log('[SIM] drive', dutyCycle);
    return;
  }
  writeFile(path.join(base, 'duty_cycle_sp'), String(dutyCycle));
  setMotorCommand(base, Math.abs(dutyCycle) > 0 ? 'run-direct' : 'stop');
}

function setMotorCommand(base, command) {
  if (!base) return;
  writeFile(path.join(base, 'command'), command);
}

function writeFile(file, value) {
  try {
    fs.writeFileSync(file, value);
  } catch (error) {
    console.log(`Write failed for ${file}: ${error.message}`);
  }
}

function handleCommand(raw) {
  const command = String(raw || '').trim().toLowerCase();
  if (!command) return;
  const action = commands[command];
  if (!action) {
    console.log(`Unknown command: ${command}`);
    return;
  }
  console.log(`Command: ${command}`);
  action();
}

console.log(`Motors: left=${MOTORS.left || 'sim'} right=${MOTORS.right || 'sim'} gripper=${MOTORS.gripper || 'sim'}`);

const server = new WebSocket.Server({ host, port });
server.on('connection', (socket, request) => {
  console.log(`Client connected: ${request.socket.remoteAddress}`);

  socket.on('message', (message) => {
    String(message)
      .split(/\r?\n/)
      .forEach((line) => {
        handleCommand(line);
        if (line.trim()) socket.send(`ACK ${line.trim()}`);
      });
  });

  socket.on('close', () => {
    console.log('Client disconnected');
    stop();
  });

  socket.on('error', (error) => {
    console.log(`Socket error: ${error.message}`);
  });
});

console.log(`Listening on ws://${host}:${port}`);

process.on('SIGINT', () => {
  stop();
  server.close(() => process.exit(0));
});
