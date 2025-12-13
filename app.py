from flask import Flask, render_template, jsonify, request
import requests
import math
import statistics

app = Flask(__name__)

# URL de tu base de datos Firebase
FIREBASE_URL = "https://recolectores-de-datos-p6-default-rtdb.firebaseio.com/sensores.json"

# --- FUNCIÓN LÓGICA DE NEGOCIO ---
def analizar_datos(data_actual, historial=[]):
    """
    Analiza los datos. 
    Para movimiento: Compara el punto actual con el anterior inmediato.
    """
    resultado = {
        "co2_estado": "Desconocido",
        "co2_clase": "secondary",
        "co2_mensaje": "",
        "gas_estado": "Desconocido",
        "gas_clase": "secondary",
        "gas_mensaje": "",
        "movimiento": "Calculando...",
        "mov_clase": "secondary"
    }

    # 1. ANÁLISIS DE CO2
    co2 = data_actual.get("co2", 0)
    if co2 < 800:
        resultado["co2_estado"] = "Aire Limpio"
        resultado["co2_clase"] = "success" 
        resultado["co2_mensaje"] = "Ambiente seguro."
    elif 800 <= co2 < 1500:
        resultado["co2_estado"] = "Precaución"
        resultado["co2_clase"] = "warning"
        resultado["co2_mensaje"] = "Aire viciado. Abre un poco las ventanas."
    else:
        resultado["co2_estado"] = "PELIGROSO"
        resultado["co2_clase"] = "danger"
        resultado["co2_mensaje"] = "¡BAJA LAS VENTANAS! Niveles tóxicos de CO2."

    # 2. ANÁLISIS DE GAS
    gas = data_actual.get("gas", 0)
    if gas < 300:
        resultado["gas_estado"] = "Normal"
        resultado["gas_clase"] = "success"
        resultado["gas_mensaje"] = "Sin presencia de gases."
    elif 300 <= gas < 550:
        resultado["gas_estado"] = "Atención"
        resultado["gas_clase"] = "warning"
        resultado["gas_mensaje"] = "Posible humo de escape detectado."
    else:
        resultado["gas_estado"] = "FUGA / HUMO"
        resultado["gas_clase"] = "danger"
        resultado["gas_mensaje"] = "¡PELIGRO CRÍTICO! Detén el vehículo."

    # 3. DETECCIÓN DE MOVIMIENTO (Lógica de Cambio Inmediato)
    if len(historial) >= 2:
        curr_acc = historial[-1].get("acelerometro", {"x": 0, "y": 0, "z": 0})
        prev_acc = historial[-2].get("acelerometro", {"x": 0, "y": 0, "z": 0})

        dx = curr_acc.get("x", 0) - prev_acc.get("x", 0)
        dy = curr_acc.get("y", 0) - prev_acc.get("y", 0)
        dz = curr_acc.get("z", 0) - prev_acc.get("z", 0)
        
        delta_total = math.sqrt(dx**2 + dy**2 + dz**2)
        
        if delta_total > 0.15:
            resultado["movimiento"] = "EN MOVIMIENTO"
            resultado["mov_clase"] = "primary"
        else:
            resultado["movimiento"] = "DETENIDO"
            resultado["mov_clase"] = "secondary"
    else:
        resultado["movimiento"] = "ESPERANDO DATOS..."
        resultado["mov_clase"] = "secondary"

    return resultado

@app.route('/')
def index():
    return render_template('index.html')

# --- NUEVA RUTA: HISTORIAL ---
@app.route('/api/history')
def get_history():
    try:
        limit = request.args.get('limit', 20)        
        url = f'{FIREBASE_URL}?orderBy="$key"&limitToLast={limit}'
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            if data:
                lista = []
                for k, v in data.items():
                    v['firebase_id'] = k
                    lista.append(v)
                
                # Ordenar inverso (El más nuevo primero)
                lista.reverse()
                
                return jsonify({"status": "success", "data": lista})
            else:
                 return jsonify({"status": "empty", "data": []})
        else:
            return jsonify({"status": "error", "message": "Error Firebase"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/data')
def get_data():
    try:
        response = requests.get(FIREBASE_URL + '?orderBy="$key"&limitToLast=5')
        
        if response.status_code == 200:
            data = response.json()
            
            if data:
                keys = sorted(data.keys())
                last_key = keys[-1]
                last_entry = data[last_key]
                historial = [data[k] for k in keys]
                
                analisis = analizar_datos(last_entry, historial)
                
                return jsonify({
                    "status": "success",
                    "data": last_entry,
                    "analisis": analisis
                })
            else:
                return jsonify({"status": "empty", "message": "No hay datos en Firebase"})
        else:
            return jsonify({"status": "error", "message": "Error conectando a Firebase"})
            
    except Exception as e:
        # Fallback simple
        try:
             response = requests.get(FIREBASE_URL)
             if response.status_code == 200:
                 data = response.json()
                 if data:
                    keys = sorted(data.keys())
                    last_entry = data[keys[-1]]
                    historial = [data[k] for k in keys[-5:]]
                    analisis = analizar_datos(last_entry, historial)
                    return jsonify({"status": "success", "data": last_entry, "analisis": analisis})
        except:
            pass
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)