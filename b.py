import socket
import ssl
import json
import time
import pandas as pd

# Configura tus credenciales
USERID = "16880105"
PASSWORD = "xoh94521"

# Dirección y puerto del servidor
host = 'xapi.xtb.com'
port = 5124

# Listas para almacenar los últimos valores de bid
bid_values = []

# Variables para almacenar las medias móviles anteriores
prev_media_movil_5 = None
prev_media_movil_20 = None

# Función para ajustar el precio al step size
def ajustar_precio_al_step(precio, step_size, precision):
    # Ajustar el precio para que sea un múltiplo del step size y redondear a la precisión adecuada
    return round(round(precio / step_size) * step_size, precision)

# Función para ajustar TP y SL según el bid, ask, y el step size
def ajustar_tp_sl(bid, ask, step_size, precision):
    tp_pips = 22  # Ajuste de TP/SL en pips (22 pips)

    # Calcular TP y SL para compra
    tp_compra = ask + tp_pips * 0.001
    sl_compra = ask - tp_pips * 0.001

    # Calcular TP y SL para venta
    tp_venta = bid - tp_pips * 0.001
    sl_venta = bid + tp_pips * 0.001

    # Ajustar los precios según el step size y redondear a la precisión adecuada
    tp_compra = ajustar_precio_al_step(tp_compra, step_size, precision)
    sl_compra = ajustar_precio_al_step(sl_compra, step_size, precision)
    tp_venta = ajustar_precio_al_step(tp_venta, step_size, precision)
    sl_venta = ajustar_precio_al_step(sl_venta, step_size, precision)

    return tp_compra, sl_compra, tp_venta, sl_venta

# Función para ejecutar una orden de compra o venta con TP y SL
def ejecutar_orden(s, cmd, symbol, volume, price, tp, sl):
    order_command = {
        "command": "tradeTransaction",
        "arguments": {
            "tradeTransInfo": {
                "cmd": cmd,  # 0 para compra, 1 para venta
                "symbol": symbol,
                "volume": volume,  # Volumen de la operación
                "price": price,  # Precio de la operación
                "type": 0,  # Tipo de operación: 0 para abrir la operación
                "tp": tp,  # Take Profit
                "sl": sl,  # Stop Loss
                "customComment": "Orden con TP y SL basada en medias móviles"
            }
        }
    }

    # Mostrar valores antes de ejecutar la orden
    print(f"Ejecutando orden: TP={tp}, SL={sl}, Precio={price}, Volumen={volume}")
    
    # Enviar la orden
    s.send(json.dumps(order_command).encode("UTF-8"))
    print(f'Orden enviada: {order_command}')
    
    # Recibir y mostrar la respuesta
    response = s.recv(8192)
    response_str = response.decode('utf-8')
    print('Respuesta de la orden:', response_str)

    # Procesar la respuesta
    try:
        response_data = json.loads(response_str)
        if response_data.get('status'):
            order_number = response_data.get('returnData', {}).get('order')
            print(f"Orden ejecutada correctamente. Número de orden: {order_number}")
        else:
            print(f"Error en la ejecución de la orden: {response_data.get('errorDescr')}")
    except Exception as e:
        print(f"Error procesando la respuesta de la orden: {e}")

