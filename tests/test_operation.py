import brownie
import pytest
from brownie import Contract, Wei
from operator import xor


def test_operation(
    chain,
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
    
    assert xor(providerA.balanceOfWant() > 0, providerB.balanceOfWant() > 0)
    assert joint.balanceOfA() == 0
    assert joint.balanceOfB() == 0
    assert joint.balanceOfStake() > 0

    investedA = vaultA.strategies(providerA).dict()['totalDebt'] - providerA.balanceOfWant()
    investedB = vaultB.strategies(providerB).dict()['totalDebt'] - providerB.balanceOfWant()

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} eth and {joint.estimatedTotalAssetsInToken(tokenB) / 1e18} yfi"
    )

    # Wait plz
    chain.sleep(3600 * 4)
    chain.mine(int(3600 / 13) * 4)

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} eth and {joint.estimatedTotalAssetsInToken(tokenB) / 1e18} yfi"
    )

    # If there is any profit it should go to the providers
    assert joint.pendingReward() > 0
    # If joint doesn't reinvest, and providers do not invest want, the want
    # will stay in the providers
    providerA.setInvestWant(False, {"from": strategist})
    providerB.setInvestWant(False, {"from": strategist})
    providerA.setTakeProfit(True, {"from": strategist})
    providerB.setTakeProfit(True, {"from": strategist})
    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
    assert providerA.balanceOfWant() > 0
    assert providerB.balanceOfWant() > 0

    gainA = vaultA.strategies(providerA).dict()["totalGain"] 
    gainB = vaultB.strategies(providerB).dict()["totalGain"] 

    assert gainA > 0
    assert gainB > 0

    returnA = gainA / investedA
    returnB = gainB / investedB

    print(f"Return: {returnA*100:.5f}% a {returnB*100:.5f}% b" )

    assert (
        pytest.approx(returnA, rel=50e-3)
        == returnB
    )

    # Harvest should be a no-op
    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
    chain.sleep(60 * 60 * 8)
    chain.mine(1)
    assert providerA.balanceOfWant() > 0
    assert providerB.balanceOfWant() > 0

    print(f"ProviderA: {providerA.balanceOfWant()/1e18}")
    print(f"ProviderB: {providerB.balanceOfWant()/1e18}")

    chain.sleep(60 * 60 * 8)
    chain.mine(1)
    assert vaultA.strategies(providerA).dict()["totalGain"] > 0
    assert vaultB.strategies(providerB).dict()["totalGain"] > 0

    print(f"eth profit: {vaultA.strategies(providerA).dict()['totalGain']/1e18} eth")
    print(f"yfi profit: {vaultB.strategies(providerB).dict()['totalGain']/1e18} yfi")


