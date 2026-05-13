import fdb

conn = fdb.connect(
    host='localhost',
    database='C:/Users/hepta/Desktop/eleventa datos/PDVDATA.FDB',
    user='SYSDBA',
    password='masterkey'
)
print("Conexión exitosa")
conn.close()