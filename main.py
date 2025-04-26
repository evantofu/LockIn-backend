import cv2
import time
import datetime
import os
import requests
import base64
import random

cap = cv2.VideoCapture(0)

def convert_to_64(img_path):
    with open(img_path, 'rb') as f:
        img_data = f.read()
        encoded_img = base64.b64encode(img_data).decode('utf-8')
        
    return encoded_img

def camera_feed():
    ret, frame = cap.read()
    then = os.path.getmtime('curr.png')
    now = int(time.time())

    if (now - then) > 0:
        cv2.imwrite(f'curr.png', frame)
    return frame

while True:
    curr_view = camera_feed()
    cv2.imshow('Current View: ', curr_view)
        
    now = datetime.datetime.now()
    date_time = now.strftime('%Y-%m-%d %H:%M:%S')
     
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()