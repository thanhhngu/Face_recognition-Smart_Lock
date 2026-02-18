import cv2
import os
import time
import face_recognition
import numpy as np
from db import user_exists, get_or_create_user, insert_encodings

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

def create_encodings_db_by_cam_url(data_dir=None, camera_url = 0, label = "user", target_frames = 50, delay = 6):
    if data_dir is None:
        data_dir = DATA_DIR
    save_dir = os.path.join(data_dir, label)
    os.makedirs(save_dir, exist_ok=True)
    cap = cv2.VideoCapture(camera_url)
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 800)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 600)

    #check webcam
    while True:
        ret, frame = cap.read()
        if not ret:
            print("error.")
            break
        cv2.imshow("Webcam", frame)
        if cv2.waitKey(1) != -1:
            break

    delay = delay/target_frames
    i = 0
    while i < target_frames:
        ret, frame = cap.read()
        if not ret:
            break
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_frame)

        cv2.imshow("Webcam", frame)

    #save file
        filename = os.path.join(save_dir, f"{label}_{i:03d}.jpg")
        for (top, right, bottom, left) in face_locations:
            face_image = frame[top:bottom, left:right]
            filename = os.path.join(save_dir, f"{label}_{i:03d}.jpg")
            cv2.imwrite(filename, face_image)
        print(f"save: {filename}")
        i += 1

        time.sleep(delay)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

def create_encodings_db(data_dir=None):
    inserted = 0

    if data_dir is None:
        data_dir = DATA_DIR

    if not os.path.isdir(data_dir):
        print("data_dir not found:", data_dir)
        return 0

    for name in os.listdir(data_dir):
        person_dir = os.path.join(data_dir, name)
        if not os.path.isdir(person_dir):
            continue
        #check if user already exists in DB to avoid duplicates
        if user_exists(name):
            print(f"Skip {name}, already in database.")
            continue

        user_id = get_or_create_user(name)
        batch = []
        for filename in os.listdir(person_dir):
            img_path = os.path.join(person_dir, filename)
            try:
                image = face_recognition.load_image_file(img_path)
                encodings = face_recognition.face_encodings(image)
                if not encodings:
                    continue
                # insert all found encodings for this image
                for enc in encodings:
                    batch.append(enc.tolist())
            except Exception as e:
                print("skip", img_path, e)

        if batch:
            insert_encodings(user_id, batch)
            inserted += len(batch)

    print(f"Inserted {inserted} encodings into database.")
    return inserted


if __name__ == "__main__":
    # simple CLI usage
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", default=DATA_DIR, help="Directory with labeled subfolders of images")
    args = parser.parse_args()
    create_encodings_db(args.data_dir)
