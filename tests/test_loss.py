import pytest
from brownie import Contract, Wei


def test_loss(
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
    attacker,
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

    # Wait plz
    chain.sleep(60 * 60 * 24 * 5)
    chain.mine(50)

    # If there is any profit it should go to the providers
    assert joint.pendingReward() > 0

    # There is a social attack and provider A was changed to the attacker!
    joint.setProviderA(attacker, {"from": joint.governance()})

    # Strategist liquidates the position and distribute profit
    assert tokenA.balanceOf(attacker) == 0
    joint.setReinvest(False, {"from": strategist})
    joint.liquidatePosition({"from": strategist})
    joint.harvest({"from": strategist})
    assert tokenA.balanceOf(attacker) > 0
    assert providerB.balanceOfWant() > 0
    # Provider A was rugged
    assert providerA.balanceOfWant() == 0

    # Do the profit/loss accounting
    providerA.setTakeProfit(True, {"from": strategist})
    providerB.setTakeProfit(True, {"from": strategist})
    providerA.setInvestWant(False, {"from": strategist})
    providerB.setInvestWant(False, {"from": strategist})
    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})

    assert vaultA.strategies(providerA).dict()["totalLoss"] > 0
    assert vaultA.strategies(providerA).dict()["totalGain"] == 0
    assert vaultB.strategies(providerB).dict()["totalGain"] > 0
