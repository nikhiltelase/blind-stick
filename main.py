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
WIFI_SSID = "bot"
WIFI_PASSWORD = "00000000"

# AP credentials
AP_SSID = "BlindStick"
AP_PASSWORD = "12345678"  # minimum 8 characters

# Global variables
finding_mode = False
last_find_request = 0

# HTML content as a string
HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Blind Stick Locator</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: sans-serif; }
        body { background: #f5f8fa; display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: 20px; }
        .container { background: white; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); width: 100%; max-width: 500px; padding: 30px; text-align: center; }
        h1 { color: #2c3e50; margin-bottom: 20px; font-size: 24px; }
        .status-container { margin: 30px 0; min-height: 60px; }
        .status { font-size: 18px; color: #7f8c8d; }
        .button-container { display: flex; gap: 20px; justify-content: center; margin: 20px 0; }
        .btn { padding: 15px 30px; border: none; border-radius: 8px; font-size: 18px; cursor: pointer; transition: all 0.3s ease; }
        .find-btn { background: #3498db; color: white; }
        .stop-btn { background: #e74c3c; color: white; }
        .btn:hover { transform: scale(1.05); }
        .btn:active { transform: scale(0.95); }
    </style>
</head>
<body>
    <div class="container">
        <h1>Blind Stick Locator</h1>
        <div class="status-container">
            <div class="status" id="status">Ready to locate your stick</div>
        </div>
        <div class="button-container">
            <button class="btn find-btn" onclick="sendRequest('/find')">Find Stick</button>
            <button class="btn stop-btn" onclick="sendRequest('/stop')">Stop</button>
        </div>
    </div>
    <script>
        function sendRequest(endpoint) {
            fetch(endpoint)
                .then(response => {
                    if (response.ok) {
                        document.getElementById('status').textContent = 
                            endpoint === '/find' ? 'Finding stick...' : 'Stopped';
                    } else {
                        throw new Error('Request failed');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    document.getElementById('status').textContent = 'Connection error';
                });
        }
    </script>
</body>
</html>
"""

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

# Function to stop the buzzer
def stop_buzzer():
    global finding_mode
    finding_mode = False
    BUZZER.off()
    LED.off()

# Function to connect to WiFi - simplified version
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if not wlan.isconnected():
        print("Connecting to WiFi...")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        
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
            beep(1.0)  # Error beep
    else:
        print("Already connected to WiFi")
        print("Network config:", wlan.ifconfig())
    
    return wlan

def setup_access_point():
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid=AP_SSID, password=AP_PASSWORD, authmode=network.AUTH_WPA_WPA2_PSK)
    
    while not ap.active():
        print("Starting access point...")
        time.sleep(1)
    
    print("Access Point active")
    print("Network config:", ap.ifconfig())
    print(f"SSID: {AP_SSID}")
    print(f"Password: {AP_PASSWORD}")
    
    # Blink LED to indicate AP is ready
    for _ in range(5):
        LED.on()
        time.sleep(0.1)
        LED.off()
        time.sleep(0.1)
    
    return ap

def handle_request(client):
    global finding_mode, last_find_request
    
    try:
        # Simple request reading with small chunks
        request = b''
        client.settimeout(0.5)  # shorter timeout
        
        while b'\r\n\r\n' not in request:
            try:
                chunk = client.recv(64)  # smaller chunks
                if not chunk:
                    break
                request += chunk
            except Exception as e:
                print("Read error:", e)
                break
        
        # Parse request
        try:
            first_line = request.split(b'\r\n')[0].decode()
            method, path, _ = first_line.split(' ')
        except:
            print("Parse error")
            return
            
        print("Request:", path)  # Debug print
        
        # Simple response function
        def send_response(content, content_type="text/html"):
            
            try:
                response = f"HTTP/1.0 200 OK\r\n"
                response += f"Content-Type: {content_type}\r\n"
                response += "Connection: close\r\n\r\n"
                client.write(response.encode())
                
                # Send content in small chunks
                chunk_size = 256
                for i in range(0, len(content), chunk_size):
                    chunk = content[i:i + chunk_size]
                    client.write(chunk.encode() if isinstance(chunk, str) else chunk)
                    time.sleep_ms(1)  # Small delay between chunks
            except Exception as e:
                print("Send error:", e)
        
        # Handle routes
        if path == "/" or path == "/index.html":
            send_response(HTML_CONTENT)
        
        elif path == "/stop":
            stop_buzzer()
            send_response("Stopped", "text/plain")
        
        elif path == "/find":
            finding_mode = True
            last_find_request = time.time()
            send_response("Finding...", "text/plain")
            
            # Beep after sending response
            for _ in range(2):
                beep(0.2, 0.1, 3)
                time.sleep(0.5)
        
        else:
            response = "HTTP/1.0 404 Not Found\r\n\r\nPage not found"
            client.write(response.encode())
            
    except Exception as e:
        print("Handler error:", e)
        try:
            client.write(b"HTTP/1.0 500 Internal Server Error\r\n\r\nServer error")
        except:
            pass
    finally:
        try:
            client.close()
        except:
            pass

def start_webserver():
    addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(1)
    print('Web server started on', addr)
    return s

# Main function
def main():
    global finding_mode, last_find_request
    
    # Start access point instead of connecting to WiFi
    ap = setup_access_point()
    
    # Start web server
    s = start_webserver()
    
    try:
        while True:
            try:
                s.settimeout(0.1)
                client, addr = s.accept()
                print('Client connected from', addr)
                handle_request(client)
            except OSError as e:
                if e.args[0] != 110: # Only print non-timeout errors
                    print("Server error:", e)
            
            # Regular distance checking
            distance = get_distance()
            if distance > 0:  # Only print valid readings
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
