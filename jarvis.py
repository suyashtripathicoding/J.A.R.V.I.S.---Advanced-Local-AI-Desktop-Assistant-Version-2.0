import os
import sys
import re
import time
import queue
import threading
import tempfile
import datetime
import webbrowser
import math

import speech_recognition as sr
import pyttsx3
import pyautogui
import tkinter as tk
from tkinter import font
from PIL import Image, ImageTk, ImageDraw

# ==========================================
# DEPENDENCY CHECKS
# ==========================================
try:
    import pyperclip
    import wikipedia
except ImportError:
    print("\n[ERROR] Missing dependencies.")
    print("Please run: pip install pyperclip wikipedia Pillow")
    sys.exit()

try:
    import ollama
except ImportError:
    print("\n[ERROR] Ollama Python library not found.")
    print("Please run: pip install ollama")
    sys.exit()

# ==========================================
# CONFIGURATION & MEMORY
# ==========================================
OLLAMA_TEXT_MODEL = 'llama3.1'   
OLLAMA_VISION_MODEL = 'llava'    
OLLAMA_KEEP_ALIVE = '30m'        

LISTEN_TIMEOUT = 5      
PHRASE_TIME_LIMIT = 8   
GESTURE_CLICK_THRESHOLD = 0.04  
GUI_POLL_MS = 50
VISION_MAX_DIMENSION = 1024

pyautogui.FAILSAFE = False 
pyautogui.PAUSE = 0.01   

conversation_history = []
MAX_HISTORY = 3 
gesture_running = False  

command_queue = queue.Queue()   
gui_event_queue = queue.Queue() 

# ==========================================
# 1. VISION (OPTIONAL HAND TRACKING)
# ==========================================
VISION_AVAILABLE = True
try:
    import cv2
    import mediapipe as mp
    mp_hands = mp.solutions.hands
    hands_tracker = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7, min_tracking_confidence=0.7)
except ImportError as e:
    VISION_AVAILABLE = False
    cv2 = None
    print(f"\n[JARVIS SYSTEM] Vision dependencies unavailable ({e}).")

# ==========================================
# 2. VOICE ENGINE (TTS & STT)
# ==========================================
_tts_lock = threading.Lock()
_tts_engine = None

def _get_tts_engine():
    global _tts_engine
    if _tts_engine is None:
        _tts_engine = pyttsx3.init()
        voices = _tts_engine.getProperty('voices')
        if voices:
            _tts_engine.setProperty('voice', voices[0].id)
        _tts_engine.setProperty('rate', 180) 
    return _tts_engine

def speak(text):
    print(f"\nJARVIS: {text}")
    gui_event_queue.put(('msg', 'JARVIS', text)) 
    
    with _tts_lock:
        try:
            engine = _get_tts_engine()
            engine.say(text)
            engine.runAndWait()
        except Exception:
            global _tts_engine
            _tts_engine = None
            try:
                engine = _get_tts_engine()
                engine.say(text)
                engine.runAndWait()
            except Exception as e:
                print(f"[JARVIS SYSTEM] Speech output failed: {e}")

_recognizer = sr.Recognizer()
_recognizer.dynamic_energy_threshold = True
_recognizer.energy_threshold = 300 

def voice_listener_loop():
    while True:
        gui_event_queue.put(('state', 'listening'))
        try:
            with sr.Microphone() as source:
                _recognizer.adjust_for_ambient_noise(source, duration=0.5)
                _recognizer.pause_threshold = 0.8 
                audio = _recognizer.listen(source, timeout=LISTEN_TIMEOUT, phrase_time_limit=PHRASE_TIME_LIMIT)
            
            gui_event_queue.put(('state', 'thinking'))
            query = _recognizer.recognize_google(audio, language='en-in')
            if query:
                command_queue.put(("VOICE", query.lower()))
        except sr.WaitTimeoutError:
            pass
        except Exception:
            pass

