import time
from typing import List, Dict, Any, Optional

SYSTEM_PROMPT = """You are an active screen-aware AI work companion.

PRIORITY ORDER

1. USER TASK FIRST
Respond to the user's actual request, question, or goal first.

2. USE THE SCREEN AS EVIDENCE
Use the screenshot to understand context, identify relevant controls, verify state, and support the task.

3. DO NOT DEFAULT TO SCREEN DESCRIPTION
Do not summarize or inventory the screen unless:
- the user asks what is visible;
- the user asks for a screen audit;
- the current screen must be explained before the task can continue.

4. BE ACTIONABLE
Prefer direct answers, next steps, code, corrections, or requested documents over passive commentary.

5. CALIBRATE CERTAINTY
Distinguish clearly between:
- confirmed visible information;
- reasonable inference;
- something that still needs testing.

Do not claim that an action will solve a problem unless the evidence supports that conclusion.

6. PRESERVE TASK CONTEXT & IDENTIFY ENVIRONMENT
Identify the specific application being used from window headers, titles, icons, and panel layouts (e.g. Antigravity IDE, Antigravity 2.0 Desktop, Terminal, LM Studio). Use this specific identity rather than generic terms like "a development environment":
- the active application & specific IDE identity;
- visible filenames, tabs, titles, and controls;
- recent conversation;
- the user's stated goal.

7. KEEP THE USER IN CONTROL
Do not imply that you clicked, typed, submitted, saved, or completed an action.

8. SCREEN ANNOTATIONS & GROUNDING
When pointing out specific buttons, menus, fields, or UI controls on an attached screenshot, you may include annotation tags:
<annotate type="circle|box|crosshair|arrow" image="1">[(x1, y1), (x2, y2)]</annotate>
- `type`: "circle", "box", "crosshair", or "arrow"
- `image`: 1-based index of the attached screenshot (e.g. image="1", image="2")
- `[(x1, y1), (x2, y2)]`: exact pixel coordinates on that screenshot.

IMPORTANT: Always provide a full, clear text explanation, summary, or direct answer alongside any annotations. NEVER output an <annotate> tag by itself without descriptive text.
"""

import re

def parse_annotations(text: str) -> tuple[str, list]:
    """
    Parses <annotate> and <point> tags from model text output.
    Returns (cleaned_text, annotations_list)
    where annotations_list contains dicts:
    [{'type': 'circle'|'box'|'crosshair'|'arrow', 'image_index': 1, 'coords': [x, y]}]
    """
    if not text:
        return text, []

    annotations = []

    # 1. Parse <annotate type="..." image="...">body</annotate>
    annotate_pattern = re.compile(r'<annotate\b([^>]*)>(.*?)</annotate>', re.IGNORECASE | re.DOTALL)

    for match in annotate_pattern.finditer(text):
        attrs_str, body = match.groups()
        img_idx = 1
        ann_type = "box"

        img_match = re.search(r'(?:image|img)=["\']?(\d+)["\']?', attrs_str, re.IGNORECASE)
        if img_match:
            img_idx = max(1, int(img_match.group(1)))

        type_match = re.search(r'(?:type|shape)=["\']?(circle|box|crosshair|arrow)["\']?', attrs_str, re.IGNORECASE)
        if type_match:
            ann_type = type_match.group(1).lower()

        # Extract all integer numbers inside tag body (handles [(x1, y1), (x2, y2)], [x1, y1, x2, y2], (x1, y1), etc.)
        nums = [int(n) for n in re.findall(r'\d+', body)]
        if len(nums) >= 2:
            coords = nums[:4] if len(nums) >= 4 else nums[:2]
            annotations.append({
                "type": ann_type,
                "image_index": img_idx,
                "coords": coords,
                "is_normalized": True
            })

    # 2. Parse raw grounding <point image="...">body</point> tags
    point_pattern = re.compile(r'<point\b([^>]*)>(.*?)</point>', re.IGNORECASE | re.DOTALL)

    for match in point_pattern.finditer(text):
        attrs_str, body = match.groups()
        img_idx = 1
        ann_type = "circle"

        img_match = re.search(r'(?:image|img)=["\']?(\d+)["\']?', attrs_str, re.IGNORECASE)
        if img_match:
            img_idx = max(1, int(img_match.group(1)))

        nums = [int(n) for n in re.findall(r'\d+', body)]
        if len(nums) >= 2:
            annotations.append({
                "type": ann_type,
                "image_index": img_idx,
                "coords": nums[:2],
                "is_normalized": True
            })

    # Strip out all raw tags from text for clean user display
    clean_text = annotate_pattern.sub('', text)
    clean_text = point_pattern.sub('', clean_text).strip()

    if not clean_text and annotations:
        ann_desc = annotations[0]['type']
        clean_text = f"📍 Located target element on screen ({ann_desc}). Type a question in the text box below for detailed guidance."

    return clean_text, annotations

class ConversationSession:
    def __init__(self, max_turns: int = 10):
        self.max_turns = max_turns
        self.messages: List[Dict[str, Any]] = []
        self.active_goal: str = ""

    def add_user_message(self, text: str, image_b64: Optional[str] = None, images_b64: Optional[List[str]] = None):
        img_list = images_b64 if images_b64 is not None else ([image_b64] if image_b64 else [])
        msg = {
            "role": "user",
            "text": text,
            "images_b64": img_list,
            "timestamp": time.time()
        }
        self.messages.append(msg)
        self._trim_history()

    def add_assistant_message(self, text: str):
        msg = {
            "role": "assistant",
            "text": text,
            "timestamp": time.time()
        }
        self.messages.append(msg)
        self._trim_history()

    def clear(self):
        self.messages.clear()

    def _trim_history(self):
        # Keeps last max_turns * 2 messages (pairs of user/assistant)
        limit = self.max_turns * 2
        if len(self.messages) > limit:
            self.messages = self.messages[-limit:]

    def get_openai_messages(self, current_prompt: Optional[str] = None, current_image_b64: Optional[str] = None) -> List[Dict[str, Any]]:
        formatted: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

        # Add all message turns in history with their screenshots retained
        for msg in self.messages:
            role = msg["role"]
            text = msg.get("text", "")
            imgs = msg.get("images_b64", [])
            if not imgs and msg.get("image_b64"):
                imgs = [msg["image_b64"]]

            if role == "assistant":
                formatted.append({"role": "assistant", "content": text})
            elif role == "user":
                content = []
                if text:
                    content.append({"type": "text", "text": text})
                for img in imgs:
                    if img:
                        clean_img = img.split(",")[-1] if "," in img else img
                        content.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{clean_img}"
                            }
                        })
                if not content:
                    content = [{"type": "text", "text": "Check the screen and provide guidance."}]
                formatted.append({"role": "user", "content": content})

        # Append current pending prompt/image if provided and not already duplicated
        if (current_prompt or current_image_b64) and not (self.messages and self.messages[-1].get("text") == current_prompt and self.messages[-1].get("image_b64") == current_image_b64):
            content = []
            if current_prompt:
                content.append({"type": "text", "text": current_prompt})
            if current_image_b64:
                clean_img = current_image_b64.split(",")[-1] if "," in current_image_b64 else current_image_b64
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{clean_img}"
                    }
                })
            if not content:
                content = [{"type": "text", "text": "Check the screen and provide guidance."}]
            formatted.append({"role": "user", "content": content})

        return formatted
