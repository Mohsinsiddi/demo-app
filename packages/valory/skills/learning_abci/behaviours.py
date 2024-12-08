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

"""This package contains round behaviours of LearningAbciApp."""

import json
from abc import ABC
from pathlib import Path
from tempfile import mkdtemp
from typing import Dict, Generator, Optional, Set, Tuple, Type, cast

from packages.valory.contracts.erc20.contract import ERC20
from packages.valory.contracts.gnosis_safe.contract import (
    GnosisSafeContract,
    SafeOperation,
)
from packages.valory.contracts.multisend.contract import (
    MultiSendContract,
    MultiSendOperation,
)
from packages.valory.contracts.sushiswap_router.contract import SushiswapRouter
from packages.valory.contracts.token_reader.contract import TokenReaderContract
from packages.valory.protocols.contract_api import ContractApiMessage
from packages.valory.protocols.ledger_api import LedgerApiMessage
from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.valory.skills.abstract_round_abci.io_.store import SupportedFiletype
from packages.valory.skills.learning_abci.models import (
    CoingeckoSpecs,
    Params,
    SharedState,
)
from packages.valory.skills.learning_abci.payloads import (
    DepositDecisionMakingPayload,
    SwapDecisionMakingPayload,
    TokenBalanceCheckPayload,
    TokenDepositPayload,
    TokenSwapPayload,
)
from packages.valory.skills.learning_abci.rounds import (
    DepositDecisionMakingRound,
    Event,
    LearningAbciApp,
    SwapDecisionMakingRound,
    SynchronizedData,
    TokenBalanceCheckRound,
    TokenDepositRound,
    TokenSwapRound,
)
from packages.valory.skills.transaction_settlement_abci.payload_tools import (
    hash_payload_to_hex,
)
from packages.valory.skills.transaction_settlement_abci.rounds import TX_HASH_LENGTH


# Define some constants
ZERO_VALUE = 0
HTTP_OK = 200
GNOSIS_CHAIN_ID = "gnosis"
EMPTY_CALL_DATA = b"0x"
SAFE_GAS = 0
VALUE_KEY = "value"
TO_ADDRESS_KEY = "to_address"
METADATA_FILENAME = "metadata.json"

# Add these constants at the top of the file
OLAS_PRICE_THRESHOLD = 5.0  # $1.00 USD
OLAS_BALANCE_THRESHOLD = 100 * 10**18  # 100 OLAS in wei
NATIVE_BALANCE_THRESHOLD = 1 * 10**18  # 1 xDAI in wei
REFILL_AMOUNT_NATIVE = 0.5 * 10**18  # 0.5 xDAI in wei
REFILL_AMOUNT_OLAS = 50 * 10**18  # 50 OLAS in wei
SWAP_AMOUNT = 100000000000000000  # 0.1 xDAI to swap

USDC_PRICE_THRESHOLD = 1.0  # Trigger swap if USDC price below $0.99
USDC_PRICE_DEVIATION_THRESHOLD = 0.00001  # 0.1% deviation threshold


class LearningBaseBehaviour(BaseBehaviour, ABC):
    """Base behaviour for the learning_abci behaviours."""

    @property
    def params(self) -> Params:
        """Return the params."""
        return cast(Params, super().params)

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return cast(SynchronizedData, super().synchronized_data)

    @property
    def local_state(self) -> SharedState:
        """Return the local state."""
        return cast(SharedState, self.context.state)

    @property
    def coingecko_specs(self) -> CoingeckoSpecs:
        """Get the Coingecko api specs."""
        return self.context.coingecko_specs

    @property
    def metadata_filepath(self) -> str:
        """Get the temporary filepath to the metadata."""
        return str(Path(mkdtemp()) / METADATA_FILENAME)

    def get_sync_timestamp(self) -> float:
        """Get the synchronized time from Tendermint's last block."""
        now = cast(
            SharedState, self.context.state
        ).round_sequence.last_round_transition_timestamp.timestamp()
        return now