# ==========================================
# 3. SAFETY FILTER & VISION TOOLS
# ==========================================
DANGEROUS_PATTERNS = [
    r'\bos\.system\b', r'\bos\.popen\b', r'\bsubprocess\b', r'\bshutil\b',
    r'\b__import__\b', r'\beval\s*\(', r'\bexec\s*\(',
    r'(?<!\.)\bopen\s*\(', 
    r'\bos\.remove\b', r'\bos\.rmdir\b', r'\bos\.unlink\b', r'\brmtree\b',
    r'\bimport\s+os\b', r'\bimport\s+sys\b',
]
_DANGEROUS_RE = re.compile('|'.join(f'(?:{p})' for p in DANGEROUS_PATTERNS))

def is_code_safe(code: str) -> bool:
    return _DANGEROUS_RE.search(code) is None

def clean_code_block(text: str) -> str:
    text = text.replace('```python', '').replace('```', '').strip()
    return text

def _capture_screen_with_cursor():
    screenshot = pyautogui.screenshot()
    try:
        cursor_x, cursor_y = pyautogui.position()
        draw = ImageDraw.Draw(screenshot)
        r = 10
        # Draw a subtle red crosshair to give LLaVA spatial reference
        draw.line((cursor_x - r, cursor_y, cursor_x + r, cursor_y), fill="red", width=2)
        draw.line((cursor_x, cursor_y - r, cursor_x, cursor_y + r), fill="red", width=2)
    except Exception:
        pass
    return screenshot

def _capture_for_vision():
    screenshot = _capture_screen_with_cursor()
    scale = 1.0
    if max(screenshot.size) > VISION_MAX_DIMENSION:
        scale = VISION_MAX_DIMENSION / max(screenshot.size)
        new_size = (int(screenshot.width * scale), int(screenshot.height * scale))
        screenshot = screenshot.resize(new_size, Image.Resampling.LANCZOS)

    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
        tmp_path = tmp.name
    screenshot.save(tmp_path)
    return tmp_path, scale, screenshot.width, screenshot.height

def analyze_screen(user_prompt="Describe what is on the screen briefly."):
    gui_event_queue.put(('state', 'vision'))
    speak("Scanning visual interface...")
    tmp_path = None
    try:
        tmp_path, _, _, _ = _capture_for_vision()
        response = ollama.chat(
            model=OLLAMA_VISION_MODEL,
            messages=[{'role': 'user', 'content': user_prompt, 'images': [tmp_path]}],
            keep_alive=OLLAMA_KEEP_ALIVE
        )
        return response['message']['content']
    except Exception:
        return "I am unable to process visual data at this moment, sir."
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

def vision_click(description, click=True):
    """Highly optimized visual targeting prompt."""
    gui_event_queue.put(('state', 'vision'))
    screen_width, screen_height = pyautogui.size()
    tmp_path = None
    try:
        tmp_path, scale, img_w, img_h = _capture_for_vision()
        prompt = (
            f"Find the UI element described as: '{description}'. "
            "Output ONLY its bounding box coordinates as [ymin, xmin, ymax, xmax] on a 0-1000 scale. "
            "Do not include any other text. If missing, output EXACTLY: [NOT_FOUND]"
        )
        response = ollama.chat(
            model=OLLAMA_VISION_MODEL,
            messages=[{'role': 'user', 'content': prompt, 'images': [tmp_path]}],
            keep_alive=OLLAMA_KEEP_ALIVE,
            options={'num_predict': 20, 'temperature': 0.0}, # Max restriction for speed
        )
        text = response['message']['content'].strip()
    except Exception:
        speak("I can't reach the vision model for that, sir.")
        return
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

    if 'NOT_FOUND' in text.upper():
        speak(f"I couldn't find {description} on screen, sir.")
        return

    match = re.search(r'\[\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\]', text)
    if not match:
        speak("I wasn't able to make sense of the coordinates, sir.")
        return

    ymin, xmin, ymax, xmax = map(int, match.groups())
    
    center_x_norm = (xmin + xmax) / 2.0
    center_y_norm = (ymin + ymax) / 2.0
    x = int((center_x_norm / 1000.0) * img_w)
    y = int((center_y_norm / 1000.0) * img_h)

    if scale != 1.0:
        x, y = int(x / scale), int(y / scale)
        
    x = max(0, min(screen_width - 1, x))
    y = max(0, min(screen_height - 1, y))

    speak(f"Clicking {description}.")
    pyautogui.moveTo(x, y, duration=0.2) 
    if click:
        pyautogui.click()

