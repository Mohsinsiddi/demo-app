# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2024 Valory AG
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------

"""This package contains the rounds of LearningAbciApp."""

from enum import Enum
from typing import Dict, FrozenSet, Optional, Set, Tuple

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
from packages.valory.skills.learning_abci.payloads import (
    TokenBalanceCheckPayload,
    TokenDepositPayload,
    TokenSwapPayload,
    DepositDecisionMakingPayload,
    SwapDecisionMakingPayload,
)


class Event(Enum):
    """LearningAbciApp Events"""
    DONE = "done"
    ERROR = "error"
    TRANSACT = "transact"
    SWAP = "swap"
    NO_MAJORITY = "no_majority"
    ROUND_TIMEOUT = "round_timeout"


class SynchronizedData(BaseSynchronizedData):
    """Class to represent the synchronized data."""

    def _get_deserialized(self, key: str) -> DeserializedCollection:
        """Strictly get a collection and return it deserialized."""
        serialized = self.db.get_strict(key)
        return CollectionRound.deserialize_collection(serialized)

    @property
    def token_balance(self) -> Optional[float]:
        """Get the token balance."""
        return self.db.get("token_balance", None)

    @property
    def native_balance(self) -> Optional[float]:
        """Get the native balance."""
        return self.db.get("native_balance", None)

    @property
    def usdc_price(self) -> Optional[float]:
        """Get the USDC price."""
        return self.db.get("usdc_price", None)

    @property
    def price_ipfs_hash(self) -> Optional[str]:
        """Get the price IPFS hash."""
        return self.db.get("price_ipfs_hash", None)

    @property
    def most_voted_tx_hash(self) -> Optional[str]:
        """Get the most voted tx hash."""
        return self.db.get("most_voted_tx_hash", None)

    @property
    def tx_submitter(self) -> Optional[str]:
        """Get the tx submitter."""
        return self.db.get("tx_submitter", None)

    @property
    def participant_to_token_balance_round(self) -> DeserializedCollection:
        """Get the token balance round data."""
        return self._get_deserialized("participant_to_token_balance_round")

    @property
    def participant_to_deposit_decision_round(self) -> DeserializedCollection:
        """Get the deposit decision round data."""
        return self._get_deserialized("participant_to_deposit_decision_round")

    @property
    def participant_to_swap_decision_round(self) -> DeserializedCollection:
        """Get the swap decision round data."""
        return self._get_deserialized("participant_to_swap_decision_round")

    @property
    def participant_to_deposit_round(self) -> DeserializedCollection:
        """Get the deposit round data."""
        return self._get_deserialized("participant_to_deposit_round")

    @property
    def participant_to_swap_round(self) -> DeserializedCollection:
        """Get the swap round data."""
        return self._get_deserialized("participant_to_swap_round")


class TokenBalanceCheckRound(CollectSameUntilThresholdRound):
    """TokenBalanceCheckRound"""
    payload_class = TokenBalanceCheckPayload
    synchronized_data_class = SynchronizedData
    done_event = Event.DONE
    no_majority_event = Event.NO_MAJORITY
    collection_key = get_name(SynchronizedData.participant_to_token_balance_round)
    selection_key = (
        get_name(SynchronizedData.token_balance),
        get_name(SynchronizedData.native_balance),
        get_name(SynchronizedData.usdc_price),
        get_name(SynchronizedData.price_ipfs_hash),
    )


class DepositDecisionMakingRound(CollectSameUntilThresholdRound):
    """DepositDecisionMakingRound"""
    payload_class = DepositDecisionMakingPayload
    synchronized_data_class = SynchronizedData

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:
            event = Event(self.most_voted_payload)
            return self.synchronized_data, event

        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY

        return None


class SwapDecisionMakingRound(CollectSameUntilThresholdRound):
    """SwapDecisionMakingRound"""
    payload_class = SwapDecisionMakingPayload
    synchronized_data_class = SynchronizedData

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:
            event = Event(self.most_voted_payload)
            return self.synchronized_data, event

        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY

        return None


class TokenDepositRound(CollectSameUntilThresholdRound):
    """TokenDepositRound"""
    payload_class = TokenDepositPayload
    synchronized_data_class = SynchronizedData
    done_event = Event.DONE
    no_majority_event = Event.NO_MAJORITY
    collection_key = get_name(SynchronizedData.participant_to_deposit_round)
    selection_key = (
        get_name(SynchronizedData.tx_submitter),
        get_name(SynchronizedData.most_voted_tx_hash),
    )


class TokenSwapRound(CollectSameUntilThresholdRound):
    """TokenSwapRound"""
    payload_class = TokenSwapPayload
    synchronized_data_class = SynchronizedData
    done_event = Event.DONE
    no_majority_event = Event.NO_MAJORITY
    collection_key = get_name(SynchronizedData.participant_to_swap_round)
    selection_key = (
        get_name(SynchronizedData.tx_submitter),
        get_name(SynchronizedData.most_voted_tx_hash),
    )


class FinishedDecisionMakingRound(DegenerateRound):
    """FinishedDecisionMakingRound"""


class FinishedTxPreparationRound(DegenerateRound):
    """FinishedTxPreparationRound"""


class LearningAbciApp(AbciApp[Event]):
    """LearningAbciApp"""

    initial_round_cls: AppState = TokenBalanceCheckRound
    initial_states: Set[AppState] = {TokenBalanceCheckRound}
    transition_function: AbciAppTransitionFunction = {
        TokenBalanceCheckRound: {
            Event.DONE: DepositDecisionMakingRound,
            Event.NO_MAJORITY: TokenBalanceCheckRound,
            Event.ROUND_TIMEOUT: TokenBalanceCheckRound,
        },
        DepositDecisionMakingRound: {
            Event.DONE: SwapDecisionMakingRound,
            Event.TRANSACT: TokenDepositRound,
            Event.ERROR: SwapDecisionMakingRound,
            Event.NO_MAJORITY: DepositDecisionMakingRound,
            Event.ROUND_TIMEOUT: DepositDecisionMakingRound,
        },
        SwapDecisionMakingRound: {
            Event.DONE: FinishedTxPreparationRound,
            Event.SWAP: TokenSwapRound,
            Event.ERROR: FinishedTxPreparationRound,
            Event.NO_MAJORITY: SwapDecisionMakingRound,
            Event.ROUND_TIMEOUT: SwapDecisionMakingRound,
        },
        TokenDepositRound: {
            Event.DONE: SwapDecisionMakingRound,
            Event.NO_MAJORITY: TokenDepositRound,
            Event.ROUND_TIMEOUT: TokenDepositRound,
        },
        TokenSwapRound: {
            Event.DONE: FinishedTxPreparationRound,
            Event.NO_MAJORITY: TokenSwapRound,
            Event.ROUND_TIMEOUT: TokenSwapRound,
        },
        FinishedDecisionMakingRound: {},
        FinishedTxPreparationRound: {},
    }
    final_states: Set[AppState] = {
        FinishedDecisionMakingRound,
        FinishedTxPreparationRound,
    }
    event_to_timeout: EventToTimeout = {}
    cross_period_persisted_keys: FrozenSet[str] = frozenset()
    db_pre_conditions: Dict[AppState, Set[str]] = {
        TokenBalanceCheckRound: set(),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedDecisionMakingRound: set(),
        FinishedTxPreparationRound: {get_name(SynchronizedData.most_voted_tx_hash)},
    }