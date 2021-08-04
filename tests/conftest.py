import pytest
from brownie import config, Contract


@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


@pytest.fixture
def gov(accounts, vaultA):
    yield accounts.at(vaultA.governance(), force=True)


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
    # WETH vault
    yield Contract("0xa258C4606Ca8206D8aA700cE2143D7db854D168c")


@pytest.fixture
def vaultB():
    # YFI vault
    yield Contract("0xE14d13d8B3b85aF791b2AADD661cDBd5E6097Db1")


@pytest.fixture
def tokenA_whale(accounts):
    yield accounts.at("0x2F0b23f53734252Bda2277357e97e1517d6B042A", force=True)


@pytest.fixture
def tokenB_whale(accounts):
    yield accounts.at("0x3ff33d9162aD47660083D7DC4bC02Fb231c81677", force=True)


@pytest.fixture
def tokenB(vaultB):
    yield Contract(vaultB.token())


@pytest.fixture
def weth():
    yield Contract("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")


@pytest.fixture
def router():
    # Sushi
    yield Contract("0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F")


@pytest.fixture
def masterchef():
    yield Contract("0xc2EdaD668740f1aA35E4D8f227fB8E17dcA888Cd")


@pytest.fixture
def sushi():
    yield Contract("0x6B3595068778DD592e39A122f4f5a5cF09C90fE2")


@pytest.fixture
def mc_pid():
    yield 11


@pytest.fixture
def joint(gov, providerA, providerB, Joint, router, masterchef, sushi, weth, mc_pid):
    joint = gov.deploy(
        Joint, providerA, providerB, router, weth, masterchef, sushi, mc_pid
    )

    providerA.setJoint(joint, {"from": gov})
    providerB.setJoint(joint, {"from": gov})

    yield joint


@pytest.fixture
def providerA(gov, strategist, keeper, vaultA, ProviderStrategy):
    strategy = strategist.deploy(ProviderStrategy, vaultA)
    strategy.setKeeper(keeper)

    vaultA.addStrategy(strategy, 2000, 0, 2 ** 256 - 1, 1_000, {"from": gov})

    yield strategy


@pytest.fixture
def providerB(gov, strategist, vaultB, ProviderStrategy):
    strategy = strategist.deploy(ProviderStrategy, vaultB)

    # free up some debt ratio space
    vaultB.updateStrategyDebtRatio(
        "0x7A5D88510cD49E878ADe26E0f08bF374b5eCAF49", 8000, {"from": gov}
    )
    vaultB.addStrategy(strategy, 2000, 0, 2 ** 256 - 1, 1_000, {"from": gov})

    yield strategy