def open_app(app_name):
    speak(f"Opening {app_name}")
    pyautogui.press('win')
    time.sleep(0.5)
    pyautogui.write(app_name, interval=0.02)
    time.sleep(0.5)
    pyautogui.press('enter')
    time.sleep(2.5) # Wait for app to render before LLM tries to click anything

SAFE_EXEC_NAMESPACE = {
    'pyautogui': pyautogui, 'time': time, 'webbrowser': webbrowser,
    'datetime': datetime, 'pyperclip': pyperclip, 'wikipedia': wikipedia,
    'speak': speak, 'analyze_screen': analyze_screen, 'vision_click': vision_click,
    'open_app': open_app
}

# ==========================================
# 4. HIGH-SPEED ANALYTICAL FAST-PATH
# ==========================================
def fast_path_interceptor(query):
    """Uses Regex and exact matching to bypass the LLM for simple tasks instantly."""
    
    # 1. Typing & Writing
    match = re.match(r"^(?:type|write)\s+(.+)$", query)
    if match:
        pyautogui.write(match.group(1), interval=0.01)
        return True
    
    # 2. Key presses
    match = re.match(r"^press\s+(.+)$", query)
    if match:
        try:
            pyautogui.press(match.group(1).strip())
            return True
        except Exception:
            pass 
            
    # 3. Smart Application Launcher
    match = re.match(r"^open\s+([a-zA-Z0-9\s]+)$", query)
    if match:
        app_name = match.group(1).strip()
        # If the user is giving a multi-step command (e.g., "open whatsapp and call"), route to LLM
        if any(word in f" {app_name} " for word in [" and ", " to ", " then ", " call ", " message "]):
            return False 
        open_app(app_name)
        return True
        
    if query in ["close window", "close this", "exit window"]:
        pyautogui.hotkey('alt', 'f4')
        return True

    # 4. Utilities
    if 'time is it' in query or 'current time' in query:
        speak(f"It is currently {datetime.datetime.now().strftime('%I:%M %p')}, sir.")
        return True
    
    media_commands = {
        'volume up': lambda: pyautogui.press('volumeup', presses=5),
        'increase volume': lambda: pyautogui.press('volumeup', presses=5),
        'volume down': lambda: pyautogui.press('volumedown', presses=5),
        'decrease volume': lambda: pyautogui.press('volumedown', presses=5),
        'mute volume': lambda: pyautogui.press('volumemute'),
        'mute audio': lambda: pyautogui.press('volumemute'),
        'play music': lambda: pyautogui.press('playpause'),
        'pause music': lambda: pyautogui.press('playpause'),
        'next track': lambda: pyautogui.press('nexttrack'),
        'next song': lambda: pyautogui.press('nexttrack'),
    }
    
    for cmd, action in media_commands.items():
        if cmd in query:
            action()
            return True

    if 'read clipboard' in query:
        text = pyperclip.paste()
        speak(f"The clipboard says: {text}" if text else "Your clipboard is currently empty, sir.")
        return True
        
    return False

