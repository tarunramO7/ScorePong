from machine import Pin
import time
import os
import random

# --- CONFIG ---
MIN_WIN_SCORE, WIN_DIFF, DEBOUNCE_TIME = 11, 2, 0.005
RESET_HOLD_TIME, MATCH_END_DELAY = 3, 5
SERVES_PER_PLAYER, LOGS_FOLDER = 2, "match_logs"

# --- SETUP ---
led_a, led_b = Pin(0, Pin.OUT), Pin(1, Pin.OUT)
verify_led, serve_led = Pin(16, Pin.OUT), Pin(19, Pin.OUT)
button_a, button_b = Pin(2, Pin.IN, Pin.PULL_UP), Pin(3, Pin.IN, Pin.PULL_UP)

# --- STATE ---
score_a = score_b = set_score_a = set_score_b = total_points = hold_stage = 0
match_id, sets_mode = 1, 1
current_server, match_started = 'A', False
match_running, last_match_end_time = True, None
side_switched = False
log_created = False
current_log_file = None  # Added to prevent NameError
mode_change_in_progress = False  # Flag to prevent scoring during mode change
first_server = 'A'  # Track the first server of the set

# --- LOGGING ---
def ensure_logs_directory():
    try: os.mkdir(LOGS_FOLDER)
    except: pass

def get_new_log_filename():
    global match_id
    files = []
    try: files = os.listdir(LOGS_FOLDER)
    except: ensure_logs_directory()

    highest = 0
    for file in files:
        if file.startswith("match_") and file.endswith(".txt"):
            try:
                num = int(file[6:-4])
                if num > highest: highest = num
            except: pass

    match_id = highest + 1
    return f"{LOGS_FOLDER}/match_{match_id}.txt"

def create_log_file():
    global current_log_file, log_created
    if log_created: return
    current_log_file = get_new_log_filename()
    with open(current_log_file, "w") as f:
        f.write("==================================\n")
        f.write("      TABLE TENNIS MATCH LOG      \n")
        f.write("==================================\n")
        f.write(f"Match #{match_id} - Started at: {time.localtime()[3]:02d}:{time.localtime()[4]:02d}\n")
        f.write(f"Sets mode: {sets_mode}-set match\n")
        f.write("==================================\n\n")
    log_created = True
    print(f"Log created: {current_log_file}")

def log_to_file(message):
    global current_log_file
    if not log_created: return
    t = time.localtime()
    timestamp = "{:02d}:{:02d}:{:02d}".format(t[3], t[4], t[5])
    try:
        with open(current_log_file, "a") as f:
            f.write(f"[{timestamp}] {message}\n")
    except: pass

# --- UTILITIES ---
def blink_led(led, times=3, speed=0.1):
    for _ in range(times):
        led.on()
        time.sleep(speed)
        led.off()
        time.sleep(speed)

def indicate_serve_change(player_led):
    player_led.on()
    serve_led.on()
    time.sleep(0.5)
    player_led.off()
    serve_led.off()

def celebrate_match_winner(winner_led):
    for _ in range(8):
        winner_led.on()
        time.sleep(0.1)
        winner_led.off()
        time.sleep(0.1)

def celebrate_sets_winner(winner_led):
    for _ in range(5):
        winner_led.on()
        verify_led.on()
        time.sleep(0.2)
        winner_led.off()
        verify_led.off()
        time.sleep(0.2)

def update_serve_indicator():
    global current_server, total_points, first_server
    old_server = current_server
    
    # Calculate who should be serving based on total points
    if total_points < 20:
        # Before deuce (20 points total), each player serves twice
        serve_count = total_points // SERVES_PER_PLAYER
        if first_server == 'A':
            current_server = 'B' if serve_count % 2 == 1 else 'A'
        else:  # first_server is 'B'
            current_server = 'A' if serve_count % 2 == 1 else 'B'
    else:
        # After 20 points (deuce), alternate every point
        if first_server == 'A':
            current_server = 'B' if total_points % 2 == 1 else 'A'
        else:  # first_server is 'B'
            current_server = 'A' if total_points % 2 == 1 else 'B'
    
    # Return True if the server changed
    return old_server != current_server

