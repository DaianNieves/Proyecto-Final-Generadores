// ==========================================
// 1. CONFIGURACIÓN DEL MAPA (LEAFLET)
// ==========================================
var map = L.map('map').setView([0, 0], 2);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

var carIcon = L.divIcon({
    html: '<i class="fas fa-car fa-2x text-primary" style="text-shadow: 2px 2px 4px rgba(0,0,0,0.5);"></i>',
    className: 'custom-div-icon',
    iconSize: [30, 30],
    iconAnchor: [15, 15]
});

var marker = L.marker([0, 0], {icon: carIcon}).addTo(map);
var firstLoad = true;

// ==========================================
// 2. CONFIGURACIÓN DE LA GRÁFICA (CHART.JS)
// ==========================================
var ctx = document.getElementById('sensorChart').getContext('2d');
var chart = new Chart(ctx, {
    type: 'line',
    data: {
        labels: [],
        datasets: [
            { 
                label: 'Gas', 
                borderColor: '#ffc107', 
                data: [], 
                tension: 0.3, 
                fill: true, 
                backgroundColor: 'rgba(255, 193, 7, 0.1)' 
            },
            { 
                label: 'CO2', 
                borderColor: '#0dcaf0', 
                data: [], 
                tension: 0.3, 
                fill: true, 
                backgroundColor: 'rgba(13, 202, 240, 0.1)' 
            }
        ]
    },
    options: { 
        responsive: true, 
        maintainAspectRatio: false, 
        scales: { x: { display: false } }, 
        animation: { duration: 0 } 
    }
});

// ==========================================
// 3. LÓGICA DE DATOS EN TIEMPO REAL
// ==========================================
function fetchData() {
    fetch('/api/data')
        .then(r => r.json())
        .then(res => {
            if(res.status === "success") {
                updateUI(res.data, res.analisis);
                document.getElementById('connectionStatus').classList.remove('bg-danger');
                document.getElementById('connectionStatus').classList.add('bg-success');
            }
        })
        .catch(err => {
            console.error(err);
            document.getElementById('connectionStatus').classList.remove('bg-success');
            document.getElementById('connectionStatus').classList.add('bg-danger');
        });
}