# ==========================================
# 5. BRAIN EXECUTION ENGINE (HIGH LOGIC)
# ==========================================
def execute_action(query):
    global conversation_history

    if 'exit' in query or 'shut down' in query or 'power down' in query:
        speak("Powering down local systems. Goodbye, sir.")
        os._exit(0)

    # Fast-Path bypasses everything else in 0.01 seconds
    if fast_path_interceptor(query):
        conversation_history.extend([{'role':'user','content':query}, {'role':'assistant','content':'Executed via fast-path.'}])
        return

    gui_event_queue.put(('state', 'thinking'))
    screen_width, screen_height = pyautogui.size()

    # Analytical Blueprint Prompt
    system_prompt = f"""
    You are JARVIS. Screen dimensions: {screen_width}x{screen_height}.
    
    STRICT CONSTRAINTS: 
    1. Return ONLY raw, executable Python code. 
    2. Do NOT wrap the code in markdown blocks. Just text.
    3. Do NOT explain yourself.
    
    ALLOWED TOOLS: pyautogui, time, webbrowser, pyperclip, speak(), analyze_screen(), vision_click(), open_app().

    TOUGH COMMAND RECIPES (FOLLOW EXACTLY):
    - "open [app] and video call [person]":
      open_app('app name')
      pyautogui.hotkey('ctrl', 'f')
      time.sleep(1.0)
      pyautogui.write('person name', interval=0.02)
      time.sleep(0.5)
      pyautogui.press('enter')
      time.sleep(1.0)
      vision_click('video call camera icon')

    - "open [app] and message [person] saying [text]":
      open_app('app name')
      pyautogui.hotkey('ctrl', 'f')
      time.sleep(1.0)
      pyautogui.write('person name', interval=0.02)
      time.sleep(0.5)
      pyautogui.press('enter')
      time.sleep(1.0)
      pyautogui.write('text', interval=0.02)
      pyautogui.press('enter')
      
    - If asked to read/analyze the screen, use:
      result = analyze_screen("specific question")
      speak(result)
    """

    messages = [{'role': 'system', 'content': system_prompt}]
    messages.extend(conversation_history)
    messages.append({'role': 'user', 'content': f"USER COMMAND: {query}"})

    try:
        response = ollama.chat(
            model=OLLAMA_TEXT_MODEL, 
            messages=messages, 
            keep_alive=OLLAMA_KEEP_ALIVE,
            options={'temperature': 0.0, 'num_predict': 200} # Strict logic, bounded tokens
        )
        dynamic_code = clean_code_block(response['message']['content'])
        print(f"\n[EXECUTING GENERATED CODE]:\n{dynamic_code}\n")

        if dynamic_code and is_code_safe(dynamic_code):
            exec(dynamic_code, dict(SAFE_EXEC_NAMESPACE))
            conversation_history.extend([{'role': 'user', 'content': query}, {'role': 'assistant', 'content': dynamic_code}])
            if len(conversation_history) > MAX_HISTORY * 2:
                del conversation_history[:-MAX_HISTORY * 2]
        else:
            speak("I blocked that action for safety, sir.")
    except Exception as e:
        speak("I encountered an error executing that, sir.")
        print(f"Error: {e}")

def brain_loop():
    global gesture_running
    time.sleep(1)
    speak("Local cognitive engine online. Dual-input mode activated.")
    while True:
        if gesture_running:
            gui_event_queue.put(('state', 'vision'))
        else:
            gui_event_queue.put(('state', 'idle'))
        
        source, query = command_queue.get() 
        
        gui_event_queue.put(('msg', f'YOU ({source})', query))
        gui_event_queue.put(('state', 'thinking'))
        
        if 'stop' in query and ('gesture' in query or 'camera' in query):
            if gesture_running:
                gesture_running = False
            else:
                speak("Gesture control is not currently active, sir.")
        elif 'gesture' in query or 'camera' in query:
            threading.Thread(target=start_gesture_mouse, daemon=True).start()
        else:
            execute_action(query)
            time.sleep(0.1)

