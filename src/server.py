from fastapi import FastAPI, WebSocket, HTTPException, status, Response, Cookie, Depends
from pydantic import BaseModel
from typing import Optional
import uvicorn
import json
import numpy as np
from src.core import fetch_access_logs_for_user
from src.db import (
    verify_user_credentials,
    verify_key
)

from src.core import FaceRecognizer
from src import train

from fastapi.middleware.cors import CORSMiddleware


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
    
if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000)
#python -m uvicorn server:app --host 0.0.0.0 --port 8000