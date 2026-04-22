import InnerHTML from "./mdls/innerHTML.js";
import WSSendFrame from "./mdls/WSSendFrame.js";
const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
var stream = null;
var intervalId = null;
const stopBtn = document.getElementById("stop-preview");
document.addEventListener('DOMContentLoaded', () => {
    checkAuthenticationAndInitialize();
});

// This function will gate access to the page.
async function checkAuthenticationAndInitialize() {
    try {
        // Use the new /check-auth endpoint
        const response = await fetch(`${API_URL}/check-auth`, { credentials: 'include' });

        // If the response is 401 Unauthorized, the cookie is missing or invalid.
        if (response.status === 401) {
            alert("Phiên đăng nhập đã hết hạn hoặc không hợp lệ. Vui lòng đăng nhập lại.");
            // Redirect to the login page. Assuming it's in a 'login' subfolder.
            window.location.href = 'login/login.html';
            return; // Stop further execution
        }

        if (!response.ok) {
            // Handle other server errors
            throw new Error(`Authentication check failed: ${response.statusText}`);
        }

        // If authentication is successful, proceed to initialize the app.
        console.log('User is authenticated. Initializing app...');
        initializeEventListeners();
        initializeCameraPreview();

    } catch (error) {
        console.error('Could not verify authentication:', error);
        alert('Không thể kết nối đến máy chủ để xác thực. Vui lòng thử lại.');
        window.location.href = 'login/login.html';
    }
}

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

    // Access logs    
    document.getElementById('get-logs').addEventListener('click', fetchAccessLogs);
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

// setInterval(async () => {
//     try {
//         const response = await fetch(`${API_URL}/check-auth`, { credentials: 'include' });
//         if (response.status === 401) {
//             alert("login again!");
//             window.location.href = 'login.html';
//         }
//     } catch (err) {
//         console.error("error:", err);
//     }
// }, 300000);

function initializeCameraPreview() {
    const startBtn = document.getElementById("start-preview");
    //const stopBtn = document.getElementById("stop-preview");
    const videoElement = document.getElementById("preview-video");
    const cameraInfo = document.getElementById("camera-info");

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

            intervalId = WSSendFrame(ws, videoElement, 1.0, 1000);

            cameraInfo.innerHTML = "<p>Camera is active</p>";
        } catch (error) {
            console.error("Cannot access camera:", error);
            cameraInfo.innerHTML = "<p>Camera access denied or not available</p>";
        }
        ws.onclose = () => {
            console.log("WebSocket connection closed for training.");
            if (stream) {
                stream.getTracks().forEach(track => track.stop());
                videoElement.srcObject = null;
                cameraInfo.innerHTML = "<p>Camera stopped</p>";
            }
            if (intervalId) {
                clearInterval(intervalId);
            }
        };
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === "error") {
                alert(data.message);
            }
            if (intervalId) {
                clearInterval(intervalId);
            }
        };
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

            intervalId = WSSendFrame(ws, videoElement, 1.0, 500);

            cameraInfo.innerHTML = "<p>Camera is active</p>";
        } catch (error) {
            console.error("Cannot access camera:", error);
            cameraInfo.innerHTML = "<p>Camera access denied or not available</p>";
        }
        ws.onmessage = (event) => {
            console.log("Server:", event.data);
        };
        ws.onclose = () => {
            if (intervalId) {
                clearInterval(intervalId);
            }
        };

    };
}

async function fetchAccessLogs() {
    const rootLogContainer = document.getElementById("root-logs");
    const userName = document.getElementById("user-name").value.trim();

    const ws = new WebSocket(`${protocol}://${WS_URL}/ws/logs`);
    ws.onopen = async () => {
        ws.send(JSON.stringify({ user_name: userName }));
    };
    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            InnerHTML(rootLogContainer, data.logs, userName);
        } catch (error) {
            console.error("Error parsing logs:", error);
        }
    }
}