# ==========================================
# 6. VISION CORE (GESTURE TRACKING)
# ==========================================
def start_gesture_mouse():
    global gesture_running
    if gesture_running:
        speak("Gesture tracking is already running, sir.")
        return

    if not VISION_AVAILABLE:
        speak("Vision core is unavailable, sir. Packages are missing.")
        return

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        speak("Camera access denied, sir.")
        return

    gesture_running = True
    screen_width, screen_height = pyautogui.size()
    speak("Vision core online. Press Q or tell me to 'stop gesture' to exit.")
    gui_event_queue.put(('state', 'vision'))

    prev_x, prev_y = 0, 0
    smoothing_factor = 0.22  
    is_clicking = False
    old_pause = pyautogui.PAUSE
    pyautogui.PAUSE = 0 

    try:
        while cap.isOpened() and gesture_running:
            success, image = cap.read()
            if not success: break

            image = cv2.flip(image, 1)
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = hands_tracker.process(rgb_image)

            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    index_tip = hand_landmarks.landmark[8]
                    thumb_tip = hand_landmarks.landmark[4]

                    x_min, x_max, y_min, y_max = 0.2, 0.8, 0.2, 0.8
                    norm_x = max(0.0, min(1.0, (index_tip.x - x_min) / (x_max - x_min)))
                    norm_y = max(0.0, min(1.0, (index_tip.y - y_min) / (y_max - y_min)))

                    target_x, target_y = int(norm_x * screen_width), int(norm_y * screen_height)

                    if prev_x == 0 and prev_y == 0:
                        curr_x, curr_y = target_x, target_y
                    else:
                        curr_x = int(smoothing_factor * target_x + (1 - smoothing_factor) * prev_x)
                        curr_y = int(smoothing_factor * target_y + (1 - smoothing_factor) * prev_y)

                    prev_x, prev_y = curr_x, curr_y
                    pyautogui.moveTo(curr_x, curr_y, duration=0)

                    if math.hypot(index_tip.x - thumb_tip.x, index_tip.y - thumb_tip.y) < GESTURE_CLICK_THRESHOLD:
                        if not is_clicking: pyautogui.mouseDown(); is_clicking = True
                    else:
                        if is_clicking: pyautogui.mouseUp(); is_clicking = False

            cv2.imshow('JARVIS Vision Overlay', image)
            if cv2.waitKey(1) & 0xFF == ord('q'): 
                gesture_running = False
                break
    finally:
        gesture_running = False
        if is_clicking: pyautogui.mouseUp()
        pyautogui.PAUSE = old_pause
        cap.release()
        cv2.destroyAllWindows()
        speak("Vision core offline.")
        gui_event_queue.put(('state', 'idle'))

