from machine import Pin, time_pulse_us
import time

# Define pins
LED = Pin(2, Pin.OUT)  # D4
LED.off()
TRIG = Pin(4, Pin.OUT)  # D2
ECHO = Pin(0, Pin.IN)   # D3
BUZZER = Pin(14, Pin.OUT)  # D5
BUZZER.off()

# Function to measure distance
def get_distance():
    TRIG.off()
    time.sleep_us(2)
    TRIG.on()
    time.sleep_us(10)
    TRIG.off()
    
    pulse_duration = time_pulse_us(ECHO, 1, 30000)  # max 30ms pulse (5 meters)
    if pulse_duration < 0:
        return -1  # No pulse detected (out of range)

    # Speed of sound = 343 m/s = 0.0343 cm/us
    distance = (pulse_duration * 0.0343) / 2  # cm
    return distance

# Main loop
while True:
    distance = get_distance()
    print("Distance:", distance, "cm")
    
    if 0 < distance < 50:  # Obstacle detected within 50cm
        BUZZER.on()
        LED.on()  # LED turns off with buzzer
        time.sleep(0.1)
        BUZZER.off()
        LED.off()   # LED turns back on with buzzer
        time.sleep(0.1)
    else:
        BUZZER.off()
        LED.off()   # Ensure LED stays on when no obstacle

    time.sleep(0.2)