# Conectar al servidor
try:
    ip_address = socket.getaddrinfo(host, port)[0][4][0]
    print(f'Dirección IP obtenida: {ip_address}')
    
    context = ssl.create_default_context()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((ip_address, port))
        with context.wrap_socket(sock, server_hostname=host) as s:

            # Comando de login
            login_command = {
                "command": "login",
                "arguments": {
                    "userId": USERID,
                    "password": PASSWORD
                }
            }
            
            # Enviar comando de login
            packet = json.dumps(login_command)
            s.send(packet.encode("UTF-8"))
            print(f'Comando enviado: {login_command}')
            
            # Recibir respuesta
            response = s.recv(8192)
            response_str = response.decode('utf-8')
            print('Respuesta de login:', response_str)

            try:
                login_response = json.loads(response_str)
            except json.JSONDecodeError:
                print("Error: Respuesta no es un JSON válido.")
                raise

            if login_response.get('status') and 'streamSessionId' in login_response:
                stream_session_id = login_response['streamSessionId']
                print(f'Stream Session ID obtenido: {stream_session_id}')
            else:
                raise Exception("Login fallido o streamSessionId no disponible.")

            symbol_to_check = "BITCOIN"
            volume = 0.1  # Volumen de la operación

            # Obtener información del símbolo para conocer el step size
            get_symbol_command = {
                "command": "getSymbol",
                "arguments": {
                    "symbol": symbol_to_check
                }
            }
            
            s.send(json.dumps(get_symbol_command).encode('UTF-8'))
            response = s.recv(8192)
            symbol_info = response.decode('utf-8')
            symbol_response = json.loads(symbol_info)

            # Imprimir la respuesta completa del símbolo para depuración
            print("Respuesta completa del símbolo:", symbol_response)

            if symbol_response.get('status'):
                # Revisa la estructura de los datos recibidos y ajusta las claves
                return_data = symbol_response['returnData']
                
                # Ajusta según la clave correcta que contenga el tamaño del paso y precisión
                # (Modifica 'lotStep' si la clave es diferente en la respuesta)
                step_size = return_data.get('lotStep')  # Ajusta si la clave es diferente
                precision = return_data.get('precision')  # Ajusta si la clave es diferente
                
                print(f'Step size: {step_size}, Precisión: {precision}')
            else:
                raise Exception("No se pudo obtener la información del símbolo.")

            # Bucle para recalcular bid y ask cada 15 segundos
            while True:
                media_movil_5 = None
                media_movil_20 = None

                get_symbol_command = {
                    "command": "getSymbol",
                    "arguments": {
                        "symbol": symbol_to_check
                    }
                }

                s.send(json.dumps(get_symbol_command).encode('UTF-8'))
                response = s.recv(8192)
                symbol_info = response.decode('utf-8')

                symbol_response = json.loads(symbol_info)
                if symbol_response.get('status'):
                    return_data = symbol_response.get('returnData', {})
                    bid = return_data.get('bid')
                    ask = return_data.get('ask')

                    print(f'Bid actual: {bid}, Ask actual: {ask}')

                    # Agregar el bid a la lista de valores
                    bid_values.append(bid)

                    # Mantener los últimos 80 valores
                    if len(bid_values) > 80:
                        bid_values.pop(0)

                    # Convertir a DataFrame para usar las medias móviles nativas de pandas
                    df = pd.DataFrame(bid_values, columns=['close'])

                    # Calcular medias móviles usando pandas
                    if len(df) >= 5:
                        df['SMA_5'] = df['close'].rolling(window=5).mean()
                        media_movil_5 = df['SMA_5'].iloc[-1]

                    if len(df) >= 20:
                        df['SMA_20'] = df['close'].rolling(window=20).mean()
                        media_movil_20 = df['SMA_20'].iloc[-1]

                    # Solo proceder si ambas medias móviles están calculadas
                    if media_movil_5 is not None and media_movil_20 is not None:
                        if prev_media_movil_5 is not None and prev_media_movil_20 is not None:
                            # Señal de compra
                            if prev_media_movil_5 <= prev_media_movil_20 and media_movil_5 > media_movil_20:
                                print("Señal de COMPRA detectada.")
                                tp_compra, sl_compra, _, _ = ajustar_tp_sl(bid, ask, step_size, precision)
                                ejecutar_orden(s, 0, symbol_to_check, volume, ask, tp_compra, sl_compra)

                            # Señal de venta
                            elif prev_media_movil_5 >= prev_media_movil_20 and media_movil_5 < media_movil_20:
                                print("Señal de VENTA detectada.")
                                _, _, tp_venta, sl_venta = ajustar_tp_sl(bid, ask, step_size, precision)
                                ejecutar_orden(s, 1, symbol_to_check, volume, bid, tp_venta, sl_venta)

                        # Actualizar las medias móviles anteriores
                        prev_media_movil_5 = media_movil_5
                        prev_media_movil_20 = media_movil_20

                # Esperar 15 segundos antes de la siguiente iteración
                time.sleep(15)

except Exception as e:
    print(f'Error: {e}')
