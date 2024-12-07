"""This module contains the behaviours for the spacex_data_abci skill."""

import json
from abc import ABC
from pathlib import Path
from tempfile import mkdtemp
from typing import Generator, Optional, Set, Type, cast

from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.valory.skills.abstract_round_abci.io_.store import SupportedFiletype
from packages.valory.skills.data_collection_abci.models import Params, SharedState
from packages.valory.skills.data_collection_abci.payloads import SpaceXDataPayload
from packages.valory.skills.data_collection_abci.rounds import (
    SpaceXDataAbciApp,
    SpaceXDataRound,
    SynchronizedData,
)

METADATA_FILENAME = "metadata.json"
HTTP_OK = 200

class SpaceXBaseBehaviour(BaseBehaviour, ABC):
    """Base behaviour for the spacex_data_abci behaviours."""
    @property
    def params(self) -> Params:
        """Return the params."""
        return cast(Params, super().params)

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return cast(SynchronizedData, super().synchronized_data)

    @property
    def metadata_filepath(self) -> str:
        """Get the temporary filepath to the metadata."""
        return str(Path(mkdtemp()) / METADATA_FILENAME)

class SpaceXDataBehaviour(SpaceXBaseBehaviour):
    """SpaceXDataBehaviour"""
    matching_round: Type[AbstractRound] = SpaceXDataRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""
        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address

            company_data = yield from self.get_spacex_company_data()
            company_valuation = company_data.get("valuation", None) if company_data else None

            self.context.logger.info(f"SpaceX company valuation: ${company_valuation:,.2f} USD")

            ipfs_hash = None
            if company_valuation is not None:
                stored_data = {"company_valuation": company_valuation}
                ipfs_hash = yield from self.send_to_ipfs(
                    filename=self.metadata_filepath,
                    obj=stored_data,
                    filetype=SupportedFiletype.JSON,
                )
                self.context.logger.info(
                    f"SpaceX data stored in IPFS: https://gateway.autonolas.tech/ipfs/{ipfs_hash}"
                )

            payload = SpaceXDataPayload(
                sender=sender,
                company_valuation=company_valuation,
                company_valuation_ipfs_hash=ipfs_hash,
            )

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def get_spacex_company_data(self) -> Generator[None, None, Optional[dict]]:
        """Get SpaceX company data."""
        url = self.params.spacex_api_url
        headers = {"Accept": "application/json"}

        response = yield from self.get_http_response(
            method="GET",
            url=url,
            headers=headers,
        )

        if response.status_code != HTTP_OK:
            self.context.logger.error(
                f"Error while pulling data from SpaceX API: {response.body}"
            )
            return None

        data = json.loads(response.body)
        self.context.logger.info("SpaceX data API call successful")
        return data

class SpaceXRoundBehaviour(AbstractRoundBehaviour):
    """SpaceXRoundBehaviour"""
    initial_behaviour_cls = SpaceXDataBehaviour
    abci_app_cls = SpaceXDataAbciApp
    behaviours: Set[Type[BaseBehaviour]] = [SpaceXDataBehaviour]