class TokenBalanceCheckBehaviour(LearningBaseBehaviour):
    """TokenBalanceCheckBehaviour"""
    matching_round: Type[AbstractRound] = TokenBalanceCheckRound

    def async_act(self) -> Generator:
        """Check token balance and price."""
        self.context.logger.info("Entering TokenBalanceCheckBehaviour")
        
        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address
            MONITORED_ADDRESS = self.params.monitored_address
            # Get USDC price instead of OLAS
            # usdc_price = yield from self.get_usdc_price()
            usdc_price = 1
            self.context.logger.info(f"Current USDC price: ${usdc_price}")
            
            # Check balances of monitored address
            olas_balance = yield from self.get_token_balance(MONITORED_ADDRESS)
            native_balance = yield from self.get_native_balance(MONITORED_ADDRESS)
            
            # Store price data in IPFS if below threshold
            price_ipfs_hash = None
            if usdc_price is not None and isinstance(usdc_price, (int, float)):
                # Calculate absolute deviation from $1
                price_deviation = abs(1 - usdc_price)
                self.context.logger.info(f"price_deviation:${price_deviation}")
                if price_deviation > USDC_PRICE_DEVIATION_THRESHOLD:

                    self.context.logger.info(
                        f"USDC price deviation detected:\n"
                        f"Current price: ${usdc_price}\n"
                        f"Deviation: {price_deviation * 100:.3f}%\n"
                        f"Threshold: {USDC_PRICE_DEVIATION_THRESHOLD * 100:.3f}%"
                    )

                    price_data = {
                        "timestamp": self.get_sync_timestamp(),
                        "usdc_price": usdc_price,
                        "price_deviation": price_deviation,
                        "target_token": "USDC" if usdc_price < 1 else "WXDAI",
                        "source_token": "WXDAI" if usdc_price < 1 else "USDC",
                        "swap_direction": "buy" if usdc_price < 1 else "sell",
                        "swap_reason": "price_deviation",
                        "monitored_address": MONITORED_ADDRESS,
                        "deviation_threshold": USDC_PRICE_DEVIATION_THRESHOLD
                    }
                    
                    try:
                        price_ipfs_hash = yield from self.send_to_ipfs(
                            filename=self.metadata_filepath,
                            obj=price_data,
                            filetype=SupportedFiletype.JSON
                        )
                        self.context.logger.info(f"Stored price data in IPFS: https://gateway.autonolas.tech/ipfs/{price_ipfs_hash}")
    
                    except Exception as e:
                        self.context.logger.error(f"Failed to store data in IPFS: {str(e)}")
                        price_ipfs_hash = None

            payload = TokenBalanceCheckPayload(
                sender=sender,
                token_balance=olas_balance,
                native_balance=native_balance,
                usdc_price=usdc_price,
                price_ipfs_hash=price_ipfs_hash
            )

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def get_usdc_price(self) -> Generator[None, None, Optional[float]]:
        """Get USDC price from Coingecko."""
        url = "https://api.coingecko.com/api/v3/simple/price?ids=usd-coin&vs_currencies=usd"
        headers = {"accept": "application/json"}

        response = yield from self.get_http_response(
            method="GET",
            url=url,
            headers=headers
        )

        if response.status_code != HTTP_OK:
            self.context.logger.error(f"Error getting USDC price: {response.body}")
            return None

        try:
            api_data = json.loads(response.body)
            price = api_data["usd-coin"]["usd"]
            return price
        except (KeyError, json.JSONDecodeError) as e:
            self.context.logger.error(f"Error parsing USDC price data: {e}")
            return None    
        
    def get_token_balance(self, address: str) -> Generator[None, None, Optional[float]]:
        """Get token balance for specific address"""
        self.context.logger.info(f"Getting OLAS balance for address {address}")

        response_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,
            contract_address=self.params.olas_token_address,
            contract_id=str(TokenReaderContract.contract_id),
            contract_callable="get_raw_balance",
            address_to_check=address,
            chain_id=GNOSIS_CHAIN_ID,
        )

        if response_msg.performative != ContractApiMessage.Performative.RAW_TRANSACTION:
            self.context.logger.error(f"Error retrieving OLAS balance: {response_msg}")
            return None

        balance = response_msg.raw_transaction.body.get("balance", None)
        if balance is None:
            return None

        balance = balance / 10**18  # Convert from wei
        return balance

    def get_native_balance(self, address: str) -> Generator[None, None, Optional[float]]:
        """Get native xDAI balance for specific address"""
        ledger_api_response = yield from self.get_ledger_api_response(
            performative=LedgerApiMessage.Performative.GET_STATE,
            ledger_callable="get_balance",
            account=address,
            chain_id=GNOSIS_CHAIN_ID,
        )

        if ledger_api_response.performative != LedgerApiMessage.Performative.STATE:
            self.context.logger.error(f"Error retrieving native balance: {ledger_api_response}")
            return None

        balance = cast(int, ledger_api_response.state.body["get_balance_result"])
        balance = balance / 10**18  # Convert from wei
        return balance

