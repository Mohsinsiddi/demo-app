"""This package contains the rounds of SpaceXDataAbciApp."""

from enum import Enum
from typing import Dict, FrozenSet, Optional, Set

from packages.valory.skills.abstract_round_abci.base import (
    AbciApp,
    AbciAppTransitionFunction,
    AppState,
    BaseSynchronizedData,
    CollectSameUntilThresholdRound,
    CollectionRound,
    DegenerateRound,
    DeserializedCollection,
    EventToTimeout,
    get_name,
)
from packages.valory.skills.data_collection_abci.payloads import SpaceXDataPayload

class Event(Enum):
    """SpaceXDataAbciApp Events"""
    DONE = "done"
    ERROR = "error"
    NO_MAJORITY = "no_majority"
    ROUND_TIMEOUT = "round_timeout"

class SynchronizedData(BaseSynchronizedData):
    """Class to represent the synchronized data."""

    @property
    def company_valuation(self) -> Optional[float]:
        """Get the company valuation."""
        return self.db.get("company_valuation", None)

    @property
    def company_valuation_ipfs_hash(self) -> Optional[str]:
        """Get the company valuation ipfs hash."""
        return self.db.get("company_valuation_ipfs_hash", None)
    
    @property
    def participant_to_spacex_round(self) -> DeserializedCollection:
        """Agent to payload mapping for the SpaceXDataRound."""
        return self._get_deserialized("participant_to_spacex_round")

class SpaceXDataRound(CollectSameUntilThresholdRound):
    """SpaceXDataRound"""
    payload_class = SpaceXDataPayload
    synchronized_data_class = SynchronizedData
    done_event = Event.DONE
    no_majority_event = Event.NO_MAJORITY
    collection_key = get_name(SynchronizedData.participant_to_spacex_round)
    selection_key = (
        get_name(SynchronizedData.company_valuation),
        get_name(SynchronizedData.company_valuation_ipfs_hash),
    )    

class FinishedSpaceXRound(DegenerateRound):
    """FinishedSpaceXRound"""

class SpaceXDataAbciApp(AbciApp[Event]):
    """SpaceXDataAbciApp"""
    initial_round_cls: AppState = SpaceXDataRound
    initial_states: Set[AppState] = {SpaceXDataRound}
    transition_function: AbciAppTransitionFunction = {
        SpaceXDataRound: {
            Event.DONE: FinishedSpaceXRound,
            Event.NO_MAJORITY: SpaceXDataRound,
            Event.ROUND_TIMEOUT: SpaceXDataRound,
        },
        FinishedSpaceXRound: {},
    }
    final_states: Set[AppState] = {FinishedSpaceXRound}
    event_to_timeout: EventToTimeout = {}
    cross_period_persisted_keys: FrozenSet[str] = frozenset()
    db_pre_conditions: Dict[AppState, Set[str]] = {
        SpaceXDataRound: set(),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedSpaceXRound: set(),
    }