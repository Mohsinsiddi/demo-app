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
    """Payload for token balance check."""
    sender: str
    token_balance: Optional[float]
    native_balance: Optional[float]
    usdc_price: Optional[float]
    price_ipfs_hash: Optional[str]


@dataclass(frozen=True)
class DepositDecisionMakingPayload(BaseTxPayload):
    """Represent a transaction payload for deposit decision making."""
    event: str


@dataclass(frozen=True)
class SwapDecisionMakingPayload(BaseTxPayload):
    """Represent a transaction payload for swap decision making."""
    event: str


@dataclass(frozen=True)
class TokenDepositPayload(BaseTxPayload):
    """Represent a transaction payload for token deposit."""
    tx_submitter: Optional[str]
    tx_hash: Optional[str]


@dataclass(frozen=True)
class TokenSwapPayload(BaseTxPayload):
    """Represent a transaction payload for token swap."""
    tx_submitter: Optional[str]
    tx_hash: Optional[str]