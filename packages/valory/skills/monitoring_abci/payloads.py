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

"""This module contains the transaction payloads of the MonitoringAbciApp."""

from dataclasses import dataclass
from typing import Optional

from packages.valory.skills.abstract_round_abci.base import BaseTxPayload


@dataclass(frozen=True)
class TokenBalanceCheckPayload(BaseTxPayload):
    """Represents a payload containing token balance and price information.

    This payload carries the results of balance checks and price monitoring:
    - Current OLAS token balance
    - Current native token (xDAI) balance
    - Current USDC price
    - IPFS hash for significant price deviation data

    Attributes:
        sender: str
            Address of the agent sending the payload
        token_balance: Optional[float]
            Current OLAS token balance, None if check failed
        native_balance: Optional[float]
            Current native token (xDAI) balance, None if check failed
        usdc_price: Optional[float]
            Current USDC price in USD, None if price fetch failed
        price_ipfs_hash: Optional[str]
            IPFS hash of stored price deviation data, None if no significant deviation
    """
    sender: str
    token_balance: Optional[float]
    native_balance: Optional[float]
    usdc_price: Optional[float]
    price_ipfs_hash: Optional[str]


@dataclass(frozen=True)
class DepositDecisionMakingPayload(BaseTxPayload):
    """Represents a payload for deposit decision consensus.

    This payload carries the agent's decision about whether deposits are needed
    based on current balance states.

    Attributes:
        event: str
            Decision event string, one of:
            - 'transact': Deposits are needed
            - 'done': No deposits needed
            - 'error': Error occurred during decision making
    """
    event: str


@dataclass(frozen=True)
class SwapDecisionMakingPayload(BaseTxPayload):
    """Represents a payload for swap decision consensus.

    This payload carries the agent's decision about whether token swaps
    should be executed based on price conditions and strategies.

    Attributes:
        event: str
            Decision event string, one of:
            - 'swap': Swap should be executed
            - 'no_swap_but_deposit': No swap needed but deposit pending
            - 'done': No action needed
            - 'error': Error occurred during decision making
    """
    event: str


@dataclass(frozen=True)
class TokenDepositPayload(BaseTxPayload):
    """Represents a payload for token deposit transaction details.

    This payload contains information about a prepared deposit transaction
    that needs to be executed through the Gnosis Safe.

    Attributes:
        tx_submitter: Optional[str]
            Address of the agent that prepared the transaction,
            None if no transaction was created
        tx_hash: Optional[str]
            Hash of the prepared Safe transaction,
            None if no transaction was created
    """
    tx_submitter: Optional[str]
    tx_hash: Optional[str]


@dataclass(frozen=True)
class TokenSwapPayload(BaseTxPayload):
    """Represents a payload for token swap transaction details.

    This payload contains information about a prepared swap transaction
    that needs to be executed through the Gnosis Safe. The transaction
    may include wrapping, approvals, and DEX interactions.

    Attributes:
        tx_submitter: Optional[str]
            Address of the agent that prepared the transaction,
            None if no transaction was created
        tx_hash: Optional[str]
            Hash of the prepared Safe transaction,
            None if no transaction was created
    """
    tx_submitter: Optional[str]
    tx_hash: Optional[str]