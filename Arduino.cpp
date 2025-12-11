#include <TinyGPS++.h>
#include <SoftwareSerial.h>
#include <Wire.h>               
#include "Adafruit_CCS811.h"    

// ==========================================
// 1. CONFIGURACIÓN
// ==========================================
// GPS conectado a pines 4 (RX) y 3 (TX)
static const int RXPin = 4;
static const int TXPin = 3;
static const uint32_t GPSBaud = 9600;

TinyGPSPlus gps;
SoftwareSerial ss(RXPin, TXPin);
Adafruit_CCS811 ccs;

const int PIN_MQ7 = A0; 
const int MPU_ADDR = 0x68; 
unsigned long lastUpdate = 0; 

// ==========================================
// 2. ESTRUCTURA DE ALTA RESOLUCIÓN (16 BITS)
// ==========================================
struct DatosSensores {
  uint16_t nivelGas;      
  uint16_t nivelCO2;      
  uint16_t movimientoX;   
  uint16_t movimientoY;   
  uint16_t movimientoZ;   
  uint16_t gpsLat_High; 
  uint16_t gpsLat_Low;  
  uint16_t gpsLon_High; 
  uint16_t gpsLon_Low;  
};

// LLAVE DE CIFRADO (XOR)
const DatosSensores llave = {
  0b1010101010101010, // Gas
  0b1100110011001100, // CO2
  0b1111000011110000, // Mov X
  0b0000111100001111, // Mov Y
  0b1010010110100101, // Mov Z
  0b0101010101010101, // Lat High
  0b1010101010101010, // Lat Low
  0b1110011111100111, // Lon High
  0b0001100000011000  // Lon Low
};

void setup() {
  // Serial Hardware (Pines 0 y 1) se usará para enviar a la Raspberry
  // Y también para ver en el monitor serial (USB)
  Serial.begin(9600);
  
  ss.begin(GPSBaud); 
  Wire.begin(); 
  pinMode(PIN_MQ7, INPUT);
  
  // Despertar MPU6050
  Wire.beginTransmission(MPU_ADDR); Wire.write(0x6B); Wire.write(0); Wire.endTransmission();
  
  if(!ccs.begin()) Serial.println(F("LOG: Fallo CCS811"));

  // Mensaje de inicio (La Raspberry ignorará esto porque no tiene formato de trama)
  Serial.println(F("LOG: Sistema Iniciado."));
  delay(1000);
}

void loop() {
  // Lectura constante del GPS
  while (ss.available() > 0) gps.encode(ss.read());

  // Enviar paquete cada 5 segundos
  if (millis() - lastUpdate > 5000) {
    procesarDatosFullResolution();
    lastUpdate = millis(); 
  }
}