class TokenDepositBehaviour(LearningBaseBehaviour):
    """TokenDepositBehaviour"""
    matching_round: Type[AbstractRound] = TokenDepositRound
    
    def async_act(self) -> Generator:
        """Deposit tokens if balances are low."""
        self.context.logger.info("Entering TokenDepositBehaviour")
        
        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address
            # Get balances from synchronized data
            token_balance = self.synchronized_data.token_balance
            self.context.logger.info(f"Token Balance: {token_balance}")
            token_balance_wei = int(token_balance * 10**18) if token_balance is not None else None

            native_balance = self.synchronized_data.native_balance
            self.context.logger.info(f"Native Balance: {native_balance}")
            native_balance_wei = int(native_balance * 10**18) if native_balance is not None else None

            # Determine which deposits are needed
            needs_native = native_balance_wei is not None and native_balance_wei < NATIVE_BALANCE_THRESHOLD
            self.context.logger.info(f"needs_native: {needs_native}")

            needs_olas = token_balance_wei is not None and token_balance_wei < OLAS_BALANCE_THRESHOLD
            self.context.logger.info(f"needs_olas: {needs_olas}")

            # Get timestamp to decide which transaction to make
            now = int(self.get_sync_timestamp())
            self.context.logger.info(f"Current timestamp: {now}")
            
            # Build appropriate transaction based on needs
            if needs_native and needs_olas:
                self.context.logger.info("Preparing multisend deposit for both native and OLAS")
                tx_hash = yield from self.get_multisend_safe_tx_hash()
            elif needs_native:
                self.context.logger.info("Preparing native deposit")
                tx_hash = yield from self.get_deposit_tx_hash(is_native=True)
            elif needs_olas:
                self.context.logger.info("Preparing OLAS deposit")
                tx_hash = yield from self.get_deposit_tx_hash(is_native=False)
            else:
                self.context.logger.info("No deposits needed")
                tx_hash = None
            
            payload = TokenDepositPayload(
                sender=sender,
                tx_submitter=self.auto_behaviour_id(),
                tx_hash=tx_hash,
            )
            
        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()
        
        self.context.logger.info("TokenDepositBehaviour completed")
        self.set_done()

    def get_multisend_safe_tx_hash(self) -> Generator[None, None, Optional[str]]:
        """Get multisend transaction hash for both native and token deposits."""
        self.context.logger.info("Building multisend transaction for both native and token deposits")
        MONITORED_ADDRESS = self.params.monitored_address

        multi_send_txs = []

        # 1. Add native transfer to multisend
        native_transfer_data = {
            VALUE_KEY: int(REFILL_AMOUNT_NATIVE),
            TO_ADDRESS_KEY: MONITORED_ADDRESS
        }
        
        multi_send_txs.append(
            {
                "operation": MultiSendOperation.CALL,
                "to": MONITORED_ADDRESS,
                "value": native_transfer_data[VALUE_KEY],
            }
        )
        self.context.logger.info("Added native transfer to multisend")

        # 2. Add ERC20 transfer to multisend
        token_transfer_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,
            contract_address=self.params.olas_token_address,
            contract_id=str(ERC20.contract_id),
            contract_callable="build_transfer_tx",
            recipient=MONITORED_ADDRESS,
            amount=int(REFILL_AMOUNT_OLAS),
            chain_id=GNOSIS_CHAIN_ID,
        )

        if token_transfer_msg.performative != ContractApiMessage.Performative.RAW_TRANSACTION:
            self.context.logger.error(f"Error building token transfer tx: {token_transfer_msg}")
            return None

        data_bytes: Optional[bytes] = token_transfer_msg.raw_transaction.body.get("data", None)
        if data_bytes is None:
            self.context.logger.error("No token transfer data received")
            return None

        multi_send_txs.append(
            {
                "operation": MultiSendOperation.CALL,
                "to": self.params.olas_token_address,
                "value": ZERO_VALUE,
                "data": bytes.fromhex(data_bytes.hex()),
            }
        )
        self.context.logger.info("Added token transfer to multisend")

        # Multisend call
        contract_api_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,
            contract_address=self.params.multisend_address,
            contract_id=str(MultiSendContract.contract_id),
            contract_callable="get_tx_data",
            multi_send_txs=multi_send_txs,
            chain_id=GNOSIS_CHAIN_ID,
        )

        if contract_api_msg.performative != ContractApiMessage.Performative.RAW_TRANSACTION:
            self.context.logger.error(
                f"Could not get Multisend tx hash. "
                f"Expected: {ContractApiMessage.Performative.RAW_TRANSACTION.value}, "
                f"Actual: {contract_api_msg.performative.value}"
            )
            return None

        multisend_data = cast(str, contract_api_msg.raw_transaction.body["data"])[2:]
        self.context.logger.info(f"Multisend data is {multisend_data}")

        # Prepare the Safe transaction
        safe_tx_hash = yield from self._build_safe_tx_hash(
            to_address=self.params.multisend_address,
            value=native_transfer_data[VALUE_KEY],
            data=bytes.fromhex(multisend_data),
            operation=SafeOperation.DELEGATE_CALL.value,
        )
        return safe_tx_hash

    def get_deposit_tx_hash(self, is_native: bool = False) -> Generator[None, None, Optional[str]]:
        """Get deposit transaction hash."""
        
        MONITORED_ADDRESS = self.params.monitored_address

        if is_native:
            # Native deposit logic
            safe_tx_hash = yield from self._build_safe_tx_hash(
                to_address=MONITORED_ADDRESS,
                value=int(REFILL_AMOUNT_NATIVE)
            )
        else:
            # OLAS deposit logic
            response_msg = yield from self.get_contract_api_response(
                performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,
                contract_address=self.params.olas_token_address,
                contract_id=str(ERC20.contract_id),
                contract_callable="build_transfer_tx",
                recipient=MONITORED_ADDRESS,
                amount=int(REFILL_AMOUNT_OLAS),
                chain_id=GNOSIS_CHAIN_ID,
            )
            
            if response_msg.performative != ContractApiMessage.Performative.RAW_TRANSACTION:
                return None
                
            data = response_msg.raw_transaction.body.get("data")
            if not data:
                return None
            
            safe_tx_hash = yield from self._build_safe_tx_hash(
                to_address=self.params.olas_token_address,
                data=data
            )
            
        return safe_tx_hash

    def _build_safe_tx_hash(
        self,
        to_address: str,
        value: int = 0,
        data: bytes = b"",
        operation: int = SafeOperation.CALL.value,
    ) -> Generator[None, None, Optional[str]]:
        """Build Safe transaction hash."""
        response_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,
            contract_address=self.synchronized_data.safe_contract_address,
            contract_id=str(GnosisSafeContract.contract_id),
            contract_callable="get_raw_safe_transaction_hash",
            to_address=to_address,
            value=value,
            data=data,
            safe_tx_gas=0,
            operation=operation,
            chain_id=GNOSIS_CHAIN_ID,
        )

        if response_msg.performative != ContractApiMessage.Performative.STATE:
            return None

        tx_hash = response_msg.state.body.get("tx_hash")
        if not tx_hash:
            return None

        safe_tx_hash = hash_payload_to_hex(
            safe_tx_hash=tx_hash[2:],
            ether_value=value,
            safe_tx_gas=0,
            to_address=to_address,
            data=data,
            operation=operation,
        )

        return safe_tx_hash

