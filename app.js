const state = {
	transport: null,
	activeMotionKeys: new Set(),
};

const keyToCommand = {
	ArrowUp: 'forward',
	ArrowDown: 'backward',
	ArrowLeft: 'left',
	ArrowRight: 'right',
	' ': 'stop',
	v: 'gripper_open',
	V: 'gripper_open',
	c: 'gripper_close',
	C: 'gripper_close',
};

const encoder = new TextEncoder();

if (!window.CommandCenterCamera) {
	throw new Error('Missing camera runtime script.');
}

const cameraController = window.CommandCenterCamera.createCameraController({
	gridEl: document.querySelector('#camera-grid'),
});

cameraController.init().catch((error) => {
	console.error('Unable to initialize camera controller', error);
});

const transports = {
	ws: (cmd) => wsSocket.send(cmd + '\n'),
	ble: (cmd) => bleCharacteristic.writeValue(encoder.encode(cmd + '\n')),
	serial: (cmd) => serialWriter.write(encoder.encode(cmd + '\n')),
};

document.forms.connectionForm['wsUrl'].value = localStorage.getItem('wsUrl') || 'ws://localhost:8080';

function ignoreEvent(e) {
	return (
		e.defaultPrevented ||
		e.repeat ||
		e.metaKey ||
		e.ctrlKey ||
		e.altKey ||
		e.target instanceof HTMLInputElement ||
		e.target instanceof HTMLTextAreaElement ||
		e.target instanceof HTMLSelectElement
	);
}

let wsSocket = null;
let bleCharacteristic = null;
let serialWriter = null;

function handleKeyboardEvent(e) {
	if (!state.transport) return;
	if (ignoreEvent(e)) return;

	if (e.type === 'keydown') {
		const command = keyToCommand[e.key];
		if (!command) return;

		e.preventDefault();

		if (e.key.startsWith('Arrow')) {
			state.activeMotionKeys.add(e.key);
		}

		transports[state.transport](command);
	} else if (e.type === 'keyup' && e.key.startsWith('Arrow')) {
		state.activeMotionKeys.delete(e.key);
		e.preventDefault();

		if (state.activeMotionKeys.size === 0) {
			transports[state.transport]('stop');
		} else {
			const nextKey = Array.from(state.activeMotionKeys)[0];
			const command = keyToCommand[nextKey];
			transports[state.transport](command);
		}
	}
}

document.forms.connectionForm.addEventListener('submit', async function (e) {
	e.preventDefault();
	const formData = new FormData(this);
	const method = this.connectionMethod.value;
	state.transport = method;
	console.log(`Selected connection method: ${method}`);
	console.log('Form data:', Object.fromEntries(formData.entries()));

	if (method === 'ws') {
		const url = this.wsUrl.value.trim().replace(/\/$/, '');
		if (!url) return;
		localStorage.setItem('wsUrl', url);
		wsSocket = new WebSocket(url);
		wsSocket.addEventListener('open', () => {
			console.log('Open event - WS connected');
			state.transport = 'ws';
		});
		wsSocket.addEventListener('close', () => {
			console.log('WS disconnected');
			state.transport = null;
			wsSocket = null;
		});
		wsSocket.addEventListener('error', (err) => console.error('WS error', err));
		wsSocket.addEventListener('message', (event) => {
			try {
				const response = JSON.parse(event.data);
				console.log('Parsed response:', response);
                
			} catch (err) {
				console.log('Non-JSON message:', event.data);
			}
		});
	} else if (method === 'ble') {
		console.log('ble');
	} else if (method === 'serial') {
		console.log('serial');
	}
});

window.addEventListener('keydown', handleKeyboardEvent);
window.addEventListener('keyup', handleKeyboardEvent);
window.addEventListener('beforeunload', () => cameraController.stopAll());