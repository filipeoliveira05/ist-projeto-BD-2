import os
from datetime import datetime, timedelta
from logging.config import dictConfig
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, request
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row # To get results as dictionaries, similar to RealDictCursor
import psycopg # For psycopg.Error and psycopg.DatabaseError

# Load environment variables from .env file at the start


# --- Configuration ---
# Timezone: UTC is a common best practice for server-side applications.
# The example used 'Etc/GMT-1', which is UTC+1. Adjust if a specific timezone is strictly required.
APP_TZ_NAME = os.environ.get("APP_TZ", "UTC")
APP_TIMEZONE = ZoneInfo(APP_TZ_NAME)

# Logging Configuration
dictConfig(
    {
        "version": 1,
        "formatters": {
            "default": {
                "format": "[%(asctime)s] %(levelname)s in %(module)s:%(lineno)s - %(funcName)20s(): %(message)s",
            }
        },
        "handlers": {
            "wsgi": {
                "class": "logging.StreamHandler",
                "stream": "ext://flask.logging.wsgi_errors_stream",
                "formatter": "default",
            }
        },
        "root": {"level": os.environ.get("LOG_LEVEL", "INFO").upper(), "handlers": ["wsgi"]},
        "loggers": { # Reduce noise from common libraries unless debugging
            "werkzeug": {"level": "WARNING"},
            "psycopg": {"level": "WARNING"}, # Catches general psycopg messages
            "psycopg.pool": {"level": "WARNING"}, # Specific to pool operations
            "psycopg.connection": {"level": "WARNING"} # Specific to connection operations
        }
    }
)

app = Flask(__name__)
log = app.logger # Use 'log' for convenience, as in the example

# Database Configuration from Environment Variables
DB_NAME = os.environ.get("DB_NAME", "aviacao")
DB_USER = os.environ.get("DB_USER", "aviacao")
DB_PASS = os.environ.get("DB_PASS", "aviacao")
DB_HOST = os.environ.get("DB_HOST", "postgres") # e.g., 'localhost' for local, 'postgres' for Docker

DATABASE_URL = os.environ.get(
    "DATABASE_URL", 
    f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"
)

# Initialize Connection Pool
# autocommit=False means we need to explicitly conn.commit() or use conn.transaction()
db_pool = ConnectionPool(
    conninfo=DATABASE_URL,
    kwargs={"row_factory": dict_row, "autocommit": False},
    min_size=int(os.environ.get("DB_POOL_MIN_SIZE", 2)),
    max_size=int(os.environ.get("DB_POOL_MAX_SIZE", 10)),
    open=True,
    name="bdist_aviation_pool",
    timeout=5,
)

# --- Error Handlers ---
@app.errorhandler(Exception)
def handle_general_exception(e):
    """Generic error handler for the application."""
    log.error(f"Unhandled exception: {type(e).__name__} - {e}", exc_info=True)

    if isinstance(e, psycopg.Error):
        error_message = str(e).splitlines()[0] if str(e) else "Database error."
        status_code = 500  # Internal Server Error for generic DB errors

        # Specific handling for psycopg.DatabaseError which may carry pgcode
        pgcode = getattr(e, "pgcode", None)
        if isinstance(e, psycopg.DatabaseError) and pgcode:
            log.info(f"Database error with pgcode: {pgcode} - {error_message}")
            # 'P0001' is raise_exception (used in triggers RI-1, RI-2, RI-3)
            if pgcode == 'P0001':
                status_code = 409  # Conflict (e.g., trigger violation)
            # Integrity constraint violations (e.g., '23505' unique, '23503' foreign key)
            elif pgcode.startswith('23'): 
                status_code = 409  # Conflict
        return jsonify(status="error", message=f"Database error: {error_message}"), status_code
    
    # Handle Werkzeug HTTP exceptions (like NotFound, BadRequest)
    # These are instances of werkzeug.exceptions.HTTPException
    if hasattr(e, 'code') and isinstance(e.code, int) and 400 <= e.code < 600:
        return jsonify(status="error", message=str(e)), e.code

    # For other unhandled exceptions
    return jsonify(status="error", message=f"An unexpected internal server error occurred: {str(e)}"), 500

