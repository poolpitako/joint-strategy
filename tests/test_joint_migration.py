import brownie
import pytest
from brownie import Contract, Wei


def test_join_migration(chain, accounts, Joint):

    providerB = Contract("0xF878E59600124ca46a30193A3F76EDAc99591698")
    old_joint = Contract(providerB.joint())
    providerA = Contract(old_joint.providerA())

    gov = accounts.at(old_joint.governance(), force=True)
    old_joint.harvest({"from": gov})
    old_joint.liquidatePosition({"from": gov})
    old_joint.setReinvest(False, {"from": gov})
    old_joint.harvest({"from": gov})

    assert providerA.balanceOfWant() > 0
    assert providerB.balanceOfWant() > 0
    assert old_joint.balanceOfB() + old_joint.balanceOfA() == 0
    assert old_joint.balanceOfStake() == 0

    new_joint = Joint.deploy(
        old_joint.governance(),
        old_joint.strategist(),
        old_joint.keeper(),
        old_joint.tokenA(),
        old_joint.tokenB(),
        old_joint.router(),
        {"from": gov},
    )

    providerA.setJoint(new_joint, {"from": gov})
    providerB.setJoint(new_joint, {"from": gov})
    new_joint.setProviderA(providerA, {"from": gov})
    new_joint.setProviderB(providerB, {"from": gov})

    assert providerA.takeProfit() == False
    assert providerB.takeProfit() == False

    vaultA = Contract(providerA.vault())
    vaultA.updateStrategyMaxDebtPerHarvest(providerA, 0, {"from": gov})
    vaultB = Contract(providerB.vault())
    vaultB.updateStrategyMaxDebtPerHarvest(providerB, 0, {"from": gov})

    providerA.harvest({"from": gov})
    providerB.harvest({"from": gov})

    # Invest capital
    new_joint.harvest({"from": gov})
    assert 1 == 2
