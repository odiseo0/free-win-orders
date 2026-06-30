from dataclasses import dataclass


@dataclass(slots=True)
class SearchCardsQuery:
    term: str