# --- Utility Functions (similar to example, if needed) ---
def get_current_time_app_tz():
    """Returns the current time in the application's defined timezone."""
    return datetime.now(APP_TIMEZONE)

# --- Routes ---
@app.route('/ping', methods=['GET'])
def ping_pong():
    """Simple endpoint to check if the application is active."""
    return jsonify(status="success", message="pong"), 200

@app.route('/', methods=['GET'])
def list_airports():
    log.info("Request to list all airports.")
    try:
        with db_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT nome, cidade FROM aeroporto ORDER BY nome;")
                airports = cur.fetchall()
                log.debug(f"Found {len(airports)} airports.")
        return jsonify(status="success", data=airports), 200
    except psycopg.Error as e:
        log.error(f"Database error in list_airports: {e}")
        raise # Re-raise to be caught by the global error handler

@app.route('/voos/<string:partida_codigo>/', methods=['GET'])
def list_flights_from_departure(partida_codigo):
    log.info(f"Request to list flights from departure: {partida_codigo}")
    if not (len(partida_codigo) == 3 and partida_codigo.isupper()):
        log.warning(f"Invalid departure code format: {partida_codigo}")
        return jsonify(status="error", message="Departure airport code invalid. Must be 3 uppercase letters."), 400

    # NOVO: Verificar se o aeroporto existe
    try:
        with db_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM aeroporto WHERE codigo = %s", (partida_codigo.upper(),))
                partida_exists = cur.fetchone()['count'] > 0
        if not partida_exists:
            log.warning(f"Aeroporto de partida '{partida_codigo.upper()}' não existe.")
            return jsonify(status="error", message=f"Aeroporto de partida '{partida_codigo.upper()}' não existe."), 404
    except psycopg.Error as e:
        log.error(f"Database error when checking airport existence: {e}")
        raise

    try:
        now_app_tz = get_current_time_app_tz()
        twelve_hours_later_app_tz = now_app_tz + timedelta(hours=12)
        log.debug(f"Time window for flights: {now_app_tz} to {twelve_hours_later_app_tz}")

        query = """
            SELECT v.no_serie, v.hora_partida, v.chegada AS aeroporto_chegada
            FROM voo v
            WHERE v.partida = %s
              AND v.hora_partida > %s 
              AND v.hora_partida <= %s  
            ORDER BY v.hora_partida;
        """
        with db_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (partida_codigo.upper(), now_app_tz, twelve_hours_later_app_tz))
                flights = cur.fetchall()
                log.debug(f"Found {len(flights)} flights for {partida_codigo}.")
        if not flights:
            log.info(f"No flights found for {partida_codigo} in the next 12 hours.")
            return jsonify(status="success", message=f"Não existem voos programados partindo de {partida_codigo} nas próximas 12 horas.", data=[]), 200
        return jsonify(status="success", data=flights), 200
    except psycopg.Error as e:
        log.error(f"Database error in list_flights_from_departure for {partida_codigo}: {e}")
        raise

@app.route('/voos/<string:partida_codigo>/<string:chegada_codigo>/', methods=['GET'])
def list_next_available_flights(partida_codigo, chegada_codigo):
    log.info(f"Request for next available flights: {partida_codigo} to {chegada_codigo}")
    partida_upper = partida_codigo.upper()
    chegada_upper = chegada_codigo.upper()

    if not (len(partida_upper) == 3 and partida_upper.isupper() and \
            len(chegada_upper) == 3 and chegada_upper.isupper()):
        log.warning(f"Invalid airport codes: {partida_codigo}, {chegada_codigo}")
        return jsonify(status="error", message="Airport codes invalid. Must be 3 uppercase letters."), 400
    if partida_upper == chegada_upper:
        log.warning(f"Departure and arrival airports are the same: {partida_codigo}")
        return jsonify(status="error", message="Departure and arrival airports cannot be the same."), 400

    # NOVO: Verificar se os aeroportos existem
    try:
        with db_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM aeroporto WHERE codigo = %s", (partida_upper,))
                partida_exists = cur.fetchone()['count'] > 0
                cur.execute("SELECT COUNT(*) FROM aeroporto WHERE codigo = %s", (chegada_upper,))
                chegada_exists = cur.fetchone()['count'] > 0
        if not partida_exists or not chegada_exists:
            msg = []
            if not partida_exists:
                msg.append(f"Aeroporto de partida '{partida_upper}' não existe.")
            if not chegada_exists:
                msg.append(f"Aeroporto de chegada '{chegada_upper}' não existe.")
            return jsonify(status="error", message=" ".join(msg)), 404
    except psycopg.Error as e:
        log.error(f"Database error when checking airport existence: {e}")
        raise

    try:
        # Consulta voos futuros (independentemente de lugares)
        query_all_flights = """
            SELECT v.id AS voo_id, v.no_serie, v.hora_partida
            FROM voo v
            WHERE v.partida = %s
              AND v.chegada = %s
              AND v.hora_partida > NOW()
            ORDER BY v.hora_partida
        """
        # Consulta voos com lugares disponíveis
        query_available = """
            SELECT v.id AS voo_id, v.no_serie, v.hora_partida
            FROM voo v
            JOIN aviao av ON v.no_serie = av.no_serie
            WHERE v.partida = %s
              AND v.chegada = %s
              AND v.hora_partida > NOW() 
              AND (
                  SELECT COUNT(*) FROM assento s_count WHERE s_count.no_serie = v.no_serie
              ) > (
                  SELECT COUNT(*) FROM bilhete b_count WHERE b_count.voo_id = v.id
              )
            ORDER BY v.hora_partida
            LIMIT 3;
        """
        with db_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query_all_flights, (partida_upper, chegada_upper))
                all_flights = cur.fetchall()
                cur.execute(query_available, (partida_upper, chegada_upper))
                flights = cur.fetchall()
        if not all_flights:
            return jsonify(status="success", message="Não existem voos programados para este trajeto.", data=[]), 200
        if not flights:
            return jsonify(status="success", message="Todos os voos estão lotados.", data=[]), 200
        return jsonify(status="success", data=flights), 200
    except psycopg.Error as e:
        log.error(f"Database error in list_next_available_flights for {partida_upper}-{chegada_upper}: {e}")
        raise

@app.route('/compra/<int:voo_id>/', methods=['POST'])
def purchase_tickets(voo_id):
    log.info(f"Attempting to purchase tickets for flight ID: {voo_id}")
    data = request.get_json()

    if not data:
        log.warning("Purchase attempt with missing JSON data.")
        return jsonify(status="error", message="Request data missing or invalid (JSON)."), 400

    nif_cliente = data.get('nif_cliente')
    bilhetes_a_comprar = data.get('bilhetes_a_comprar')

    if not nif_cliente or not isinstance(nif_cliente, str) or len(nif_cliente) != 9 or not nif_cliente.isdigit():
        log.warning(f"Invalid client NIF: {nif_cliente}")
        return jsonify(status="error", message="Client NIF invalid (must be a 9-digit string)."), 400
    if not bilhetes_a_comprar or not isinstance(bilhetes_a_comprar, list) or not bilhetes_a_comprar:
        log.warning("Invalid 'bilhetes_a_comprar' list.")
        return jsonify(status="error", message="List of tickets to purchase is missing or invalid."), 400

    for i, bilhete_info in enumerate(bilhetes_a_comprar):
        if not isinstance(bilhete_info, dict) or \
           'nome_passageiro' not in bilhete_info or not isinstance(bilhete_info['nome_passageiro'], str) or \
           not bilhete_info['nome_passageiro'].strip() or \
           'prim_classe' not in bilhete_info or not isinstance(bilhete_info['prim_classe'], bool):
            log.warning(f"Invalid ticket format in list at index {i}: {bilhete_info}")
            return jsonify(status="error", message=f"Invalid ticket format in list (index {i}). Each ticket must have 'nome_passageiro' (non-empty string) and 'prim_classe' (boolean)."), 400
    
    try:
        with db_pool.connection() as conn:
            with conn.transaction(): # Manages BEGIN/COMMIT/ROLLBACK
                with conn.cursor() as cur:
                    cur.execute("SELECT hora_partida, partida, no_serie FROM voo WHERE id = %s FOR UPDATE;", (voo_id,))
                    voo_info = cur.fetchone()
                    if not voo_info:
                        log.warning(f"Flight ID {voo_id} not found for purchase.")
                        return jsonify(status="error", message=f"Flight with ID {voo_id} not found."), 404
                    
                    # Use NOW() from PostgreSQL for consistent time. Both should be TIMESTAMPTZ.
                    cur.execute("SELECT NOW() as hora_atual_db;")
                    hora_venda_db = cur.fetchone()['hora_atual_db']
                    hora_partida = voo_info['hora_partida']

                    # Corrigir: garantir que hora_partida é offset-aware
                    if hora_partida.tzinfo is None:
                        hora_partida = hora_partida.replace(tzinfo=ZoneInfo("UTC"))

                    if hora_venda_db >= hora_partida:
                        log.warning(f"Purchase attempt for departed/closed flight {voo_id}. Sale time: {hora_venda_db}, Departure: {hora_partida}")
                        return jsonify(status="error", message="Cannot purchase tickets: flight has already departed or sale is too close to departure."), 409

                    if hora_venda_db >= hora_partida:
                        log.warning(f"Purchase attempt for departed/closed flight {voo_id}. Sale time: {hora_venda_db}, Departure: {hora_partida}")
                        return jsonify(status="error", message="Cannot purchase tickets: flight has already departed or sale is too close to departure."), 409

                    aeroporto_partida_voo = voo_info['partida']
                    no_serie_voo = voo_info['no_serie']  # <-- Adicione esta linha para obter o no_serie do voo

                    sql_insert_venda = """
                        INSERT INTO venda (nif_cliente, balcao, hora) 
                        VALUES (%s, %s, %s) RETURNING codigo_reserva;
                    """
                    cur.execute(sql_insert_venda, (nif_cliente, aeroporto_partida_voo, hora_venda_db))
                    codigo_reserva = cur.fetchone()['codigo_reserva']
                    log.info(f"Created new sale with reserva_codigo: {codigo_reserva} for NIF: {nif_cliente}")

                    bilhetes_comprados_detalhes = []
                    for bilhete_info in bilhetes_a_comprar:
                        nome_passageiro = bilhete_info['nome_passageiro']
                        prim_classe = bilhete_info['prim_classe']
                        preco = 500.00 if prim_classe else 150.00 

                        sql_insert_bilhete = """
                            INSERT INTO bilhete (voo_id, codigo_reserva, nome_passegeiro, preco, prim_classe, no_serie)
                            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id;
                        """
                        cur.execute(sql_insert_bilhete, (voo_id, codigo_reserva, nome_passageiro, preco, prim_classe, no_serie_voo))
                        bilhete_id_comprado = cur.fetchone()['id']
                        bilhetes_comprados_detalhes.append({
                            "id_bilhete": bilhete_id_comprado, 
                            "passageiro": nome_passageiro, 
                            "classe": "Primeira" if prim_classe else "Económica",
                            "preco": preco
                        })
                        log.debug(f"Inserted bilhete ID: {bilhete_id_comprado} for {nome_passageiro}")
            
            # Transaction committed if no exceptions
            log.info(f"Successfully purchased {len(bilhetes_comprados_detalhes)} tickets for reserva {codigo_reserva}.")
            return jsonify(status="success", 
                           message="Purchase successful.", 
                           codigo_reserva=codigo_reserva, 
                           bilhetes_comprados=bilhetes_comprados_detalhes), 201
    except psycopg.Error as e:
        log.error(f"Database error during ticket purchase for flight {voo_id}: {e}")
        raise 

@app.route('/checkin/<int:bilhete_id>/', methods=['POST'])
def checkin_ticket(bilhete_id):
    log.info(f"Attempting check-in for bilhete ID: {bilhete_id}")
    try:
        with db_pool.connection() as conn:
            with conn.transaction(): # Manages BEGIN/COMMIT/ROLLBACK
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT b.id, b.voo_id, b.prim_classe, b.lugar, 
                               v.no_serie AS aviao_do_voo_ns, v.hora_partida
                        FROM bilhete b
                        JOIN voo v ON b.voo_id = v.id
                        WHERE b.id = %s FOR UPDATE OF b;
                    """, (bilhete_id,))
                    bilhete_info = cur.fetchone()

                    if not bilhete_info:
                        log.warning(f"Bilhete ID {bilhete_id} not found for check-in.")
                        return jsonify(status="error", message=f"Ticket with ID {bilhete_id} not found."), 404
                    
                    if bilhete_info['lugar'] is not None:
                        log.warning(f"Check-in already completed for bilhete {bilhete_id}. Seat: {bilhete_info['lugar']}.")
                        return jsonify(status="error", message=f"Check-in already completed for ticket {bilhete_id}. Seat: {bilhete_info['lugar']}."), 409

                    cur.execute("SELECT NOW() as hora_atual_db;")
                    hora_atual_db = cur.fetchone()['hora_atual_db']
                    hora_partida = bilhete_info['hora_partida']

                    # Corrigir: garantir que hora_partida é offset-aware
                    if hora_partida.tzinfo is None:
                        hora_partida = hora_partida.replace(tzinfo=ZoneInfo("UTC"))

                    if hora_atual_db >= hora_partida:
                        log.warning(f"Check-in attempt for departed flight. Bilhete: {bilhete_id}. Check-in time: {hora_atual_db}, Departure: {hora_partida}")
                        return jsonify(status="error", message="Cannot check-in: flight has already departed."), 409

                    
                    voo_id = bilhete_info['voo_id']
                    classe_bilhete = bilhete_info['prim_classe']
                    aviao_ns_do_voo = bilhete_info['aviao_do_voo_ns']

                    sql_find_seat = """
                        SELECT a.lugar
                        FROM assento a
                        WHERE a.no_serie = %s
                          AND a.prim_classe = %s
                          AND NOT EXISTS (
                              SELECT 1
                              FROM bilhete b_ocupado
                              WHERE b_ocupado.voo_id = %s
                                AND b_ocupado.lugar = a.lugar
                                AND b_ocupado.no_serie = a.no_serie 
                          )
                        ORDER BY CAST(regexp_replace(a.lugar, '[A-Z]', '') AS INTEGER), regexp_replace(a.lugar, '[0-9]', '')
                        LIMIT 1;
                    """
                    cur.execute(sql_find_seat, (aviao_ns_do_voo, classe_bilhete, voo_id))
                    assento_disponivel_info = cur.fetchone()

                    if not assento_disponivel_info:
                        classe_str = "Primeira" if classe_bilhete else "Económica"
                        log.warning(f"No available seats for check-in. Bilhete: {bilhete_id}, Class: {classe_str}, Flight: {voo_id}, Plane: {aviao_ns_do_voo}")
                        return jsonify(status="error", message=f"No available seats of class {classe_str} for check-in on flight {voo_id} (plane {aviao_ns_do_voo})."), 409
                    
                    lugar_atribuido = assento_disponivel_info['lugar']
                    log.debug(f"Assigning seat {lugar_atribuido} to bilhete {bilhete_id}")

                    sql_update_bilhete = """
                        UPDATE bilhete 
                        SET lugar = %s, no_serie = %s 
                        WHERE id = %s;
                    """
                    cur.execute(sql_update_bilhete, (lugar_atribuido, aviao_ns_do_voo, bilhete_id))
            
            # Transaction committed if no exceptions
            log.info(f"Check-in successful for bilhete ID: {bilhete_id}. Seat: {lugar_atribuido}, Plane: {aviao_ns_do_voo}")
            return jsonify(status="success", 
                           message="Check-in successful.", 
                           bilhete_id=bilhete_id, 
                           lugar_atribuido=lugar_atribuido, 
                           aviao_no_serie=aviao_ns_do_voo), 200
    except psycopg.Error as e:
        log.error(f"Database error during check-in for bilhete {bilhete_id}: {e}")
        raise

if __name__ == '__main__':
    # Port configuration aligns with fly.toml (internal_port = 8080)
    # and common practice for containerized web apps.
    flask_port = int(os.environ.get("FLASK_RUN_PORT", 8080))
    # Debug mode should be disabled in production. Controlled by FLASK_DEBUG env var.
    # '1' or 'true' (case-insensitive) enables debug mode.
    flask_debug_str = os.environ.get("FLASK_DEBUG", "0").lower()
    flask_debug = flask_debug_str in ['1', 'true']
    
    log.info(f"Starting Flask application on host 0.0.0.0, port {flask_port}, debug mode: {flask_debug}")
    app.run(host='0.0.0.0', port=flask_port, debug=flask_debug)