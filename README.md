# J.A.R.V.I.S. - Advanced Local AI Desktop Assistant 🤖

J.A.R.V.I.S. is a fully local, privacy-first desktop automation assistant powered by open-source Large Language Models (Llama 3.1) and Vision-Language Models (LLaVA). Featuring a sleek dual-input GUI, parallel gesture tracking, and real-time screen analysis, it allows you to completely control your computer using your voice, text, or hand gestures.

---

## ✨ Key Features

* **100% Local & Private:** Powered completely by Ollama. No voice data, keystrokes, or screenshots are ever sent to the cloud.
* **Dual-Input Reactor GUI:** A modern, split-screen Tkinter interface. Type commands silently or speak them aloud—JARVIS processes both simultaneously.
* **The "Optic Nerve":** JARVIS can "see" your screen. It analyzes visual context, reads system errors, and can even locate and click buttons based on text descriptions using LLaVA.
* **Parallel Gesture Control:** Drop the mouse and control your cursor with your index finger. Pinch to click, drag, and highlight—all running on a parallel thread so JARVIS can still hear you.
* **Fast-Path Interception:** Zero-latency execution for basic commands (volume, media playback, system time, clipboard actions) by bypassing the AI layer for instant results.
* **Short-Term Memory:** Retains the context of your last few interactions, allowing for chained, conversational commands (e.g., *"Open Notepad"* followed by *"Type hello world"*).

---

## 🛠️ Prerequisites

Before installing, ensure your system meets the following requirements:
* **Python 3.9+** installed on your system.
* **Ollama** installed and running on your local machine. [Download Ollama here](https://ollama.com).
* A working **microphone** and **webcam**.

---

## 🚀 Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/jarvis-local-ai.git
cd jarvis-local-ai
```

### 2. Install Python Dependencies
Install the required libraries using the provided `requirements.txt` file:
```bash
pip install -r requirements.txt
```
> 💡 **Note for Linux Users:** You may also need to install system-level packages for Tkinter and audio support:
> ```bash
> sudo apt-get install python3-tk portaudio19-dev
> ```

### 3. Download the Local AI Models
Pull the specific models JARVIS uses into your local Ollama library. Open your terminal and run:
```bash
ollama pull llama3.1
ollama pull llava
```

### 4. Run J.A.R.V.I.S.
```bash
python jarvis.py
```

---

## 📖 Documentation

Please reference the [MANUAL.md](MANUAL.md) file in this repository for a complete breakdown of:
- Valid voice and text commands
- Hand gesture instructions and mapping
- System optimization tips

---




https://github.com/user-attachments/assets/4e0c4fb9-19a4-49a2-90fb-556a04dcebdb


https://github.com/user-attachments/assets/b6adc21a-6787-4372-af85-a776826c7653








## ⚠️ Disclaimer

This is an experimental AI automation tool. While safety filters (`is_code_safe`) are active to intercept destructive OS commands, the AI ultimately executes dynamic Python code (`pyautogui`) to interact with your system mouse and keyboard. **Do not leave the application unattended during complex automated tasks.**
