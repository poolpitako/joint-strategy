import pytest
from brownie import config, Contract


@pytest.fixture
def gov(accounts):
    yield accounts[0]


@pytest.fixture
def rewards(accounts):
    yield accounts[1]


@pytest.fixture
def guardian(accounts):
    yield accounts[2]


@pytest.fixture
def management(accounts):
    yield accounts[3]


@pytest.fixture
def strategist(accounts):
    yield accounts[4]


@pytest.fixture
def keeper(accounts):
    yield accounts[5]


@pytest.fixture
def attacker(accounts):
    yield accounts[6]


@pytest.fixture
def tokenA(vaultA):
    yield Contract(vaultA.token())


@pytest.fixture
def vaultA():
    # WFTM vault
    yield Contract("0x36e7aF39b921235c4b01508BE38F27A535851a5c")


@pytest.fixture
def wftm():
    # WFTM token
    yield Contract("0x21be370d5312f44cb42ce377bc9b8a0cef1a4c83")


@pytest.fixture
def tokenA_whale(accounts):
    yield accounts.at("0xbb634cafef389cdd03bb276c82738726079fcf2e", force=True)


@pytest.fixture
def tokenB_whale(accounts):
    yield accounts.at("0x05200cb2cee4b6144b2b2984e246b52bb1afcbd0", force=True)


@pytest.fixture
def tokenB(vaultB):
    yield Contract(vaultB.token())


@pytest.fixture
def vaultB():
    # ICE vault
    yield Contract("0xEea0714eC1af3b0D41C624Ba5ce09aC92F4062b1")


@pytest.fixture
def ice_rewards():
    # ICE masterchef
    yield Contract("0x05200cb2cee4b6144b2b2984e246b52bb1afcbd0")


@pytest.fixture
def ice():
    # ICE token
    yield Contract("0xf16e81dce15b08f326220742020379b855b87df9")


@pytest.fixture
def pancake_swap():
    yield Contract("0x10ED43C718714eb63d5aA57B78B54704E256024E")


@pytest.fixture
def wbnb():
    yield Contract("0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c")


@pytest.fixture
def binance_eth():
    yield Contract("0x2170Ed0880ac9A755fd29B2688956BD959F933F8")


@pytest.fixture
def binance_eth():
    yield Contract("0x2170Ed0880ac9A755fd29B2688956BD959F933F8")


@pytest.fixture
def cake_joint(gov, strategist, CakeJoint, wbnb, binance_eth, pancake_swap):
    tokenA = wbnb
    tokenB = binance_eth
    joint = gov.deploy(CakeJoint, gov, strategist, tokenA, tokenB, pancake_swap, 261)
    yield joint


@pytest.fixture
def boo_joint(gov, keeper, strategist, BooJoint, wftm):
    tokenA = wftm
    tokenB = Contract("0x049d68029688eabf473097a2fc38ef61633a3c7a")
    router = Contract("0xbe4fc72f8293f9d3512d58b969c98c3f676cb957")
    joint = gov.deploy(BooJoint, gov, keeper, strategist, tokenA, tokenB, router)
    mc = "0x2b2929E785374c651a81A63878Ab22742656DcDd"
    joint.setMasterChef(mc, {"from": gov})
    joint.setReward("0x841FAD6EAe12c286d1Fd18d1d525DFfA75C7EFFE", {"from": gov})
    joint.setWETH(wftm, {"from": gov})
    yield joint


@pytest.fixture
def joint(
    gov, keeper, strategist, tokenA, tokenB, Joint, router, ice_rewards, ice, wftm
):
    joint = gov.deploy(Joint, gov, keeper, strategist, tokenA, tokenB, router)
    joint.setMasterChef(ice_rewards, {"from": gov})
    joint.setReward(ice, {"from": gov})
    joint.setWETH(wftm, {"from": gov})
    yield joint


@pytest.fixture
def router():
    # Sushi in FTM
    yield Contract("0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506")


@pytest.fixture
def providerA(gov, strategist, keeper, vaultA, ProviderStrategy, joint):
    strategy = strategist.deploy(ProviderStrategy, vaultA, joint)
    strategy.setKeeper(keeper)

    # Steal the debt ratio from strat2 before adding
    strat_2 = Contract(vaultA.withdrawalQueue(2))
    debt_ratio = vaultA.strategies(strat_2).dict()["debtRatio"]
    vaultA.updateStrategyDebtRatio(strat_2, 0, {"from": vaultA.governance()})
    vaultA.addStrategy(
        strategy, debt_ratio, 0, 2 ** 256 - 1, 1_000, {"from": vaultA.governance()}
    )

    joint.setProviderA(strategy, {"from": gov})

    yield strategy


@pytest.fixture
def providerB(gov, strategist, keeper, vaultB, ProviderStrategy, joint):
    strategy = strategist.deploy(ProviderStrategy, vaultB, joint)

    # Steal the debt ratio from strat0 before adding
    strat_0 = Contract(vaultB.withdrawalQueue(0))
    debt_ratio = vaultB.strategies(strat_0).dict()["debtRatio"]
    vaultB.updateStrategyDebtRatio(strat_0, 0, {"from": vaultB.governance()})
    vaultB.addStrategy(
        strategy, debt_ratio, 0, 2 ** 256 - 1, 1_000, {"from": vaultB.governance()}
    )

    joint.setProviderB(strategy, {"from": gov})

    yield strategy
