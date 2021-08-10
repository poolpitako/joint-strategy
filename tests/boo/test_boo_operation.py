import brownie
import pytest
from brownie import Contract, Wei


@pytest.mark.require_network("ftm-main-fork")
def test_operation(
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
    tokenA_amount,
    tokenB_amount,
):

    tokenA.approve(vaultA, 2 ** 256 - 1, {"from": tokenA_whale})
    vaultA.deposit(tokenA_amount, {"from": tokenA_whale})

    tokenB.approve(vaultB, 2 ** 256 - 1, {"from": tokenB_whale})
    vaultB.deposit(tokenB_amount, {"from": tokenB_whale})

    providerA.harvest({"from": strategist})
    print(f"Joint has {joint.balanceOfA()/1e18} boo and {joint.balanceOfB()/1e18} wftm")
    providerB.harvest({"from": strategist})
    assert joint.balanceOfA() > 0 or joint.balanceOfB() > 0

    print(f"Joint has {joint.balanceOfA()/1e18} boo and {joint.balanceOfB()/1e18} wftm")
    assert joint.balanceOfStake() > 0

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} boo and {joint.estimatedTotalAssetsInToken(tokenB) / 1e18} wftm"
    )

    # Wait plz
    chain.sleep(3600 * 10)
    chain.mine(int(3600 / 13) * 10)

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} boo and {joint.estimatedTotalAssetsInToken(tokenB) / 1e18} wftm"
    )

    # If there is any profit it should go to the providers
    assert joint.pendingReward() > 0
    # If joint doesn't reinvest, and providers do not invest want, the want
    # will stay in the providers
    joint.setReinvest(False, {"from": strategist})
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
    assert vaultA.strategies(providerA).dict()["totalGain"] > 0
    assert vaultB.strategies(providerB).dict()["totalGain"] > 0
    assert ratios_events[-1]["tokenA"] == ratios_events[-1]["tokenB"]

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
    assert vaultA.pricePerShare() > 1e18
    assert vaultB.pricePerShare() > 1e18

    print(f"boo profit: {vaultA.strategies(providerA).dict()['totalGain']/1e18} boo")
    print(f"wftm profit: {vaultB.strategies(providerB).dict()['totalGain']/1e18} wftm")


@pytest.mark.require_network("ftm-main-fork")
def test_operation_swap_a4b(
    chain,
    vaultA,
    vaultB,
    tokenA,
    tokenB,
    providerA,
    providerB,
    joint,
    router,
    strategist,
    tokenA_whale,
    tokenB_whale,
    tokenA_amount,
    tokenB_amount,
):

    tokenA.approve(vaultA, 2 ** 256 - 1, {"from": tokenA_whale})
    vaultA.deposit(tokenA_amount, {"from": tokenA_whale})

    tokenB.approve(vaultB, 2 ** 256 - 1, {"from": tokenB_whale})
    vaultB.deposit(tokenB_amount, {"from": tokenB_whale})

    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
    assert joint.balanceOfA() > 0 or joint.balanceOfB() > 0

    print(f"Joint has {joint.balanceOfA()/1e18} boo and {joint.balanceOfB()/1e18} wftm")
    assert joint.balanceOfStake() > 0

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} boo and {joint.estimatedTotalAssetsInToken(tokenB) / 1e18} wftm"
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
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} boo and {joint.estimatedTotalAssetsInToken(tokenB) / 1e18} wftm"
    )

    # Wait plz
    chain.sleep(3600 * 1)
    chain.mine(int(3600 / 13))

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} boo and {joint.estimatedTotalAssetsInToken(tokenB) / 1e18} wftm"
    )

    # If there is any profit it should go to the providers
    assert joint.pendingReward() > 0
    # If joint doesn't reinvest, and providers do not invest want, the want
    # will stay in the providers
    joint.setReinvest(False, {"from": strategist})
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
        pytest.approx(ratios_events[-1]["tokenA"], abs=75)
        == ratios_events[-1]["tokenB"]
    )

    print(f"ProviderA: {providerA.balanceOfWant()/1e18}")
    print(f"ProviderB: {providerB.balanceOfWant()/1e18}")
    print(f"boo loss: {vaultA.strategies(providerA).dict()['totalLoss']/1e18} boo")
    print(f"wftm loss: {vaultB.strategies(providerB).dict()['totalLoss']/1e18} wftm")


@pytest.mark.require_network("ftm-main-fork")
def test_operation_swap_b4a(
    chain,
    vaultA,
    vaultB,
    tokenA,
    tokenB,
    providerA,
    providerB,
    joint,
    router,
    strategist,
    tokenA_whale,
    tokenB_whale,
    tokenA_amount,
    tokenB_amount,
):

    tokenA.approve(vaultA, 2 ** 256 - 1, {"from": tokenA_whale})
    vaultA.deposit(tokenA_amount, {"from": tokenA_whale})

    tokenB.approve(vaultB, 2 ** 256 - 1, {"from": tokenB_whale})
    vaultB.deposit(tokenB_amount, {"from": tokenB_whale})

    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
    assert joint.balanceOfA() > 0 or joint.balanceOfB() > 0

    print(f"Joint has {joint.balanceOfA()/1e18} boo and {joint.balanceOfB()/1e18} wftm")
    assert joint.balanceOfStake() > 0

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} boo and {joint.estimatedTotalAssetsInToken(tokenB) / 1e18} wftm"
    )

    tokenB.approve(router, 2 ** 256 - 1, {"from": tokenB_whale})
    router.swapExactTokensForTokens(
        tokenB.balanceOf(tokenB_whale),
        0,
        [tokenB, tokenA],
        tokenB_whale,
        2 ** 256 - 1,
        {"from": tokenB_whale},
    )

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} boo and {joint.estimatedTotalAssetsInToken(tokenB) / 1e18} wftm"
    )

    # Wait plz
    chain.sleep(3600 * 1)
    chain.mine(int(3600 / 13))

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} boo and {joint.estimatedTotalAssetsInToken(tokenB) / 1e18} wftm"
    )

    # If there is any profit it should go to the providers
    assert joint.pendingReward() > 0
    # If joint doesn't reinvest, and providers do not invest want, the want
    # will stay in the providers
    joint.setReinvest(False, {"from": strategist})
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
        pytest.approx(ratios_events[-1]["tokenA"], abs=75)
        == ratios_events[-1]["tokenB"]
    )

    print(f"ProviderA: {providerA.balanceOfWant()/1e18}")
    print(f"ProviderB: {providerB.balanceOfWant()/1e18}")
    print(f"boo loss: {vaultA.strategies(providerA).dict()['totalLoss']/1e18} boo")
    print(f"wftm loss: {vaultB.strategies(providerB).dict()['totalLoss']/1e18} wftm")
