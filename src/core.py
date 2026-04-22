import asyncio
import json
import cv2
import numpy as np
from fastapi import WebSocket
from deepface import DeepFace
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=1)

from collections import defaultdict
from src.db import (
    fetch_all_encodings_with_names,
    get_user_id,
    create_user,
    insert_encodings,
    count_encodings_for_user,
    delete_oldest_encodings,
    log_access_attempt,
    fetch_access_logs
)


def cosine_distance(a, b):
    a = np.array(a)
    b = np.array(b)
    return 1 - (np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))



ARC_FACE_THRESHOLD = 0.68

def fetch_access_logs_for_user(un: str, key: str):
    logs = fetch_access_logs(key=key)
    user_logs = defaultdict(list)
    for user_name, access_time, success in logs:
        user_logs[user_name].append((access_time, success))
    if not un:
        return user_logs
    else:
        return user_logs.get(un, [])


class FaceRecognizer:
    def __init__(self, encodings_file=None, max_count_per_user=50, key=None):
        # encodings_file retained for backward compatibility but ignored when using DB
        self.encodings_file = encodings_file
        self.replace_limit = 2
        self.update_count = 0
        self.pending_updates = []
        self.max_count_per_user = max_count_per_user
        self.key = key
        

        # load encodings from DB
        try:
            encs, names = fetch_all_encodings_with_names(key=self.key)
            self.known_encodings = encs
            self.known_names = names
            print(f"Loaded {len(self.known_encodings)} known encodings from DB.")   
        except Exception as e:
            print("warning: failed to load encodings from DB:", e)
            self.known_encodings = []
            self.known_names = []
   
    def update_encodings(self, name, new_vectors, max_count=50):
        # Insert provided vectors into DB for the given user name.
        try:
            user_id = get_user_id(name, self.key)
            # convert vectors to plain lists
            batch = [list(map(float, v)) for v in new_vectors]
            insert_encodings(user_id, batch)
            # trim older encodings if over limit
            total = count_encodings_for_user(user_id)
            if total > max_count:
                delete_oldest_encodings(user_id, max_count)

            # refresh in-memory lists (simple approach: append and reload from DB)
            encs, names = fetch_all_encodings_with_names(key=self.key)
            self.known_encodings = encs
            self.known_names = names
        except Exception as e:
            print("error updating encodings in DB:", e)

    def recognize_frame(self, image, similarity_threshold=70):
        try:
            embedding_objs = DeepFace.represent(
                img_path=image,
                model_name='ArcFace',
                enforce_detection=False,
                detector_backend='retinaface',
                align=True
            )
        except Exception as e:
            print(f"Error in DeepFace.represent: {e}")
            return []

        results = []
        
        distance_threshold = (100 - similarity_threshold) / 50 * ARC_FACE_THRESHOLD

        for face_obj in embedding_objs:
            face_encoding = face_obj['embedding']

            if not self.known_encodings:
                continue

            distances = [cosine_distance(face_encoding, known_enc) for known_enc in self.known_encodings]

            name = "Unknown"
            similarity = 0.0
            unlock = False
            if distances:
                best_match_index = np.argmin(distances)
                best_distance = distances[best_match_index]

                similarity = max(0, 100 - (best_distance / ARC_FACE_THRESHOLD * 50))

                if best_distance <= distance_threshold:
                    name = self.known_names[best_match_index]
                    unlock = True
                    if len(self.pending_updates) < 3:
                        self.pending_updates.append((name, face_encoding))

            results.append({
                "name": name,
                "similarity": float(similarity),
                "unlock": bool(unlock)
            })

        return results

    async def recognize_with_websocket(self, websocket: WebSocket, max_frames=21, frame_skip=3, similarity_threshold=70):
        frame_count = 0
        processed = 0
        loop = asyncio.get_running_loop()

        while processed < max_frames:
        # Luôn luôn đọc frame để tránh tràn bộ đệm WebSocket
            try:
                data = await websocket.receive_bytes()
            except Exception:
                break # Kết thúc nếu kết nối bị ngắt

            frame_count += 1

            if frame_count % frame_skip == 0:
                nparr = np.frombuffer(data, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                results = await loop.run_in_executor(executor, self.recognize_frame, frame, similarity_threshold)
            
                processed += 1
                print(f"Processed frame {processed}/{max_frames}. Detections: {len(results)}")
                
                await websocket.send_json({"type": "detection", "results": results})
                for r in results:
                    if r["unlock"]:
                        # flush pending updates and send unlock decision
                        if self.pending_updates:
                            grouped = defaultdict(list)
                            for name, vec in self.pending_updates:
                                grouped[name].append(vec)
                            for name, vectors in grouped.items():
                                self.update_encodings(name, vectors)
                        self.pending_updates.clear()
                        log_access_attempt(user_id=get_user_id(r["name"], self.key), success=True)
                        await websocket.send_json({"type": "decision", "decision": r})
                        print(f"Recognition successful for user: {r['name']}")
                        return
        await websocket.close()
        
    async def recognize_arr_frames(self, websocket: WebSocket, frames: list, max_frames=21, similarity_threshold=70):
        frame_count = 0
        processed = 0
        loop = asyncio.get_running_loop()
        
        found = False
        
        for frame in frames:
            frame_count += 1
            if frame_count % 2 == 0:
                results = await loop.run_in_executor(executor, self.recognize_frame, frame, similarity_threshold)
                processed += 1
                
                for r in results:
                    if r.get("unlock"):
                        name = r.get("name", "Unknown")
                        confidence = float(r.get("similarity", 0))

                        print(f">>> UNLOCK: {name} ({confidence:.1f}%)")

                        for esp in esp_clients:
                            await esp.send_text(json.dumps({
                                "unlock": True,
                                "name": name,
                                "confidence": round(confidence, 1)
                            }))
                        found = True
                        return
        
        if not found:
            for esp in esp_clients:
                await esp.send_text(json.dumps({
                    "unlock": False
                }))            
        
        await websocket.close()
        return    