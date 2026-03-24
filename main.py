import cv2
import time
import os
import base64
import pyautogui
from google import genai
from google.genai import types
from dotenv import load_dotenv
import getpass
from firebase_admin import auth, firestore, initialize_app, credentials
import json
import re
import pyttsx3
import datetime
from datetime import timezone

cap = cv2.VideoCapture(0)
engine = pyttsx3.init()
engine.setProperty('rate', 150)
engine.setProperty('volume',1.0)

load_dotenv()

client = genai.Client(api_key=os.getenv('GENAI_API_KEY'))

cred = credentials.Certificate('creds.json')
app = initialize_app(cred)
db = firestore.client()

global current_session
global session_active
global last_session_count
current_session = None
session_active = False
last_session_count = 0

def login():
    global uid 
    uid = None

    email = input("Enter your email: ").strip()
    password = getpass.getpass("Enter your password: ").strip()

    try:
        user = auth.get_user_by_email(email)
        uid = user.uid
        doc = db.collection('users').document(uid).get()
        if not doc.exists:
            print("User data not found in database.")
            return False
        else:
            data = doc.to_dict()
            stored_password = data.get('password')
            if stored_password != password:
                print("Incorrect password.")
                return False
    except auth.UserNotFoundError:
        print("Error: User not found.")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False
    
    name = db.collection('users').document(uid).get().to_dict().get('name')

    print(f"Login successful! Welcome {name}")
    return True  

def convert_to_64(img_path):
    with open(img_path, 'rb') as f:
        img_data = f.read()
        encoded_img = base64.b64encode(img_data).decode('utf-8')
        
    return encoded_img

def revert_from_64(encoded_img):
    decoded_img = base64.b64decode(encoded_img)
    with open('calibration.jpg', 'wb') as f:
        f.write(decoded_img)

def camera_feed():
    ret, frame = cap.read()
    if os.path.exists('curr.png'):
        then = os.path.getmtime('curr.png')
    else:
        then = 0
    now = int(time.time())

    cv2.imshow('Currently: ', frame)

    return ret, frame, now, then

