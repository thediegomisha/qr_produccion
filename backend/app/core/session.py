SESSION = {"usuario": None}

def set_usuario(usuario: str):
    SESSION["usuario"] = usuario

def get_usuario():
    return SESSION["usuario"]
