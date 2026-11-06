import pandas as pd
from sqlalchemy import create_engine

# 1. Conexión a PostgreSQL
engine = create_engine('postgresql://postgres:123456789@localhost:5432/bi_envasado')

# 2. Cargar datos de la hoja 'Base De Datos'
excel_path = 'SEGUIMIENTO TEMPERAS Y VINILOS Actividad.xlsm'
df = pd.read_excel(excel_path, sheet_name='Base De Datos', header=8)
df.columns = [str(col).strip() for col in df.columns]

# 3. Cargar mapeos de dimensiones desde PostgreSQL
with engine.connect() as conn:
    maquinas = pd.read_sql("SELECT id_maquina, nombre_maquina FROM dim_maquina;", conn)
    operadores = pd.read_sql("SELECT id_operador, nombre_operador FROM dim_operador;", conn)
    productos = pd.read_sql("SELECT id_producto, nombre_referencia FROM dim_producto;", conn)
    codigos_paro = pd.read_sql("SELECT id_codigo_paro, codigo_oficial FROM dim_codigo_paro;", conn)

# Crear diccionarios de mapeo
dict_maq = dict(zip(maquinas['nombre_maquina'].str.strip(), maquinas['id_maquina']))
dict_op = dict(zip(operadores['nombre_operador'].str.strip(), operadores['id_operador']))
dict_prod = dict(zip(productos['nombre_referencia'].str.strip(), productos['id_producto']))
dict_paro = dict(zip(codigos_paro['codigo_oficial'].str.strip(), codigos_paro['id_codigo_paro']))

# 4. Transformaciones y Limpieza
df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce').dt.date
df['id_maquina'] = df['Maquina'].astype(str).str.strip().map(dict_maq)
df['id_operador'] = df['Operario'].astype(str).str.strip().map(dict_op)
df['id_producto'] = df['Referencia'].astype(str).str.strip().map(dict_prod)

# Extraer el código estándar [01] al [19]
df['codigo_extraido'] = df['Tipo de paro'].astype(str).str.extract(r'(\[\d+\])')[0]
df['id_codigo_paro'] = df['codigo_extraido'].map(dict_paro)

# Limpieza numérica
df['pacas_producidas'] = pd.to_numeric(df['Pacas producidas'], errors='coerce').fillna(0)
df['horas_trabajadas'] = pd.to_numeric(df['Horas trabajadas'], errors='coerce').fillna(0)
df['horas_sin_trabajar'] = pd.to_numeric(df['Horas no trabajadas'], errors='coerce').fillna(0)

# Filtrar solo filas con Fecha y Máquina válidas
df_fact = df.dropna(subset=['Fecha', 'id_maquina']).copy()

# Convertir llaves foráneas a tipo entero nullable Int64
df_to_insert = pd.DataFrame({
    'id_fecha': df_fact['Fecha'],
    'id_maquina': df_fact['id_maquina'].astype('Int64'),
    'id_operador': df_fact['id_operador'].astype('Int64'),
    'id_producto': df_fact['id_producto'].astype('Int64'),
    'id_codigo_paro': df_fact['id_codigo_paro'].astype('Int64'),
    'horas_trabajadas': df_fact['horas_trabajadas'],
    'pacas_producidas': df_fact['pacas_producidas'],
    'horas_sin_trabajar': df_fact['horas_sin_trabajar'],
    'observacion': df_fact['Observaciones de paro'].fillna('').astype(str)
})

# 5. Carga a PostgreSQL
df_to_insert.to_sql('fact_paros_produccion', engine, if_exists='append', index=False, method='multi', chunksize=1000)

print(f" Proceso ETL completado con éxito: Se cargaron {len(df_to_insert)} registros en 'fact_paros_produccion'.")