from sqlalchemy import text

def next_num_orden(db):
    usados = {
        int(r[0])
        for r in db.execute(text("SELECT num_orden FROM trabajadores WHERE num_orden IS NOT NULL")).all()
    }
    for i in range(1, 1000):
        v = i
        if v not in usados:
            return v
    raise ValueError("No hay números de orden disponibles")

def next_cod_letra(db):
    usados = {
        str(r[0]).strip().upper()
        for r in db.execute(text("SELECT cod_letra FROM trabajadores WHERE cod_letra IS NOT NULL")).all()
    }
    for a in range(ord("A"), ord("Z")+1):
        for b in range(ord("A"), ord("Z")+1):
            for c in range(ord("A"), ord("Z")+1):
                v = chr(a) + chr(b) + chr(c)
                if v not in usados:
                    return v
    raise ValueError("No hay códigos de letra disponibles")
