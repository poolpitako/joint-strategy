from brownie import Contract, Wei, chain, accounts
import click


def main():

    providerB = Contract("0xF878E59600124ca46a30193A3F76EDAc99591698")
    old_joint = Contract(providerB.joint())
    providerA = Contract(old_joint.providerA())

    gov = accounts.load(click.prompt("Account", type=click.Choice(accounts.load())))
    old_joint.harvest({"from": gov, "gas_price": "1 gwei"})
    old_joint.liquidatePosition({"from": gov, "gas_price": "1 gwei"})
    old_joint.setReinvest(False, {"from": gov, "gas_price": "1 gwei"})
    old_joint.harvest({"from": gov, "gas_price": "1 gwei"})

    assert providerA.balanceOfWant() > 0
    assert providerB.balanceOfWant() > 0
    assert old_joint.balanceOfB() + old_joint.balanceOfA() == 0
    assert old_joint.balanceOfStake() == 0

    new_joint = Contract("0x201b41f69a4870323d8c9118e1d1b979939f8d45")

    providerA.setJoint(new_joint, {"from": gov, "gas_price": "1 gwei"})
    providerB.setJoint(new_joint, {"from": gov, "gas_price": "1 gwei"})
    new_joint.setProviderA(providerA, {"from": gov, "gas_price": "1 gwei"})
    new_joint.setProviderB(providerB, {"from": gov, "gas_price": "1 gwei"})

    assert providerA.takeProfit() == False
    assert providerB.takeProfit() == False

    vaultA = Contract(providerA.vault())
    vaultA.updateStrategyMaxDebtPerHarvest(
        providerA, 0, {"from": gov, "gas_price": "1 gwei"}
    )
    vaultB = Contract(providerB.vault())
    vaultB.updateStrategyMaxDebtPerHarvest(
        providerB, 0, {"from": gov, "gas_price": "1 gwei"}
    )

    providerA.harvest({"from": gov, "gas_price": "1 gwei"})
    providerB.harvest({"from": gov, "gas_price": "1 gwei"})

    # Invest capital
    new_joint.harvest({"from": gov, "gas_price": "1 gwei"})
