from sqlalchemy import text

def next_num_orden(db):
    usados = set(
        r[0] for r in db.execute(text("SELECT num_orden FROM trabajadores")).all()
    )
    for i in range(1, 100):
        v = f"{i:03d}"
        if v not in usados:
            return v
    raise ValueError("No hay números de orden disponibles")

def next_cod_letra(db):
    usados = set(
        r[0] for r in db.execute(text("SELECT cod_letra FROM trabajadores")).all()
    )
    for a in range(ord("A"), ord("Z")+1):
        for b in range(ord("A"), ord("Z")+1):
            for c in range(ord("A"), ord("Z")+1):
                v = chr(a) + chr(b) + chr(c)

            if v not in usados:
                return v
    raise ValueError("No hay códigos de letra disponibles")
