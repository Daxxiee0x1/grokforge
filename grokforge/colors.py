"""ANSI color helpers."""


class C:
    R   = "\033[0m"
    RED = "\033[91m"
    GRN = "\033[92m"
    YEL = "\033[93m"
    BLU = "\033[94m"
    CYN = "\033[96m"
    BLD = "\033[1m"
    DIM = "\033[2m"


def ok(m: str) -> str:   return f"{C.GRN}{m}{C.R}"
def err(m: str) -> str:  return f"{C.RED}{m}{C.R}"
def warn(m: str) -> str: return f"{C.YEL}{m}{C.R}"
def info(m: str) -> str: return f"{C.CYN}{m}{C.R}"
def step(m: str) -> str: return f"{C.BLU}{m}{C.R}"
def bold(m: str) -> str: return f"{C.BLD}{m}{C.R}"
def dim(m: str) -> str:  return f"{C.DIM}{m}{C.R}"