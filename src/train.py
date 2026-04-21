import cv2
import os
import asyncio
import numpy as np
from deepface import DeepFace
from src.db import get_or_create_user, insert_encodings, user_exists
from fastapi import WebSocket
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=1)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

async def test_train():
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 800)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 600)
    
    delay = 6/30
    i = 0
    batch = []
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("error.")
            break
        cv2.imshow("Webcam", frame)
        if cv2.waitKey(1) != -1:
            break
    
    while i < 50:
        ret, frame = cap.read()
        if not ret:
            break
        
        embedding_objs = DeepFace.represent(img_path=frame, model_name='ArcFace', enforce_detection=True, detector_backend='opencv')
        print(f"Frame {i+1}: Found {len(embedding_objs)} faces")
        for face_obj in embedding_objs:
                batch.append(face_obj['embedding'])
        i += 1
        await asyncio.sleep(delay)
    
    cap.release()
    

def compute_embedding(frame):
    return DeepFace.represent(
        img_path=frame, 
        model_name='ArcFace', 
        enforce_detection=True, 
        detector_backend='retinaface',
        align=True
    )

async def train_from_websocket(websocket: WebSocket, label: str, target_frames: int = 50, delay: int = 6):
    if user_exists(label):
        await websocket.close()
        return
    
    user_id = get_or_create_user(label)
    count = 0
    batch = []
    #get event loop running in main thread
    loop = asyncio.get_event_loop()

    while count < target_frames:
        try: 
            data = await websocket.receive_bytes()
            nparr = np.frombuffer(data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR) # frame is BGR
            if frame is None:
                continue
            # DeepFace handles face 
            embedding_objs = await loop.run_in_executor(executor, compute_embedding, frame)

            for face_obj in embedding_objs:
                batch.append(face_obj['embedding'])
                count += 1
                if count >= target_frames:
                    break
                
        except Exception as e:
            print("Error processing frame:", e)
            break

    if batch:
        insert_encodings(user_id, batch)
        print(f"Inserted {len(batch)} encodings for user {label}")
    else:
        print(f"No encodings created for user {label}")

    await websocket.close()



if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", default=DATA_DIR, help="Directory with labeled subfolders of images")
    args = parser.parse_args()

'''
embedding_obj = {
    "embedding": [0.123, -0.456, 0.789, ...], # Mảng các số thực (vector đặc trưng)
    "facial_area": {
        "x": 100,      # Tọa độ x của góc trên bên trái khung hình khuôn mặt
        "y": 50,       # Tọa độ y của góc trên bên trái khung hình khuôn mặt
        "w": 150,      # Chiều rộng của khung hình khuôn mặt
        "h": 150,      # Chiều cao của khung hình khuôn mặt
        "left_eye": (x, y), # Tọa độ mắt trái
        "right_eye": (x, y) # Tọa độ mắt phải
    },
    "face": [...],     # Hình ảnh khuôn mặt đã được cắt (cropped) và căn chỉnh (aligned)
    "confidence": 0.99 # Độ tin cậy của thuật toán phát hiện khuôn mặt (0.0 đến 1.0)
}

# Lấy kết quả từ hàm represent
embedding_objs = DeepFace.represent(...)

for face_obj in embedding_objs:
    # 1. Lấy vector đặc trưng
    my_embedding = face_obj['embedding']
    
    # 2. Lấy tọa độ khuôn mặt (để vẽ hình vuông lên camera)
    area = face_obj['facial_area']
    x, y, w, h = area['x'], area['y'], area['w'], area['h']
    
    # 3. Kiểm tra độ tin cậy
    conf = face_obj['confidence']
    
    print(f"Khuôn mặt tại vị trí ({x}, {y}) có độ tin cậy: {conf}")

'''
