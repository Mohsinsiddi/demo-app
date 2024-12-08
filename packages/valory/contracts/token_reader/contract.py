# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023-2024 Valory AG
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

"""This module contains the class to connect to an ERC20 token contract."""

from typing import Dict, List

from aea.common import JSONLike
from aea.configurations.base import PublicId
from aea.contracts.base import Contract
from aea.crypto.base import LedgerApi
from aea_ledger_ethereum import EthereumApi
from eth_typing import BlockIdentifier


PUBLIC_ID = PublicId.from_str("valory/token_reader:0.1.0")

class TokenReaderContract(Contract):
    """A simple contract to read token balances."""

    contract_id = PUBLIC_ID

    @classmethod
    def get_raw_balance(
        cls,
        ledger_api: EthereumApi,
        contract_address: str,
        address_to_check: str,
    ) -> JSONLike:
        """Get the balance of a given address."""
        contract_instance = cls.get_instance(ledger_api, contract_address)
        balance_of = getattr(contract_instance.functions, "balanceOf")  # noqa
        token_balance = balance_of(address_to_check).call()
        return dict(balance=token_balance)

    @classmethod
    def build_deposit_tx(
        cls,
        ledger_api: EthereumApi,
        contract_address: str,
    ) -> Dict[str, bytes]:
        """Build a deposit transaction."""
        contract_instance = cls.get_instance(ledger_api, contract_address)
        data = contract_instance.encodeABI("deposit") 
        return {"data": bytes.fromhex(data[2:])}        