class DepositDecisionMakingBehaviour(LearningBaseBehaviour):
    """DepositDecisionMakingBehaviour"""
    matching_round: Type[AbstractRound] = DepositDecisionMakingRound

    def async_act(self) -> Generator:
        """Decide if deposits are needed."""
        self.context.logger.info("Entering DepositDecisionMakingBehaviour")
        
        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address
            
            # Get the latest data from synchronized_data
            token_balance = self.synchronized_data.token_balance
            native_balance = self.synchronized_data.native_balance

            self.context.logger.info(
                f"Making deposit decision with:\n"
                f"Token balance: {token_balance}\n"
                f"Native balance: {native_balance}"
            )

            event = self.get_deposit_decision(token_balance, native_balance)
            
            self.context.logger.info(f"Deposit decision made: {event}")
            
            payload = DepositDecisionMakingPayload(
                sender=sender,
                event=event
            )

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def get_deposit_decision(
        self,
        token_balance: Optional[float],
        native_balance: Optional[float],
    ) -> str:
        """Determine if deposits are needed."""
        
        if None in (token_balance, native_balance):
            self.context.logger.error("Missing balance data for deposit decision")
            return "error"

        try:
            token_balance_wei = int(round(token_balance * 10**18))
            native_balance_wei = int(round(native_balance * 10**18))

            needs_native = native_balance_wei < NATIVE_BALANCE_THRESHOLD
            needs_tokens = token_balance_wei < OLAS_BALANCE_THRESHOLD

            self.context.logger.info(
                f"Deposit decision factors:\n"
                f"Needs native: {needs_native} ({native_balance_wei} < {NATIVE_BALANCE_THRESHOLD})\n"
                f"Needs tokens: {needs_tokens} ({token_balance_wei} < {OLAS_BALANCE_THRESHOLD})"
            )

            if needs_native or needs_tokens:
                self.context.logger.info("Deposits needed")
                return "transact"

        except (ValueError, TypeError, OverflowError) as e:
            self.context.logger.error(f"Error checking deposit needs: {str(e)}")
            return "error"

        self.context.logger.info("No deposits needed")
        return "done"


