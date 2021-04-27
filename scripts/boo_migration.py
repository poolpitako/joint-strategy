from brownie import Contract, Wei, chain, accounts
import click


def main():
    new_joint = Contract("0x3bE77c7707666a8656bD49D91B875F28cb803471")
    old_joint = Contract("0x51eb737C5F76A031A1b8Aa9de272cd55865677Af")
    providerB = Contract("0x0Dbb0D0586CD7705636b820170811FE1378AB8dA")
    providerA = Contract("0x572E2248841b6DB05b0303A243Dbb475d7010B0c")
    # gov = accounts.load(click.prompt("Account", type=click.Choice(accounts.load())))
    gov = old_joint.governance()

    # set the new joint as both providers
    old_joint.setProviderA(new_joint, {"from": gov, "gas_price": "1 gwei"})
    old_joint.setProviderB(new_joint, {"from": gov, "gas_price": "1 gwei"})

    # Liquidate position and sell reward for ftm
    old_joint.liquidatePosition({"from": gov, "gas_price": "1 gwei"})
    assert old_joint.balanceOfReward() > 0
    old_joint.sellCapital(
        old_joint.reward(),
        old_joint.tokenA(),
        old_joint.balanceOfReward(),
        {"from": gov, "gas_price": "1 gwei"},
    )
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

    # Invest
    new_joint.invest({"from": gov, "gas_price": "1 gwei"})
