import streamlit as st
import os
import subprocess
import psutil
import sys
import time
import threading
import queue

# Thread-safe queue for messages
message_queue = queue.Queue()

# Paths
NEXIS_DIR = "C:/Users/Ujesh/Desktop/NEXIS"
GESTURE_PY_PATH = os.path.join(NEXIS_DIR, "gesture.py")
MAIN_PY_PATH = os.path.join(NEXIS_DIR, "main.py")

# Initialize Streamlit session state
def initialize_session_state():
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "gesture_process" not in st.session_state:
        st.session_state.gesture_process = None
    if "main_process" not in st.session_state:
        st.session_state.main_process = None
    if "gesture_running" not in st.session_state:
        st.session_state.gesture_running = False
    if "main_running" not in st.session_state:
        st.session_state.main_running = False
    if "last_command" not in st.session_state:
        st.session_state.last_command = None
    if "command_input" not in st.session_state:
        st.session_state.command_input = ""

initialize_session_state()

def display_message(speaker, message):
    print(f"Displaying: {speaker}: {message}")
    message_queue.put((speaker, message))

def is_process_alive(process):
    if process is None:
        return False
    try:
        p = psutil.Process(process.pid)
        return p.is_running() and p.status() != psutil.STATUS_ZOMBIE
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False

def read_process_output(process, output_type):
    """Read subprocess output and add to message queue."""
    while is_process_alive(process):
        try:
            # Read stdout
            line = process.stdout.readline().decode('utf-8', errors='ignore').strip()
            if line:
                display_message(f"{output_type} Output", line)
            # Read stderr
            err_line = process.stderr.readline().decode('utf-8', errors='ignore').strip()
            if err_line:
                display_message(f"{output_type} Error", err_line)
        except Exception as e:
            display_message("Bot", f"Error reading {output_type.lower()} output: {e}")
            break
        time.sleep(0.1)  # Prevent tight loop
    # Ensure process is cleaned up
    process.stdout.close()
    process.stderr.close()