def start_new_set():
    global score_a, score_b, total_points, current_server, match_running, match_started, side_switched, first_server
    score_a = score_b = total_points = 0
    current_server = random.choice(['A', 'B'])
    first_server = current_server  # Remember who served first in this set
    match_running = True
    match_started = False
    side_switched = False
    print(f"\nNew set started! Starting with Player {current_server}'s serve")
    log_to_file(f"New set started. First serve by Player {current_server}")
    indicate_serve_change(led_a if current_server == 'A' else led_b)

def reset_sets():
    global sets_mode, set_score_a, set_score_b, hold_stage, log_created
    log_to_file(f"Set reset from {sets_mode}-set mode")
    sets_mode, set_score_a, set_score_b, hold_stage = 1, 0, 0, 0
    log_created = False
    print("Sets reset to 1-set mode.")

def toggle_sets_mode():
    global hold_stage, sets_mode, score_a, score_b, total_points
    old_mode = sets_mode
    hold_stage = (hold_stage + 1) % 3
    
    # Reset scores when mode changes
    score_a = score_b = total_points = 0

    if hold_stage == 1:
        sets_mode = 5
        print("Switched to 5-set match")
        log_to_file(f"Changed from {old_mode}-set to 5-set match")
        blink_led(verify_led, 5, 0.2)
    elif hold_stage == 2:
        sets_mode = 7
        print("Switched to 7-set match")
        log_to_file(f"Changed from {old_mode}-set to 7-set match")
        blink_led(verify_led, 7, 0.2)
    else:
        sets_mode = 1
        print("Back to single set mode")
        log_to_file(f"Changed from {old_mode}-set to 1-set match")
        blink_led(verify_led, 1, 0.2)

# --- MAIN LOOP ---
print("Table Tennis Scorer Ready")  # Removed emoji
ensure_logs_directory()
start_new_set()

