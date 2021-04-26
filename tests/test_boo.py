import pytest
from brownie import Contract, Wei, accounts, chain


def test_loss(boo_joint, gov, strategist):

    tokenA = Contract("0x21be370d5312f44cb42ce377bc9b8a0cef1a4c83")
    tokenA_whale = accounts.at("0xbb634cafef389cdd03bb276c82738726079fcf2e", force=True)
    tokenA.transfer(boo_joint, Wei("16000 ether"), {"from": tokenA_whale})

    tokenB = Contract("0x049d68029688eabf473097a2fc38ef61633a3c7a")
    tokenB_whale = accounts.at("0xcdf46720bdf30d6bd0912162677c865d4344b0ca", force=True)
    tokenB.transfer(boo_joint, 5_000 * 1e6, {"from": tokenB_whale})

    assert boo_joint.balanceOfA() > 0
    assert boo_joint.balanceOfB() > 0

    boo_joint.setReinvest(True, {"from": gov})
    boo_joint.harvest({"from": gov})

    chain.sleep(60 * 60 * 3)
    chain.mine(1)

    assert boo_joint.pendingReward() > 0
    boo_joint.liquidatePosition({"from": gov})

    assert boo_joint.balanceOfA() > 0
    assert boo_joint.balanceOfB() > 0
    assert boo_joint.balanceOfReward() > 0

    boo_joint.sellCapital(
        boo_joint.reward(),
        boo_joint.tokenA(),
        boo_joint.balanceOfReward() // 2,
        {"from": gov},
    )

    boo_joint.sellCapital(
        boo_joint.reward(),
        boo_joint.tokenB(),
        boo_joint.balanceOfReward(),
        {"from": gov},
    )

    assert boo_joint.balanceOfA() > Wei("16000 ether")
    assert boo_joint.balanceOfB() > 5_000 * 1e6
