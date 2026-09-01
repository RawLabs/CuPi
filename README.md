# AI Work Companion — Guide Builder Alpha

A cross-platform floating desktop AI companion. Application features depend on the `PlatformBackend` API; Linux/X11, Linux/Wayland, and Windows are separate adapters, with a macOS stub reserved for later implementation.

> **Hyprland status:** the bundled native helper captures a selected application cleanly—even on another workspace—without changing the current workspace or moving windows. If that helper is unavailable, the app never substitutes a current-workspace region crop for an inactive-workspace request.

## Architecture

* `platform_api/`: OS-neutral capture, window, cursor, hotkey, permission, and capability API.
* `platform_api/linux_x11.py`: all `xprop`, `xwininfo`, `xdotool`, and `x11grab` behavior.
* `platform_api/linux_wayland.py`: Wayland-safe adapter with grim monitor/region capture and Hyprland clean-window capture.
* `platform_api/windows.py`: native Win32 window enumeration/focus plus Qt capture.
* `storage/`: portable (`portable.flag` + `./data`) and installed per-user layouts.
* `sessions/`: versioned OS-neutral SOP session/step representation.

Place an empty `portable.flag` beside the executable (or source entry point) to keep all state under `./data/{config,sessions,captures,exports,logs}`.

---

## 🌟 Key Features (Currently Implemented)

### 1. 🛡️ Sentinel Watchdog (Passive Co-Pilot Mode)
* **Zero-Cost Background Monitoring**: Periodically observes target windows or displays (~37ms processing time) using channel-correct 3D NumPy array differencing. Uses 0 API tokens and makes zero network calls while idle.
* **Dual-Threshold Motion Hysteresis**: Ignores blinking text cursors, typing jitter ($1.6\% - 2.2\%$), and tab switches, preventing observation resets during normal typing.
* **Latched Candidate Engine & Fingerprinting**: Uses `CandidateState` enums, `hashlib.sha256` stable digests, and 64-bit block average perceptual crop hashing (Hamming distance $\le 6$) to eliminate 2-second repeat candidate log loops.
* **Composite Anomaly Scoring**: Evaluates persistent regions (+3), new red color accents (+2), text-like edge density (+1), and dialog geometry (+1) without requiring any single color as a mandatory gate.
* **Non-Intrusive Floating Toast HUD Popup**: Displays a bottom-right HUD alert when anomaly score $S \ge 3$:
  * **`🔍 Inspect with AI`**: Auto-dismisses HUD, suppresses fingerprint from re-alerting, populates prompt, and attaches cropped error screenshot ready for review.
  * **`🔕 Mute 5m`**: Temporarily mutes toasts for 5 minutes while maintaining background monitoring and releasing crop memory.
  * **`❌ Dismiss`**: Suppresses the specific candidate fingerprint.
* **In-App Evaluation Log Modal (`📊 Log`)**: Real-time performance dashboard displaying latency, processed/dropped frame metrics, candidate counts, and persistent event logging (`~/.config/ai_work_companion/sentinel_events.log`).

