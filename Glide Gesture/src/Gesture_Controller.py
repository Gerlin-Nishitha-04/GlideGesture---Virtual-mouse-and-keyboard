import cv2
import mediapipe as mp
import pyautogui
import math
from enum import IntEnum
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from google.protobuf.json_format import MessageToDict
import screen_brightness_control as sbcontrol
import numpy as np
import time

pyautogui.FAILSAFE = False
mp_drawing = mp.solutions.drawing_utils
mp_hands = mp.solutions.hands


# Gesture Encodings
class Gest(IntEnum):
    FIST = 0
    PINKY = 1
    RING = 2
    MID = 4
    LAST3 = 7
    INDEX = 8
    FIRST2 = 12
    LAST4 = 15
    THUMB = 16
    PALM = 31
    V_GEST = 33
    TWO_FINGER_CLOSED = 34
    PINCH_MAJOR = 35
    PINCH_MINOR = 36
    THUMBS_UP = 37


# Multi-handedness Labels
class HLabel(IntEnum):
    MINOR = 0
    MAJOR = 1


# Hand Recognition Class
class HandRecog:
    def __init__(self, hand_label):
        self.finger = 0
        self.ori_gesture = Gest.PALM
        self.prev_gesture = Gest.PALM
        self.frame_count = 0
        self.hand_result = None
        self.hand_label = hand_label

    def update_hand_result(self, hand_result):
        self.hand_result = hand_result

    def get_signed_dist(self, point):
        sign = -1
        if self.hand_result.landmark[point[0]].y < self.hand_result.landmark[point[1]].y:
            sign = 1
        dist = (self.hand_result.landmark[point[0]].x - self.hand_result.landmark[point[1]].x) ** 2
        dist += (self.hand_result.landmark[point[0]].y - self.hand_result.landmark[point[1]].y) ** 2
        dist = math.sqrt(dist)
        return dist * sign

    def get_dist(self, point):
        dist = (self.hand_result.landmark[point[0]].x - self.hand_result.landmark[point[1]].x) ** 2
        dist += (self.hand_result.landmark[point[0]].y - self.hand_result.landmark[point[1]].y) ** 2
        dist = math.sqrt(dist)
        return dist

    def get_dz(self, point):
        return abs(self.hand_result.landmark[point[0]].z - self.hand_result.landmark[point[1]].z)

    def set_finger_state(self):
        if self.hand_result is None:
            return
        points = [[8, 5, 0], [12, 9, 0], [16, 13, 0], [20, 17, 0]]
        self.finger = 0
        self.finger = self.finger | 0  # thumb
        for idx, point in enumerate(points):
            dist = self.get_signed_dist(point[:2])
            dist2 = self.get_signed_dist(point[1:])
            try:
                ratio = round(dist / dist2, 1)
            except:
                ratio = round(dist / 0.01, 1)
            self.finger = self.finger << 1
            if ratio > 0.5:
                self.finger = self.finger | 1

    def get_gesture(self):
        if self.hand_result is None:
            return Gest.PALM
        current_gesture = Gest.PALM
        if self.finger in [Gest.LAST3, Gest.LAST4] and self.get_dist([8, 4]) < 0.05:
            if self.hand_label == HLabel.MINOR:
                current_gesture = Gest.PINCH_MINOR
            else:
                current_gesture = Gest.PINCH_MAJOR
        elif Gest.FIRST2 == self.finger:
            point = [[8, 12], [5, 9]]
            dist1 = self.get_dist(point[0])
            dist2 = self.get_dist(point[1])
            ratio = dist1 / dist2
            if ratio > 1.7:
                current_gesture = Gest.V_GEST
            else:
                if self.get_dz([8, 12]) < 0.1:
                    current_gesture = Gest.TWO_FINGER_CLOSED
                else:
                    current_gesture = Gest.MID
        elif self.finger == Gest.THUMB:
            thumb_tip_y = self.hand_result.landmark[4].y
            thumb_base_y = self.hand_result.landmark[2].y
            index_tip_y = self.hand_result.landmark[8].y
            index_base_y = self.hand_result.landmark[5].y
            if thumb_tip_y < thumb_base_y and index_tip_y > index_base_y:
                current_gesture = Gest.THUMBS_UP
        else:
            current_gesture = self.finger
        if current_gesture == self.prev_gesture:
            self.frame_count += 1
        else:
            self.frame_count = 0
        self.prev_gesture = current_gesture
        if self.frame_count > 4:
            self.ori_gesture = current_gesture
        print(f"Detected gesture: {current_gesture}")  # Debug gesture detection
        return self.ori_gesture


