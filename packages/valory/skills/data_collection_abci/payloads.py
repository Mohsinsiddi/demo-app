"""This module contains the payloads of SpaceXDataAbciApp."""

from dataclasses import dataclass
from typing import Optional

from packages.valory.skills.abstract_round_abci.base import BaseTxPayload

@dataclass(frozen=True)
class SpaceXDataPayload(BaseTxPayload):
    """Represent a transaction payload for the SpaceXDataRound."""
    company_valuation: Optional[float]
    company_valuation_ipfs_hash: Optional[str]