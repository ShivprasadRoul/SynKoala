from pydantic import BaseModel


class FigmaStatusRead(BaseModel):
    connected: bool