# ==========================================
# 7. GUI (ADVANCED SPLIT LAYOUT)
# ==========================================
class JarvisGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("J.A.R.V.I.S. Core Interface")
        self.root.geometry("850x600")
        self.root.configure(bg='#0f172a') 
        
        self.left_frame = tk.Frame(root, bg='#0f172a', width=300)
        self.left_frame.pack(side="left", fill="y", padx=20, pady=20)
        
        self.right_frame = tk.Frame(root, bg='#1e293b', relief="flat", bd=0)
        self.right_frame.pack(side="right", fill="both", expand=True, padx=20, pady=20)

        self.header = tk.Label(self.left_frame, text="J.A.R.V.I.S.", fg="#38bdf8", bg="#0f172a", font=("Helvetica", 24, "bold"))
        self.header.pack(pady=10)

        self.canvas = tk.Canvas(self.left_frame, width=250, height=250, bg='#0f172a', highlightthickness=0)
        self.canvas.pack()
        self.ring_outer = self.canvas.create_oval(10, 10, 240, 240, outline='#1e293b', width=2)
        self.ring_middle = self.canvas.create_oval(30, 30, 220, 220, outline='#38bdf8', width=5, dash=(10, 5))
        self.inner_core = self.canvas.create_oval(75, 75, 175, 175, fill='#38bdf8', outline="#ffffff")

        self.status_label = tk.Label(self.left_frame, text="STATUS: INITIALIZING", fg="#38bdf8", bg="#0f172a", font=("Courier", 11, "bold"))
        self.status_label.pack(pady=10)

        tk.Label(self.left_frame, text="LIVE OPTIC FEED", fg="#94a3b8", bg="#0f172a", font=("Courier", 9)).pack()
        self.live_feed_display = tk.Label(self.left_frame, bg="#000000", highlightbackground="#1e293b", highlightthickness=2)
        self.live_feed_display.pack(pady=5)
        self.photo_buffer = None

        self.chat_log = tk.Text(self.right_frame, bg="#0f172a", fg="#f8fafc", font=("Consolas", 11), wrap="word", state="disabled", bd=0, padx=15, pady=15)
        self.chat_log.pack(fill="both", expand=True)
        
        self.chat_log.tag_config('JARVIS', foreground='#38bdf8', font=("Consolas", 11, "bold"))
        self.chat_log.tag_config('YOU (VOICE)', foreground='#22c55e', font=("Consolas", 11, "bold"))
        self.chat_log.tag_config('YOU (TEXT)', foreground='#f59e0b', font=("Consolas", 11, "bold"))

        self.input_frame = tk.Frame(self.right_frame, bg="#1e293b")
        self.input_frame.pack(fill="x", pady=10, padx=10)
        
        self.entry_box = tk.Entry(self.input_frame, bg="#334155", fg="#ffffff", font=("Consolas", 12), insertbackground="white", relief="flat")
        self.entry_box.pack(side="left", fill="x", expand=True, ipady=8, padx=5)
        self.entry_box.bind('<Return>', self.send_text_command)

        self.send_btn = tk.Button(self.input_frame, text="SEND", bg="#38bdf8", fg="#0f172a", font=("Helvetica", 10, "bold"), relief="flat", command=self.send_text_command)
        self.send_btn.pack(side="right", ipady=4, ipadx=10)

        self.animation_state = "idle"
        self.pulse_size = 0
        self.pulse_dir = 1
        
        self.update_live_feed()
        self.animate_reactor()
        self._poll_event_queue()

    def send_text_command(self, event=None):
        text = self.entry_box.get().strip()
        if text:
            command_queue.put(("TEXT", text))
            self.entry_box.delete(0, tk.END)

    def write_chat(self, sender, message):
        self.chat_log.configure(state="normal")
        self.chat_log.insert(tk.END, f"{sender}: ", sender)
        self.chat_log.insert(tk.END, f"{message}\n\n")
        self.chat_log.configure(state="disabled")
        self.chat_log.see(tk.END) 

    def _poll_event_queue(self):
        try:
            while True:
                event = gui_event_queue.get_nowait()
                if event[0] == 'state':
                    self._apply_state(event[1])
                elif event[0] == 'msg':
                    self.write_chat(event[1], event[2])
        except queue.Empty:
            pass
        self.root.after(GUI_POLL_MS, self._poll_event_queue)

    def _apply_state(self, state):
        self.animation_state = state
        if state == "listening":
            self.status_label.config(text="STATUS: LISTENING MIC...", fg="#22c55e")
            self.canvas.itemconfig(self.inner_core, fill="#22c55e")
            self.canvas.itemconfig(self.ring_middle, outline="#22c55e")
        elif state == "thinking":
            self.status_label.config(text="STATUS: COGNITIVE PROCESSING", fg="#f59e0b")
            self.canvas.itemconfig(self.inner_core, fill="#f59e0b")
            self.canvas.itemconfig(self.ring_middle, outline="#f59e0b")
        elif state == "vision":
            self.status_label.config(text="STATUS: OPTIC NERVE ACTIVE", fg="#ef4444")
            self.canvas.itemconfig(self.inner_core, fill="#ef4444")
            self.canvas.itemconfig(self.ring_middle, outline="#ef4444")
            self.live_feed_display.config(highlightbackground="#ef4444")
        else:
            self.status_label.config(text="STATUS: STANDBY", fg="#38bdf8")
            self.canvas.itemconfig(self.inner_core, fill="#38bdf8")
            self.canvas.itemconfig(self.ring_middle, outline="#38bdf8")
            self.live_feed_display.config(highlightbackground="#1e293b")

    def animate_reactor(self):
        if self.animation_state == "idle":
            scale = 0.3 if self.pulse_dir == 1 else -0.3
            self.canvas.move(self.inner_core, scale, scale)
            self.pulse_size += scale
            if abs(self.pulse_size) > 5:
                self.pulse_dir *= -1
        elif self.animation_state == "thinking":
            scale = 1.0 if self.pulse_dir == 1 else -1.0
            self.canvas.move(self.inner_core, scale, scale)
            self.pulse_size += scale
            if abs(self.pulse_size) > 8:
                self.pulse_dir *= -1
        self.root.after(40, self.animate_reactor)

    def update_live_feed(self):
        try:
            screenshot = _capture_screen_with_cursor()
            screenshot.thumbnail((250, 150), Image.Resampling.LANCZOS)
            self.photo_buffer = ImageTk.PhotoImage(screenshot)
            self.live_feed_display.config(image=self.photo_buffer)
        except Exception:
            pass
        self.root.after(500, self.update_live_feed)

if __name__ == "__main__":
    root = tk.Tk()
    app = JarvisGUI(root)
    threading.Thread(target=voice_listener_loop, daemon=True).start()
    threading.Thread(target=brain_loop, daemon=True).start()
    root.mainloop()
