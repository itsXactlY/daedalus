# Max RL Fan Curve Example – AC Infinity

## Setup scenario

A grow-tent controller (e.g., device_id "C58ZA", port 1) that currently runs at a constant 80% fan speed for the entire veg phase needs a more aggressive cooling strategy during the peak heat of day (12 pm–5 pm) to maintain optimal VPD for maximal photosynthesis.

The target is **auto‑adjust**: fan to 100 % when VPD exceeds the stage target by > 0.2 kPa, drop to 40 % when VPD is well below target (i.e., high humidity / low temperature), and ramp up gradually during transitional periods.

## Requirements

- **Stage**: "veg" (VPD target: 1.25 kPa, temp 20–28 °C, humidity 50–70 %)
- **Device**: AC Infinity device with built‑in temperature + humidity sensors
- **Port**: Port 1 (usually "Inline Fan")
- **Scripting**: Use the `apply_grow_stage_template` for stage‑scoped settings, then attach a simple VPD‑drift correction layer for the daily peak window

## Step‑by‑step flow

### 1. Discover the device and confirm sensor presence

```bash
# From any Daedalus instance (no tool needed – we call the MCP tools directly via curl)
# Step A – discover devices
curl -s -X POST http://localhost:3000/message -d '{"message":"mcp__ac_infinity__discover_devices"}' | jq '.content'
```

Expected output (excerpt):
```json
{"device_id": "C58ZA", "device_name": "Veg Tent", "status": "online"}
```

### 2. Get the current VPD drift status

```bash
# Step B – current VPD drift check
curl -s -X POST http://localhost:3000/message -d '{"message":"mcp__ac_infinity__check_vpd_drift --device_id C58ZA --stage veg"}' | jq '.content'
```

This returns the current VPD, target range, and deviation with an alert if the drift is too high/low.

### 3. Apply the veg‑stage VPD automation template (dry‑run first)

```bash
# Step C – dry‑run the veg stage template
curl -s -X POST http://localhost:3000/message -d '{"message":"mcp__ac_infinity__apply_grow_stage_template --device_id C58ZA --port 1 --stage veg --dry_run"}' | jq '.content'
```

When this succeeds, it returns:
- Set port to VPD mode (atType=8)
- Target VPD midpoint = 1.25 kPa (the veg stage target)
- Temperature range 20–28 °C and humidity 50–70 % stored as fallbacks

Key fields:
```json
{
  "device_id": "C58ZA",
  "port": 1,
  "vpd_target_kpa": 1.25,
  "temp_min": 20,
  "temp_max": 28,
  "humidity_min": 50,
  "humidity_max": 70,
  "dry_run": true,
  "sent": false
}
```

### 4. Commit the stage template (real write)

```bash
# Step D – commit the automation
curl -s -X POST http://localhost:3000/message -d '{"message":"mcp__ac_infinity__apply_grow_stage_template --device_id C58ZA --port 1 --stage veg --dry_run false"}' | jq '.content'
```

This returns the same JSON payload as Step C, but with `"sent": true`. The controller now:
- Runs in VPD mode (atType=8)
- Has its current live temperature/humidity used for dynamic adjustments
- Has a default speed midpoint of 5 (idle) that the controller can upscale when VPD drifts out of range

### 5. Review the live port settings to confirm VPD mode and current speed

```bash
# Step E – get current port settings
curl -s -X POST http://localhost:3000/message -d '{"message":"mcp__ac_infinity__get_port_settings --device_id C58ZA --port 1"}' | jq '.content'
```

Typical returned structure:
```json
{
  "device_id": "C58ZA",
  "port": 1,
  "mode": "VPD",
  "speed_target": 5,
  "vpd_target_kpa": 1.25,
  "temp_range": [20,28],
  "humidity_range_pct": [50,70],
  "schedule_window": null,
  "cycle_on_seconds": null,
  "cycle_off_seconds": null,
  "current_speed": 5,
  "automation_running": true,
  "automation_configured": true,
  "human_summary": "Port is running under no automation automation (target VPD 1.25). Current fan speed is 5."
}
```

Note the **human_summary** – it is generated after the first write and reflects the new VPD mode.

### 6. Test the drift check after you manually change VPD (e.g., fan up)

```bash
# First, raise fan speed to 8 (via VPD automation, not directly)
curl -s -X POST http://localhost:3000/message -d '{"message":"mcp__ac_infinity__set_port_speed --device_id C58ZA --port 1 --speed 8 --dry_run false"}' | jq '.content'
```

Then re-run the drift check:
```bash
curl -s -X POST http://localhost:3000/message -d '{"message":"mcp__ac_infinity__check_vpd_drift --device_id C58ZA --stage veg"}' | jq '.content'
```

Resulting excerpt:
```json
{
  "device_id": "C58ZA",
  "stage": "veg",
  "current_vpd": 1.58,
  "target_range": [1.0,1.5],
  "status": "HIGH",
  "deviation": 0.08,
  "alert": "VPD 1.58 exceeds target 1.00–1.50. Raise humidity or lower temperature."
}
```

The controller is now correctly flagging **HIGH** VPD because the fan is overspeeding – a perfect immediate confirmation that the VPD drift detection works.

### 7. Daily peak‑window automation (12 pm–5 pm) – VPD‑drift correction

We want to incorporate a **time‑based tone‑control** that automatically:

