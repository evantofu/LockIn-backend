# LOCK IN Backend

The LOCK IN backend is a local Python companion that analyzes webcam frames and screenshots with Gemini, provides experimental posture and distraction alerts, and writes session feedback to Firestore.

[Devpost project](https://devpost.com/software/lockin-97l4bf) · [Frontend and screenshots](https://github.com/evantofu/LockIn)

## How to use

This is a desktop process, not an HTTP API. It runs on the computer being used for the focus session and watches Firebase for new session records.

### 1. Prepare a local test session

Configure the [LOCK IN frontend](https://github.com/evantofu/LockIn) and this process to use the same Firebase test project. Prepare a local calibration image showing your preferred working posture.

### 2. Start the companion process

Run `python main.py` and follow the terminal's legacy test-account login prompts. The process opens the local camera and listens for a new entry in the user's Firestore `sessions` array.

### 3. Begin a focus session

In the frontend, choose a timer and describe your task. During the session, the Python process periodically uploads webcam images and screenshots to Gemini and records the generated feedback in Firestore.

### 4. Review alerts and feedback

The script can speak alerts and display desktop dialogs. Its off-task branch also sends a `Command+W` shortcut, which can close the active window or tab on macOS. Test this behavior in a disposable workspace. Feedback is an unvalidated model estimate, not a health assessment.

## Prerequisites

- A local Python 3 environment; no supported version range is currently pinned
- A webcam, graphical desktop, and working audio output
- A Gemini API key
- A Firebase test project, a service-account credential file, and a compatible legacy test user
- Camera and screen-recording/automation permissions on the local machine

The script contains macOS-specific keyboard behavior and has no headless-server setup.

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/evantofu/LockIn-backend.git
cd LockIn-backend
python3 -m venv .venv
source .venv/bin/activate
```

On Windows, activate the environment with `.venv\Scripts\activate`; desktop behavior still requires platform-specific changes.

### 2. Install the imported packages

The repository does not currently contain a `requirements.txt`. These package names correspond to the third-party imports in `main.py`; versions are not pinned:

```bash
python -m pip install opencv-python pyautogui google-genai python-dotenv firebase-admin pyttsx3
```

Text-to-speech and desktop automation may also need operating-system components or permissions.

### 3. Configure credentials

Create a `.env` file in the repository root:

```dotenv
GENAI_API_KEY=your-gemini-api-key
```

Place your Firebase service-account credentials in a local file named `creds.json`, which is the filename loaded by `main.py`. Use the same project configured in the frontend. Keep the credential file out of version control.

### 4. Add a calibration image

Create your own image named **`calibration.jpg`** in the repository root. This exact lowercase name is used by the upload call; the tracked `Calibration.jpg` has different capitalization on case-sensitive systems. The web profile photo is not automatically transferred into this file by the current startup code.

### 5. Run the process

```bash
python main.py
```

Use a disposable test account that matches the existing legacy login implementation, then create a new session from the frontend. A Firebase Authentication account alone is insufficient for this login: the current script also checks a password field in the user's Firestore document. Replacing that check with verified Firebase authentication is required before broader use.

## Expected session data

The process watches a `sessions` array on `users/{uid}`. Each session contains fields such as:

```json
{
  "task": "Review lecture notes",
  "timestamp": "2025-04-27T12:00:00.000Z",
  "duration": 1500,
  "emotionAlerts": 0,
  "postureAlerts": 0,
  "notes": []
}
```

`duration` is in seconds. Feedback appends timestamps and generated notes to this record. The frontend dashboard currently reads a different subcollection layout, so displaying these notes there requires a shared-schema fix.

## Project files

| File | Purpose |
|---|---|
| `main.py` | Camera capture, Gemini calls, Firestore listener, speech, and desktop actions |
| `calibration.jpg` | Your local posture reference image |
| `curr.png`, `prev.png` | Working webcam-frame files |
| `screenshot.png` | Desktop capture used for task feedback |
| `previous_assessment.json` | Previous generated feedback |

Images are sent to the configured Gemini service during analysis. Use a controlled test workspace and inspect the capture/automation code before starting it.

## Troubleshooting

- **Credential file not found:** run from the repository root and supply your local `creds.json`.
- **Calibration image not found:** check the exact lowercase filename.
- **No session starts:** confirm the Firebase project, user ID, `sessions` array, and session timestamp/duration.
- **Webcam, screenshots, or speech fail:** check local permissions, hardware access, and OS support.
- **Gemini rejects the request:** check the key and access to the model configured in `main.py`.

## About

This is the original LOCK IN hackathon companion. It has no packaged HTTP service, pinned dependency set, or automated test suite. Authentication, session-schema consistency, and desktop action controls remain development work. See the [frontend README](https://github.com/evantofu/LockIn#readme) for the application walkthrough.
