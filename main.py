from machine import Pin, time_pulse_us
import time
import network
import socket
import gc

# Define pins
LED = Pin(2, Pin.OUT)  # D4 (Built-in LED on most ESP8266 boards)
LED.off()
TRIG = Pin(4, Pin.OUT)  # D2
ECHO = Pin(0, Pin.IN)   # D3
BUZZER = Pin(14, Pin.OUT)  # D5
BUZZER.off()

# WiFi credentials - replace with your network details
WIFI_SSID = "my_phone"
WIFI_PASSWORD = "187829200"

# Global variables
finding_mode = False
last_find_request = 0

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

# Function to beep the buzzer
def beep(duration=0.1, pause=0.1, count=1):
    for _ in range(count):
        BUZZER.on()
        LED.on()  # Turn LED on with buzzer (inverted logic - on is LOW)
        time.sleep(duration)
        BUZZER.off()
        LED.off()  # Turn LED off with buzzer
        if _ < count - 1:  # Don't pause after the last beep
            time.sleep(pause)

# Function to connect to WiFi
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if not wlan.isconnected():
        print("Connecting to WiFi...")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        
        # Wait for connection with timeout
        max_wait = 10
        while max_wait > 0:
            if wlan.isconnected():
                break
            max_wait -= 1
            print("Waiting for connection...")
            time.sleep(1)
        
        if wlan.isconnected():
            print("Connected to WiFi")
            print("Network config:", wlan.ifconfig())
            # Blink LED to indicate successful connection
            for _ in range(3):
                LED.on()
                time.sleep(0.1)
                LED.off()
                time.sleep(0.1)
        else:
            print("Failed to connect to WiFi")
            # Long beep to indicate failure
            beep(1.0)
    else:
        print("Already connected to WiFi")
        print("Network config:", wlan.ifconfig())
    
    return wlan

# Function to start web server
def start_webserver():
    addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(5)
    print('Web server started on', addr)
    return s

# Function to handle HTTP requests
def handle_request(client):
    global finding_mode, last_find_request
    
    try:
        client.settimeout(3.0)  # Set timeout for client operations
        request = client.recv(1024)
        request = request.decode('utf-8')
        
        # Parse the request
        request_line = request.split('\r\n')[0]
        method, path, _ = request_line.split(' ')
        
        # Handle different endpoints
        if path == '/find':
            # Activate "find mode" for the stick
            finding_mode = True
            last_find_request = time.time()
            
            response = "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nAccess-Control-Allow-Origin: *\r\n\r\nFinding stick..."
            client.send(response)
            print("Find request received")
            
            # Make noise to help locate the stick
            for _ in range(2):
                beep(0.2, 0.1, 3)
                time.sleep(0.5)
        
        elif path == '/status':
            # Return stick status
            distance = get_distance()
            status = {
                "distance": distance,
                "finding_mode": finding_mode,
                "battery": "unknown"  # You could add battery monitoring
            }
            
            response = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nAccess-Control-Allow-Origin: *\r\n\r\n"
            response += str(status)
            client.send(response)
            
        else:
            # Default homepage
            response = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nAccess-Control-Allow-Origin: *\r\n\r\n"
            response += "<html><body><h1>Blind Stick Server</h1><p>Use /find to locate the stick</p></body></html>"
            client.send(response)
            
    except socket.timeout:
        print("Request timed out")
    except OSError as e:
        if e.errno == 110:  # ETIMEDOUT
            print("Connection timed out")
        else:
            print("Network error:", e)
    except Exception as e:
        print("Error handling request:", e)
        
    finally:
        try:
            client.close()
        except:
            pass  # Ignore errors when closing an already closed connection

# Main function
def main():
    global finding_mode, last_find_request
    
    # Connect to WiFi
    wlan = connect_wifi()
    if not wlan.isconnected():
        # Run in standalone mode if WiFi connection fails
        print("Running in standalone mode (no WiFi)")
        while True:
            distance = get_distance()
            print("Distance:", distance, "cm")
            
            if 0 < distance < 50:  # Obstacle detected within 50cm
                beep(0.1, 0.1)
            else:
                BUZZER.off()
                LED.off()
                
            time.sleep(0.2)
    
    # Start web server
    s = start_webserver()
    
    try:
        while True:
            try:
                # Check for web clients (non-blocking with timeout)
                s.settimeout(0.01)
                client, addr = s.accept()
                print('Client connected from', addr)
                handle_request(client)
            except OSError as e:
                # No client connected within timeout period
                pass
            
            # Regular distance checking
            distance = get_distance()
            print("Distance:", distance, "cm")
            
            # Handle obstacle detection
            if 0 < distance < 50:  # Obstacle detected within 50cm
                beep(0.1, 0.1)
            else:
                BUZZER.off()
                LED.off()
            
            # If in finding mode, make extra noise
            current_time = time.time()
            if finding_mode:
                if current_time - last_find_request < 30:  # Stay in finding mode for 30 seconds
                    beep(0.1, 0.3, 1)
                else:
                    finding_mode = False  # Exit finding mode after 30 seconds
            
            # Garbage collection to avoid memory issues
            gc.collect()
            
            time.sleep(0.2)
            
    except KeyboardInterrupt:
        s.close()
        print("Server stopped")

# Start the program
if __name__ == "__main__":
    main()