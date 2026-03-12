var API_URL = 'http://localhost:8000';
var WS_URL = 'localhost';
const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';

// State management
const state = {
    selectedCamera: "0",
    stream: null,
    isTraining: false,
    isRecognizing: false
};

document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
    checkBackendConnection();
    initializeCameraPreview();
});

function initializeEventListeners() {
    // Tab navigation
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            switchTab(e.target.dataset.tab);
        });
    });

    // Training controls
    document.getElementById('start-training').addEventListener('click', startTraining);

    // Recognition controls
    document.getElementById('start-recognition').addEventListener('click', startRecognition);
}

function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-pane').forEach(pane => {
        pane.classList.remove('active');
    });

    // Deactivate all buttons
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // Show selected tab
    document.getElementById(tabName).classList.add('active');

    // Activate selected button
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
}

async function checkBackendConnection() {
    try {
        const response = await fetch(API_URL + '/');
        if (response.ok) {
            console.log('Backend is available');
        }
    } catch (error) {
        console.error('Backend is not available:', error);
    }
}

function initializeCameraPreview() {
    const startBtn = document.getElementById("start-preview");
    const stopBtn = document.getElementById("stop-preview");
    const videoElement = document.getElementById("preview-video");
    const cameraInfo = document.getElementById("camera-info");

    let stream = null;

    // Start preview
    startBtn.addEventListener("click", async () => {
        try {
            stream = await navigator.mediaDevices.getUserMedia({ video: true });
            videoElement.srcObject = stream;
            cameraInfo.innerHTML = "<p>Camera is active</p>";
        } catch (error) {
            console.error("Cannot access camera:", error);
            cameraInfo.innerHTML = "<p>Camera access denied or not available</p>";
        }
    });

    // Stop preview
    stopBtn.addEventListener("click", () => {
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
            videoElement.srcObject = null;
            cameraInfo.innerHTML = "<p>Camera stopped</p>";
        }
    });
}

async function startTraining() {
    const label = document.getElementById("train-name").value.trim();
    const targetFrames = parseInt(document.getElementById("target-frames").value);
    const delay = parseFloat(document.getElementById("capture-delay").value);
    const videoElement = document.getElementById("preview-video");
    const cameraInfo = document.getElementById("camera-info");
    if (!label) {
        alert("Please enter a name for training.");
        return;
    }
    const ws = new WebSocket(`${protocol}://${WS_URL}/ws/train`);

    ws.onopen = async () => {
        ws.send(JSON.stringify({
            label: label,
            target_frames: targetFrames,
            delay: delay
        }));
        try {
            stream = await navigator.mediaDevices.getUserMedia({ video: true });
            videoElement.srcObject = stream;
            videoElement.play();

            const canvas = document.createElement("canvas");
            const ctx = canvas.getContext("2d");

            intervalId = setInterval(() => {
                if (!videoElement.videoWidth) return;
                canvas.width = videoElement.videoWidth;
                canvas.height = videoElement.videoHeight;
                ctx.drawImage(videoElement, 0, 0);

                canvas.toBlob(blob => {
                    if (blob && ws.readyState === WebSocket.OPEN) {
                        blob.arrayBuffer().then(buffer => {
                            ws.send(buffer);
                            console.log('Sent frame to server for training');
                        });
                    }
                }, "image/jpeg", 0.8);
            }, 200);

            cameraInfo.innerHTML = "<p>Camera is active</p>";
        } catch (error) {
            console.error("Cannot access camera:", error);
            cameraInfo.innerHTML = "<p>Camera access denied or not available</p>";
        }
    };
}

async function startRecognition() {
    const videoElement = document.getElementById("preview-video");
    const cameraInfo = document.getElementById("camera-info");
    const threshold = parseInt(document.getElementById('similarity-threshold').value);
    const maxFrames = parseInt(document.getElementById('max-frames').value);

    const ws = new WebSocket(`${protocol}://${WS_URL}/ws/recognize`);
    ws.onopen = async () => {
        ws.send(JSON.stringify({
            max_frames: maxFrames,
            similarity_threshold: threshold
        }));
        try {
            stream = await navigator.mediaDevices.getUserMedia({ video: true });
            videoElement.srcObject = stream;
            videoElement.play();

            const canvas = document.createElement("canvas");
            const ctx = canvas.getContext("2d");

            intervalId = setInterval(() => {
                if (!videoElement.videoWidth) return;
                canvas.width = videoElement.videoWidth;
                canvas.height = videoElement.videoHeight;
                ctx.drawImage(videoElement, 0, 0);

                canvas.toBlob(blob => {
                    if (blob && ws.readyState === WebSocket.OPEN) {
                        blob.arrayBuffer().then(buffer => {
                            ws.send(buffer);
                            console.log('Sent frame to server for recognition');
                        });
                    }
                }, "image/jpeg", 0.8);
            }, 1000);

            cameraInfo.innerHTML = "<p>Camera is active</p>";
        } catch (error) {
            console.error("Cannot access camera:", error);
            cameraInfo.innerHTML = "<p>Camera access denied or not available</p>";
        }
        ws.onmessage = (event) => {
            console.log("Server:", event.data);
        };

    };
}