from brownie import Contract, Wei, chain, accounts
import click


def main():
    providerB = Contract("0xF878E59600124ca46a30193A3F76EDAc99591698")
    old_joint = Contract(providerB.joint())
    providerA = Contract(old_joint.providerA())

    # gov = accounts.load(click.prompt("Account", type=click.Choice(accounts.load())))
    gov = old_joint.governance()

    new_joint = Contract("0x3F770158A92Fb7649ffce4313F8b6B1B1941ad9c")
    old_joint.setProviderA(new_joint, {"from": gov, "gas_price": "1 gwei"})
    old_joint.setProviderB(new_joint, {"from": gov, "gas_price": "1 gwei"})
    old_joint.liquidatePosition({"from": gov, "gas_price": "1 gwei"})
    old_joint.setReinvest(False, {"from": gov, "gas_price": "1 gwei"})
    old_joint.harvest({"from": gov, "gas_price": "1 gwei"})

    assert providerA.balanceOfWant() == 0
    assert providerB.balanceOfWant() == 0
    assert old_joint.balanceOfB() + old_joint.balanceOfA() == 0
    assert old_joint.balanceOfStake() == 0
    assert new_joint.balanceOfA() > 0
    assert new_joint.balanceOfB() > 0

    providerA.setJoint(new_joint, {"from": gov, "gas_price": "1 gwei"})
    providerB.setJoint(new_joint, {"from": gov, "gas_price": "1 gwei"})
    new_joint.setProviderA(providerA, {"from": gov, "gas_price": "1 gwei"})
    new_joint.setProviderB(providerB, {"from": gov, "gas_price": "1 gwei"})

    # Rebalance
    ftm_capital = Wei("46_000 ether")
    ice_capital = Wei("3996 ether")
    ftm_profit = (new_joint.balanceOfA() - ftm_capital) / 1e18
    ice_profit = (new_joint.balanceOfB() - ice_capital) / 1e18
    print(
        f"available FTM before sell: {new_joint.balanceOfA()/1e18} with profit: {ftm_profit}"
    )
    print(
        f"available ICE before sell: {new_joint.balanceOfB()/1e18} with profit: {ice_profit}"
    )
    new_joint.sellCapital(
        new_joint.tokenA(),
        new_joint.tokenB(),
        Wei("4_862 ether"),
        {"from": gov, "gas_price": "1 gwei"},
    )

    ftm_profit = (new_joint.balanceOfA() - ftm_capital) / 1e18
    ice_profit = (new_joint.balanceOfB() - ice_capital) / 1e18
    print(
        f"available FTM after sell: {new_joint.balanceOfA()/1e18} with profit: {ftm_profit}"
    )
    print(
        f"available ICE after sell: {new_joint.balanceOfB()/1e18} with profit: {ice_profit}"
    )

    # Return money to providers
    new_joint.setReinvest(False, {"from": gov, "gas_price": "1 gwei"})
    new_joint.harvest({"from": gov, "gas_price": "1 gwei"})

    # Providers state
    vaultA = Contract(providerA.vault())
    vaultB = Contract(providerB.vault())

    profitA_before = vaultA.strategies(providerA).dict()["totalGain"]
    profitB_before = vaultB.strategies(providerB).dict()["totalGain"]
    lossA_before = vaultA.strategies(providerA).dict()["totalLoss"]
    lossB_before = vaultB.strategies(providerB).dict()["totalLoss"]
    ppsA_before = vaultA.pricePerShare()
    ppsB_before = vaultB.pricePerShare()

    providerA.setTakeProfit(True, {"from": gov, "gas_price": "1 gwei"})
    providerB.setTakeProfit(True, {"from": gov, "gas_price": "1 gwei"})
    providerA.setInvestWant(False, {"from": gov, "gas_price": "1 gwei"})
    providerB.setInvestWant(False, {"from": gov, "gas_price": "1 gwei"})
    vaultA.updateStrategyDebtRatio(providerA, 0, {"from": gov, "gas_price": "1 gwei"})
    vaultB.updateStrategyDebtRatio(providerB, 0, {"from": gov, "gas_price": "1 gwei"})
    providerA.harvest({"from": gov, "gas_price": "1 gwei"})
    providerB.harvest({"from": gov, "gas_price": "1 gwei"})

    chain.sleep(60 * 60 * 8)
    chain.mine(1)
    # Providers state
    profitA_new = vaultA.strategies(providerA).dict()["totalGain"]
    profitB_new = vaultB.strategies(providerB).dict()["totalGain"]
    lossA_new = vaultA.strategies(providerA).dict()["totalLoss"]
    lossB_new = vaultB.strategies(providerB).dict()["totalLoss"]
    ppsA_new = vaultA.pricePerShare()
    ppsB_new = vaultB.pricePerShare()

    assert profitA_new - profitA_before > 0
    assert profitB_new - profitB_before > 0
    assert lossA_new - lossA_before == 0
    assert lossB_new - lossB_before == 0
    assert ppsA_new > ppsA_before
    assert ppsB_new > ppsB_before

    print(f"VaultA pps: {ppsA_new/1e18}, increase: {(ppsA_new-ppsA_before)/1e18}")
    print(f"VaultB pps: {ppsB_new/1e18}, increase: {(ppsB_new-ppsB_before)/1e18}")