### 2. 🎨 Guide Builder UI & Resizable Workspace
* **Generous Source & Model Selectors**: 3-row layout ensures target window/monitor titles in **Source** dropdown and model names in **Model** dropdown are fully readable without truncation.
* **Frameless Always-On-Top UI**: Includes collapse/expand toggle (`🔽 Collapse`), titlebar drag handles, and dynamic cursor indicators (`<->`, `^v`, `\`, `/`) with a bottom-right `QSizeGrip` handle.
* **Guide Builder Hierarchy**: The interface separates capture steps, guide drafting, and the AI conversation so the work stays focused on making usable instructions.
* **Readable Cross-Platform Type**: Prefers Inter, Segoe UI Variable, Segoe UI, and Noto Sans with platform fallbacks.
* **Window Transparency Slider**: Live opacity control slider (`👁️ 30% - 100%`) persisting preferences to `~/.config/ai_work_companion/config.json`.

### 3. 🎯 Unobscured Target Capture Pipeline
* **Source Selector**: Choose any display monitor or managed window (Firefox, Terminal, IDE, etc.); Hyprland window labels include their workspace.
* **Target Picker Overlay**: Click and drag across the screen to visually target any window or custom screen area.
* **X11 Composite Buffer & Auto-Uncover**: Captures offscreen window buffers (`ffmpeg -f x11grab`) and automatically raises target windows (`xdotool windowactivate`) during capture so covered windows are captured unobscured.
* **Hyprland Clean Window Capture**: Uses Hyprland's toplevel-export protocol for selected windows, including windows on inactive workspaces, so their client surfaces are captured cleanly even when the desktop is cluttered or another window is above them. Multiple selected windows are then placed into one spatially preserved composite.
* **Self-Hiding Companion**: Companion window temporarily hides during capture so it never overlays the captured image.

### 4. 🖼️ Editable Capture Steps & Screen Saving
* **Add Capture**: Captures the selected target and adds it to your editable guide steps only. Nothing is sent to AI until you choose **Ask AI**.
* **Save Screenshot**: Instantly captures target window/screen and saves numbered images (`capture_step_01_...png`) to `~/Pictures/AI_Companion_Captures/` without sending them to AI.
* **Editable Capture Tray**: Accumulate multiple captures as guide steps. Every pending step can be annotated again or removed without restarting the capture session.

### 5. 📍 Screen Annotations & Reasoning Support
* **Re-editable Annotations**: Reopen and revise annotations for any pending guide step; AI annotations replace only the affected exported image.
* **Multi-Tuple Coordinate Parsing**: Robustly parses all vision model coordinate tuple formats (`[(x1, y1), (x2, y2)]`, `[x1, y1, x2, y2]`, `(x, y)`), drawing clean hollow red rounded boxes/circles on thumbnails and stripping raw XML tags from user text.
* **Reasoning Model Support**: Robustly handles OpenRouter reasoning models (`choices[0].message.reasoning` / `reasoning_content`) and displays raw provider JSON previews on error returns.

### 6. 🔒 Dual Provider Connections & Privacy
* **LM Studio (Local 🔒)**: Connects to local server (`http://localhost:1234/v1`). 100% private, stays on your device.
* **OpenRouter (Hosted 🌐)**: Connects to hosted multimodal models (`https://openrouter.ai/api/v1`) with explicit online confirmation modal.

### 7. 📄 Guide Drafting & Export
* **Guide Types**: Draft a Work Instruction, SOP, Teaching Guide, Study Guide, or Quick Reference from your request and captured steps.
* Preserves conversation context across multiple turns without uploading redundant heavy image history.
* **Export Guide** creates clean HTML and Markdown bundles with the captured evidence images retained, even if AI did not annotate them.

---

## 🛠️ Setup & Requirements

### System Requirements
* OS: Linux (Pop!_OS, Ubuntu, Debian, Fedora with X11)
* Python 3.10+
* System utilities: `ffmpeg`, `xwininfo`, `xdotool`, `xprop` (standard X11 tools); Hyprland Wayland builds also need `grim`, `hyprctl`, `wayland-scanner`, `wayland-client`, `pkg-config`, and a C++ compiler.

### Python Dependencies
Install required packages:
```bash
pip install PyQt6 mss requests Pillow numpy
```

---

## 🚀 Quick Start

### 1. Launching the App
Run the convenience script:
```bash
./run.sh
```
or launch directly with Python:
```bash
python3 main.py
```

### Hyprland: test clean capture across workspaces

The source checkout needs the native helper before it can capture a window on
another workspace without switching to it. Build it once, then launch normally:

```bash
./packaging/build_hyprland_helper.sh
./run.sh
```

Choose a window labelled with its workspace in **Source**, stay on your current
workspace, and use **Preview** or **Add Capture**. If clean capture cannot
run, the app fails safely instead of capturing the current workspace at the
same screen coordinates.

### 2. Activating Sentinel Watchdog
1. Select your target **Source** (e.g. `Gnome-terminal` or `Screen 1`).
2. Click **`🛡️ Watchdog`** in the `Sentinel:` controls row so it displays `🛡️ Active`.
3. Work normally. If an error or persistent traceback appears on screen, a floating **Toast HUD Alert** will pop up at the bottom-right of your screen offering **`🔍 Inspect with AI`**.
4. Click **`📊 Log`** anytime to view real-time performance metrics and latency logs.

---

## 🧪 Running Automated Unit Tests

Run the test suite from the project directory:

```bash
python3 -m unittest discover -s tests
```
GUI tests require an active desktop session. The capture and guide UI should also be exercised manually on the desktop where the app will run.
Pytest initializes one shared offscreen Qt application for image and widget tests.

**What the test suite covers:**
* `test_sentinel_engine.py`: Channel-correct 3D numpy delta math ($\le 1.0$), baseline resets, candidate states.
* `test_sentinel_hysteresis.py`: Dual-threshold motion hysteresis ignoring text cursor blinking and typing jitter.
* `test_sentinel_regions.py`: Downsampled mask cleanup, IoU matching, and padded coordinate scaling at all 4 screen edges.
* `test_sentinel_candidate.py`: Latched candidate manager, stable SHA-256 digests, 64-bit perceptual crop hashing, disappearance hysteresis, and mute memory release.
* `test_sentinel_signals.py`: Composite anomaly scoring, new red accent detection, and text-like edge density.
* `test_annotations.py`: Double-tuple box annotation parsing and pixel scaling.
* `test_companion.py`: UI initialization, layout constraints, model search, history context, export formatting.

---

## 🎯 How to Use

1. **Adjust Size & Transparency**: Use header **👁️ opacity slider** or drag window edges to position companion.
2. **Select Source & Model**: Choose a target window or display from the **Source** dropdown and pick an active model.
3. **Build a Guide**:
   * Click **Preview** to inspect a capture without saving or sending it.
   * Click **＋ Add Capture** to make an editable guide step without sending it to AI.
   * Select a guide format, write your request, then click **✦ Ask AI**.
   * Click **💾 Save PNG** to save a capture to disk only.
4. **Export**: Use **📄 Export Guide** on the AI response to create a Markdown/HTML evidence bundle.

Sentinel is optional background monitoring and is available under **Options** so it does not distract from the normal capture workflow.
