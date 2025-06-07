/*
  ESP32-WROOM-32D Script for Python Communication (v2)

  This script detects button presses and holds, then sends a clean,
  machine-readable command over USB serial to the listening Python script.

  *** LOGIC FIX ***
  - The state machine has been rewritten to be more robust.
  - Releasing a button after a "HOLD" event has been sent will no longer
    also send a "PRESS" event. The actions are now mutually exclusive.

  How it works:
  - The baud rate is set to 9600 to match the Python script.
  - A clean state machine determines if an action is a PRESS or a HOLD.
    - A PRESS command is only sent if the button is released before the hold time.
    - A HOLD command is sent once the hold time is exceeded.
  - The Python script receives either "BUTTON_X_PRESS" or "BUTTON_X_HOLD".

  Button Mapping:
  - Button 1: D15 (GPIO 15)
  - Button 2: D4  (GPIO 4)
  - Button 3: D18 (GPIO 18)
  - Button 4: D12 (GPIO 12)
  - Button 5: D27 (GPIO 27)
  - Button 6: D23 (GPIO 23)
  - Button 7: D25 (GPIO 25)
  - Button 8: D32 (GPIO 32)
  - Button 9: D17 (GPIO 17)
*/

// --- Configuration ---
const int NUM_BUTTONS = 9;
const unsigned long debounceTime = 50;  // Debounce not explicitly used in new FSM, but good to keep
const unsigned long holdTime = 1000;   // 1000 milliseconds (1 second) to trigger a hold

// --- Button Pin Definitions ---
const int buttonPins[NUM_BUTTONS] = {
  15, 4, 18, 12, 27, 23, 25, 32, 17
};

// --- State Machine Variables ---
byte buttonFSM[NUM_BUTTONS];
unsigned long buttonPressTime[NUM_BUTTONS];

// Define the states for our Finite State Machine (FSM)
#define STATE_IDLE 0        // Button is up and inactive
#define STATE_PRESSED 1     // Button is down, awaiting release or hold
#define STATE_HELD 2        // Button has been held down, awaiting release

void setup() {
  // Set the baud rate to match the Python script
  Serial.begin(9600);

  for (int i = 0; i < NUM_BUTTONS; i++) {
    pinMode(buttonPins[i], INPUT_PULLUP);
    // Initialize the state for all buttons to IDLE
    buttonFSM[i] = STATE_IDLE;
  }
}

void loop() {
  // Check each button's state
  for (int i = 0; i < NUM_BUTTONS; i++) {
    updateButtonState(i);
  }
}

// The new, more robust state machine logic
void updateButtonState(int i) {
  byte currentState = digitalRead(buttonPins[i]);

  switch(buttonFSM[i]) {
    case STATE_IDLE:
      // If the button is pressed, move to the PRESSED state and record the time.
      if (currentState == LOW) {
        buttonFSM[i] = STATE_PRESSED;
        buttonPressTime[i] = millis();
      }
      break;

    case STATE_PRESSED:
      // If the button is released from the PRESSED state...
      if (currentState == HIGH) {
        // ...it was released before the hold timer expired. This is a "PRESS" event.
        String command = "BUTTON_" + String(i + 1) + "_PRESS";
        Serial.println(command);
        buttonFSM[i] = STATE_IDLE; // Reset to idle
      } 
      // If the hold timer expires while still in the PRESSED state...
      else if (millis() - buttonPressTime[i] > holdTime) {
        // ...this is a "HOLD" event.
        String command = "BUTTON_" + String(i + 1) + "_HOLD";
        Serial.println(command);
        buttonFSM[i] = STATE_HELD; // Move to the HELD state
      }
      break;

    case STATE_HELD:
      // If the button is released from the HELD state...
      if (currentState == HIGH) {
        // ...do nothing. The HOLD action was already sent. Just reset to idle.
        buttonFSM[i] = STATE_IDLE;
      }
      break;
  }
}
