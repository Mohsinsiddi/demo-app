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

"""This module contains the class to swap tokens on Sushiswap V2."""

from typing import Dict, List

from aea.common import JSONLike
from aea.configurations.base import PublicId
from aea.contracts.base import Contract
from aea_ledger_ethereum import EthereumApi


PUBLIC_ID = PublicId.from_str("valory/sushiswap_router:0.1.0")

class SushiswapRouter(Contract):
    """Class for token swaps on Sushiswap."""

    contract_id = PUBLIC_ID

    @classmethod
    def get_amounts_out(
        cls,
        ledger_api: EthereumApi,
        router_address: str,
        amount_in: int,
        path: List[str],
    ) -> JSONLike:
        """Get expected output amount for a swap."""
        contract_instance = cls.get_instance(ledger_api, router_address)
        amounts = contract_instance.functions.getAmountsOut(amount_in, path).call()
        return {"amounts": amounts}

    @classmethod
    def build_swap_exact_tokens_for_tokens_tx(
        cls,
        ledger_api: EthereumApi,
        router_address: str,
        amount_in: int,
        amount_out_min: int,
        path: List[str],
        to_address: str,
        deadline: int,
    ) -> Dict[str, bytes]:
        """Build swap transaction data."""
        contract_instance = cls.get_instance(ledger_api, router_address)
        data = contract_instance.encodeABI(
            fn_name="swapExactTokensForTokens",
            args=[
                amount_in,
                amount_out_min,
                path,
                to_address,
                deadline,
            ],
        )
        return {"data": bytes.fromhex(data[2:])}

    @classmethod
    def build_swap_exact_eth_for_tokens_tx(
        cls,
        ledger_api: EthereumApi,
        router_address: str,
        amount_out_min: int,
        path: List[str],
        to_address: str,
        deadline: int,
    ) -> Dict[str, bytes]:
        """Build swap ETH for tokens transaction data."""
        contract_instance = cls.get_instance(ledger_api, router_address)
        data = contract_instance.encodeABI(
            fn_name="swapExactETHForTokens",
            args=[
                amount_out_min,
                path,
                to_address,
                deadline,
            ],
        )
        return {"data": bytes.fromhex(data[2:])}