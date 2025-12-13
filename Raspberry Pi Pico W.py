from machine import UART, Pin
import time
import network   
import urequests 
import ujson     

# CREDENCIALES Y CONFIGURACIÓN DE RED
WIFI_SSID = "Computo"
WIFI_PASS = "Centro20#25Computo?"
FIREBASE_URL = "https://recolectores-de-datos-p6-default-rtdb.firebaseio.com/sensores.json"

# CONFIGURACIÓN UART (SERIAL)
# UART 0, Baudrate 9600 (Igual que Arduino), TX=GP0, RX=GP1
uart = UART(1, baudrate=9600, tx=Pin(8), rx=Pin(9))

# 2. LLAVE DE CIFRADO
KEY_GAS      = 0b1010101010101010
KEY_CO2      = 0b1100110011001100
KEY_MOV_X    = 0b1111000011110000
KEY_MOV_Y    = 0b0000111100001111
KEY_MOV_Z    = 0b1010010110100101
KEY_LAT_HIGH = 0b0101010101010101
KEY_LAT_LOW  = 0b1010101010101010
KEY_LON_HIGH = 0b1110011111100111
KEY_LON_LOW  = 0b0001100000011000

print("=== SISTEMA IOT: RECEPCIÓN, DESCIFRADO Y NUBE ===")

# --- FUNCIÓN PARA CONECTAR A WIFI ---
def conectar_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASS)

    print(f"Conectando a {WIFI_SSID}...")
    max_wait = 20
    while max_wait > 0:
        if wlan.status() < 0 or wlan.status() >= 3:
            break
        max_wait -= 1
        print('Esperando conexión...')
        time.sleep(1)

    if wlan.status() != 3:
        print('Error: No se pudo conectar al WiFi')
        return False
    else:
        print('¡Conectado! IP:', wlan.ifconfig()[0])
        return True

if not conectar_wifi():
    print("ADVERTENCIA: Trabajando sin conexión a internet.")

def enviar_a_firebase(datos_dict):
    try:
        # Convertimos el diccionario a JSON string
        json_data = ujson.dumps(datos_dict)
        response = urequests.post(FIREBASE_URL, data=json_data)
        
        if response.status_code == 200:
            print(">> Datos enviados a Firebase correctamente.")
        else:
            print(f">> Error Firebase: {response.status_code}")
            
        response.close() # Importante cerrar para liberar memoria
    except Exception as e:
        print(f">> Error de red: {e}")

def procesar_trama(trama):
    try:
        partes = trama.split(',')
        if len(partes) != 9:
            print("Error: Trama incompleta")
            return

        # Convertir texto a enteros (CIFRADOS)
        cif_gas      = int(partes[0])
        cif_co2      = int(partes[1])
        cif_mov_x    = int(partes[2])
        cif_mov_y    = int(partes[3])
        cif_mov_z    = int(partes[4])
        cif_lat_h    = int(partes[5])
        cif_lat_l    = int(partes[6])
        cif_lon_h    = int(partes[7])
        cif_lon_l    = int(partes[8])

        # DESCIFRAR
        val_gas   = cif_gas   ^ KEY_GAS
        val_co2   = cif_co2   ^ KEY_CO2
        val_mov_x = cif_mov_x ^ KEY_MOV_X
        val_mov_y = cif_mov_y ^ KEY_MOV_Y
        val_mov_z = cif_mov_z ^ KEY_MOV_Z
        val_lat_h = cif_lat_h ^ KEY_LAT_HIGH
        val_lat_l = cif_lat_l ^ KEY_LAT_LOW
        val_lon_h = cif_lon_h ^ KEY_LON_HIGH
        val_lon_l = cif_lon_l ^ KEY_LON_LOW

        # RECONSTRUCCIÓN
        def signed_16(val):
            if val > 32767: return val - 65536
            return val

        acc_x_g = signed_16(val_mov_x) / 16384.0
        acc_y_g = signed_16(val_mov_y) / 16384.0
        acc_z_g = signed_16(val_mov_z) / 16384.0

        lat_entera = (val_lat_h << 16) | val_lat_l
        lon_entera = (val_lon_h << 16) | val_lon_l
        
        if lat_entera > 2147483647: lat_entera -= 4294967296
        if lon_entera > 2147483647: lon_entera -= 4294967296

        gps_lat = lat_entera / 1000000.0
        gps_lon = lon_entera / 1000000.0

        # IMPRIMIR REPORTE LOCAL
        print(f"Gas: {val_gas} | CO2: {val_co2} | GPS: {gps_lat}, {gps_lon}")

        # PREPARAR Y ENVIAR JSON A FIREBASE
        objeto_json = {
            "gas": val_gas,
            "co2": val_co2,
            "acelerometro": {
                "x": acc_x_g,
                "y": acc_y_g,
                "z": acc_z_g
            },
            "ubicacion": {
                "latitud": gps_lat,
                "longitud": gps_lon
            },
            # Timestamp simple (tiempo desde arranque) para referencia
            "uptime_ms": time.ticks_ms()
        }
        
        enviar_a_firebase(objeto_json)

    except ValueError:
        print("Error: Datos corruptos en la trama")

buffer_serial = ""

while True:
    if uart.any():
        try:
            data = uart.read().decode('utf-8')
            buffer_serial += data
            if '>' in buffer_serial and '<' in buffer_serial:
                inicio = buffer_serial.find('>')
                fin = buffer_serial.find('<')
                if fin > inicio:
                    trama_limpia = buffer_serial[inicio+1 : fin]
                    procesar_trama(trama_limpia)
                    buffer_serial = buffer_serial[fin+1:]
                else:
                    buffer_serial = ""
        except Exception as e:
            print(f"Error Serial: {e}")
            buffer_serial = ""
    time.sleep(0.01)