def start_gesture_bot():
    print(f"Attempting to start gesture.py at {GESTURE_PY_PATH}")
    print(f"Current gesture_process: {st.session_state.gesture_process}, gesture_running: {st.session_state.gesture_running}")
    if st.session_state.gesture_running and is_process_alive(st.session_state.gesture_process):
        print("Gesture process already running.")
        return "Mouse and keyboard control is already running."
    # Clear stale process
    if st.session_state.gesture_process is not None and not is_process_alive(st.session_state.gesture_process):
        st.session_state.gesture_process = None
        st.session_state.gesture_running = False
    try:
        python_executable = sys.executable
        gesture_process = subprocess.Popen(
            [python_executable, GESTURE_PY_PATH],
            cwd=NEXIS_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,  # Use bytes for compatibility
            shell=False,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        )
        # Check if process started
        time.sleep(0.5)  # Brief delay to allow process to initialize
        if is_process_alive(gesture_process):
            st.session_state.gesture_process = gesture_process
            st.session_state.gesture_running = True
            print(f"Started gesture.py with PID: {gesture_process.pid}")
            # Start thread to read output
            threading.Thread(target=read_process_output, args=(gesture_process, "Gesture.py"), daemon=True).start()
            return "Mouse and keyboard control started."
        else:
            print("Gesture process failed to start.")
            return "Error: Failed to start mouse and keyboard control."
    except FileNotFoundError:
        error_msg = f"Error: gesture.py not found at {GESTURE_PY_PATH}"
        print(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"Error starting mouse and keyboard control: {e}"
        print(error_msg)
        return error_msg

def stop_gesture_bot():
    print("Attempting to stop gesture.py...")
    print(f"Current gesture_process: {st.session_state.gesture_process}, gesture_running: {st.session_state.gesture_running}")
    if not st.session_state.gesture_running or not is_process_alive(st.session_state.gesture_process):
        st.session_state.gesture_process = None
        st.session_state.gesture_running = False
        print("No gesture process running.")
        return "Mouse and keyboard control is not running."
    try:
        process = psutil.Process(st.session_state.gesture_process.pid)
        for child in process.children(recursive=True):
            child.terminate()
        process.terminate()
        st.session_state.gesture_process.wait(timeout=5)
        st.session_state.gesture_process = None
        st.session_state.gesture_running = False
        print("Gesture process stopped.")
        return "Mouse and keyboard control stopped."
    except Exception as e:
        error_msg = f"Error stopping mouse and keyboard control: {e}"
        print(error_msg)
        return error_msg

def start_main():
    print(f"Attempting to start main.py at {MAIN_PY_PATH}")
    print(f"Current main_process: {st.session_state.main_process}, main_running: {st.session_state.main_running}")
    if st.session_state.main_running and is_process_alive(st.session_state.main_process):
        print("Main process already running.")
        return "Main program is already running."
    # Clear stale process
    if st.session_state.main_process is not None and not is_process_alive(st.session_state.main_process):
        st.session_state.main_process = None
        st.session_state.main_running = False
    try:
        python_executable = sys.executable
        main_process = subprocess.Popen(
            [python_executable, MAIN_PY_PATH],
            cwd=NEXIS_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,  # Use bytes for compatibility
            shell=False,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        )
        # Check if process started
        time.sleep(0.5)  # Brief delay to allow process to initialize
        if is_process_alive(main_process):
            st.session_state.main_process = main_process
            st.session_state.main_running = True
            print(f"Started main.py with PID: {main_process.pid}")
            # Start thread to read output
            threading.Thread(target=read_process_output, args=(main_process, "Main.py"), daemon=True).start()
            return "Main program started."
        else:
            print("Main process failed to start.")
            return "Error: Failed to start main program."
    except FileNotFoundError:
        error_msg = f"Error: main.py not found at {MAIN_PY_PATH}"
        print(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"Error starting main program: {e}"
        print(error_msg)
        return error_msg

def stop_main():
    print("Attempting to stop main.py...")
    print(f"Current main_process: {st.session_state.main_process}, main_running: {st.session_state.main_running}")
    if not st.session_state.main_running or not is_process_alive(st.session_state.main_process):
        st.session_state.main_process = None
        st.session_state.main_running = False
        print("No main process running.")
        return "Main program is not running."
    try:
        process = psutil.Process(st.session_state.main_process.pid)
        for child in process.children(recursive=True):
            child.terminate()
        process.terminate()
        st.session_state.main_process.wait(timeout=5)
        st.session_state.main_process = None
        st.session_state.main_running = False
        print("Main process stopped.")
        return "Main program stopped."
    except Exception as e:
        error_msg = f"Error stopping main program: {e}"
        print(error_msg)
        return error_msg

def process_command(command):
    if command is None or not command.strip():
        print("Empty or whitespace command, skipping.")
        return
    print(f"Processing command: '{command}'")
    command = command.lower().strip()
    # Avoid reprocessing the same command
    if st.session_state.last_command == command:
        print("Command already processed, skipping.")
        return
    st.session_state.last_command = command
    if any(phrase in command for phrase in ["open mouse and keyboard", "open mouse keyboard"]):
        status = start_gesture_bot()
        display_message("Bot", status)
    elif any(phrase in command for phrase in ["close mouse and keyboard", "close mouse keyboard"]):
        status = stop_gesture_bot()
        display_message("Bot", status)
    elif "open main" in command:
        status = start_main()
        display_message("Bot", status)
    elif "close main" in command:
        status = stop_main()
        display_message("Bot", status)
    elif "hi" in command:
        display_message("Bot", "Hello! How can I assist you today?")
    elif "how are you" in command:
        display_message("Bot", "I'm doing great, thanks for asking! How about you?")
    elif "what's up" in command:
        display_message("Bot", "Not much, just here to help you out! What's on your mind?")
    elif "good morning" in command:
        display_message("Bot", "Good morning to you too! Ready to start the day?")
    elif "exit" in command or "quit" in command:
        status_gesture = stop_gesture_bot()
        status_main = stop_main()
        display_message("Bot", status_gesture)
        display_message("Bot", status_main)
        display_message("Bot", "Goodbye!")
        st.stop()
    else:
        display_message("Bot", "I can open or close the mouse and keyboard or the main program, or chat with you. Try saying 'open mouse and keyboard', 'close mouse and keyboard', 'open main', 'close main', 'hi', 'how are you', 'what's up', or 'good morning'.")

def process_queued_messages():
    # Process all queued messages
    while not message_queue.empty():
        speaker, message = message_queue.get()
        st.session_state.chat_history.append((speaker, message))
    print(f"Chat history updated, length: {len(st.session_state.chat_history)}")

# Streamlit UI
st.title("Gesture Control and Main Program Chatbot")
st.markdown("Interact with the chatbot using **text input**. Type 'open mouse and keyboard' to start mouse and keyboard control, 'close mouse and keyboard' to stop it, 'open main' to start the main program, 'close main' to stop it, 'hi', 'how are you', 'what's up', 'good morning', or 'exit' to quit.")

# Text input form
with st.form(key="command_form", clear_on_submit=True):
    text_input = st.text_input("Enter a command:", value=st.session_state.command_input, key="command_input_widget")
    submit_button = st.form_submit_button("Submit")
    if submit_button and text_input:
        st.session_state.chat_history.append(("User", text_input.lower()))
        process_command(text_input.lower())
        # Clear the input by updating the session state variable
        st.session_state.command_input = ""
        # Delay rerun to ensure state is updated
        time.sleep(0.1)
        st.rerun()

# Process queued messages and display chat history
process_queued_messages()
st.subheader("Chat History")
chat_container = st.container()
with chat_container:
    for speaker, message in st.session_state.chat_history:
        if speaker == "User":
            st.markdown(f"**You**: {message}")
        elif speaker == "Bot":
            st.markdown(f"**Bot**: {message}")
        elif speaker == "Gesture.py Output":
            st.markdown(f"**Gesture.py Output**: {message}")
        elif speaker == "Gesture.py Error":
            st.markdown(f"**Gesture.py Error**: {message}")
        elif speaker == "Main.py Output":
            st.markdown(f"**Main.py Output**: {message}")
        elif speaker == "Main.py Error":
            st.markdown(f"**Main.py Error**: {message}")

# Stop processes if they are not alive
if st.session_state.gesture_process is not None and not is_process_alive(st.session_state.gesture_process):
    stop_gesture_bot()
if st.session_state.main_process is not None and not is_process_alive(st.session_state.main_process):
    stop_main()