function updateUI(data, analisis) {
    // Actualizar valores numéricos
    document.getElementById('valCO2').innerText = data.co2;
    document.getElementById('valGas').innerText = data.gas;
    document.getElementById('accX').innerText = data.acelerometro.x.toFixed(2);
    document.getElementById('accY').innerText = data.acelerometro.y.toFixed(2);
    document.getElementById('accZ').innerText = data.acelerometro.z.toFixed(2);
    document.getElementById('accStateText').innerText = analisis.movimiento;

    // Actualizar Estado del Vehículo (Badge superior)
    const vStatus = document.getElementById('vehicleStatus');
    vStatus.className = `badge bg-${analisis.mov_clase} fs-5 me-3`;
    vStatus.innerHTML = analisis.mov_clase === 'primary' 
        ? '<i class="fas fa-running"></i> ' + analisis.movimiento 
        : '<i class="fas fa-parking"></i> ' + analisis.movimiento;

    // Actualizar tarjetas de sensores
    updateCardStatus('cardCO2', 'statusCO2', 'msgCO2', analisis.co2_estado, analisis.co2_clase, analisis.co2_mensaje);
    updateCardStatus('cardGas', 'statusGas', 'msgGas', analisis.gas_estado, analisis.gas_clase, analisis.gas_mensaje);

    // Alerta Global
    const globalAlert = document.getElementById('globalAlert');
    if(analisis.co2_clase === 'danger' || analisis.gas_clase === 'danger') {
        globalAlert.classList.remove('d-none');
        document.getElementById('globalAlertText').innerText = analisis.co2_clase === 'danger' ? analisis.co2_mensaje : analisis.gas_mensaje;
    } else {
        globalAlert.classList.add('d-none');
    }

    // Actualizar Mapa
    if (data.ubicacion.latitud !== 0) {
        const lat = data.ubicacion.latitud;
        const lon = data.ubicacion.longitud;
        marker.setLatLng([lat, lon]);
        document.getElementById('gpsCoords').innerText = `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
        
        if (firstLoad) { 
            map.setView([lat, lon], 16); 
            firstLoad = false; 
        } else { 
            map.panTo([lat, lon]); 
        }
    }

    // Actualizar Gráfica
    const now = new Date().toLocaleTimeString();
    if (chart.data.labels.length > 20) { 
        chart.data.labels.shift(); 
        chart.data.datasets.forEach(d => d.data.shift()); 
    }
    chart.data.labels.push(now);
    chart.data.datasets[0].data.push(data.gas);
    chart.data.datasets[1].data.push(data.co2);
    chart.update();
}

function updateCardStatus(cardId, badgeId, msgId, estado, clase, mensaje) {
    const card = document.getElementById(cardId);
    const badge = document.getElementById(badgeId);
    const msg = document.getElementById(msgId);
    
    badge.className = `badge bg-${clase} status-badge`;
    badge.innerText = estado;
    msg.innerText = mensaje;
    
    if(clase === 'danger') {
        card.classList.add('danger-card', 'blink-bg');
    } else {
        card.classList.remove('danger-card', 'blink-bg');
    }
}

// ==========================================
// 4. LÓGICA DE HISTORIAL (FIREBASE)
// ==========================================

function decodeFirebaseTime(id) {
    if (!id || typeof id !== 'string' || id.length < 8) return null;
    const PUSH_CHARS = "-0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz";
    let time = 0;
    for (let i = 0; i < 8; i++) {
        const c = id.charAt(i);
        const idx = PUSH_CHARS.indexOf(c);
        if (idx === -1) return null;
        time = time * 64 + idx;
    }
    return new Date(time);
}

function cargarHistorial() {
    const limit = document.getElementById('limitSelector').value;
    const tbody = document.getElementById('historyTableBody');
    tbody.innerHTML = '<tr><td colspan="5"><i class="fas fa-spinner fa-spin"></i> Cargando datos...</td></tr>';

    fetch(`/api/history?limit=${limit}`)
        .then(r => r.json())
        .then(res => {
            tbody.innerHTML = ''; 
            if(res.status === "success" && res.data.length > 0) {
                res.data.forEach(item => {
                    let etiquetaTiempo = "";
                    
                    // Decodificar fecha del ID
                    let dateObj = decodeFirebaseTime(item.firebase_id);
                    
                    if (dateObj && dateObj.getFullYear() > 2020) {
                        etiquetaTiempo = dateObj.toLocaleString('es-MX', { 
                            month: '2-digit', day: '2-digit',
                            hour: '2-digit', minute: '2-digit', second: '2-digit',
                            hour12: true
                        });
                    } else if(item.uptime_ms) {
                        etiquetaTiempo = (item.uptime_ms / 1000).toFixed(0) + "s (uptime)";
                    } else {
                        etiquetaTiempo = "ID: " + String(item.firebase_id).slice(-6);
                    }

                    const accStr = `X:${item.acelerometro.x.toFixed(1)} Y:${item.acelerometro.y.toFixed(1)} Z:${item.acelerometro.z.toFixed(1)}`;
                    
                    const row = `
                        <tr>
                            <td><span class="badge bg-light text-dark border fw-bold">${etiquetaTiempo}</span></td>
                            <td>${item.co2}</td>
                            <td>${item.gas}</td>
                            <td class="small">${accStr}</td>
                            <td>
                                <a href="https://maps.google.com/?q=${item.ubicacion.latitud},${item.ubicacion.longitud}" target="_blank" class="text-decoration-none">
                                    <i class="fas fa-map-marker-alt text-danger"></i> Ver Mapa
                                </a>
                            </td>
                        </tr>
                    `;
                    tbody.innerHTML += row;
                });
            } else {
                tbody.innerHTML = '<tr><td colspan="5" class="text-muted">No se encontraron datos.</td></tr>';
            }
        })
        .catch(err => {
            console.error(err);
            tbody.innerHTML = '<tr><td colspan="5" class="text-danger">Error al cargar datos.</td></tr>';
        });
}

// ==========================================
// 5. INICIO DEL BUCLE
// ==========================================
setInterval(fetchData, 2000); // Polling cada 2 segundos
fetchData(); // Primera llamada inmediata