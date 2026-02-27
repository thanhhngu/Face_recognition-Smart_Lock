var API_URL = 'http://localhost:8000';

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
    //initializeCameraPreview();
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

// function initializeCameraPreview() {
//     const startBtn = document.getElementById("start-preview");
//     const stopBtn = document.getElementById("stop-preview");
//     const videoElement = document.getElementById("preview-video");
//     const cameraInfo = document.getElementById("camera-info");

//     let stream = null;

//     // Start preview
//     startBtn.addEventListener("click", async () => {
//         try {
//             stream = await navigator.mediaDevices.getUserMedia({ video: true });
//             videoElement.srcObject = stream;
//             cameraInfo.innerHTML = "<p>Camera is active</p>";
//         } catch (error) {
//             console.error("Cannot access camera:", error);
//             cameraInfo.innerHTML = "<p>Camera access denied or not available</p>";
//         }
//     });

//     // Stop preview
//     stopBtn.addEventListener("click", () => {
//         if (stream) {
//             stream.getTracks().forEach(track => track.stop());
//             videoElement.srcObject = null;
//             cameraInfo.innerHTML = "<p>Camera stopped</p>";
//         }
//     });
// }

async function startTraining() {
    const label = document.getElementById('train-name').value.trim();
    const targetFrames = parseInt(document.getElementById('target-frames').value);
    const delay = parseFloat(document.getElementById('capture-delay').value);

    if (!label) {
        console.log('Name is required for training.');
        return;
    }

    //state.isTraining = true;

    try {

        const response = await fetch(API_URL + '/train_by_cam_url', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                label: label,
                target_frames: targetFrames,
                delay: delay,
                camera_url: state.selectedCamera,
                data_dir: 'data'
            })
        });

        const data = await response.json();

        if (response.ok) {
            console.log('Training completed successfully:', data);
        } else {
            console.error('Training failed:', data);
        }
    } catch (error) {
        console.error('Error starting training:', error);
       
    }
}


async function startRecognition() {
    const threshold = parseInt(document.getElementById('similarity-threshold').value);
    const maxFrames = parseInt(document.getElementById('max-frames').value);

    if (threshold < 50 || threshold > 100) {
        console.log('Similarity threshold must be between 50 and 100.');
        return;
    }

    if (maxFrames < 5 || maxFrames > 100) {
        console.log('Max frames must be between 5 and 100.');
        return;
    }

    //state.isRecognizing = true;

    try {

        const response = await fetch(API_URL + '/recognize', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                frame_skip: 3,
                similarity_threshold: threshold,
                max_frames: maxFrames,
                camera_url: state.selectedCamera
            })
        });

        const data = await response.json();

        if (response.ok) {
            console.log('Recognition completed successfully:', data);
        } else {
            console.error('Recognition failed:', data);
        }
    } catch (error) {
        console.error('Error starting recognition:', error);
        // showRecognizeStatus(`Error: ${error.message}`, 'error');
    }
}
