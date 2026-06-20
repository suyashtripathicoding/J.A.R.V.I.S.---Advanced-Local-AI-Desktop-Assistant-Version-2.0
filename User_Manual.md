# J.A.R.V.I.S. User Manual 📖

Welcome to the J.A.R.V.I.S. Core Interface. This manual outlines how to interact with the assistant, configure your workspace, and leverage its specific command architecture.

---

## 🖥️ The Interface

When you launch `jarvis.py`, the Core Interface initializes two primary hubs:

### Left Panel: The Reactor
* **System Status:** Displays real-time operational states (`Standby`, `Listening`, `Thinking`, `Vision Active`) alongside an animated reactor core.
* **Live Optic Feed:** A low-framerate monitor showing exactly what JARVIS can "see" through your webcam or screen capture.

### Right Panel: The Chat Console
* **Interaction History:** A scrolling log of your past inputs and JARVIS's responses.
* **Silent Input:** A bottom text input box allowing you to execute commands silently by typing and pressing `Enter`.

---

## 🗣️ Interaction Modes

You can interact with JARVIS using three simultaneous inputs:
1. **Voice:** Speak directly into your microphone; background processes continuously listen for active triggers.
2. **Text:** Type commands directly into the GUI console text box.
3. **Gestures:** Use localized hand movements in front of your webcam.

---

## ⚡ 1. Fast-Path Commands (Instant Execution)

These commands are intercepted locally before hitting the AI brain, offering zero-latency execution.

| Category | Example Phrases | Expected Action |
| :--- | :--- | :--- |
| **Time** | `"What time is it?"` / `"Current time"` | JARVIS states the current local system time. |
| **Volume** | `"Volume up"` / `"Volume down"` / `"Mute volume"` | Adjusts or mutes the master system volume. |
| **Media** | `"Play music"` / `"Pause music"` / `"Next track"` | Triggers universal OS media key events. |
| **Clipboard** | `"Read clipboard"` | JARVIS reads out loud whatever text is copied. |

---

## 🧠 2. Desktop Automation & Memory

JARVIS translates complex requests into dynamic `PyAutoGUI` instructions. Because it tracks context, you can chain commands together sequentially.

* **Launch Apps:** `"Open Notepad"`, `"Open Google Chrome"`, `"Launch Spotify"`.
* **Web Browsing:** `"Search Google for quantum computing"`.
* **Dictation & Typing:** *(After an app is in focus)* `"Type 'The project is done'."`
* **In-App Navigation:** *(While an app is active)* `"Find my chat with John"` *(Uses `Ctrl+F` to query the UI)*.
* **Information Retrieval:** `"Who is Nikola Tesla?"` *(Fetches condensed Wikipedia summaries)*.

### 🔄 Example of Chained Memory
> **You:** "Open Notepad."  
> *(Wait for window initialization)*  
> **You:** "Type 'Remember to buy milk'."  
> **You:** "Close this window."

---

## 👁️ 3. The Optic Nerve (Vision Commands)

JARVIS takes an internal system screenshot, passes it to your local LLaVA vision-language engine, and interprets the workspace layout.

* **General Analysis:** `"What am I looking at?"` / `"Analyze my screen."`
* **Error Diagnosis:** `"Read this error popup to me."`
* **Vision Clicking:** `"Click the red subscribe button."` / `"Click on the user profile icon."`  
  *(Note: Vision clicking relies on visual coordinate approximations. Best used for clear, distinct UI elements).*

---

## 🖐️ 4. Gesture Control (Spatial Mouse)

Control your cursor via real-time computer vision tracking. This runs on an isolated parallel thread so JARVIS can still process voice commands while you navigate.

### ⚙️ Camera Toggles
* **To Activate:** Say `"Activate gesture control"` or `"Turn on the camera"`.
* **To Deactivate:** Press the `Q` key on your keyboard while the camera window is focused, or say `"Stop gesture"`.

### 🎮 Gesture Mappings
* **Cursor Movement:** Hold up your hand. Move your **Index Finger** to guide the mouse pointer. The model maps the center 60% of your camera stream to your entire screen boundary for ergonomic comfort.
* **Left Click:** **Pinch** your index finger and thumb tightly together.
* **Click-and-Drag / Highlight:** **Hold the Pinch** and shift your hand across the axis to drag windows or sweep across text strings.

---

## 🛑 Troubleshooting

### ❌ `AttributeError: Could not find PyAudio`
Your environment is missing the core audio library bindings.
* **Windows:** Run `pip install pyaudio`.
* **Linux:** Run `sudo apt-get install portaudio19-dev` before attempting `pip install pyaudio`.
* **macOS:** Install the underlying package via Homebrew: `brew install portaudio`.

### ⌨️ JARVIS Types Too Fast / Drops Characters
The automation module uses an execution gap of `interval=0.05` seconds. If your host computer experiences lag, reduce background CPU utilization or increase the interval delay directly inside your source configurations.

### 🐢 Vision Features are Very Slow (30+ Seconds)
The local LLaVA vision engine demands a high memory overhead. Ensure Ollama is configured to leverage a dedicated GPU, or close unnecessary processes to free up system VRAM/RAM.

### 🖱️ Mouse Cursor Jitters in Gesture Mode
MediaPipe requires sharp, crisp contrast to trace finger skeletal joints. Brighten your room's ambient lighting or adjust your webcam exposure to remove spatial noise.