# Controller for Mouse and System Actions
class Controller:
    tx_old = 0
    ty_old = 0
    trial = True
    flag = False
    grabflag = False
    pinchmajorflag = False
    pinchminorflag = False
    pinchstartxcoord = None
    pinchstartycoord = None
    pinchdirectionflag = None
    prevpinchlv = 0
    pinchlv = 0
    framecount = 0
    prev_hand = None
    pinch_threshold = 0.3

    @staticmethod
    def getpinchylv(hand_result):
        dist = round((Controller.pinchstartycoord - hand_result.landmark[8].y) * 10, 1)
        return dist

    @staticmethod
    def getpinchxlv(hand_result):
        dist = round((hand_result.landmark[8].x - Controller.pinchstartxcoord) * 10, 1)
        return dist

    @staticmethod
    def changesystembrightness():
        currentBrightnessLv = sbcontrol.get_brightness(display=0) / 100.0
        currentBrightnessLv += Controller.pinchlv / 50.0
        if currentBrightnessLv > 1.0:
            currentBrightnessLv = 1.0
        elif currentBrightnessLv < 0.0:
            currentBrightnessLv = 0.0
        sbcontrol.fade_brightness(int(100 * currentBrightnessLv), start=sbcontrol.get_brightness(display=0))

    @staticmethod
    def changesystemvolume():
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        currentVolumeLv = volume.GetMasterVolumeLevelScalar()
        currentVolumeLv += Controller.pinchlv / 50.0
        if currentVolumeLv > 1.0:
            currentVolumeLv = 1.0
        elif currentVolumeLv < 0.0:
            currentVolumeLv = 0.0
        volume.SetMasterVolumeLevelScalar(currentVolumeLv, None)

    @staticmethod
    def scrollVertical():
        pyautogui.scroll(120 if Controller.pinchlv > 0.0 else -120)

    @staticmethod
    def scrollHorizontal():
        pyautogui.keyDown('shift')
        pyautogui.keyDown('ctrl')
        pyautogui.scroll(-120 if Controller.pinchlv > 0.0 else 120)
        pyautogui.keyUp('ctrl')
        pyautogui.keyUp('shift')

    @staticmethod
    def get_position(hand_result):
        point = 9
        position = [hand_result.landmark[point].x, hand_result.landmark[point].y]
        sx, sy = pyautogui.size()
        x_old, y_old = pyautogui.position()
        x = int(position[0] * sx)
        y = int(position[1] * sy)
        if Controller.prev_hand is None:
            Controller.prev_hand = x, y
        delta_x = x - Controller.prev_hand[0]
        delta_y = y - Controller.prev_hand[1]
        distsq = delta_x ** 2 + delta_y ** 2
        ratio = 1
        Controller.prev_hand = [x, y]
        if distsq <= 25:
            ratio = 0
        elif distsq <= 900:
            ratio = 0.07 * (distsq ** (1 / 2))
        else:
            ratio = 2.1
        x, y = x_old + delta_x * ratio, y_old + delta_y * ratio
        return (x, y)

    @staticmethod
    def pinch_control_init(hand_result):
        Controller.pinchstartxcoord = hand_result.landmark[8].x
        Controller.pinchstartycoord = hand_result.landmark[8].y
        Controller.pinchlv = 0
        Controller.prevpinchlv = 0
        Controller.framecount = 0

    @staticmethod
    def pinch_control(hand_result, controlHorizontal, controlVertical):
        if Controller.framecount == 5:
            Controller.framecount = 0
            Controller.pinchlv = Controller.prevpinchlv
            if Controller.pinchdirectionflag:
                controlHorizontal()
            elif Controller.pinchdirectionflag == False:
                controlVertical()
        lvx = Controller.getpinchxlv(hand_result)
        lvy = Controller.getpinchylv(hand_result)
        if abs(lvy) > abs(lvx) and abs(lvy) > Controller.pinch_threshold:
            Controller.pinchdirectionflag = False
            if abs(Controller.prevpinchlv - lvy) < Controller.pinch_threshold:
                Controller.framecount += 1
            else:
                Controller.prevpinchlv = lvy
                Controller.framecount = 0
        elif abs(lvx) > Controller.pinch_threshold:
            Controller.pinchdirectionflag = True
            if abs(Controller.prevpinchlv - lvx) < Controller.pinch_threshold:
                Controller.framecount += 1
            else:
                Controller.prevpinchlv = lvx
                Controller.framecount = 0

    @staticmethod
    def handle_controls(gesture, hand_result, keyboard_visible, toggle_keyboard, mouse_enabled):
        x, y = None, None
        if gesture != Gest.PALM and mouse_enabled:
            x, y = Controller.get_position(hand_result)

        if gesture != Gest.FIST and Controller.grabflag:
            Controller.grabflag = False
            pyautogui.mouseUp(button="left")

        if gesture != Gest.PINCH_MAJOR and Controller.pinchmajorflag:
            Controller.pinchmajorflag = False

        if gesture != Gest.PINCH_MINOR and Controller.pinchminorflag:
            Controller.pinchminorflag = False

        if gesture == Gest.V_GEST and mouse_enabled:
            Controller.flag = True
            pyautogui.moveTo(x, y, duration=0.1)
            print("V_GEST: Moving cursor")

        elif gesture == Gest.FIST and mouse_enabled:
            if not Controller.grabflag:
                Controller.grabflag = True
                pyautogui.mouseDown(button="left")
            pyautogui.moveTo(x, y, duration=0.1)
            print("FIST: Dragging")

        elif gesture == Gest.MID and Controller.flag:
            print("MID: Clicking")
            pyautogui.click()
            Controller.flag = False
            time.sleep(0.1)  # Ensure text field focus
            toggle_keyboard()  # Toggle keyboard for text field or search button

        elif gesture == Gest.THUMBS_UP and Controller.flag:
            print("THUMBS_UP: Manual keyboard toggle")
            toggle_keyboard()
            Controller.flag = False

        elif gesture == Gest.INDEX and Controller.flag and mouse_enabled:
            pyautogui.click(button='right')
            Controller.flag = False
            print("INDEX: Right-click")

        elif gesture == Gest.TWO_FINGER_CLOSED and Controller.flag and mouse_enabled:
            pyautogui.doubleClick()
            Controller.flag = False
            print("TWO_FINGER_CLOSED: Double-click")

        elif gesture == Gest.PINCH_MINOR:
            if not Controller.pinchminorflag:
                Controller.pinch_control_init(hand_result)
                Controller.pinchminorflag = True
            Controller.pinch_control(hand_result, Controller.scrollHorizontal, Controller.scrollVertical)
            print("PINCH_MINOR: Scrolling")

        elif gesture == Gest.PINCH_MAJOR:
            if not Controller.pinchmajorflag:
                Controller.pinch_control_init(hand_result)
                Controller.pinchmajorflag = True
            Controller.pinch_control(hand_result, Controller.changesystembrightness, Controller.changesystemvolume)
            print("PINCH_MAJOR: Brightness/Volume")