while True:
    # Check for long button press (mode change)
    if not button_a.value() or not button_b.value():
        mode_change_in_progress = True  # Set flag to prevent scoring
        hold_start = time.ticks_ms()
        
        # Keep checking if buttons are still pressed
        while (not button_a.value() or not button_b.value()) and time.ticks_diff(time.ticks_ms(), hold_start) <= RESET_HOLD_TIME * 1000:
            time.sleep(0.01)  # Short sleep to prevent CPU hogging
            
        # Check if button was held long enough for mode change
        if time.ticks_diff(time.ticks_ms(), hold_start) > RESET_HOLD_TIME * 1000:
            toggle_sets_mode()
            time.sleep(0.5)  # Debounce after mode change
        
        # Allow time for button release
        while not button_a.value() or not button_b.value():
            time.sleep(0.01)
            
        mode_change_in_progress = False  # Clear flag after button release
        continue  # Skip the rest of the loop to avoid accidental point scoring

    if not match_running and last_match_end_time:
        if time.ticks_diff(time.ticks_ms(), last_match_end_time) > MATCH_END_DELAY * 1000:
            if sets_mode == 1 or set_score_a == sets_mode // 2 + 1 or set_score_b == sets_mode // 2 + 1:
                reset_sets()
            start_new_set()

    if not match_running or mode_change_in_progress: 
        continue

    if not button_a.value():
        time.sleep(DEBOUNCE_TIME)
        if not button_a.value() and not mode_change_in_progress:
            if not log_created:
                create_log_file()
                log_to_file("First point scored - Logging started")
            score_a += 1
            total_points += 1
            print("Player A scores ->", score_a)
            log_to_file(f"Player A scores. Score: {score_a}-{score_b}")
            blink_led(verify_led, 1, 0.01)
            if update_serve_indicator():
                player_led = led_a if current_server == 'A' else led_b
                print(f"Service changes to Player {current_server}")
                log_to_file(f"Service changes to Player {current_server}")
                indicate_serve_change(player_led)
            time.sleep(0.05)
            # Wait for button release to prevent multiple counts
            while not button_a.value():
                time.sleep(0.01)

    elif not button_b.value():
        time.sleep(DEBOUNCE_TIME)
        if not button_b.value() and not mode_change_in_progress:
            if not log_created:
                create_log_file()
                log_to_file("First point scored - Logging started")
            score_b += 1
            total_points += 1
            print("Player B scores ->", score_b)
            log_to_file(f"Player B scores. Score: {score_a}-{score_b}")
            blink_led(verify_led, 1, 0.01)
            if update_serve_indicator():
                player_led = led_a if current_server == 'A' else led_b
                print(f"Service changes to Player {current_server}")
                log_to_file(f"Service changes to Player {current_server}")
                indicate_serve_change(player_led)
            time.sleep(0.05)
            # Wait for button release to prevent multiple counts
            while not button_b.value():
                time.sleep(0.01)

    # Win detection first, then handle side switch if needed
    if score_a >= MIN_WIN_SCORE and (score_a - score_b) >= WIN_DIFF:
        match_running = False
        set_score_a += 1
        print(f"Player A wins the set! ({score_a}-{score_b})")
        log_to_file("==================================")
        log_to_file("MATCH SUMMARY:")
        log_to_file(f"Final Score: Player A {score_a} - Player B {score_b}")
        log_to_file(f"Set Score: Player A {set_score_a} - Player B {set_score_b}")
        log_to_file("==================================")
        celebrate_match_winner(led_a)
        last_match_end_time = time.ticks_ms()
        
        # Now handle side switch if needed
        if not side_switched:
            time.sleep(1)  # Brief pause after celebrating
            for led in [led_a, led_b, verify_led, serve_led]:
                led.on()
            time.sleep(8)
            for led in [led_a, led_b, verify_led, serve_led]:
                led.off()
            led_a, led_b = led_b, led_a
            button_a, button_b = button_b, button_a
            side_switched = True
            log_to_file("Players switched sides")

    elif score_b >= MIN_WIN_SCORE and (score_b - score_a) >= WIN_DIFF:
        match_running = False
        set_score_b += 1
        print(f"Player B wins the set! ({score_b}-{score_a})")
        log_to_file("==================================")
        log_to_file("MATCH SUMMARY:")
        log_to_file(f"Final Score: Player A {score_a} - Player B {score_b}")
        log_to_file(f"Set Score: Player A {set_score_a} - Player B {set_score_b}")
        log_to_file("==================================")
        celebrate_match_winner(led_b)
        last_match_end_time = time.ticks_ms()
        
        # Now handle side switch if needed
        if not side_switched:
            time.sleep(1)  # Brief pause after celebrating
            for led in [led_a, led_b, verify_led, serve_led]:
                led.on()
            time.sleep(8)
            for led in [led_a, led_b, verify_led, serve_led]:
                led.off()
            led_a, led_b = led_b, led_a
            button_a, button_b = button_b, button_a
            side_switched = True
            log_to_file("Players switched sides")

    if sets_mode > 1:
        if set_score_a == sets_mode // 2 + 1:
            print(f"Player A wins the match! ({set_score_a}-{set_score_b})")
            log_to_file("Player A wins the match!")
            log_to_file(f"Final Set Score: Player A {set_score_a} - Player B {set_score_b}")
            celebrate_sets_winner(led_a)
            reset_sets()
            start_new_set()

        elif set_score_b == sets_mode // 2 + 1:
            print(f"Player B wins the match! ({set_score_b}-{set_score_a})")
            log_to_file("Player B wins the match!")
            log_to_file(f"Final Set Score: Player A {set_score_a} - Player B {set_score_b}")
            celebrate_sets_winner(led_b)
            reset_sets()
            start_new_set()