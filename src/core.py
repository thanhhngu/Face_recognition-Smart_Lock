import face_recognition
import cv2
import numpy as np
import requests
import json
from collections import defaultdict
from db import (
    fetch_all_encodings_with_names,
    get_or_create_user,
    insert_encodings,
    count_encodings_for_user,
    delete_oldest_encodings,
)

class FaceRecognizer:
    def __init__(self, encodings_file=None, max_count_per_user=50):
        # encodings_file retained for backward compatibility but ignored when using DB
        self.encodings_file = encodings_file
        self.replace_limit = 2
        self.update_count = 0
        self.pending_updates = []
        self.max_count_per_user = max_count_per_user

        # load encodings from DB
        try:
            encs, names = fetch_all_encodings_with_names()
            self.known_encodings = encs
            self.known_names = names
        except Exception as e:
            print("warning: failed to load encodings from DB:", e)
            self.known_encodings = []
            self.known_names = []
   
    def update_encodings(self, name, new_vectors, max_count=50):
        # Insert provided vectors into DB for the given user name.
        try:
            user_id = get_or_create_user(name)
            # convert vectors to plain lists
            batch = [list(map(float, v)) for v in new_vectors]
            insert_encodings(user_id, batch)
            # trim older encodings if over limit
            total = count_encodings_for_user(user_id)
            if total > max_count:
                delete_oldest_encodings(user_id, max_count)

            # refresh in-memory lists (simple approach: append and reload from DB)
            encs, names = fetch_all_encodings_with_names()
            self.known_encodings = encs
            self.known_names = names
        except Exception as e:
            print("error updating encodings in DB:", e)

    def recognize_frame(self, image, similarity_threshold=70):
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(image_rgb)
        face_encodings = face_recognition.face_encodings(image_rgb, face_locations)

        results = []
        for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
            matches = face_recognition.compare_faces(self.known_encodings, face_encoding)
            face_distances = face_recognition.face_distance(self.known_encodings, face_encoding)

            name = "Unknown"
            similarity = 0.0
            unlock = False
            if len(face_distances) > 0:
                best_match_index = face_distances.argmin()
                similarity = (1 - float(face_distances[best_match_index])) * 100
                if matches[best_match_index]:
                    name = self.known_names[best_match_index]

                if similarity >= similarity_threshold and matches[best_match_index]:
                    unlock = True
                    # collect pending update vectors (kept small)
                    if len(self.pending_updates) < 3:
                        self.pending_updates.append((name, face_encoding))

            results.append({
                "location": [int(top), int(right), int(bottom), int(left)],
                "name": name,
                "similarity": float(similarity),
                "unlock": bool(unlock)
            })

        return results

    def recognize_stream_no_ui(self, camera_url=0, max_frames=30, frame_skip=3, similarity_threshold=70):
        cap = cv2.VideoCapture(camera_url)
        frame_count = 0
        processed = 0
        detections = []
        decision = {"unlock": False, "user": None, "similarity": 0.0}

        while processed < max_frames:
            ret, frame = cap.read()
            if not ret:
                break
            frame_count += 1
            if frame_count % frame_skip != 0:
                continue
            processed += 1

            results = self.recognize_frame(frame, similarity_threshold=similarity_threshold)
            for r in results:
                detections.append(r)
                if r["unlock"] and r["similarity"] > decision["similarity"]:
                    decision = {"unlock": True, "user": r["name"], "similarity": r["similarity"]}
                    # flush pending updates and return early (fast unlock)
                    cap.release()
                    if self.pending_updates:
                        grouped = defaultdict(list)
                        for name, vec in self.pending_updates:
                            grouped[name].append(vec)
                        for name, vectors in grouped.items():
                            self.update_encodings(name, vectors)
                        self.pending_updates.clear()
                    return {"detections": detections, "decision": decision}

        cap.release()
        # flush pending updates if any ***************************
        if self.pending_updates:
            grouped = defaultdict(list)
            for name, vec in self.pending_updates:
                grouped[name].append(vec)
            for name, vectors in grouped.items():
                self.update_encodings(name, vectors)
            self.pending_updates.clear()

        return {"detections": detections, "decision": decision}


# recognizer = FaceRecognizer("encodings.pkl")
# image, results = recognizer.recognize("C:/Users/ADMIN/OneDrive/Desktop/z7415063940931_4992fc5ac76a26366f13513541be3f49.jpg")
# cv2.namedWindow("Face Recognition", cv2.WINDOW_NORMAL)
# cv2.imshow("Face Recognition", image)
# cv2.resizeWindow("Face Recognition", 800, 600)
# cv2.waitKey(0)
# cv2.destroyAllWindows()
# for loc, name in results:
#     print("Location:", loc, "=>", name)


# In[ ]:




