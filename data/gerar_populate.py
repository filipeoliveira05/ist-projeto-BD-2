import random
import datetime
from faker import Faker
import math

fake = Faker()
Faker.seed(0) # for reproducibility
random.seed(0)

# --- Configuration ---
NUM_AIRPORTS_MIN = 10
NUM_CITIES_WITH_TWO_AIRPORTS = 2 # This is ensured by the AIRPORTS_DATA list
NUM_AIRPLANES_MIN = 12 # Aumentado de 10
NUM_AIRPLANE_MODELS_MIN = 3
FLIGHTS_PER_DAY_MIN = 10 # Aumentado de 5
START_DATE = datetime.date(2025, 1, 1)
END_DATE = datetime.date(2025, 7, 31)
CURRENT_DATETIME = datetime.datetime(2025, 6, 17, 14, 0, 0) # As per problem statement
NUM_SALES_MIN = 300000 # Aumentado de 10000
NUM_TICKETS_MIN = 700000 # Aumentado de 30000

# --- Schema Definition (as provided, cannot be changed by this script) ---
SCHEMA_SQL = """
DROP TABLE IF EXISTS aeroporto CASCADE;
DROP TABLE IF EXISTS aviao CASCADE;
DROP TABLE IF EXISTS assento CASCADE;
DROP TABLE IF EXISTS voo CASCADE;
DROP TABLE IF EXISTS venda CASCADE;
DROP TABLE IF EXISTS bilhete CASCADE;

CREATE TABLE aeroporto(
    codigo CHAR(3) PRIMARY KEY CHECK (codigo ~ '^[A-Z]{3}$'),
    nome VARCHAR(80) NOT NULL,
    cidade VARCHAR(255) NOT NULL,
    pais VARCHAR(255) NOT NULL,
    UNIQUE (nome, cidade)
);

CREATE TABLE aviao(
    no_serie VARCHAR(80) PRIMARY KEY,
    modelo VARCHAR(80) NOT NULL
);

CREATE TABLE assento (
    lugar VARCHAR(3) CHECK (lugar ~ '^[0-9]{1,2}[A-Z]$'),
    no_serie VARCHAR(80) REFERENCES aviao,
    prim_classe BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (lugar, no_serie)
);

CREATE TABLE voo (
    id SERIAL PRIMARY KEY,
    no_serie VARCHAR(80) REFERENCES aviao,
    hora_partida TIMESTAMP,
    hora_chegada TIMESTAMP, 
    partida CHAR(3) REFERENCES aeroporto(codigo),
    chegada CHAR(3) REFERENCES aeroporto(codigo),
    UNIQUE (no_serie, hora_partida),
    UNIQUE (no_serie, hora_chegada),
    UNIQUE (hora_partida, partida, chegada),
    UNIQUE (hora_chegada, partida, chegada),
    CHECK (partida!=chegada),
    CHECK (hora_partida<=hora_chegada)
);

CREATE TABLE venda (
    codigo_reserva SERIAL PRIMARY KEY,
    nif_cliente CHAR(9) NOT NULL,
    balcao CHAR(3) REFERENCES aeroporto(codigo),
    hora TIMESTAMP
);

CREATE TABLE bilhete (
    id SERIAL PRIMARY KEY,
    voo_id INTEGER REFERENCES voo,
    codigo_reserva INTEGER REFERENCES venda,
    nome_passegeiro VARCHAR(80),
    preco NUMERIC(7,2) NOT NULL,
    prim_classe BOOLEAN NOT NULL DEFAULT FALSE,
    lugar VARCHAR(3),
    no_serie VARCHAR(80),
    UNIQUE (voo_id, codigo_reserva, nome_passegeiro),
    FOREIGN KEY (lugar, no_serie) REFERENCES assento
);
"""

# --- Data Definitions ---
AIRPORTS_DATA = [
    {"codigo": "LHR", "nome": "London Heathrow", "cidade": "London", "pais": "United Kingdom"},
    {"codigo": "LGW", "nome": "London Gatwick", "cidade": "London", "pais": "United Kingdom"}, # London has 2
    {"codigo": "CDG", "nome": "Paris Charles de Gaulle", "cidade": "Paris", "pais": "France"},
    {"codigo": "ORY", "nome": "Paris Orly", "cidade": "Paris", "pais": "France"}, # Paris has 2
    {"codigo": "AMS", "nome": "Amsterdam Schiphol", "cidade": "Amsterdam", "pais": "Netherlands"},
    {"codigo": "FRA", "nome": "Frankfurt Airport", "cidade": "Frankfurt", "pais": "Germany"},
    {"codigo": "MAD", "nome": "Madrid Barajas", "cidade": "Madrid", "pais": "Spain"},
    {"codigo": "LIS", "nome": "Lisbon Airport", "cidade": "Lisbon", "pais": "Portugal"},
    {"codigo": "FCO", "nome": "Rome Fiumicino", "cidade": "Rome", "pais": "Italy"},
    {"codigo": "MUC", "nome": "Munich Airport", "cidade": "Munich", "pais": "Germany"},
    {"codigo": "ZRH", "nome": "Zurich Airport", "cidade": "Zurich", "pais": "Switzerland"},
    {"codigo": "BCN", "nome": "Barcelona El Prat", "cidade": "Barcelona", "pais": "Spain"}
]
actual_airports_data = AIRPORTS_DATA[:max(NUM_AIRPORTS_MIN, len(AIRPORTS_DATA))]
airport_codes = [a["codigo"] for a in actual_airports_data]

AIRPLANE_MODELS_CONFIG = {
    "Airbus A320neo": {"rows": 30, "seats_per_row_map": ['A', 'B', 'C', 'D', 'E', 'F'], "first_class_rows_percentage": 0.10},
    "Boeing 737-800": {"rows": 28, "seats_per_row_map": ['A', 'B', 'C', 'D', 'E', 'F'], "first_class_rows_percentage": 0.10},
    "Embraer E195-E2": {"rows": 25, "seats_per_row_map": ['A', 'B', 'C', 'D'], "first_class_rows_percentage": 0.08},
    "Boeing 777-300ER": {"rows": 42, "seats_per_row_map": ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'J'], "first_class_rows_percentage": 0.10}
}
model_names = list(AIRPLANE_MODELS_CONFIG.keys())
if len(model_names) < NUM_AIRPLANE_MODELS_MIN:
    print(f"Warning: Not enough airplane models defined ({len(model_names)}) to meet minimum of {NUM_AIRPLANE_MODELS_MIN}. Using all defined models.")

# --- Helper Functions ---
def generate_serial_number(model_name, count):
    return f"{model_name.replace(' ', '-').split('-')[0][:4].upper()}-{count:03d}-{fake.unique.ean(length=8)}"

def format_sql_string(s):
    return s.replace("'", "''")

def format_timestamp_for_sql(dt_obj):
    return dt_obj.strftime('%Y-%m-%d %H:%M:%S')

# --- Data Generation ---
print("--- Starting Data Generation ---")
print(f"IMPORTANT NOTE: The requirement for 'check-in' of tickets for past flights cannot be fully met "
      f"without altering the SQL schema to add a check-in status column to the 'bilhete' table. "
      f"This script populates data according to the provided schema.")

airplanes_generated = []
seats_generated = []
flights_generated = []
sales_generated = []
tickets_generated = []

# 1. Generate Aeroportos (Data is predefined)

# 2. Generate Avioes and Assentos
airplane_seat_config_map = {}
for i in range(NUM_AIRPLANES_MIN):
    model = model_names[i % len(model_names)]
    serial_no = generate_serial_number(model, i + 1)
    airplanes_generated.append({"no_serie": serial_no, "modelo": model})
    
    model_config = AIRPLANE_MODELS_CONFIG[model]
    num_rows = model_config["rows"]
    seats_map = model_config["seats_per_row_map"]
    first_class_rows = math.ceil(num_rows * model_config["first_class_rows_percentage"])

    current_plane_seats = []
    for r_idx in range(1, num_rows + 1):
        is_first_class = (r_idx <= first_class_rows)
        for seat_char in seats_map:
            lugar = f"{r_idx}{seat_char}"
            seats_generated.append({"lugar": lugar, "no_serie": serial_no, "prim_classe": is_first_class})
            current_plane_seats.append({"lugar": lugar, "prim_classe": is_first_class, "no_serie": serial_no})
    airplane_seat_config_map[serial_no] = current_plane_seats

# 3. Generate Voos
airplane_current_status = {}
for plane in airplanes_generated:
    airplane_current_status[plane["no_serie"]] = {
        "location": random.choice(airport_codes),
        "available_at": datetime.datetime.combine(START_DATE, datetime.time(random.randint(0,5), random.randint(0,59))), # Start early on day 1
        "pending_return_destination": None # Destination for the mandatory return leg
    }

flight_id_counter = 1
all_flights_details_for_tickets = [] 
plane_flight_counts = {p["no_serie"]: 0 for p in airplanes_generated}
airport_departure_counts = {code: 0 for code in airport_codes}
airport_arrival_counts = {code: 0 for code in airport_codes}

current_processing_date = START_DATE
while current_processing_date <= END_DATE:
    flights_scheduled_today = 0
    planes_that_flew_today_or_are_busy = set() # Track planes used in the current day's scheduling pass

    # Phase 1: Schedule mandatory return flights
    # Sort by availability to give preference to planes ready earlier
    planes_to_check_for_return = sorted(
        airplanes_generated,
        key=lambda p: airplane_current_status[p["no_serie"]]["available_at"]
    )
    for plane_data in planes_to_check_for_return:
        plane_no_serie = plane_data["no_serie"]
        status = airplane_current_status[plane_no_serie]

        if plane_no_serie in planes_that_flew_today_or_are_busy: continue
        if not status["pending_return_destination"]: continue
        
        # Plane must make a return flight. Check if it can depart today.
        min_departure_time_ret = status["available_at"]
        if min_departure_time_ret.date() > current_processing_date: continue # Not available today
        
        # Ensure departure is on current_processing_date, at a reasonable hour
        if min_departure_time_ret.time() < datetime.time(6,0) and min_departure_time_ret.date() == current_processing_date:
            departure_time_ret = datetime.datetime.combine(current_processing_date, datetime.time(random.randint(6,9), random.randint(0,59)))
        elif min_departure_time_ret.date() < current_processing_date: # Should not happen if available_at is updated correctly
             departure_time_ret = datetime.datetime.combine(current_processing_date, datetime.time(random.randint(6,9), random.randint(0,59)))
        else: # Available today at or after 6 AM
            departure_time_ret = max(min_departure_time_ret, datetime.datetime.combine(current_processing_date, datetime.time(6,0)))


        if departure_time_ret.time() > datetime.time(21, 0): # Too late to depart today for a return
            continue

        partida_ret = status["location"]
        chegada_ret = status["pending_return_destination"]
        if partida_ret == chegada_ret: # Should not happen with pending_return_destination logic
            status["pending_return_destination"] = None
            continue

        flight_duration_hours_ret = random.uniform(1.0, 4.5) # Assume similar range
        flight_duration_ret = datetime.timedelta(hours=flight_duration_hours_ret)
        arrival_time_ret = departure_time_ret + flight_duration_ret

        if arrival_time_ret.date() > END_DATE: continue

        flight_ret_id = flight_id_counter
        flights_generated.append({
            "id": flight_ret_id, "no_serie": plane_no_serie,
            "hora_partida": format_timestamp_for_sql(departure_time_ret),
            "hora_chegada": format_timestamp_for_sql(arrival_time_ret),
            "partida": partida_ret, "chegada": chegada_ret
        })
        all_flights_details_for_tickets.append({
            "id": flight_ret_id, "no_serie": plane_no_serie, "partida_dt": departure_time_ret,
            "chegada_dt": arrival_time_ret, "partida_cod": partida_ret, "chegada_cod": chegada_ret,
            "seats": airplane_seat_config_map[plane_no_serie]
        })
        flight_id_counter += 1
        flights_scheduled_today +=1
        plane_flight_counts[plane_no_serie] += 1
        airport_departure_counts[partida_ret] += 1
        airport_arrival_counts[chegada_ret] += 1
        
        turnaround_time = datetime.timedelta(hours=random.uniform(1.0, 3.0))
        status["location"] = chegada_ret
        status["available_at"] = arrival_time_ret + turnaround_time
        status["pending_return_destination"] = None # Return completed
        planes_that_flew_today_or_are_busy.add(plane_no_serie)

    # Phase 2: Schedule new "outbound" flights (A->B), and attempt immediate return (B->A)
    # Prioritize planes that haven't flown much, then by availability.
    # Only consider planes that are free (no pending return) and haven't flown today.
    outbound_candidates = sorted(
        [p for p in airplanes_generated if not airplane_current_status[p["no_serie"]]["pending_return_destination"] and \
                                           p["no_serie"] not in planes_that_flew_today_or_are_busy and \
                                           airplane_current_status[p["no_serie"]]["available_at"].date() <= current_processing_date],
        key=lambda p: (plane_flight_counts[p["no_serie"]], airplane_current_status[p["no_serie"]]["available_at"])
    )

    for plane_data in outbound_candidates:
        # Stop if min daily flights met AND all planes have some flights (overall, not necessarily today)
        # This condition is tricky; for now, let's ensure FLIGHTS_PER_DAY_MIN is a soft target if planes are available.
        if flights_scheduled_today >= FLIGHTS_PER_DAY_MIN and plane_flight_counts[plane_data["no_serie"]] > (sum(plane_flight_counts.values()) / len(airplanes_generated) if len(airplanes_generated) > 0 else 0) :
             if all(plane_flight_counts[p["no_serie"]] > 0 for p in airplanes_generated): # Ensure all planes have at least one flight overall
                pass # Continue to try to use planes if available, but don't force too many extra flights

        plane_no_serie = plane_data["no_serie"]
        status = airplane_current_status[plane_no_serie]

        if plane_no_serie in planes_that_flew_today_or_are_busy: continue # Already flew or processed

        min_departure_time_A_B = status["available_at"]
        if min_departure_time_A_B.date() > current_processing_date: continue

        if min_departure_time_A_B.time() < datetime.time(6,0) and min_departure_time_A_B.date() == current_processing_date:
            departure_time_A_B = datetime.datetime.combine(current_processing_date, datetime.time(random.randint(6,18), random.randint(0,59)))
        elif min_departure_time_A_B.date() < current_processing_date:
             departure_time_A_B = datetime.datetime.combine(current_processing_date, datetime.time(random.randint(6,18), random.randint(0,59)))
        else:
            departure_time_A_B = max(min_departure_time_A_B, datetime.datetime.combine(current_processing_date, datetime.time(6,0)))
        
        if departure_time_A_B.time() > datetime.time(19,0): # Too late for A->B and potential B->A
            continue

        partida_A = status["location"]
        possible_chegadas_B = [ap for ap in airport_codes if ap != partida_A]
        if not possible_chegadas_B: continue
        
        chegada_B = min(possible_chegadas_B, key=lambda ap: airport_arrival_counts[ap])

        flight_duration_hours_A_B = random.uniform(1.0, 4.5)
        flight_duration_A_B = datetime.timedelta(hours=flight_duration_hours_A_B)
        arrival_time_A_B = departure_time_A_B + flight_duration_A_B

        if arrival_time_A_B.date() > END_DATE: continue

        # Schedule A -> B
        flight_ab_id = flight_id_counter
        flights_generated.append({
            "id": flight_ab_id, "no_serie": plane_no_serie,
            "hora_partida": format_timestamp_for_sql(departure_time_A_B),
            "hora_chegada": format_timestamp_for_sql(arrival_time_A_B),
            "partida": partida_A, "chegada": chegada_B
        })
        all_flights_details_for_tickets.append({
            "id": flight_ab_id, "no_serie": plane_no_serie, "partida_dt": departure_time_A_B,
            "chegada_dt": arrival_time_A_B, "partida_cod": partida_A, "chegada_cod": chegada_B,
            "seats": airplane_seat_config_map[plane_no_serie]
        })
        flight_id_counter += 1
        flights_scheduled_today +=1
        plane_flight_counts[plane_no_serie] += 1
        airport_departure_counts[partida_A] += 1
        airport_arrival_counts[chegada_B] += 1
        
        turnaround_time = datetime.timedelta(hours=random.uniform(1.0, 3.0))
        status["location"] = chegada_B
        status["available_at"] = arrival_time_A_B + turnaround_time
        status["pending_return_destination"] = partida_A # Set pending return
        planes_that_flew_today_or_are_busy.add(plane_no_serie)

        # Attempt immediate return B -> A
        min_departure_time_B_A = status["available_at"] # Already includes turnaround from A->B
        if min_departure_time_B_A.date() > current_processing_date and min_departure_time_B_A.date() > END_DATE : continue # Cannot return within period

        if min_departure_time_B_A.date() == current_processing_date:
            if min_departure_time_B_A.time() < datetime.time(6,0):
                 departure_time_B_A = datetime.datetime.combine(current_processing_date, datetime.time(random.randint(6,9), random.randint(0,59)))
            else: # Available today
                 departure_time_B_A = min_departure_time_B_A
        elif min_departure_time_B_A.date() < current_processing_date: # Should not happen
             departure_time_B_A = datetime.datetime.combine(current_processing_date, datetime.time(random.randint(6,9), random.randint(0,59)))
        else: # Available on a future date
            departure_time_B_A = datetime.datetime.combine(min_departure_time_B_A.date(), datetime.time(random.randint(6,9), random.randint(0,59)))


        if departure_time_B_A.time() > datetime.time(21,0) and departure_time_B_A.date() == current_processing_date:
            # Too late for immediate return today, will be handled by Phase 1 on a subsequent day
            pass
        else:
            flight_duration_B_A = flight_duration_A_B # Assume similar duration
            arrival_time_B_A = departure_time_B_A + flight_duration_B_A

            if arrival_time_B_A.date() <= END_DATE:
                flight_ba_id = flight_id_counter
                flights_generated.append({
                    "id": flight_ba_id, "no_serie": plane_no_serie,
                    "hora_partida": format_timestamp_for_sql(departure_time_B_A),
                    "hora_chegada": format_timestamp_for_sql(arrival_time_B_A),
                    "partida": chegada_B, "chegada": partida_A # B -> A
                })
                all_flights_details_for_tickets.append({
                    "id": flight_ba_id, "no_serie": plane_no_serie, "partida_dt": departure_time_B_A,
                    "chegada_dt": arrival_time_B_A, "partida_cod": chegada_B, "chegada_cod": partida_A,
                    "seats": airplane_seat_config_map[plane_no_serie]
                })
                flight_id_counter += 1
                flights_scheduled_today +=1 # This flight might be on a different day than current_processing_date
                plane_flight_counts[plane_no_serie] += 1
                airport_departure_counts[chegada_B] += 1
                airport_arrival_counts[partida_A] += 1

                status["location"] = partida_A
                status["available_at"] = arrival_time_B_A + turnaround_time
                status["pending_return_destination"] = None # Immediate return completed
                # planes_that_flew_today_or_are_busy.add(plane_no_serie) # Already added
            # else: B->A return would be too late, pending_return_destination remains set.
    
    # Ensure at least FLIGHTS_PER_DAY_MIN are scheduled if possible, by adding more single outbound legs
    # This loop is a fallback if the above didn't generate enough for *today*
    additional_outbound_candidates = sorted(
        [p for p in airplanes_generated if not airplane_current_status[p["no_serie"]]["pending_return_destination"] and \
                                           p["no_serie"] not in planes_that_flew_today_or_are_busy and \
                                           airplane_current_status[p["no_serie"]]["available_at"].date() <= current_processing_date],
        key=lambda p: (plane_flight_counts[p["no_serie"]], airplane_current_status[p["no_serie"]]["available_at"])
    )
    idx_cand = 0
    while flights_scheduled_today < FLIGHTS_PER_DAY_MIN and idx_cand < len(additional_outbound_candidates):
        plane_data = additional_outbound_candidates[idx_cand]
        idx_cand += 1

        plane_no_serie = plane_data["no_serie"]
        status = airplane_current_status[plane_no_serie]

        if plane_no_serie in planes_that_flew_today_or_are_busy: continue

        min_dep_time = status["available_at"]
        if min_dep_time.date() > current_processing_date: continue

        if min_dep_time.time() < datetime.time(6,0) and min_dep_time.date() == current_processing_date:
            dep_time = datetime.datetime.combine(current_processing_date, datetime.time(random.randint(6,19), random.randint(0,59)))
        elif min_dep_time.date() < current_processing_date:
             dep_time = datetime.datetime.combine(current_processing_date, datetime.time(random.randint(6,19), random.randint(0,59)))
        else:
            dep_time = max(min_dep_time, datetime.datetime.combine(current_processing_date, datetime.time(6,0)))

        if dep_time.time() > datetime.time(20,0): continue # Too late for a single leg

        partida = status["location"]
        possible_chegadas = [ap for ap in airport_codes if ap != partida]
        if not possible_chegadas: continue
        chegada = min(possible_chegadas, key=lambda ap: airport_arrival_counts[ap])
        
        flight_dur = datetime.timedelta(hours=random.uniform(1.0, 4.5))
        arr_time = dep_time + flight_dur

        if arr_time.date() > END_DATE: continue
        
        f_id = flight_id_counter
        flights_generated.append({
            "id": f_id, "no_serie": plane_no_serie,
            "hora_partida": format_timestamp_for_sql(dep_time),
            "hora_chegada": format_timestamp_for_sql(arr_time),
            "partida": partida, "chegada": chegada
        })
        all_flights_details_for_tickets.append({
            "id": f_id, "no_serie": plane_no_serie, "partida_dt": dep_time,
            "chegada_dt": arr_time, "partida_cod": partida, "chegada_cod": chegada,
            "seats": airplane_seat_config_map[plane_no_serie]
        })
        flight_id_counter += 1
        flights_scheduled_today +=1
        plane_flight_counts[plane_no_serie] += 1
        airport_departure_counts[partida] += 1
        airport_arrival_counts[chegada] += 1
        
        status["location"] = chegada
        status["available_at"] = arr_time + datetime.timedelta(hours=random.uniform(1.0, 3.0))
        status["pending_return_destination"] = partida # This single leg now requires a return
        planes_that_flew_today_or_are_busy.add(plane_no_serie)


    current_processing_date += datetime.timedelta(days=1)

# Garante que todos os aviões passam por LIS <-> CDG entre 2025-03-18 e 2025-06-17
garantia_inicio = datetime.datetime(2025, 3, 18, 10, 0)
garantia_fim = datetime.datetime(2025, 6, 17, 20, 0)
lis = "LIS"
cdg = "CDG"
for plane in airplanes_generated:
    plane_serial = plane["no_serie"]
    # LIS -> CDG
    hora_partida = garantia_inicio + datetime.timedelta(days=random.randint(0, 45), hours=random.randint(0, 12))
    duracao = datetime.timedelta(hours=random.uniform(2.0, 3.0))
    hora_chegada = hora_partida + duracao
    flights_generated.append({
        "id": flight_id_counter, "no_serie": plane_serial,
        "hora_partida": format_timestamp_for_sql(hora_partida),
        "hora_chegada": format_timestamp_for_sql(hora_chegada),
        "partida": lis, "chegada": cdg
    })
    all_flights_details_for_tickets.append({
        "id": flight_id_counter, "no_serie": plane_serial, "partida_dt": hora_partida,
        "chegada_dt": hora_chegada, "partida_cod": lis, "chegada_cod": cdg,
        "seats": airplane_seat_config_map[plane_serial]
    })
    flight_id_counter += 1

    # CDG -> LIS
    hora_partida = garantia_fim - datetime.timedelta(days=random.randint(0, 45), hours=random.randint(0, 12))
    duracao = datetime.timedelta(hours=random.uniform(2.0, 3.0))
    hora_chegada = hora_partida + duracao
    flights_generated.append({
        "id": flight_id_counter, "no_serie": plane_serial,
        "hora_partida": format_timestamp_for_sql(hora_partida),
        "hora_chegada": format_timestamp_for_sql(hora_chegada),
        "partida": cdg, "chegada": lis
    })
    all_flights_details_for_tickets.append({
        "id": flight_id_counter, "no_serie": plane_serial, "partida_dt": hora_partida,
        "chegada_dt": hora_chegada, "partida_cod": cdg, "chegada_cod": lis,
        "seats": airplane_seat_config_map[plane_serial]
    })
    flight_id_counter += 1

# 4. Generate Vendas
sale_id_counter = 1
for _ in range(NUM_SALES_MIN):
    sale_time = fake.date_time_between(start_date=START_DATE - datetime.timedelta(days=180), end_date=CURRENT_DATETIME) 
    sales_generated.append({
        "codigo_reserva": sale_id_counter,
        "nif_cliente": fake.numerify('#########'),
        "balcao": random.choice(airport_codes),
        "hora": format_timestamp_for_sql(sale_time)
    })
    sale_id_counter += 1

import numpy as np  # Adicione no topo do arquivo se ainda não estiver

# 5. Generate Bilhetes
ticket_id_counter = 1
booked_seats_on_flight = {} 
flight_class_tickets_sold = {f["id"]: {"first": 0, "economy": 0} for f in all_flights_details_for_tickets}

if not all_flights_details_for_tickets:
    print("Warning: No flights generated, so no tickets will be generated.")
if not sales_generated:
    print("Warning: No sales generated, so no tickets will be generated.")

CHECKIN_DEADLINE = datetime.datetime(2025, 6, 17, 14, 40)

# Garante pelo menos 1 de cada classe por voo
for flight_info in all_flights_details_for_tickets:
    if not sales_generated: break
    flight_id = flight_info["id"]
    plane_serial = flight_info["no_serie"]
    chegada_dt = flight_info["chegada_dt"]
    seats_for_this_plane = airplane_seat_config_map[plane_serial]
    first_class_seats_avail = [s for s in seats_for_this_plane if s["prim_classe"]]
    economy_seats_avail = [s for s in seats_for_this_plane if not s["prim_classe"]]
    random.shuffle(first_class_seats_avail)
    random.shuffle(economy_seats_avail)
    current_sale_fc = random.choice(sales_generated)
    current_sale_eco = random.choice(sales_generated)
    if flight_id not in booked_seats_on_flight: booked_seats_on_flight[flight_id] = set()

    # 1 bilhete primeira classe
    if first_class_seats_avail and flight_class_tickets_sold[flight_id]["first"] == 0:
        seat_to_book_fc = first_class_seats_avail[0]
        lugar_fc = seat_to_book_fc["lugar"]
        if (lugar_fc, plane_serial) not in booked_seats_on_flight[flight_id]:
            tickets_generated.append({
                "id": ticket_id_counter, "voo_id": flight_id, "codigo_reserva": current_sale_fc["codigo_reserva"],
                "nome_passegeiro": format_sql_string(fake.name()), "preco": round(random.uniform(200.00, 1500.00), 2),
                "prim_classe": True,
                "lugar": lugar_fc if chegada_dt <= CHECKIN_DEADLINE else None,
                "no_serie": plane_serial
            })
            booked_seats_on_flight[flight_id].add((lugar_fc, plane_serial))
            flight_class_tickets_sold[flight_id]["first"] += 1
            ticket_id_counter += 1

    # 1 bilhete económica
    if economy_seats_avail and flight_class_tickets_sold[flight_id]["economy"] == 0:
        seat_to_book_eco = economy_seats_avail[0]
        lugar_eco = seat_to_book_eco["lugar"]
        if (lugar_eco, plane_serial) not in booked_seats_on_flight[flight_id]:
            tickets_generated.append({
                "id": ticket_id_counter, "voo_id": flight_id, "codigo_reserva": current_sale_eco["codigo_reserva"],
                "nome_passegeiro": format_sql_string(fake.name()), "preco": round(random.uniform(50.00, 500.00), 2),
                "prim_classe": False,
                "lugar": lugar_eco if chegada_dt <= CHECKIN_DEADLINE else None,
                "no_serie": plane_serial
            })
            booked_seats_on_flight[flight_id].add((lugar_eco, plane_serial))
            flight_class_tickets_sold[flight_id]["economy"] += 1
            ticket_id_counter += 1

# Para cada voo, sorteia uma ocupação alvo e vende até esse percentual de assentos
for flight_info in all_flights_details_for_tickets:
    flight_id = flight_info["id"]
    plane_serial = flight_info["no_serie"]
    chegada_dt = flight_info["chegada_dt"]
    seats_for_this_plane = list(airplane_seat_config_map[plane_serial])
    total_seats = len(seats_for_this_plane)
    # Sorteia uma ocupação alvo entre 20% e 95%, distribuição normal centrada em 60%
    occupancy = float(np.clip(np.random.normal(0.6, 0.2), 0.2, 0.95))
    max_tickets = int(total_seats * occupancy)
    already_sold = len(booked_seats_on_flight.get(flight_id, set()))
    seats_left = max_tickets - already_sold
    if seats_left <= 0:
        continue
    random.shuffle(seats_for_this_plane)
    for seat_info in seats_for_this_plane:
        if seats_left <= 0:
            break
        lugar = seat_info["lugar"]
        is_first_class = seat_info["prim_classe"]
        if flight_id not in booked_seats_on_flight:
            booked_seats_on_flight[flight_id] = set()
        if (lugar, plane_serial) not in booked_seats_on_flight[flight_id]:
            preco = round(random.uniform(180.00, 1600.00), 2) if is_first_class else round(random.uniform(40.00, 600.00), 2)
            current_sale = random.choice(sales_generated)
            tickets_generated.append({
                "id": ticket_id_counter, "voo_id": flight_id, "codigo_reserva": current_sale["codigo_reserva"],
                "nome_passegeiro": format_sql_string(fake.name()), "preco": preco,
                "prim_classe": is_first_class,
                "lugar": lugar if chegada_dt <= CHECKIN_DEADLINE else None,
                "no_serie": plane_serial
            })
            booked_seats_on_flight[flight_id].add((lugar, plane_serial))
            if is_first_class: flight_class_tickets_sold[flight_id]["first"] += 1
            else: flight_class_tickets_sold[flight_id]["economy"] += 1
            ticket_id_counter += 1
            seats_left -= 1

# --- Write to SQL file ---
with open("populate.sql", "w", encoding="utf-8") as f:
    f.write("-- Schema Definition (as provided)\n")
    f.write(SCHEMA_SQL)
    f.write("\n\n-- Data Population\n\n")
    f.write(f"-- IMPORTANT NOTE: The requirement for 'check-in' of tickets for past flights cannot be fully met\n"
            f"-- without altering the SQL schema to add a check-in status column to the 'bilhete' table.\n"
            f"-- This script populates data according to the provided schema.\n\n")

    f.write("-- Aeroportos\n")
    for airport in actual_airports_data:
        f.write(f"INSERT INTO aeroporto (codigo, nome, cidade, pais) VALUES ('{airport['codigo']}', '{format_sql_string(airport['nome'])}', '{format_sql_string(airport['cidade'])}', '{format_sql_string(airport['pais'])}');\n")
    f.write("\n")

    f.write("-- Avioes\n")
    for aviao in airplanes_generated:
        f.write(f"INSERT INTO aviao (no_serie, modelo) VALUES ('{aviao['no_serie']}', '{format_sql_string(aviao['modelo'])}');\n")
    f.write("\n")

    f.write("-- Assentos\n")
    for assento in seats_generated:
        f.write(f"INSERT INTO assento (lugar, no_serie, prim_classe) VALUES ('{assento['lugar']}', '{assento['no_serie']}', {assento['prim_classe']});\n")
    f.write("\n")

    f.write("-- Voos\n")
    flights_generated.sort(key=lambda v: v['id']) 
    for voo in flights_generated:
        f.write(f"INSERT INTO voo (id, no_serie, hora_partida, hora_chegada, partida, chegada) VALUES ({voo['id']}, '{voo['no_serie']}', '{voo['hora_partida']}', '{voo['hora_chegada']}', '{voo['partida']}', '{voo['chegada']}');\n")
    f.write("\n")
    
    f.write("-- Vendas\n")
    sales_generated.sort(key=lambda s: s['codigo_reserva'])
    for venda in sales_generated:
        f.write(f"INSERT INTO venda (codigo_reserva, nif_cliente, balcao, hora) VALUES ({venda['codigo_reserva']}, '{venda['nif_cliente']}', '{venda['balcao']}', '{venda['hora']}');\n")
    f.write("\n")

    f.write("-- Bilhetes\n")
    tickets_generated.sort(key=lambda t: t['id']) 
    for bilhete in tickets_generated:
        f.write(
            f"INSERT INTO bilhete (id, voo_id, codigo_reserva, nome_passegeiro, preco, prim_classe, lugar, no_serie) VALUES "
            f"({bilhete['id']}, {bilhete['voo_id']}, {bilhete['codigo_reserva']}, '{bilhete['nome_passegeiro']}', {bilhete['preco']}, {bilhete['prim_classe']}, "
            f"NULL, '{bilhete['no_serie']}');\n"
        )
    f.write("\n")
    
    f.write("-- Update sequences for SERIAL columns (PostgreSQL specific)\n")
    f.write(f"SELECT setval(pg_get_serial_sequence('voo', 'id'), COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM voo;\n")
    f.write(f"SELECT setval(pg_get_serial_sequence('venda', 'codigo_reserva'), COALESCE(MAX(codigo_reserva), 1), MAX(codigo_reserva) IS NOT NULL) FROM venda;\n")
    f.write(f"SELECT setval(pg_get_serial_sequence('bilhete', 'id'), COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM bilhete;\n")

print(f"--- Data Generation Summary ---")
print(f"Generated {len(actual_airports_data)} airports.")
print(f"Generated {len(airplanes_generated)} airplanes.")
print(f"Generated {len(seats_generated)} seats.")
print(f"Generated {len(flights_generated)} flights.")
print(f"Generated {len(sales_generated)} sales.")
print(f"Generated {len(tickets_generated)} tickets.")

# Verification for ticket class distribution
missing_class_flights = 0
for flight_id_check, counts in flight_class_tickets_sold.items():
    flight_detail = next((f for f in all_flights_details_for_tickets if f["id"] == flight_id_check), None)
    if flight_detail:
        # Only warn if tickets were sold but a class is missing
        total_tickets_for_flight = sum(1 for t in tickets_generated if t['voo_id'] == flight_id_check)
        if total_tickets_for_flight > 0 and (counts["first"] == 0 or counts["economy"] == 0) :
             # print(f"Warning: Flight ID {flight_id_check} ({flight_detail['partida_cod']}->{flight_detail['chegada_cod']} on {flight_detail['partida_dt'].date()}) "
             #       f"has tickets but might be missing a class. First: {counts['first']}, Economy: {counts['economy']}")
             missing_class_flights +=1
if missing_class_flights > 0:
    print(f"Warning: {missing_class_flights} flights have tickets sold but might be missing representation from both first and economy classes. Review logs if concerned.")
else:
    print("All flights with tickets sold appear to have both first and economy class representation (based on initial seeding).")


# Verification for return flights logic (conceptual)
# This is hard to verify programmatically without tracing each plane's full history.
# The logic with 'pending_return_destination' aims to enforce this.
print("Flight return logic: The script attempts to ensure each outbound flight is eventually followed by a return flight by the same plane before another outbound leg.")

print("SQL data written to populate.sql")
print("--- End of Script ---")