def test_operation_swap_a4b(
    chain,
    vaultA,
    vaultB,
    tokenA,
    tokenB,
    amountA,
    amountB,
    providerA,
    providerB,
    joint,
    router,
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
    assert xor(providerA.balanceOfWant() > 0, providerB.balanceOfWant() > 0)
    assert joint.balanceOfA() == 0 and joint.balanceOfB() == 0

    print(f"Joint has {joint.balanceOfA()/1e18} eth and {joint.balanceOfB()/1e18} yfi")
    assert joint.balanceOfStake() > 0

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} eth and {joint.estimatedTotalAssetsInToken(tokenB) / 1e18} yfi"
    )

    tokenA.approve(router, 2 ** 256 - 1, {"from": tokenA_whale})
    router.swapExactTokensForTokens(
        tokenA.balanceOf(tokenA_whale),
        0,
        [tokenA, tokenB],
        tokenA_whale,
        2 ** 256 - 1,
        {"from": tokenA_whale},
    )

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} eth and {joint.estimatedTotalAssetsInToken(tokenB) / 1e18} yfi"
    )

    # Wait plz
    chain.sleep(3600 * 1)
    chain.mine(int(3600 / 13))

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} eth and {joint.estimatedTotalAssetsInToken(tokenB) / 1e18} yfi"
    )

    # If there is any profit it should go to the providers
    assert joint.pendingReward() > 0
    # If joint doesn't reinvest, and providers do not invest want, the want
    # will stay in the providers
    providerA.setInvestWant(False, {"from": strategist})
    providerB.setInvestWant(False, {"from": strategist})
    providerA.setTakeProfit(True, {"from": strategist})
    providerB.setTakeProfit(True, {"from": strategist})
    tx = providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
    ratios_events = tx.events["Ratios"]
    print(f"Ratios: {ratios_events}")
    assert providerA.balanceOfWant() > 0
    assert providerB.balanceOfWant() > 0
    assert vaultA.strategies(providerA).dict()["totalLoss"] > 0
    assert vaultB.strategies(providerB).dict()["totalLoss"] > 0
    assert (
        pytest.approx(ratios_events[-1]["tokenA"], abs=125)
        == ratios_events[-1]["tokenB"]
    )

    print(f"ProviderA: {providerA.balanceOfWant()/1e18}")
    print(f"ProviderB: {providerB.balanceOfWant()/1e18}")
    print(f"eth loss: {vaultA.strategies(providerA).dict()['totalLoss']/1e18} eth")
    print(f"yfi loss: {vaultB.strategies(providerB).dict()['totalLoss']/1e18} yfi")


def test_operation_swap_b4a(
    chain,
    vaultA,
    vaultB,
    tokenA,
    tokenB,
    amountA,
    amountB,
    providerA,
    providerB,
    joint,
    router,
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
    assert xor(providerA.balanceOfWant() > 0, providerB.balanceOfWant() > 0)
    assert joint.balanceOfA() == 0 and joint.balanceOfB() == 0

    print(f"Joint has {joint.balanceOfA()/1e18} eth and {joint.balanceOfB()/1e18} yfi")
    assert joint.balanceOfStake() > 0

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} eth and {joint.estimatedTotalAssetsInToken(tokenB) / 1e18} yfi"
    )

    tokenB.approve(router, 2 ** 256 - 1, {"from": tokenB_whale})
    router.swapExactTokensForTokens(
        1500 * 1e18,
        0,
        [tokenB, tokenA],
        tokenB_whale,
        2 ** 256 - 1,
        {"from": tokenB_whale},
    )

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} eth and {joint.estimatedTotalAssetsInToken(tokenB) / 1e18} yfi"
    )

    # Wait plz
    chain.sleep(3600 * 1)
    chain.mine(int(3600 / 13))

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} eth and {joint.estimatedTotalAssetsInToken(tokenB) / 1e18} yfi"
    )

    # If there is any profit it should go to the providers
    assert joint.pendingReward() > 0
    # If joint doesn't reinvest, and providers do not invest want, the want
    # will stay in the providers
    providerA.setInvestWant(False, {"from": strategist})
    providerB.setInvestWant(False, {"from": strategist})
    providerA.setTakeProfit(True, {"from": strategist})
    providerB.setTakeProfit(True, {"from": strategist})
    tx = providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
    ratios_events = tx.events["Ratios"]
    print(f"Ratios: {ratios_events}")
    assert providerA.balanceOfWant() > 0
    assert providerB.balanceOfWant() > 0
    assert vaultA.strategies(providerA).dict()["totalLoss"] > 0
    assert vaultB.strategies(providerB).dict()["totalLoss"] > 0
    assert (
        pytest.approx(ratios_events[-1]["tokenA"], abs=125)
        == ratios_events[-1]["tokenB"]
    )

    print(f"ProviderA: {providerA.balanceOfWant()/1e18}")
    print(f"ProviderB: {providerB.balanceOfWant()/1e18}")
    print(f"eth loss: {vaultA.strategies(providerA).dict()['totalLoss']/1e18} eth")
    print(f"yfi loss: {vaultB.strategies(providerB).dict()['totalLoss']/1e18} yfi")
