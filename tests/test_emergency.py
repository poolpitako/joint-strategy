import brownie
import pytest
from operator import xor


def test_emergency_exit(
    vaultA,
    vaultB,
    tokenA,
    tokenB,
    amountA,
    amountB,
    providerA,
    providerB,
    joint,
    gov,
    strategist,
    tokenA_whale,
    tokenB_whale,
):

    tokenA.approve(vaultA, 2 ** 256 - 1, {"from": tokenA_whale})
    vaultA.deposit(amountA, {"from": tokenA_whale})

    tokenB.approve(vaultB, 2 ** 256 - 1, {"from": tokenB_whale})
    vaultB.deposit(amountB, {"from": tokenB_whale})

    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
    assert xor(
        providerA.balanceOfWant() > 0, providerB.balanceOfWant() > 0
    )  # exactly one should have some remainder
    assert providerA.estimatedTotalAssets() > 0
    assert providerB.estimatedTotalAssets() > 0
    assert joint.balanceOfStake() > 0

    providerA.setEmergencyExit({"from": gov})
    providerB.setEmergencyExit({"from": gov})

    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})

    assert vaultA.strategies(providerA).dict()["totalLoss"] == 0
    assert vaultB.strategies(providerB).dict()["totalLoss"] == 0
    assert providerA.estimatedTotalAssets() == 0
    assert providerB.estimatedTotalAssets() == 0


def test_liquidate_from_joint(
    vaultA,
    vaultB,
    tokenA,
    tokenB,
    amountA,
    amountB,
    providerA,
    providerB,
    joint,
    gov,
    strategist,
    tokenA_whale,
    tokenB_whale,
):

    tokenA.approve(vaultA, 2 ** 256 - 1, {"from": tokenA_whale})
    vaultA.deposit(amountA, {"from": tokenA_whale})

    tokenB.approve(vaultB, 2 ** 256 - 1, {"from": tokenB_whale})
    vaultB.deposit(amountB, {"from": tokenB_whale})

    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
    assert xor(
        providerA.balanceOfWant() > 0, providerB.balanceOfWant() > 0
    )  # exactly one should have some remainder
    assert providerA.estimatedTotalAssets() > 0
    assert providerB.estimatedTotalAssets() > 0

    joint.liquidatePosition({"from": gov})
    joint.returnLooseToProviders({"from": gov})

    assert providerA.estimatedTotalAssets() > 0
    assert providerB.estimatedTotalAssets() > 0
    assert joint.balanceOfStake() == 0
    assert joint.estimatedTotalAssetsInToken(tokenA) == 0
    assert joint.estimatedTotalAssetsInToken(tokenB) == 0


def test_liquidate_from_joint_and_swap_reward(
    vaultA,
    vaultB,
    tokenA,
    tokenB,
    amountA,
    amountB,
    providerA,
    providerB,
    joint,
    gov,
    strategist,
    tokenA_whale,
    tokenB_whale,
    chain,
    sushi,
):

    tokenA.approve(vaultA, 2 ** 256 - 1, {"from": tokenA_whale})
    vaultA.deposit(amountA, {"from": tokenA_whale})

    tokenB.approve(vaultB, 2 ** 256 - 1, {"from": tokenB_whale})
    vaultB.deposit(amountB, {"from": tokenB_whale})

    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
    assert xor(
        providerA.balanceOfWant() > 0, providerB.balanceOfWant() > 0
    )  # exactly one should have some remainder
    assert providerA.estimatedTotalAssets() > 0
    assert providerB.estimatedTotalAssets() > 0

    # Wait plz
    chain.sleep(3600 * 1)
    chain.mine(int(3600 / 13) * 1)

    assert joint.pendingReward() > 0
    joint.liquidatePosition({"from": gov})
    assert joint.balanceOfReward() > 0

    with brownie.reverts():
        joint.swapTokenForToken(tokenA, sushi, joint.balanceOfA(), {"from": gov})

    joint.swapTokenForToken(sushi, tokenA, joint.balanceOfReward(), {"from": gov})

    joint.returnLooseToProviders({"from": gov})

    assert providerA.estimatedTotalAssets() > 0
    assert providerB.estimatedTotalAssets() > 0
    assert joint.balanceOfStake() == 0
    assert joint.estimatedTotalAssetsInToken(tokenA) == 0
    assert joint.estimatedTotalAssetsInToken(tokenB) == 0
