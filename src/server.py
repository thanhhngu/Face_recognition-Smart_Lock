from fastapi import FastAPI, WebSocket
from pydantic import BaseModel
from typing import Optional
import uvicorn
import threading
import json
import asyncio
import numpy as np
import cv2
from src.core import fetch_access_logs_for_user

from src.core import FaceRecognizer
from src import train

from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()
recognizer = None

esp_clients = set()

origins = [
    "http://localhost",
    "http://127.0.0.1",
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

#test websocket 
@app.websocket("/ws/test")
async def ws_test(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        cfg = json.loads(data)
        print("Received:", cfg)
        await websocket.send_text(f"Echo: {cfg}")

@app.websocket("/ws/train")
async def ws_train(websocket: WebSocket):
    await websocket.accept()
    config = await websocket.receive_text()
    cfg = json.loads(config)

    label = cfg.get("label", "user")
    target_frames = int(cfg.get("target_frames", 50))
    delay = int(cfg.get("delay", 6))

    await train.train_from_websocket(websocket, label=label, target_frames=target_frames, delay=delay)
        
@app.websocket("/ws/logs")
async def ws_show_logs(websocket: WebSocket):
    await websocket.accept()
    config = await websocket.receive_text()
    cfg = json.loads(config)
    un = cfg.get("user_name", "").strip()
    if un:
        logs = fetch_access_logs_for_user(un)
        await websocket.send_json({"logs": logs})
    else:
        logs = fetch_access_logs_for_user("")
        await websocket.send_json({"logs": logs})

@app.websocket("/ws/recognize")
async def ws_recognize(websocket: WebSocket):
    global recognizer
    await websocket.accept()
    if recognizer is None:
        recognizer = FaceRecognizer()
    config = await websocket.receive_text()
    cfg = json.loads(config)
    
    max_frames = int(cfg.get("max_frames", 30))
    similarity_threshold = int(cfg.get("similarity_threshold", 70))

    await recognizer.recognize_with_websocket(websocket, max_frames=max_frames, similarity_threshold=similarity_threshold)

@app.post("/recognize")
def api_recognize(req: RecognizeRequest):
    global recognizer
    if recognizer is None:
        recognizer = FaceRecognizer()
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
    decision = result.get("decision", {})
    return {"decision": decision, "detections": result.get("detections", [])}


@app.websocket("/ws/cam")
async def ws_cam(websocket: WebSocket):
    global recognizer

    await websocket.accept()
    print("CAM connected")

    if recognizer is None:
        recognizer = FaceRecognizer()
        
    config = await websocket.receive_text()
    cfg = json.loads(config)
    similarity_threshold = int(cfg.get("similarity_threshold", 70))
    key = cfg.get("key", "")
    max_frames = int(cfg.get("max_frames", 10))
    
    esp_clients.add(websocket)
    found = False
    processed = 0
    loop = asyncio.get_running_loop()

    try:
        while processed < max_frames:
            # Nhận dữ liệu ảnh từ ESP32
            data = await websocket.receive_bytes()
            
            # Giải mã frame
            nparr = np.frombuffer(data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is None:
                continue
                
            # Dùng recognize_frame để xử lý từng frame ảnh cụ thể
            results = await loop.run_in_executor(None, recognizer.recognize_frame, frame, similarity_threshold)
            processed += 1

            for r in results:
                if r.get("unlock"):
                    name = r.get("name", "Unknown")
                    confidence = float(r.get("similarity", 0))

                    print(f">>> UNLOCK: {name} ({confidence:.1f}%)")

                    for esp in list(esp_clients):
                        try:
                            await esp.send_text(json.dumps({
                                "unlock": True,
                                "name": name,
                                "confidence": round(confidence, 1)
                            }))
                        except Exception:
                            pass

                    found = True
                    return
                    
    except Exception as e:
        print("CAM WS error:", e) 
    finally:
        esp_clients.discard(websocket)

    if not found:
        for esp in list(esp_clients):
            try:
                await esp.send_text(json.dumps({
                    "unlock": False
                }))
            except Exception:
                pass
        try:
            await websocket.close()
        except Exception:
            pass

@app.get("/")
def root():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000)
#python -m uvicorn server:app --host 0.0.0.0 --port 8000