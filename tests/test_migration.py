import brownie
import pytest
from brownie import Contract, Wei


def test_migration(
    chain,
    vaultA,
    vaultB,
    tokenA,
    tokenB,
    providerA,
    providerB,
    joint,
    gov,
    strategist,
    tokenA_whale,
    tokenB_whale,
    ProviderStrategy,
):

    tokenA.approve(vaultA, 2 ** 256 - 1, {"from": tokenA_whale})
    vaultA.deposit({"from": tokenA_whale})

    tokenB.approve(vaultB, 2 ** 256 - 1, {"from": tokenB_whale})
    vaultB.deposit({"from": tokenB_whale})

    # https://www.coingecko.com/en/coins/fantom
    tokenA_price = 0.438065
    # https://www.coingecko.com/en/coins/popsicle-finance
    tokenB_price = 4.47
    usd_amount = Wei("1000 ether")

    vaultA.updateStrategyMaxDebtPerHarvest(
        providerA, usd_amount // tokenA_price, {"from": vaultA.governance()}
    )
    vaultB.updateStrategyMaxDebtPerHarvest(
        providerB, usd_amount // tokenB_price, {"from": vaultB.governance()}
    )

    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
    assert joint.balanceOfA() * usd_amount > Wei("990 ether")
    assert joint.balanceOfB() * usd_amount > Wei("990 ether")
    joint.harvest({"from": strategist})
    assert joint.balanceOfStake() > 0

    tx = providerA.cloneProviderStrategy(
        providerA.vault(),
        providerA.strategist(),
        providerA.rewards(),
        providerA.keeper(),
        providerA.joint(),
    )
    new_a = ProviderStrategy.at(tx.events["Cloned"]["clone"])
    vaultA.migrateStrategy(providerA, new_a, {"from": vaultA.governance()})
    joint.setProviderA(new_a, {"from": gov})

    # Wait plz
    chain.sleep(60 * 60 * 24 * 5)
    chain.mine(50)

    # If there is any profit it should go to the providers
    assert joint.pendingReward() > 0
    # If joint doesn't reinvest, and providers do not invest want, the want
    # will stay in the providers
    joint.setReinvest(False, {"from": strategist})
    new_a.setInvestWant(False, {"from": strategist})
    providerB.setInvestWant(False, {"from": strategist})
    joint.harvest({"from": strategist})
    assert new_a.balanceOfWant() > 0
    assert providerB.balanceOfWant() > 0

    # Harvest should be a no-op
    new_a.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
    chain.sleep(60 * 60 * 8)
    chain.mine(1)
    assert new_a.balanceOfWant() > 0
    assert providerB.balanceOfWant() > 0
    assert vaultA.strategies(new_a).dict()["totalGain"] == 0
    assert vaultB.strategies(providerB).dict()["totalGain"] == 0

    # Liquidate position and make sure capital + profit is back
    joint.liquidatePosition({"from": strategist})
    new_a.setTakeProfit(True, {"from": strategist})
    providerB.setTakeProfit(True, {"from": strategist})
    new_a.setInvestWant(False, {"from": strategist})
    providerB.setInvestWant(False, {"from": strategist})

    joint.harvest({"from": strategist})
    assert new_a.balanceOfWant() > 0
    assert providerB.balanceOfWant() > 0

    new_a.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
    assert vaultA.strategies(new_a).dict()["totalGain"] > 0
    assert vaultB.strategies(providerB).dict()["totalGain"] > 0
