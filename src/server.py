from fastapi import FastAPI, WebSocket, HTTPException, status, Response, Cookie, Depends, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional
import uvicorn
import json
import numpy as np
import cv2
import asyncio
from functools import partial
from src.core import fetch_access_logs_for_user
from src.db import (
    verify_user_credentials,
    verify_key
)

from src.core import FaceRecognizer
from src import train

from fastapi.middleware.cors import CORSMiddleware

esp_clients = []  
app = FastAPI()

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

async def get_session_key(session_token: str = Cookie(None)):
    if session_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    if not verify_key(session_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token"
        )
    return session_token

@app.get("/check-auth")
async def check_auth(session_key: str = Depends(get_session_key)):
    return {"status": "authenticated"}

@app.get("/")
def root():
    return {"status": "ok"}

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
    
class LoginRequest(BaseModel):
    email: str
    password_hash: str
    key_esp: str

#test websocket 
@app.websocket("/ws/test")
async def ws_test(websocket: WebSocket, session_token: str = Cookie(None)):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        cfg = json.loads(data)
        print("Received:", cfg)
        await websocket.send_text(f"Echo: {cfg}")

@app.websocket("/ws/train")
async def ws_train(websocket: WebSocket, session_token: str = Cookie(None)):
    if session_token is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    key = session_token
        
    await websocket.accept()
    
    config = await websocket.receive_text()
    cfg = json.loads(config)

    label = cfg.get("label", "user")
    target_frames = int(cfg.get("target_frames", 50))
    delay = int(cfg.get("delay", 6))

    await train.train_from_websocket(websocket, label=label, key=key, target_frames=target_frames, delay=delay)
        
@app.websocket("/ws/logs")
async def ws_show_logs(websocket: WebSocket, session_token: str = Cookie(None)):
    if session_token is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    key = session_token

    await websocket.accept()
    config = await websocket.receive_text()
    cfg = json.loads(config)
    un = cfg.get("user_name", "").strip()
    if un:
        logs = fetch_access_logs_for_user(un, key)
        await websocket.send_json({"logs": logs})
    else:
        logs = fetch_access_logs_for_user("", key)
        await websocket.send_json({"logs": logs})

@app.websocket("/ws/recognize")
async def ws_recognize(websocket: WebSocket, session_token: str = Cookie(None)):
    if session_token is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    key = session_token

    await websocket.accept()
    recognizer = FaceRecognizer(key=key)
    config = await websocket.receive_text()
    cfg = json.loads(config)
    
    max_frames = int(cfg.get("max_frames", 30))
    similarity_threshold = int(cfg.get("similarity_threshold", 70))

    await recognizer.recognize_with_websocket(websocket, max_frames=max_frames, similarity_threshold=similarity_threshold)

@app.post("/login")
async def login(data: LoginRequest, response: Response):

    stored_key = verify_user_credentials(data.email, data.password_hash) 
    
    if stored_key and stored_key == data.key_esp:
        # setup cookie
        response.set_cookie(
            key="session_token",
            value=stored_key,
            httponly=True,
            secure=False,  # true if using HTTPS
            samesite="lax",
            max_age=3600
        )
        return {"status": "success", "message": "login successful"}
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid credentials"
        )
        
@app.websocket("/ws/esp")
async def ws_esp(websocket: WebSocket):
    await websocket.accept()
    esp_clients.append(websocket)
    print("ESP connected")

    try:
        while True:
            await websocket.receive_text()  # giữ kết nối
    except:
        esp_clients.remove(websocket)
        print("ESP disconnected")


@app.websocket("/ws/cam")
async def ws_cam(websocket: WebSocket):
    await websocket.accept()
    print("CAM connected")
        
    try:
        config = await websocket.receive_text()
        cfg = json.loads(config)
    except WebSocketDisconnect:
        print("CAM disconnected before sending config")
        return
    except json.JSONDecodeError:
        print("CAM sent invalid JSON config")
        await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
        return
    except Exception as e:
        print(f"Error receiving CAM config: {e}")
        await websocket.close()
        return
        
    similarity_threshold = int(cfg.get("similarity_threshold", 70))
    key = cfg.get("key", "")
    max_frames = int(cfg.get("max_frames", 10))
    
    if not key or not verify_key(key):
        print(f"CAM provided invalid or empty key: {key}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    try:
        loop = asyncio.get_running_loop()
        # Chạy khởi tạo FaceRecognizer trên ThreadPool để không block event loop
        recognizer = await loop.run_in_executor(None, partial(FaceRecognizer, key=key))
        await recognizer.process_camera_stream(websocket, max_frames=max_frames, similarity_threshold=similarity_threshold)
    except WebSocketDisconnect:
        print("CAM websocket disconnected during processing")
    except Exception as e:
        print(f"CAM processing error: {e}")
        try:
            await websocket.close()
        except Exception:
            pass

# @app.websocket("/ws/cam-stream")
# async def cam_stream(websocket: WebSocket):
#     await websocket.accept()
#     try:
#         while True:
#             if latest_frame is not None:
#                 # Chuyển ảnh từ OpenCV sang JPEG bytes để gửi về Web
#                 _, buffer = cv2.imencode('.jpg', latest_frame)
#                 await websocket.send_bytes(buffer.tobytes())
#             await asyncio.sleep(0.04) # Giới hạn ~25 FPS để tiết kiệm tài nguyên
#     except Exception as e:
#         print(f"Stream client disconnected: {e}")  
#     finally:
#         await websocket.close()

 
if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000)
#python -m uvicorn server:app --host 0.0.0.0 --port 8000