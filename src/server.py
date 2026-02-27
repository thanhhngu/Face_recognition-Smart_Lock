from fastapi import FastAPI, WebSocket
from pydantic import BaseModel
from typing import Optional
import uvicorn
import threading
import json

from src.core import FaceRecognizer
from src import train

from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()
recognizer = None

origins = [
    "http://localhost:5500",
    "http://127.0.0.1:5500"

]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,   # hoặc ["*"] để cho phép tất cả
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TrainRequest(BaseModel):
    data_dir: Optional[str] = "data"
    encodings_file: Optional[str] = None
    label: Optional[str] = "user"
    camera_url: str 
    target_frames: Optional[int] = 50
    delay: Optional[int] = 6



class RecognizeRequest(BaseModel):
    camera_url: str
    max_frames: Optional[int] = 30
    frame_skip: Optional[int] = 3
    similarity_threshold: Optional[int] = 70


@app.post("/train")
def api_train(req: TrainRequest):
    # run training in background thread to avoid blocking
    def _job():
        # use DB-backed trainer
        train.create_encodings_db(req.data_dir)

    thread = threading.Thread(target=_job, daemon=True)
    thread.start()
    return {"status": "started", "data_dir": req.data_dir, "encodings_file": req.encodings_file}

@app.post("/train_by_cam_url")
def api_train_by_cam(req: TrainRequest):
    def _job():
        cam = req.camera_url
        if isinstance(cam, str) and cam.isdigit():
            cam = int(cam)
        train.create_encodings_db_by_cam_url(
            data_dir=req.data_dir,
            camera_url=cam,
            label=req.label,
            target_frames=req.target_frames,
            delay=req.delay
        )

    thread = threading.Thread(target=_job, daemon=True)
    thread.start()
    return {
        "status": "started",
        "data_dir": req.data_dir,
        "label": req.label,
        "target_frames": req.target_frames
    }

@app.websocket("/ws/train")
async def ws_train(websocket: WebSocket):
    await websocket.accept()
    config = await websocket.receive_text()
    cfg = json.loads(config)

    label = cfg.get("label", "user")
    target_frames = int(cfg.get("target_frames", 50))
    delay = int(cfg.get("delay", 6))

    await train.train_from_websocket(websocket, label=label, target_frames=target_frames, delay=delay)



@app.post("/recognize")
def api_recognize(req: RecognizeRequest):
    global recognizer
    if recognizer is None:
        recognizer = FaceRecognizer()

    # convert camera_url to int if it's a digit(webcam)
    cam = req.camera_url
    try:
        if isinstance(cam, str) and cam.isdigit():
            cam = int(cam)
    except Exception:
        pass

    result = recognizer.recognize_stream_no_ui(
        camera_url=cam,
        max_frames=req.max_frames,
        frame_skip=req.frame_skip,
        similarity_threshold=req.similarity_threshold,
    )
    # decision: return minimal JSON so ESP32 can decide to unlock
    decision = result.get("decision", {})
    return {"decision": decision, "detections": result.get("detections", [])}


@app.get("/")
def root():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000)
#python -m uvicorn server:app --host 0.0.0.0 --port 8000