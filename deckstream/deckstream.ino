/*
  ESP32-WROOM-32D Script for Python Communication (v3 - Remapped)

  This script detects button presses and holds, then sends a clean,
  machine-readable command over USB serial to the listening Python script.

  *** LOGIC FIX ***
  - The button mapping has been updated to match user's preferred layout.
  - The state machine prevents a "PRESS" event from firing after a "HOLD".

  New Button Mapping:
  - UI Button 1 -> Physical Pin 17 (Your old button 9)
  - UI Button 2 -> Physical Pin 32 (Your old button 8)
  - UI Button 3 -> Physical Pin 25 (Your old button 7)
  - UI Button 4 -> Physical Pin 23 (Your old button 6)
  - UI Button 5 -> Physical Pin 27 (Your old button 5)
  - UI Button 6 -> Physical Pin 12 (Your old button 4)
  - UI Button 7 -> Physical Pin 18 (Your old button 3)
  - UI Button 8 -> Physical Pin 4  (Your old button 2)
  - UI Button 9 -> Physical Pin 15 (Your old button 1)
*/

// --- Configuration ---
const int NUM_BUTTONS = 9;
const unsigned long holdTime = 1000;   // 1 second to trigger a hold

// --- Button Pin Definitions (Remapped) ---
const int buttonPins[NUM_BUTTONS] = {
  17, // Button 1
  32, // Button 2
  25, // Button 3
  23, // Button 4
  27, // Button 5
  12, // Button 6
  18, // Button 7
  4,  // Button 8
  15  // Button 9
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

// The robust state machine logic
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