class SwapDecisionMakingBehaviour(LearningBaseBehaviour):
    """SwapDecisionMakingBehaviour"""
    matching_round: Type[AbstractRound] = SwapDecisionMakingRound

    def async_act(self) -> Generator:
        """Decide if swap is needed."""
        self.context.logger.info("Entering SwapDecisionMakingBehaviour")
        
        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address
            
            # Get relevant data
            usdc_price = self.synchronized_data.usdc_price
            price_ipfs_hash = self.synchronized_data.price_ipfs_hash

            self.context.logger.info(
                f"Making swap decision with:\n"
                f"USDC price: {usdc_price}\n"
                f"Price IPFS hash: {price_ipfs_hash}"
            )

            event = self.get_swap_decision(usdc_price, price_ipfs_hash)
            
            self.context.logger.info(f"Swap decision made: {event}")
            
            payload = SwapDecisionMakingPayload(
                sender=sender,
                event=event
            )

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def get_swap_decision(
        self,
        usdc_price: Optional[float],
        price_ipfs_hash: Optional[str],
    ) -> str:
        """Determine if swap is needed."""
        
        if usdc_price is None:
            self.context.logger.error("Missing price data for swap decision")
            return "error"

        needs_swap = bool(price_ipfs_hash)

        self.context.logger.info(
            f"Swap decision factors:\n"
            f"Current USDC price: {usdc_price}\n"
            f"Price deviation exists: {needs_swap}"
        )

        if needs_swap:
            self.context.logger.info("Swap conditions met")
            return "swap"

        self.context.logger.info("No swap needed")
        return "done"

