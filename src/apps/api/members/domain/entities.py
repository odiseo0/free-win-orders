from dataclasses import dataclass


@dataclass(slots=True)
class Member:
    id: str
    name: str