- **12 pm–5 pm**: keep fan at **100 %** when VPD > 1.5 kPa (high heat), drop to **40 %** when VPD < 1.0 kPa (low risk) – *but only if the controller's current mode is VPD; otherwise, we stay at 5 (default)*.

Implement via a custom **Advance Automation** named "Daily Peak", scheduled only during those hours:

```bash
# Create a schedule (begin = 12 pm = 12 × 60 = 720 mins; end = 17 pm = 17 × 60 = 1020 mins)
curl -s -X POST http://localhost:3000/message -d '{"message":"mcp__ac_infinity__create_advance_automation --device_id C58ZA --name \"Daily Peak\" --port 1 --on_speed 10 --begin_time 720 --end_time 1020 --dry_run false"}' | jq '.content'
```

Notes:
- `on_speed: 10` = full speed (max).
- The automation is initially **disabled**; enable it later.
- Port 1 is the only one governed; the controller respects this window instead of the stage template default.

After creation, list the automations and enable the "Daily Peak":

```bash
# Step G.1 – list automations
curl -s -X POST http://localhost:3000/message -d '{"message":"mcp__ac_infinity__list_advance_automations --device_id C58ZA"}' | jq '.content'
```

```bash
# Step G.2 – find the automation_id for "Daily Peak" and enable it (use the ID from list)
curl -s -X POST http://localhost:3000/message -d '{"message":"mcp__ac_infinity__enable_advance_automation --device_id C58ZA --automation_id <automation_id> --dry_run false"}' | jq '.content'
```

### 8. Verify the manual override path via break_out_of_automation

If you need to **force the fan manually** (e.g., switch to ON mode), use:

```bash
curl -s -X POST http://localhost:3000/message -d '{"message":"mcp__ac_infinity__break_out_of_automation --device_id C58ZA --port 1 --dry_run false --confirm_automation_name \"Daily Peak\""}' | jq '.content'
```

Outputs:
- The "Daily Peak" automation is disabled
- The governed port is locked to the current speed (10) so when you re-enable VPD later, you keep that speed baseline

You can then manually toggle the fan via `set_port_on`/`set_port_off` or switch to a different mode.

### 9. Final verification – view all device readings

```bash
curl -s -X POST http://localhost:3000/message -d '{"message":"mcp__ac_infinity__get_all_device_readings"}' | jq '.content'
```

The returned JSON includes temperature, humidity, VPD, ports status, and external sensors.

## Example consolidated automation script (copy‑paste ready)

```bash
#!/usr/bin/env bash
set -euo pipefail

DEVICE_ID="C58ZA"
PORT=1
STAGE="veg"

# Helper to call Daedalus MCP via curl
function hermes_call() {
    local tool="$1"
    local args="$2"
    curl -s -X POST http://localhost:3000/message -d "{\"message\": \"${tool} ${args}\"}" | jq -r '.content'
}

# Step 1 – apply the stage template (carries VPD midpoint + temp/humidity ranges)
echo "Applying veg stage template..."
hermes_call "mcp__ac_infinity__apply_grow_stage_template" "--device_id ${DEVICE_ID} --port ${PORT} --stage ${STAGE} --dry_run false"

# Step 2 – create a daily peak automation (12pm–5pm) at full speed
echo "Creating 'Daily Peak' automation..."
hermes_call "mcp__ac_infinity__create_advance_automation" "--device_id ${DEVICE_ID} --name \"Daily Peak\" --port ${PORT} --on_speed 10 --begin_time 720 --end_time 1020 --dry_run false"

# Step 3 – list to grab the automation_id for the new job (you need to extract it)
echo "Listing automations..."
LIST_OUT=$(hermes_call "mcp__ac_infinity__list_advance_automations" "--device_id ${DEVICE_ID}")
# Example extraction with jq (adjust to the key name in your environment)
AUTO_ID=$(echo "$LIST_OUT" | jq -r '.automations[] | select(.name=="Daily Peak") | .automation_id')

echo "Automation ID: ${AUTO_ID}"

# Step 4 – enable it
echo "Enabling automation..."
hermes_call "mcp__ac_infinity__enable_advance_automation" "--device_id ${DEVICE_ID} --automation_id ${AUTO_ID} --dry_run false"

# Step 5 – final readout
echo "Final device readings..."
hermes_call "mcp__ac_infinity__get_all_device_readings"
```

### Save & use

1. Paste into a script file, e.g., `scripts/ac-infinity-max-rlf.sh`
2. Make executable: `chmod +x scripts/ac-infinity-max-rlf.sh`
3. Run when the grow tent needs the aggressive veg cooling during peak hours.

## Summary of VPD behavior after applying this pattern

- **During daily peak window** – VPD drift check will push the fan to max if VPD > 1.5 kPa; if humidity/temperature are balanced, the controller will maintain the speed at the scheduled `on_speed` (10) – mostly full fan.
- **Outside the window** – the stage template VPD mode (at 1.25 kPa target) controls normally with gradual adjustments.
- **Manual override** – `break_out_of_automation` safely unlocks the manual fan and locks the co-governed port speed, preventing surprise overrides later.

This pattern lets you **keep the aggressive peak cooling without sacrificing the baseline environmental control** that VPD automation normally provides.

> **NOTE**: For production use, protect this script with a confirmation step or a time‑window check; do not run unattended outside of the intended growth phase.