class TokenSwapBehaviour(LearningBaseBehaviour):
    """TokenSwapBehaviour"""
    matching_round: Type[AbstractRound] = TokenSwapRound

    def async_act(self) -> Generator:
        """Perform token swap if price conditions are met."""
        self.context.logger.info("Entering TokenSwapBehaviour")
        
        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address
            
            # Check if we have a price hash from previous round
            price_ipfs_hash = self.synchronized_data.price_ipfs_hash
            
            if not price_ipfs_hash:
                self.context.logger.info("No price data to process - skipping swap")
                payload = TokenSwapPayload(
                    sender=sender,
                    tx_submitter=self.auto_behaviour_id(),
                    tx_hash="",  # Empty string instead of None
                )
            else:
                self.context.logger.info(
                    f"Price data stored in IPFS: https://gateway.autonolas.tech/ipfs/{price_ipfs_hash}"
                )
                # Get the price data from IPFS
                price_data = yield from self.get_from_ipfs(
                    ipfs_hash=price_ipfs_hash,
                    filetype=SupportedFiletype.JSON
                )
                
                if price_data and price_data.get("usdc_price", float("inf")) < USDC_PRICE_THRESHOLD:
                    self.context.logger.info(f"Price conditions met for swap. Price data: {price_data}")
                    tx_hash = yield from self.get_wrap_and_swap_tx_hash()
                else:
                    self.context.logger.info("Price conditions not met for swap")
                    tx_hash = ""
                    
                payload = TokenSwapPayload(
                    sender=sender,
                    tx_submitter=self.auto_behaviour_id(),
                    tx_hash=tx_hash if tx_hash else "",
                )

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            self.context.logger.info("Sending transaction to other agents...")
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.context.logger.info("TokenSwapBehaviour completed")
        self.set_done()

    def get_wrap_and_swap_tx_hash(self) -> Generator[None, None, Optional[str]]:
        """Get transaction hash for wrapping xDAI and swapping to USDC."""
        
        self.context.logger.info("Starting get_wrap_and_swap_tx_hash")
        
        # Token addresses
        wxdai = "0xe91D153E0b41518A2Ce8Dd3D7944Fa863463a97d"  # WXDAI contract
        usdc = "0xDDAfbb505ad214D7b80b1f830fcCc89B60fb7A83"         
        # Amount of xDAI to wrap and swap (0.1 xDAI)
        amount = SWAP_AMOUNT
        path = [wxdai, usdc]
        
        self.context.logger.info(
            f"Swap parameters:\n"
            f"WXDAI address: {wxdai}\n"
            f"USDC address: {usdc}\n"
            f"Amount: {amount} wei\n"
            f"Router address: {self.params.sushiswap_router_address}"
        )
      
        # Get expected output amount
        self.context.logger.info("Getting expected swap amounts...")
        response_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,
            contract_address=self.params.sushiswap_router_address,
            contract_id=str(SushiswapRouter.contract_id),
            contract_callable="get_amounts_out",
            amount_in=amount,
            path=path,
            chain_id=GNOSIS_CHAIN_ID,
        )

        if response_msg.performative != ContractApiMessage.Performative.STATE:
            self.context.logger.error(
                f"Error getting swap amounts.\n"
                f"Expected performative: {ContractApiMessage.Performative.STATE}\n"
                f"Got: {response_msg.performative}"
            )
            return None

        amounts = response_msg.state.body.get("amounts")
        if not amounts or len(amounts) != 2:
            self.context.logger.error(f"Invalid amounts returned: {amounts}")
            return None

        self.context.logger.info(f"Input amount: {amounts[0]} WXDAI")
        self.context.logger.info(f"Expected output: {amounts[1]} USDC")

        # Set minimum output with 0.5% slippage
        amount_out_min = int(amounts[1] * 0.995)
        now = int(self.get_sync_timestamp())
        deadline = now + 300  # 5 minutes

        # 1. Build wrap transaction
        self.context.logger.info("Building wrap transaction...")
        wrap_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,
            contract_address=wxdai,
            contract_id=str(ERC20.contract_id),
            contract_callable="build_deposit_tx",
            chain_id=GNOSIS_CHAIN_ID,
        )
        
        if wrap_msg.performative != ContractApiMessage.Performative.RAW_TRANSACTION:
            self.context.logger.error(f"Error building wrap tx: {wrap_msg}")
            return None
        self.context.logger.info("Successfully built wrap transaction")

        # 2. Build approval transaction
        self.context.logger.info("Building approval transaction...")
        approval_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,
            contract_address=wxdai,
            contract_id=str(ERC20.contract_id),
            contract_callable="build_approval_tx",
            spender=self.params.sushiswap_router_address,
            amount=amount,
            chain_id=GNOSIS_CHAIN_ID,
        )
        if approval_msg.performative != ContractApiMessage.Performative.RAW_TRANSACTION:
            self.context.logger.error(f"Error building approval tx: {approval_msg}")
            return None
        self.context.logger.info("Successfully built approval transaction")

        # 3. Build swap transaction
        self.context.logger.info("Building swap transaction...")
        swap_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,
            contract_address=self.params.sushiswap_router_address,
            contract_id=str(SushiswapRouter.contract_id),
            contract_callable="build_swap_exact_tokens_for_tokens_tx",
            amount_in=amount,
            amount_out_min=amount_out_min,
            path=path,
            to_address=self.synchronized_data.safe_contract_address,
            deadline=deadline,
            chain_id=GNOSIS_CHAIN_ID,
        )

        if swap_msg.performative != ContractApiMessage.Performative.RAW_TRANSACTION:
            self.context.logger.error(f"Error building swap tx: {swap_msg}")
            return None
        self.context.logger.info("Successfully built swap transaction")

        # Combine all transactions using multisend
        self.context.logger.info("Building multisend transaction...")
        multi_send_txs = [
            {
                "operation": MultiSendOperation.CALL,
                "to": wxdai,
                "value": amount,  # Send xDAI with the wrap tx
                "data": wrap_msg.raw_transaction.body["data"],
            },
            {
                "operation": MultiSendOperation.CALL,
                "to": wxdai,
                "value": 0,
                "data": approval_msg.raw_transaction.body["data"],
            },
            {
                "operation": MultiSendOperation.CALL,
                "to": self.params.sushiswap_router_address,
                "value": 0,
                "data": swap_msg.raw_transaction.body["data"],
            }
        ]

        multisend_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,
            contract_address=self.params.multisend_address,
            contract_id=str(MultiSendContract.contract_id),
            contract_callable="get_tx_data",
            multi_send_txs=multi_send_txs,
            chain_id=GNOSIS_CHAIN_ID,
        )

        if multisend_msg.performative != ContractApiMessage.Performative.RAW_TRANSACTION:
            self.context.logger.error(f"Error building multisend tx: {multisend_msg}")
            return None

        multisend_data = multisend_msg.raw_transaction.body["data"]
        if not multisend_data:
            self.context.logger.error("No multisend data received")
            return None

        # Build final safe transaction
        self.context.logger.info("Building final Safe transaction hash...")
        safe_tx_hash = yield from self._build_safe_tx_hash(
            to_address=self.params.multisend_address,
            value=amount,  # Need to send xDAI with the transaction
            data=bytes.fromhex(multisend_data[2:]),  # Strip '0x' prefix
            operation=SafeOperation.DELEGATE_CALL.value,
        )

        if safe_tx_hash:
            self.context.logger.info(f"Generated Safe tx hash: {safe_tx_hash}")
        else:
            self.context.logger.error("Failed to generate Safe tx hash")

        return safe_tx_hash

    def _build_safe_tx_hash(
        self,
        to_address: str,
        value: int = 0,
        data: bytes = b"",
        operation: int = SafeOperation.CALL.value,
    ) -> Generator[None, None, Optional[str]]:
        """Build Safe transaction hash."""
        
        self.context.logger.info(
            f"Building Safe tx hash with params:\n"
            f"to_address: {to_address}\n"
            f"value: {value}\n"
            f"data length: {len(data)} bytes\n"
            f"operation: {operation}"
        )

        response_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,
            contract_address=self.synchronized_data.safe_contract_address,
            contract_id=str(GnosisSafeContract.contract_id),
            contract_callable="get_raw_safe_transaction_hash",
            to_address=to_address,
            value=value,
            data=data,
            safe_tx_gas=0,
            operation=operation,
            chain_id=GNOSIS_CHAIN_ID,
        )

        if response_msg.performative != ContractApiMessage.Performative.STATE:
            self.context.logger.error(
                f"Error building Safe tx hash: got performative {response_msg.performative} "
                f"instead of {ContractApiMessage.Performative.STATE}"
            )
            return None

        tx_hash = response_msg.state.body.get("tx_hash")
        if not tx_hash:
            self.context.logger.error("No tx hash received in response")
            return None

        safe_tx_hash = hash_payload_to_hex(
            safe_tx_hash=tx_hash[2:],
            ether_value=value,
            safe_tx_gas=0,
            to_address=to_address,
            data=data,
            operation=operation,
        )

        return safe_tx_hash


class LearningRoundBehaviour(AbstractRoundBehaviour):
    """LearningRoundBehaviour"""
    initial_behaviour_cls = TokenBalanceCheckBehaviour
    abci_app_cls = LearningAbciApp
    behaviours: Set[Type[BaseBehaviour]] = {
        TokenBalanceCheckBehaviour,
        DepositDecisionMakingBehaviour,
        SwapDecisionMakingBehaviour,
        TokenDepositBehaviour,
        TokenSwapBehaviour,
    }