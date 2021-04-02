import brownie
import pytest
from brownie import Contract, Wei


def test_operation(
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
    assert joint.balanceOfPair() > 0

    joint.setReinvest(False, {"from": strategist})
    joint.harvest({"from": strategist})

    providerA.balanceOfWant() > 0
    providerB.balanceOfWant() > 0
    assert 1 == 2
