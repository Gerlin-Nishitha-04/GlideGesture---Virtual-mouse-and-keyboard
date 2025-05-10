import cv2
import mediapipe as mp
import pyautogui
import numpy as np
import time
import ctypes  # For always-on-top (Windows-specific)

# PyAutoGUI settings
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.01
screen_width, screen_height = pyautogui.size()

# Initialize MediaPipe Hands
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7)
mp_drawing = mp.solutions.drawing_utils

# Initialize webcam
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
frame_width, frame_height = 1280, 720

# State variables
prev_x, prev_y = 0, 0
smoothing_factor = 0.5
last_key_press = 0
debounce_delay = 0.5
is_dragging = False
show_keyboard = False
last_interaction = time.time()
blink_key = None
blink_start_time = 0
blink_duration = 0.2  # Duration of red blink in seconds
pinch_start_time = 0
pinch_hold_threshold = 0.3  # Time to hold pinch for drag (seconds)

# Virtual keyboard layout
keys = [
    ['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P'],
    ['A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L'],
    ['Z', 'X', 'C', 'V', 'B', 'N', 'M'],
    ['Space', 'Backspace']
]
key_width, key_height = 60, 60
key_spacing = 10
keyboard_y = frame_height - 300

def draw_virtual_keyboard(frame, highlight_key=None):
    """Draw virtual keyboard with proper alignment and optional red highlight."""
    for row_idx, row in enumerate(keys):
        row_width = sum(key_width * 3 if key in ['Space', 'Backspace'] else key_width for key in row) + (len(row) - 1) * key_spacing
        start_x = (frame_width - row_width) // 2
        y = keyboard_y + row_idx * (key_height + key_spacing)
        x_offset = start_x
        for key in row:
            width = key_width * 3 if key in ['Space', 'Backspace'] else key_width
            # Draw red rectangle if this key is highlighted
            color = (0, 0, 255) if key == highlight_key else (255, 255, 255)
            cv2.rectangle(frame, (x_offset, y), (x_offset + width, y + key_height), color, 2)
            # Center text
            text_size = cv2.getTextSize(key, cv2.FONT_HERSHEY_SIMPLEX, 1, 2)[0]
            text_x = x_offset + (width - text_size[0]) // 2
            text_y = y + (key_height + text_size[1]) // 2
            cv2.putText(frame, key, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            x_offset += width + key_spacing
    return frame

def get_key_at_position(x, y):
    """Return key at (x, y) position."""
    for row_idx, row in enumerate(keys):
        row_width = sum(key_width * 3 if key in ['Space', 'Backspace'] else key_width for key in row) + (len(row) - 1) * key_spacing
        start_x = (frame_width - row_width) // 2
        y_pos = keyboard_y + row_idx * (key_height + key_spacing)
        x_offset = start_x
        for key in row:
            width = key_width * 3 if key in ['Space', 'Backspace'] else key_width
            if x_offset <= x <= x_offset + width and y_pos <= y <= y_pos + key_height:
                return key
            x_offset += width + key_spacing
    return None

def is_thumbs_up(landmarks):
    """Detect thumbs-up gesture."""
    thumb_tip = landmarks[4]  # Thumb tip
    index_tip = landmarks[8]  # Index finger tip
    middle_tip = landmarks[12]  # Middle finger tip
    ring_tip = landmarks[16]  # Ring finger tip
    pinky_tip = landmarks[20]  # Pinky finger tip
    wrist = landmarks[0]  # Wrist

    # Thumbs-up: thumb tip is higher than other fingertips and fingers are folded
    if (thumb_tip.y < index_tip.y and
        thumb_tip.y < middle_tip.y and
        thumb_tip.y < ring_tip.y and
        thumb_tip.y < pinky_tip.y and
        index_tip.y > landmarks[6].y and  # Index finger folded
        middle_tip.y > landmarks[10].y and  # Middle finger folded
        ring_tip.y > landmarks[14].y and  # Ring finger folded
        pinky_tip.y > landmarks[18].y):  # Pinky finger folded
        return True
    return False

def is_thumbs_down(landmarks):
    """Detect thumbs-down gesture."""
    thumb_tip = landmarks[4]  # Thumb tip
    index_tip = landmarks[8]  # Index finger tip
    middle_tip = landmarks[12]  # Middle finger tip
    ring_tip = landmarks[16]  # Ring finger tip
    pinky_tip = landmarks[20]  # Pinky finger tip
    wrist = landmarks[0]  # Wrist

    # Thumbs-down: thumb tip is lower than other fingertips and fingers are folded
    if (thumb_tip.y > index_tip.y and
        thumb_tip.y > middle_tip.y and
        thumb_tip.y > ring_tip.y and
        thumb_tip.y > pinky_tip.y and
        index_tip.y > landmarks[6].y and  # Index finger folded
        middle_tip.y > landmarks[10].y and  # Middle finger folded
        ring_tip.y > landmarks[14].y and  # Ring finger folded
        pinky_tip.y > landmarks[18].y):  # Pinky finger folded
        return True
    return False

# Set window always on top (Windows)
cv2.namedWindow('Gesture Control')
hwnd = ctypes.windll.user32.FindWindowW(None, 'Gesture Control')
ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(frame_rgb)

    # Draw keyboard if active
    if show_keyboard:
        # Draw with red highlight if a key is blinking
        if blink_key and time.time() - blink_start_time < blink_duration:
            frame = draw_virtual_keyboard(frame, highlight_key=blink_key)
        else:
            frame = draw_virtual_keyboard(frame)
            blink_key = None  # Reset blink after duration

    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

            index_tip = hand_landmarks.landmark[8]
            thumb_tip = hand_landmarks.landmark[4]
            x, y = int(index_tip.x * frame_width), int(index_tip.y * frame_height)

            # Detect thumbs-up to open keyboard
            if is_thumbs_up(hand_landmarks.landmark) and not show_keyboard:
                show_keyboard = True
                last_interaction = time.time()
                time.sleep(0.5)  # Prevent multiple toggles
                continue

            # Detect thumbs-down to close keyboard
            if is_thumbs_down(hand_landmarks.landmark) and show_keyboard:
                show_keyboard = False
                last_interaction = time.time()
                time.sleep(0.5)  # Prevent multiple toggles
                continue

            # Pinch detection
            dist = np.hypot(thumb_tip.x - index_tip.x, thumb_tip.y - index_tip.y)
            is_pinching = dist < 0.05

            if show_keyboard:
                # Keyboard input with pinch
                current_time = time.time()
                if is_pinching and current_time - last_key_press > debounce_delay:
                    key = get_key_at_position(x, y)
                    if key:
                        last_interaction = time.time()
                        blink_key = key  # Set key to blink
                        blink_start_time = time.time()
                        if key == 'Space':
                            pyautogui.press('space')
                        elif key == 'Backspace':
                            pyautogui.press('backspace')
                        else:
                            pyautogui.press(key.lower())
                        last_key_press = current_time
            else:
                # Mouse control
                screen_x = np.interp(x, [0, frame_width], [0, screen_width])
                screen_y = np.interp(y, [0, frame_height], [0, screen_height])
                screen_x = smoothing_factor * screen_x + (1 - smoothing_factor) * prev_x
                screen_y = smoothing_factor * screen_y + (1 - smoothing_factor) * prev_y
                pyautogui.moveTo(screen_x, screen_y)
                prev_x, prev_y = screen_x, screen_y

                current_time = time.time()
                if is_pinching:
                    if pinch_start_time == 0:
                        pinch_start_time = current_time
                    elif current_time - pinch_start_time > pinch_hold_threshold and not is_dragging:
                        # Start drag
                        pyautogui.mouseDown()
                        is_dragging = True
                    elif current_time - pinch_start_time <= pinch_hold_threshold and not is_dragging:
                        # Short pinch for select (click)
                        pyautogui.click()
                        time.sleep(0.2)  # Debounce to avoid multiple clicks
                else:
                    if is_dragging:
                        # End drag (drop)
                        pyautogui.mouseUp()
                        is_dragging = False
                    pinch_start_time = 0  # Reset pinch timer

    # Display status
    status = 'Keyboard' if show_keyboard else 'Mouse'
    cv2.putText(frame, f'Mode: {status}', (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.imshow('Gesture Control', frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()