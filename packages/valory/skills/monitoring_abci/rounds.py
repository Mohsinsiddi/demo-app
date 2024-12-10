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

"""This package contains the rounds of MonitoringAbciApp.

The MonitoringAbciApp implements a round-based consensus system for monitoring
token balances, making deposit/swap decisions, and executing transactions. 
The rounds are organized in a sequential flow, with each round collecting and
validating data from participating agents before proceeding to the next stage.
"""

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
from packages.valory.skills.monitoring_abci.payloads import (
    TokenBalanceCheckPayload,
    TokenDepositPayload,
    TokenSwapPayload,
    DepositDecisionMakingPayload,
    SwapDecisionMakingPayload,
)


class Event(Enum):
    """Events triggered during the MonitoringAbciApp rounds.
    
    These events determine the transitions between different rounds:
    DONE: Round completed successfully
    ERROR: Error occurred during round execution
    TRANSACT: Transaction needs to be executed
    SWAP: Token swap needs to be performed
    NO_MAJORITY: Consensus could not be reached
    ROUND_TIMEOUT: Round timed out
    NO_SWAP_BUT_DEPOSIT: No swap needed but deposit is pending
    """

    DONE = "done"
    ERROR = "error"
    TRANSACT = "transact"
    SWAP = "swap"
    NO_MAJORITY = "no_majority"
    ROUND_TIMEOUT = "round_timeout"
    NO_SWAP_BUT_DEPOSIT = "no_swap_but_deposit"



class SynchronizedData(BaseSynchronizedData):
    """Synchronized data shared between agents during rounds.
    
    This class manages the shared state between agents including:
    - Token balances and prices
    - Transaction details
    - Round participation data
    - IPFS hashes for price deviation records
    
    All data is stored in a synchronized database accessible to all agents.
    """

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
    """Round for collecting and validating token balance and price data.
    
    This round:
    1. Collects balance checks for OLAS and native tokens
    2. Gathers current USDC price data
    3. Records significant price deviations to IPFS
    4. Ensures consensus on collected data before proceeding
    """

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
    """Round for reaching consensus on deposit decisions.
    
    This round:
    1. Collects deposit decisions from all agents
    2. Compares current balances against thresholds
    3. Reaches consensus on whether deposits are needed
    4. Triggers appropriate follow-up rounds based on decision
    """
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
    """Round for reaching consensus on swap decisions.
    
    This round:
    1. Analyzes price data and deviation records
    2. Collects swap decisions from all agents
    3. Reaches consensus on whether swaps should be executed
    4. Considers deposit status when making swap decisions
    """
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
    """Round for preparing and validating deposit transactions.
    
    This round:
    1. Collects prepared deposit transaction details
    2. Validates transaction parameters
    3. Reaches consensus on transaction hash
    4. Prepares transaction for submission to Safe
    """
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
    """Round for preparing and validating swap transactions.
    
    This round:
    1. Collects prepared swap transaction details
    2. Validates DEX interaction parameters
    3. Reaches consensus on transaction hash
    4. Prepares complex transactions (wrap, approve, swap)
    """
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
   """Terminal round indicating completion of decision-making process.
    
    This round is reached when:
    1. All necessary decisions have been made
    2. No actions (deposits/swaps) are required
    3. System can proceed to next monitoring cycle
    """


class FinishedTxPreparationRound(DegenerateRound):
    """Terminal round indicating completion of transaction preparation.
    
    This round is reached when:
    1. All necessary transactions have been prepared
    2. Transaction hashes have been validated
    3. System is ready for transaction execution
    """


class MonitoringAbciApp(AbciApp[Event]):
    """Main ABCI application for token monitoring and management.
    
    This application coordinates the entire monitoring process:
    1. Initiates balance and price checks
    2. Manages decision-making rounds for deposits and swaps
    3. Handles transaction preparation and validation
    4. Controls transitions between different rounds
    5. Ensures proper completion of monitoring cycles
    
    The application follows a strict state machine pattern with
    well-defined transitions and checks at each stage.
    """

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
            Event.DONE: FinishedDecisionMakingRound,
            Event.SWAP: TokenSwapRound,
            Event.NO_SWAP_BUT_DEPOSIT:FinishedTxPreparationRound,
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