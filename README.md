# Monitoring Service

A service to learn about [Olas](https://olas.network/) agents and [Open Autonomy](https://github.com/valory-xyz/open-autonomy).

## Project Overview

The Monitoring Service is an autonomous DeFi management system that monitors token balances and prices on the Gnosis Chain, automatically executing deposits and swaps when certain conditions are met. The service uses a multi-agent system with consensus-based decision making to ensure reliable and secure operation.

## Use Case & Benefits

The Monitoring Service is a decentralized application that automates the monitoring and management of token balances and prices on the Gnosis Chain. It provides:

1. **Automated Balance Monitoring**: Continuously monitors OLAS token and native xDAI balances of specified addresses
2. **Price Deviation Detection**: Tracks USDC price movements and identifies significant deviations from the $1 peg
3. **Automated Fund Management**: Handles deposits when balances fall below thresholds
4. **DEX Integration**: Executes automated swaps on SushiSwap when price opportunities arise
5. **Multi-Signature Security**: Uses Gnosis Safe for secure transaction execution

Key benefits:
- Reduced manual monitoring overhead
- Quick response to price deviations
- Automated liquidity management
- Decentralized operation with consensus
- Transparent on-chain execution

### Technical Architecture

The service implements a state machine with five main rounds, each handling specific aspects of the monitoring and execution process:

#### Rounds and Behaviors

1. **TokenBalanceCheckRound**
   - **Purpose**: Initial monitoring and data collection
   - **Behaviors**:
     - Checks OLAS and xDAI balances
     - Monitors USDC price
     - Records significant price deviations to IPFS
     - Triggers subsequent rounds based on findings
   - **Thresholds**: 
     - OLAS Balance: 1000 OLAS
     - Native Balance: 100 xDAI

2. **DepositDecisionMakingRound**
   - **Purpose**: Evaluates need for deposits
   - **Behaviors**:
     - Analyzes current balances against thresholds
     - Determines which tokens need replenishment
     - Decides between single or multi-token deposits
   - **Key Decisions**:
     - Single token deposit
     - Multi-token deposit
     - No action needed

3. **TokenDepositRound**
   - **Purpose**: Handles deposit transaction creation
   - **Behaviors**:
     - Constructs Safe transactions for deposits
     - Handles multi-send transactions for multiple tokens
     - Sets refill amounts (0.5 xDAI, 50 OLAS)
   - **Transaction Types**:
     - Native xDAI transfers
     - OLAS token transfers
     - Multi-token batched transfers

4. **SwapDecisionMakingRound**
   - **Purpose**: Evaluates trading opportunities
   - **Behaviors**:
     - Analyzes USDC price deviations
     - Checks IPFS for stored price data
     - Determines optimal swap direction
   - **Threshold**:
     - Price Deviation: 0.001%

5. **TokenSwapRound**
   - **Purpose**: Executes swap transactions
   - **Behaviors**:
     - Creates swap transactions on SushiSwap
     - Handles token wrapping (xDAI → WXDAI)
     - Manages token approvals
     - Combines swaps with deposits when needed
   - **Parameters**:
     - Swap Amount: 0.1 xDAI
     - Slippage: 1%
     - Transaction Deadline: 5 minutes

#### Consensus Mechanism

The service uses a consensus-based approach where:
- Multiple agents independently monitor and propose actions
- Decisions require agreement among agents (3/4 threshold)
- Safe transactions require multiple signatures
- Failed consensus triggers reset mechanisms

#### Transaction Flow

1. Monitoring Phase:
   ```
   Balance/Price Check → Decision Making → Transaction Creation
   ```

2. Execution Phase:
   ```
   Safe Transaction → Multi-sig Signing → On-chain Execution
   ```

3. Verification Phase:
   ```
   Transaction Confirmation → State Update → New Monitoring Cycle
   ```

## System Requirements

- Python `>=3.10`
- [Tendermint](https://docs.tendermint.com/v0.34/introduction/install.html) `==0.34.19`
- [IPFS node](https://docs.ipfs.io/install/command-line/#official-distributions) `==0.6.0`
- [Pip](https://pip.pypa.io/en/stable/installation/)
- [Poetry](https://python-poetry.org/)
- [Docker Engine](https://docs.docker.com/engine/install/)
- [Docker Compose](https://docs.docker.com/compose/install/)
- [Set Docker permissions so you can run containers as non-root user](https://docs.docker.com/engine/install/linux-postinstall/)

## Run Your Own Agent

### Get the Code

1. Clone this repo:
    ```
    git clone https://github.com/Mohsinsiddi/demo-app.git
    ```

2. Create the virtual environment:
    ```
    cd demo-app
    poetry shell
    poetry install
    ```

3. Sync packages:
    ```
    autonomy packages sync --update-packages
    ```

### Generate Keys and Setup Environment

1. Generate keys for four agents:
    ```
    autonomy generate-key ethereum -n 4
    ```
    This will create a `keys.json` file with addresses and private keys. Example addresses:
    ```
    0x6ab053bc2d19F3cFcda910CC0265678EcF990886
    0x2942D4a5Eb45aE2E0e90c50Ebfe29B218588Dc82
    0x4F7632B6F5964BaAAf2DcE14694DC464674C75F6
    0x23C2883b12a577685FB3cFc558d74525d239CfF5
    ```

2. Create `ethereum_private_key.txt`:
   - Copy one private key from `keys.json`
   - Paste it into `ethereum_private_key.txt`
   - Ensure there's no newline at the end of the file

3. Deploy Gnosis Safes:
   - Visit [Safe on Gnosis](https://app.safe.global/welcome)
   - Create two safes with your agent addresses as signers:
     - One safe with 1/4 threshold (for testing)
     - One safe with 3/4 threshold (for production)
   Example addresses:
   ```
   Single-signer Safe: 0x9076C7C2d751d1CE7F332744cc752f722E3cC6
   Multi-signer Safe: 0x0360F9fB57882DfD6d22E5F4015F0FC2039946f0
   ```

4. Setup Tenderly:
   - Create account at [Tenderly](https://tenderly.co/)
   - Create a Gnosis chain fork
   - Fund your agents and Safes with xDAI and OLAS tokens
   - Note your fork's RPC URL

5. Configure Environment:
   - Copy sample.env: `cp sample.env .env`
   - Add the following configuration:

   ```
   # Agent Configuration
   ALL_PARTICIPANTS='["0x6ab053bc2d19F3cFcda910CC0265678EcF990886","0x2942D4a5Eb45aE2E0e90c50Ebfe29B218588Dc82","0x4F7632B6F5964BaAAf2DcE14694DC464674C75F6","0x23C2883b12a577685FB3cFc558d74525d239CfF5"]'
   SAFE_CONTRACT_ADDRESS=0x0360F9fB57882DfD6d22E5F4015F0FC2039946f0
   SAFE_CONTRACT_ADDRESS_SINGLE=0x9076C7C2d751d1CE7F332744cc752f722E3cC6
   
   # Network & API Configuration
   GNOSIS_LEDGER_RPC=https://virtual.gnosis.rpc.tenderly.co/f61f203b-adce-4639-8281-d2af89aff188
   COINGECKO_API_KEY=CG-5Nn7yAS9qAvHZxKtGqfjQHri
   TRANSFER_TARGET_ADDRESS=0x4e9a8fE0e0499c58a53d3C2A2dE25aaCF9b925A8
   
   # Service Parameters
   ON_CHAIN_SERVICE_ID=1
   RESET_PAUSE_DURATION=10
   RESET_TENDERMINT_AFTER=10
   ```

Environment Variables Explained:
- `ALL_PARTICIPANTS`: List of agent addresses for consensus
- `SAFE_CONTRACT_ADDRESS`: Multi-sig safe address (3/4 threshold)
- `SAFE_CONTRACT_ADDRESS_SINGLE`: Testing safe address (1/4 threshold)
- `GNOSIS_LEDGER_RPC`: Tenderly fork RPC endpoint
- `COINGECKO_API_KEY`: API key for price monitoring
- `TRANSFER_TARGET_ADDRESS`: Default recipient for test transfers
- `ON_CHAIN_SERVICE_ID`: Unique identifier for the service
- `RESET_PAUSE_DURATION`: Time between reset attempts (seconds)
- `RESET_TENDERMINT_AFTER`: Number of blocks before resetting Tendermint

### Run the Service

#### Single Agent (Testing)
1. Modify .env to include only one address in ALL_PARTICIPANTS
2. Run:
    ```
    bash run_agent.sh
    ```

#### Full Service (4 Agents)
1. Ensure ALL_PARTICIPANTS contains all 4 addresses
2. Start Docker:
    ```
    docker
    ```
3. Launch service:
    ```
    bash run_service.sh
    ```
4. Monitor logs:
    ```
    docker logs -f monitoringservice_abci_0
    ```