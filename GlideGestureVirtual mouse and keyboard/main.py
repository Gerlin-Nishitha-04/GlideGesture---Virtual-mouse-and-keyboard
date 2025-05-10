import cv2
import time
import win32gui
import win32con
from pynput.keyboard import Controller, Key
from gesture_utils import HandGesture

# Initialize keyboard controller
keyboard = Controller()

def focus_window(title_contains, max_retries=3, retry_delay=1):
    """
    Attempts to find and focus a window with a title containing the specified string.
    Returns True if successful, False otherwise.
    """
    target_hwnd = None

    def enumHandler(hwnd, lParam):
        nonlocal target_hwnd
        if win32gui.IsWindowVisible(hwnd):
            window_title = win32gui.GetWindowText(hwnd).lower()
            if title_contains.lower() in window_title:
                target_hwnd = hwnd

    for attempt in range(max_retries):
        target_hwnd = None
        win32gui.EnumWindows(enumHandler, None)

        if target_hwnd is None:
            print(f"🔍 Attempt {attempt + 1}/{max_retries}: Window with title containing '{title_contains}' not found.")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            continue

        try:
            # Ensure the window is restored (not minimized)
            if win32gui.IsIconic(target_hwnd):
                win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)

            # Attempt to set the window as foreground
            win32gui.SetForegroundWindow(target_hwnd)
            print(f"✅ Focused window: {win32gui.GetWindowText(target_hwnd)}")
            return True

        except Exception as e:
            print(f"⚠️ Attempt {attempt + 1}/{max_retries}: Failed to focus window. Error: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)

    print(f"❌ Failed to focus window with title containing '{title_contains}' after {max_retries} attempts.")
    return False

# Prompt user to open the game
print("🕹️ Please open Hill Climb Racing manually now...")
time.sleep(5)

# Attempt to focus the game window
if not focus_window("Hill Climb"):
    print("🛑 Could not find or focus the game window. Please ensure the game is open and try again.")
    exit(1)

# Initialize webcam and gesture detector
cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
if not cap.isOpened():
    print("❌ Failed to open webcam. Please check your camera connection.")
    exit(1)

gesture_detector = HandGesture()
current_action = None

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            print("❌ Failed to grab frame from webcam")
            break

        # Detect gesture and display output
        gesture, output_frame = gesture_detector.detect_gesture(frame)
        cv2.imshow("Gesture Controller", output_frame)

        # Handle gestures
        if gesture == "open":
            if current_action != "accelerate":
                # Release brake if pressed
                keyboard.release(Key.left)
                # Press gas
                keyboard.press(Key.right)
                print("🚀 Holding Accelerate")
                current_action = "accelerate"

        elif gesture == "fist":
            if current_action != "brake":
                # Release gas if pressed
                keyboard.release(Key.right)
                # Press brake
                keyboard.press(Key.left)
                print("🛑 Holding Brake")
                current_action = "brake"

        else:
            # No hand detected or unknown gesture, release all
            if current_action is not None:
                keyboard.release(Key.right)
                keyboard.release(Key.left)
                print("🕳️ No gesture → Releasing all keys")
                current_action = None

        # Exit on 'q' key press
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("🛑 User terminated the program")
            break

except KeyboardInterrupt:
    print("🛑 Program interrupted by user")

finally:
    # Cleanup
    keyboard.release(Key.right)
    keyboard.release(Key.left)
    cap.release()
    cv2.destroyAllWindows()
    print("🧹 Cleanup complete: Released keys and closed windows")