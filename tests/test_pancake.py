import pytest
from brownie import Wei, accounts, chain


def test_pancake(cake_joint, gov, strategist, wbnb, binance_eth):
    wbnb_whale = accounts.at("0x7Bb89460599Dbf32ee3Aa50798BBcEae2A5F7f6a", force=True)
    eth_whale = accounts.at("0x631Fc1EA2270e98fbD9D92658eCe0F5a269Aa161", force=True)
    wbnb.transfer(cake_joint, Wei("100 ether"), {"from": wbnb_whale})
    binance_eth.transfer(cake_joint, Wei("50 ether"), {"from": eth_whale})

    assert cake_joint.balanceOfA() > 0
    assert cake_joint.balanceOfB() > 0

    cake_joint.invest({"from": strategist})

    chain.sleep(60 * 60 * 24 * 3)
    chain.mine(1)

    assert cake_joint.pendingReward() > 0
    cake_joint.liquidatePosition({"from": strategist})

    assert cake_joint.balanceOfA() > 0
    assert cake_joint.balanceOfB() > 0
    assert cake_joint.balanceOfReward() > 0

    cake_joint.sellCapital(
        cake_joint.reward(),
        cake_joint.tokenA(),
        cake_joint.balanceOfReward() // 2,
        {"from": strategist},
    )

    cake_joint.sellCapital(
        cake_joint.reward(),
        cake_joint.tokenB(),
        cake_joint.balanceOfReward(),
        {"from": strategist},
    )

    assert cake_joint.balanceOfA() > Wei("100 ether")
    assert cake_joint.balanceOfB() > Wei("50 ether")