void procesarDatosFullResolution() {
  DatosSensores datosOriginales;

  // --- A. LECTURA SENSORS ---
  datosOriginales.nivelGas = analogRead(PIN_MQ7);

  if(ccs.available() && !ccs.readData()){
    datosOriginales.nivelCO2 = ccs.geteCO2();
  } else {
    datosOriginales.nivelCO2 = 0;
  }

  // Lectura MPU6050
  Wire.beginTransmission(MPU_ADDR); 
  Wire.write(0x3B); Wire.endTransmission(false);
  Wire.requestFrom(MPU_ADDR, 6, true);
  
  if (Wire.available() >= 6) {
    int16_t rawX = Wire.read() << 8 | Wire.read();
    int16_t rawY = Wire.read() << 8 | Wire.read();
    int16_t rawZ = Wire.read() << 8 | Wire.read();
    datosOriginales.movimientoX = (uint16_t)rawX;
    datosOriginales.movimientoY = (uint16_t)rawY;
    datosOriginales.movimientoZ = (uint16_t)rawZ;
  } else {
    datosOriginales.movimientoX = 0; datosOriginales.movimientoY = 0; datosOriginales.movimientoZ = 0;
  }

  // Lectura y Conversión GPS
  if (gps.location.isValid()) {
    int32_t latEntera = (int32_t)(gps.location.lat() * 1000000.0);
    datosOriginales.gpsLat_High = (uint16_t)((latEntera >> 16) & 0xFFFF); 
    datosOriginales.gpsLat_Low  = (uint16_t)(latEntera & 0xFFFF);         

    int32_t lonEntera = (int32_t)(gps.location.lng() * 1000000.0);
    datosOriginales.gpsLon_High = (uint16_t)((lonEntera >> 16) & 0xFFFF);
    datosOriginales.gpsLon_Low  = (uint16_t)(lonEntera & 0xFFFF);
  } else {
    datosOriginales.gpsLat_High = 0; datosOriginales.gpsLat_Low  = 0;
    datosOriginales.gpsLon_High = 0; datosOriginales.gpsLon_Low  = 0;
  }

  // --- B. CIFRADO (XOR) ---
  DatosSensores datosCifrados;
  datosCifrados.nivelGas      = datosOriginales.nivelGas ^ llave.nivelGas;
  datosCifrados.nivelCO2      = datosOriginales.nivelCO2 ^ llave.nivelCO2;
  datosCifrados.movimientoX   = datosOriginales.movimientoX ^ llave.movimientoX;
  datosCifrados.movimientoY   = datosOriginales.movimientoY ^ llave.movimientoY;
  datosCifrados.movimientoZ   = datosOriginales.movimientoZ ^ llave.movimientoZ;
  datosCifrados.gpsLat_High   = datosOriginales.gpsLat_High ^ llave.gpsLat_High;
  datosCifrados.gpsLat_Low    = datosOriginales.gpsLat_Low  ^ llave.gpsLat_Low;
  datosCifrados.gpsLon_High   = datosOriginales.gpsLon_High ^ llave.gpsLon_High;
  datosCifrados.gpsLon_Low    = datosOriginales.gpsLon_Low  ^ llave.gpsLon_Low;

  // --- C. ENVÍO DE DATOS ---
  
  // 1. Mostrar en Monitor Serial (para humanos)
  Serial.println(F("\n--- MONITOR (Depuración) ---"));
  imprimirDatosClaros(datosOriginales); // Mostramos los originales para comparar

  // 2. ENVIAR TRAMA A RASPBERRY (Datos Cifrados)
  // Esta función envía el string especial que leerá la Raspberry
  enviarTramaRaspberry(datosCifrados);
}

// --------------------------------------------------------
// FUNCIÓN CLAVE: Genera el string para la Raspberry
// Formato: >Val1,Val2,Val3,Val4,Val5,Val6,Val7,Val8,Val9<
// --------------------------------------------------------
void enviarTramaRaspberry(const DatosSensores& d) {
  Serial.print(">"); // Carácter de INICIO
  
  Serial.print(d.nivelGas);    Serial.print(",");
  Serial.print(d.nivelCO2);    Serial.print(",");
  Serial.print(d.movimientoX); Serial.print(",");
  Serial.print(d.movimientoY); Serial.print(",");
  Serial.print(d.movimientoZ); Serial.print(",");
  Serial.print(d.gpsLat_High); Serial.print(",");
  Serial.print(d.gpsLat_Low);  Serial.print(",");
  Serial.print(d.gpsLon_High); Serial.print(",");
  Serial.print(d.gpsLon_Low);
  
  Serial.println("<"); // Carácter de FIN
}

// Función auxiliar para ver datos claros en el monitor
void imprimirDatosClaros(const DatosSensores& d) {
  Serial.print(F("Gas: ")); Serial.print(d.nivelGas);
  Serial.print(F(" | CO2: ")); Serial.println(d.nivelCO2);
  Serial.print(F("Mov X: ")); Serial.print((int16_t)d.movimientoX);
  
  // Reconstrucción visual GPS
  int32_t latRec = ((int32_t)d.gpsLat_High << 16) | d.gpsLat_Low;
  int32_t lonRec = ((int32_t)d.gpsLon_High << 16) | d.gpsLon_Low;
  Serial.print(F(" | GPS Lat: ")); Serial.print(latRec / 1000000.0, 6);
  Serial.print(F(", Lon: ")); Serial.println(lonRec / 1000000.0, 6);
}