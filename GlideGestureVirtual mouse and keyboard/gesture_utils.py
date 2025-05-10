import mediapipe as mp
import cv2

import cv2
import mediapipe as mp

class HandGesture:
    def __init__(self):
        self.hands = mp.solutions.hands.Hands(static_image_mode=False,
                                              max_num_hands=1,
                                              min_detection_confidence=0.7,
                                              min_tracking_confidence=0.7)
        self.mp_draw = mp.solutions.drawing_utils

    def detect_gesture(self, frame):
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(frame_rgb)
        gesture = None

        if results.multi_hand_landmarks:
            hand_landmarks = results.multi_hand_landmarks[0]

            # Tip and MCP of index and middle finger
            tips_ids = [8, 12]
            mcp_ids = [5, 9]

            fingers = []
            for tip_id, mcp_id in zip(tips_ids, mcp_ids):
                tip_y = hand_landmarks.landmark[tip_id].y
                mcp_y = hand_landmarks.landmark[mcp_id].y
                fingers.append(tip_y < mcp_y)

            if all(fingers):
                gesture = "open"
            else:
                gesture = "fist"

            self.mp_draw.draw_landmarks(frame, hand_landmarks, mp.solutions.hands.HAND_CONNECTIONS)

        return gesture, frame