# Virtual Keyboard Button Class
class Button:
    def __init__(self, pos, text, size=[60, 60]):
        self.pos = pos
        self.size = size
        self.text = text

    def draw(self, img):
        x, y = self.pos
        w, h = self.size
        cv2.rectangle(img, self.pos, (x + w, y + h), (255, 0, 255), cv2.FILLED)
        cv2.putText(img, self.text, (x + 20, y + 40),
                    cv2.FONT_HERSHEY_PLAIN, 2, (255, 255, 255), 2)
        return img

    def check_click(self, x, y):
        bx, by = self.pos
        bw, bh = self.size
        return bx < x < bx + bw and by < y < by + bh


# Main Gesture and Keyboard Controller
class GestureKeyboardController:
    gc_mode = 0
    cap = None
    CAM_HEIGHT = None
    CAM_WIDTH = None
    hr_major = None
    hr_minor = None
    dom_hand = True
    keyboard_visible = False
    mouse_enabled = True  # Mouse enabled by default
    final_text = ""
    last_press_time = 0
    press_cooldown = 0.5

    def __init__(self):
        GestureKeyboardController.gc_mode = 1
        GestureKeyboardController.cap = cv2.VideoCapture(0)
        GestureKeyboardController.cap.set(3, 1280)
        GestureKeyboardController.cap.set(4, 720)
        GestureKeyboardController.CAM_HEIGHT = GestureKeyboardController.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        GestureKeyboardController.CAM_WIDTH = GestureKeyboardController.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        self.button_list = []
        self.setup_keyboard()
        print(f"Initial state: Keyboard visible: {self.keyboard_visible}, Mouse enabled: {self.mouse_enabled}")

    def setup_keyboard(self):
        keys = [
            ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"],
            ["A", "S", "D", "F", "G", "H", "J", "K", "L"],
            ["Z", "X", "C", "V", "B", "N", "M", "<", " ", "Enter"]
        ]
        for i in range(len(keys)):
            for j, key in enumerate(keys[i]):
                x = 70 * j + 50
                y = 80 * i + 100
                # Make "Enter" key wider for visibility
                size = [120, 60] if key == "Enter" else [60, 60]
                self.button_list.append(Button([x, y], key, size))

    def toggle_keyboard(self):
        GestureKeyboardController.keyboard_visible = not GestureKeyboardController.keyboard_visible
        GestureKeyboardController.mouse_enabled = not GestureKeyboardController.keyboard_visible
        if GestureKeyboardController.keyboard_visible:
            GestureKeyboardController.final_text = ""  # Reset text when keyboard is shown
        print(f"Keyboard visible: {GestureKeyboardController.keyboard_visible}, Mouse enabled: {GestureKeyboardController.mouse_enabled}")

    def classify_hands(self, results):
        left, right = None, None
        try:
            handedness_dict = MessageToDict(results.multi_handedness[0])
            if handedness_dict['classification'][0]['label'] == 'Right':
                right = results.multi_hand_landmarks[0]
            else:
                left = results.multi_hand_landmarks[0]
        except:
            pass
        try:
            handedness_dict = MessageToDict(results.multi_handedness[1])
            if handedness_dict['classification'][0]['label'] == 'Right':
                right = results.multi_hand_landmarks[1]
            else:
                left = results.multi_hand_landmarks[1]
        except:
            pass
        if GestureKeyboardController.dom_hand:
            GestureKeyboardController.hr_major = right
            GestureKeyboardController.hr_minor = left
        else:
            GestureKeyboardController.hr_major = left
            GestureKeyboardController.hr_minor = right

    def handle_keyboard(self, img, lm_list):
        if not lm_list:
            return img
        x1, y1 = lm_list[8]  # Index fingertip
        x2, y2 = lm_list[4]  # Thumb fingertip
        distance = math.hypot(x2 - x1, y2 - y1)
        click = distance < 40
        for button in self.button_list:
            img = button.draw(img)
            if button.check_click(x1, y1):
                cv2.rectangle(img, button.pos,
                              (button.pos[0] + button.size[0], button.pos[1] + button.size[1]),
                              (0, 255, 0), cv2.FILLED)
                cv2.putText(img, button.text, (button.pos[0] + 20, button.pos[1] + 40),
                            cv2.FONT_HERSHEY_PLAIN, 2, (255, 255, 255), 2)
                if click and (
                        time.time() - GestureKeyboardController.last_press_time) > GestureKeyboardController.press_cooldown:
                    key = button.text
                    if key == "<":
                        GestureKeyboardController.final_text = GestureKeyboardController.final_text[:-1]
                        pyautogui.press("backspace")
                    elif key == " ":
                        GestureKeyboardController.final_text += " "
                        pyautogui.write(" ")
                    elif key == "Enter":
                        pyautogui.press("enter")
                        GestureKeyboardController.keyboard_visible = False
                        GestureKeyboardController.mouse_enabled = True
                        GestureKeyboardController.final_text = ""
                        print("Enter: Submitted input, keyboard deactivated, mouse enabled")
                    else:
                        GestureKeyboardController.final_text += key
                        pyautogui.write(key.lower())
                    print(f"Typed: {key}")
                    GestureKeyboardController.last_press_time = time.time()
                    cv2.waitKey(100)
        cv2.rectangle(img, (50, 550), (1200, 650), (175, 0, 175), cv2.FILLED)
        cv2.putText(img, GestureKeyboardController.final_text, (60, 630),
                    cv2.FONT_HERSHEY_PLAIN, 4, (255, 255, 255), 4)
        return img

    def start(self):
        handmajor = HandRecog(HLabel.MAJOR)
        handminor = HandRecog(HLabel.MINOR)
        with mp_hands.Hands(max_num_hands=2, min_detection_confidence=0.5, min_tracking_confidence=0.5) as hands:
            while GestureKeyboardController.cap.isOpened() and GestureKeyboardController.gc_mode:
                success, image = GestureKeyboardController.cap.read()
                if not success:
                    print("Ignoring empty camera frame.")
                    continue
                image = cv2.cvtColor(cv2.flip(image, 1), cv2.COLOR_BGR2RGB)
                image.flags.writeable = False
                results = hands.process(image)
                image.flags.writeable = True
                image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
                lm_list = []
                if results.multi_hand_landmarks:
                    self.classify_hands(results)
                    handmajor.update_hand_result(GestureKeyboardController.hr_major)
                    handminor.update_hand_result(GestureKeyboardController.hr_minor)
                    handmajor.set_finger_state()
                    handminor.set_finger_state()
                    gest_name = handminor.get_gesture()
                    if gest_name == Gest.PINCH_MINOR:
                        Controller.handle_controls(gest_name, handminor.hand_result,
                                                   GestureKeyboardController.keyboard_visible, self.toggle_keyboard,
                                                   GestureKeyboardController.mouse_enabled)
                    else:
                        gest_name = handmajor.get_gesture()
                        Controller.handle_controls(gest_name, handmajor.hand_result,
                                                   GestureKeyboardController.keyboard_visible, self.toggle_keyboard,
                                                   GestureKeyboardController.mouse_enabled)
                    for hand_landmarks in results.multi_hand_landmarks:
                        mp_drawing.draw_landmarks(image, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                        for id, lm in enumerate(hand_landmarks.landmark):
                            h, w, _ = image.shape
                            lm_list.append((int(lm.x * w), int(lm.y * h)))
                    if GestureKeyboardController.keyboard_visible and lm_list:
                        image = self.handle_keyboard(image, lm_list)
                else:
                    Controller.prev_hand = None
                cv2.imshow('Gesture Keyboard Controller', image)
                if cv2.waitKey(5) & 0xFF == ord('q'):
                    break
        GestureKeyboardController.cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    gc = GestureKeyboardController()
    gc.start()