def main():
    if not login():
        return

    image_1 = client.files.upload(file="calibration.jpg")
    response = None

    ### listen for firebase changes using on_snapshot to see if a session is active
    ### sessions = db.collection('users').document(uid).collection('sessions').get()
    ### if a new session is created, start the camera feed

    # Create a callback function to handle session changes
    # Create a callback function to handle user document changes
    # Create a callback function to handle user document changes
    def on_snapshot(doc_snapshot, changes, read_time):
        global session_active
        global current_session
        global last_session_count  # Access global variable
        
        if not doc_snapshot:
            print("Warning: Empty snapshot received")
            return
            
        # Get the updated document
        user_doc = doc_snapshot[0]
        user_data = user_doc.to_dict()
        
        # Check if the sessions array exists
        if 'sessions' not in user_data:
            print("No sessions array found in user document")
            return
            
        sessions = user_data.get('sessions', [])
        current_session_count = len(sessions)
        
        print(f"Document updated. Current sessions count: {current_session_count}, Last count: {last_session_count}")
        
        # Check if this is the first callback (initialization)
        if last_session_count == 0 and current_session_count > 0:
            # Just update the counter without triggering a session
            print("First callback - initializing session count without triggering new session")
            last_session_count = current_session_count
            return

        # Check if new sessions were added
        if current_session_count > last_session_count and current_session_count > 0:
            # New session detected
            latest_session = sessions[-1]  # Get the last session in the array
            
            print(f"New session detected: {latest_session}")
            
            # Store the session information
            current_session = {
                'id': current_session_count - 1,  # Use array index as ID
                'data': latest_session
            }
            
            # Signal that a session is active
            session_active = True
            
        # Update the last known count
        last_session_count = current_session_count
    
    # Set up the listener on the user document instead of a sessions collection
    try:
        user_ref = db.collection('users').document(uid)
        
        # Get the initial document to check existing sessions
        user_doc = user_ref.get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            sessions = user_data.get('sessions', [])
            last_session_count = len(sessions)
                    
        # Set up the listener on the document
        doc_watch = user_ref.on_snapshot(on_snapshot)
        print("Firebase listener set up successfully")
    except Exception as e:
        print(f"Error setting up document listener: {e}")
        return
    
    print("Waiting for a session to be created...")
    
    while True:
        global session_active
        global current_session
        # Check if a session has been activated

        if session_active and current_session:
            print("Session is active")
            print("Session ID: ", current_session['id'])
            print("Session Data: ", current_session['data'])

            timestamp = current_session['data'].get('timestamp', "2025-04-27T11:42:47.373Z")
            dt = datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
            dt = dt.replace(tzinfo=timezone.utc)
            seconds_since_epoch = int(dt.timestamp())

            print("Seconds since epoch: ", seconds_since_epoch)

            duration = current_session['data'].get('duration', 60)

            print("Duration: ", duration)
            print(int(time.time()))

            task = current_session['data'].get('task', "No task assigned")

            while cap.isOpened() and session_active and int(time.time()) < (seconds_since_epoch + duration):

                ret, frame, now, then = camera_feed()
                if not ret:
                    break

                if (now - then) > 10:
                    if not os.path.exists('curr.png'):
                        cv2.imwrite(f'curr.png', frame)
                        image_2 = client.files.upload(file="curr.png")

                        response = client.models.generate_content(
                            model="gemini-2.0-flash",
                            config=types.GenerateContentConfig(
                            system_instruction="You are a health assistant tasked with correcting indicators of negative well-being. You will analyze images of the user and return responses in json format (1 = True, 0 = False): {\"improper_posture\": 1/0, \"stress\": 1/0, \"all_notes\": \"\"}. If the user has bad posture or is stressed, include those in your notes along with any other observations (nervous tics, how long user has been at screen). Keep notes to 1-3 sentences."),
                            contents=[image_1, image_2, "Calibration.png is what I look like working with proper posture. Curr.png is what I look like now. Provide feedback in json format."],
                        )
                        
                        # Parse and save the initial assessment
                        response_text = response.text
                        print(response_text)
                        try:
                            match = re.search(r'\{.*\}', response_text, re.DOTALL).group(0)
                            match = match.replace("True", "true").replace("False", "false")
                            current_assessment = json.loads(match)
                            with open('previous_assessment.json', 'w') as f:
                                json.dump(current_assessment, f)
                            
                            user_ref = db.collection('users').document(uid)
                            user_doc = user_ref.get()

                            # (db.collection('users').document(uid).get().to_dict().get('timestamp', 2025-04-27T11:42:47.373Z))
                            
                            if user_doc.exists:
                                user_data = user_doc.to_dict()
                                sessions = user_data.get('sessions', [])
                                
                                # Find the current session in the array
                                if current_session['id'] < len(sessions):
                                    # Update the session data
                                    session_data = sessions[current_session['id']]
                                    
                                    # Get current values or use defaults
                                    emotion_alerts = session_data.get('emotionAlerts', 0)
                                    posture_alerts = session_data.get('postureAlerts', 0)
                                    notes = session_data.get('notes', [])
                                    
                                    # Check for improper posture and stress
                                    if current_assessment.get("improper_posture") == 1 or current_assessment.get("improper_posture") is True:
                                        posture_alerts += 1
                                    
                                    if current_assessment.get("stress") == 1 or current_assessment.get("stress") is True:
                                        emotion_alerts += 1
                                    
                                    # Update values in session data
                                    session_data['emotionAlerts'] = emotion_alerts
                                    session_data['postureAlerts'] = posture_alerts
                                    
                                    session_data['notes'] = notes + [
                                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                                        current_assessment["all_notes"]
                                    ]
                                    
                                    # Update the session in the array
                                    sessions[current_session['id']] = session_data
                                    
                                    # Update the entire sessions array in Firestore
                                    user_ref.update({'sessions': sessions})

                        except json.JSONDecodeError:
                            print("Error: Could not parse JSON response from Gemini")
                        
                    else:
                        # Read previous assessment if available
                        try:
                            with open('previous_assessment.json', 'r') as f:
                                previous_assessment = json.load(f)
                            previous_feedback = previous_assessment.get('all_notes', '')
                        except (FileNotFoundError, json.JSONDecodeError):
                            previous_feedback = "No previous assessment available."
                        
                        # Save current frame
                        cv2.imwrite('curr.png', frame)
                        image_current = client.files.upload(file="curr.png")
                        
                        # Create prompt with previous assessment context
                        prompt = f"Calibration.png is what I look like working with proper posture. Prev.png is from the last time you analyzed me. Curr.png is my current posture/state. Previous assessment noted: '{previous_feedback}'. Has my posture/state improved? Provide feedback in json format."
                        
                        # Get new assessment from Gemini
                        response = client.models.generate_content(
                            model="gemini-2.0-flash",
                            config=types.GenerateContentConfig(
                            system_instruction="You are a health assistant tasked with correcting indicators of negative well-being. You will analyze images of the user and return responses in json format: {\"improper_posture\": True/False, \"stress\": True/False, \"all_notes\": \"\"}. If the user has bad posture or is stressed, include those in your notes along with any other observations (nervous tics, how long user has been at screen). Keep notes to 1-3 sentences."),
                            contents=[image_1, image_current, prompt],
                        )

                        img = cv2.imread('curr.png')
                        cv2.imwrite('prev.png', img)
                        image_2 = client.files.upload(file="prev.png")
                        
                        # Parse and save the new assessment
                        response_text = response.text
                        print(response_text)
                        try:
                            match = re.search(r'\{.*\}', response_text, re.DOTALL).group(0)
                            match = match.replace("True", "true").replace("False", "false")
                            current_assessment = json.loads(match)
                            with open('previous_assessment.json', 'w') as f:
                                json.dump(current_assessment, f)
                                # Update the user document to modify the session
                                user_ref = db.collection('users').document(uid)
                                user_doc = user_ref.get()
                                
                                if user_doc.exists:
                                    user_data = user_doc.to_dict()
                                    sessions = user_data.get('sessions', [])
                                    
                                    # Find the current session in the array
                                if current_session['id'] < len(sessions):
                                    # Update the session data
                                    session_data = sessions[current_session['id']]
                                    
                                    # Get current values or use defaults
                                    emotion_alerts = session_data.get('emotionAlerts', 0)
                                    posture_alerts = session_data.get('postureAlerts', 0)
                                    notes = session_data.get('notes', [])
                                    
                                    # Check for improper posture and stress
                                    if current_assessment.get("improper_posture") == 1 or current_assessment.get("improper_posture") is True:
                                        posture_alerts += 1
                                    
                                    if current_assessment.get("stress") == 1 or current_assessment.get("stress") is True:
                                        emotion_alerts += 1
                                    
                                    # Update values in session data
                                    session_data['emotionAlerts'] = emotion_alerts
                                    session_data['postureAlerts'] = posture_alerts
                                    
                                    session_data['notes'] = notes + [
                                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                                        current_assessment["all_notes"]
                                    ]
                                    
                                    # Update the session in the array
                                    sessions[current_session['id']] = session_data
                                    
                                    # Update the entire sessions array in Firestore
                                    user_ref.update({'sessions': sessions})

                            if current_assessment.get('improper_posture'):
                                engine.say("Fix your posture.")
                                engine.runAndWait()
                                engine.stop()
                                pyautogui.alert(text="Your posture is improper. Please correct it.", title="Posture Alert", button="OK")
                            if current_assessment.get('stress'):
                                engine.say("Go outside.")
                                engine.runAndWait()
                                engine.stop()
                                pyautogui.alert(text="You seem stressed. Touch grass.", title="Stress Alert", button="OK")
                        except json.JSONDecodeError:
                            print("Error: Could not parse JSON response from Gemini")

                if (now - then) > 10:
                    im1 = pyautogui.screenshot()
                    im1.save("screenshot.png")
                    image_3 = client.files.upload(file="screenshot.png")
                    response = client.models.generate_content(
                        model="gemini-2.0-flash",
                        config=types.GenerateContentConfig(
                        system_instruction="You are an assistant tasked with checking if a user is staying on task. Check the user's to dos, analyze their screen, and determine whether they are on task. Answer in JSON format: {\"on_task\": True/False, \"all_notes\": \"\"}."),
                        contents=[task, image_3],
                    )

                    response_text = response.text
                    print(response_text)

                    try:
                        match = re.search(r'\{.*\}', response_text, re.DOTALL).group(0)
                        match = match.replace("True", "true").replace("False", "false")
                        current_assessment = json.loads(match)
                        with open('previous_assessment.json', 'w') as f:
                            json.dump(current_assessment, f)
                            # Update the user document to modify the session
                            user_ref = db.collection('users').document(uid)
                            user_doc = user_ref.get()
                            
                            if user_doc.exists:
                                user_data = user_doc.to_dict()
                                sessions = user_data.get('sessions', [])
                                
                                # Find the current session in the array
                                if current_session['id'] < len(sessions):
                                    # Update the session data
                                    session_data = sessions[current_session['id']]
                                    
                                    # Get current values or use defaults
                                    notes = session_data.get('notes', [])
                                    
                                    # Update notes
                                    session_data['notes'] = notes + [
                                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                        current_assessment["all_notes"]
                                    ]
                                    
                                    # Update the session in the array
                                    sessions[current_session['id']] = session_data
                                    
                                    # Update the entire sessions array in Firestore
                                    user_ref.update({'sessions': sessions})

                        if not current_assessment.get('on_task'):
                            pyautogui.hotkey('command', 'w')
                            engine.say("LOCK IN BUD.")
                            engine.runAndWait()
                            engine.stop()
                            pyautogui.alert(text="LOCK IN BUD.", title="LOCK IN", button="OK")
                    except json.JSONDecodeError:
                        print("Error: Could not parse JSON response from Gemini")

                if cv2.waitKey(5) & 0xFF == ord('q'):
                    session_active = False
                    current_session = None
                    break
            
            print("Session ended.")
            session_active = False
            current_session = None
            cap.release()
            cv2.destroyAllWindows()

        else:
            # Small sleep to prevent CPU hogging while waiting for a session
            time.sleep(1)
            
            # Optional: add a timeout or keyboard interrupt check here
            if cv2.waitKey(5) & 0xFF == ord('q'):
                print("Quitting: No active session detected")
                session_active = False
                current_session = None
                break


if __name__== "__main__":
    main()

