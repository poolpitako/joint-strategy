from brownie import Contract, Wei, chain, accounts
import click
from pycoingecko import CoinGeckoAPI


def main():
    # gov = accounts.load(click.prompt("Account", type=click.Choice(accounts.load())))
    # print(f"You are using: 'gov' [{gov}]")
    gov = accounts.at("0xC27DdC26F48724AD90E4d152940e4981af7Ed50d", force=True)
    providerA = Contract("0x572E2248841b6DB05b0303A243Dbb475d7010B0c")
    providerB = Contract("0x0Dbb0D0586CD7705636b820170811FE1378AB8dA")
    joint = Contract("0x3bE77c7707666a8656bD49D91B875F28cb803471")
    vaultA = Contract("0x36e7aF39b921235c4b01508BE38F27A535851a5c")
    vaultB = Contract("0x1E9eC284BA99E14436f809291eBF7dC8CCDB12e1")
    ftm = Contract("0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83")
    fusdt = Contract("0x049d68029688eAbF473097a2fC38ef61633A3C7A")
    boo = Contract("0x841FAD6EAe12c286d1Fd18d1d525DFfA75C7EFFE")
    ftm_capital = Wei(
        "12_364.532347266988 ether"
    )  # actualizar en cada iteracion - (26/04) 0xc5bc135e95655fb0601fbd1d63723c5a71140438e959d75bf29664be00851e79
    fusdt_capital = Wei(
        "4_153.272242 ether"
    )  # actualizar en cada iteracion - (26/04) 0xc5bc135e95655fb0601fbd1d63723c5a71140438e959d75bf29664be00851e79
    cg = CoinGeckoAPI()
    ret = cg.get_price(ids=["fantom", "tether"], vs_currencies="usd")

    ftm_profit_usd = (
        -1012.5366144730546
    )  # se carga con los datos de joint_status en fork, despues del joint_sell_reward
    fusdt_profit_usd = 1031.0654278269499  # se carga con los datos de joint_status en fork, despues del joint_sell_reward
    media_profit_lp = (ftm_profit_usd + fusdt_profit_usd) / 2

    if fusdt_profit_usd > ftm_profit_usd:
        joint.liquidatePosition({"from": gov, "gas_price": "1 gwei"})
        sell_fusdt_buy_ftm = (media_profit_lp - ftm_profit_usd) * ret["tether"]["usd"]
        joint.sellCapital(
            joint.tokenB(),
            joint.tokenA(),
            Wei(f"{sell_fusdt_buy_ftm} ether"),
            {"from": gov, "gas_price": "1 gwei", "gas_limit": 2_000_000},
        )
        joint.distributeProfit({"from": gov, "gas_price": "1 gwei"})
        ftm_profit = (joint.balanceOfA() - ftm_capital) / 1e18
        ftm_gp = ftm_profit / (ftm_capital / 1e18)
        fusdt_profit = (joint.balanceOfB() / 1e6) - (fusdt_capital / 1e18)
        fusdt_gp = fusdt_profit / (fusdt_capital / 1e18)
        ftm_profit_usd = ret["fantom"]["usd"] * ftm_profit
        fusdt_profit_usd = ret["tether"]["usd"] * fusdt_profit
        print(f"")
        print(f"With fusdt profit > ftm profit. Sell Capital")
        print(f"jointStaked: {joint.balanceOfStake()}")
        print(f"Pending reward: {joint.pendingReward()/1e18} boo")
        print(f"ftm avail in joint {joint.balanceOfA()/1e18}")
        print(f"fusdt avail in joint {joint.balanceOfB()/1e6}")
        print(f"ftm avail in ProviderA {providerA.balanceOf()/1e18}")
        print(f"fusdt avail in ProviderB {providerB.balanceOf()/1e6}")
        print(
            f"ftm profit {ftm_profit} in providerA with usd value of {ftm_profit_usd}"
        )
        print(
            f"ice profit {fusdt_profit} in providerB with usd value of {fusdt_profit_usd}"
        )
        print(f"ftm GP {ftm_gp}")
        print(f"ice GP {fusdt_gp}")
        print(f"")

    elif fusdt_profit_usd < ftm_profit_usd:
        joint.liquidatePosition({"from": gov, "gas_price": "1 gwei"})
        sell_ftm_buy_fusdt = (media_profit_lp - fusdt_profit_usd) * ret["fantom"]["usd"]
        joint.sellCapital(
            joint.tokenA(),
            joint.tokenB(),
            Wei(f"{sell_ftm_buy_fusdt} ether"),
            {"from": gov, "gas_price": "1 gwei", "gas_limit": 2_000_000},
        )
        joint.distributeProfit({"from": gov, "gas_price": "1 gwei"})
        ftm_profit = (joint.balanceOfA() - ftm_capital) / 1e18
        ftm_gp = ftm_profit / (ftm_capital / 1e18)
        fusdt_profit = (joint.balanceOfB() / 1e6) - (fusdt_capital / 1e18)
        fusdt_gp = fusdt_profit / (fusdt_capital / 1e18)
        ftm_profit_usd = ret["fantom"]["usd"] * ftm_profit
        fusdt_profit_usd = ret["tether"]["usd"] * fusdt_profit
        print(f"")
        print(f"With fusdt profit < ftm profit. Sell Capital")
        print(f"jointStaked: {joint.balanceOfStake()}")
        print(f"Pending reward: {joint.pendingReward()/1e18} boo")
        print(f"ftm avail in joint {joint.balanceOfA()/1e18}")
        print(f"fusdt avail in joint {joint.balanceOfB()/1e6}")
        print(f"ftm avail in ProviderA {providerA.balanceOf()/1e18}")

        print(f"fusdt avail in ProviderB {providerB.balanceOf()/1e6}")
        print(
            f"ftm profit {ftm_profit} in providerA with usd value of {ftm_profit_usd}"
        )
        print(
            f"ice profit {fusdt_profit} in providerB with usd value of {fusdt_profit_usd}"
        )
        print(f"ftm GP {ftm_gp}")
        print(f"ice GP {fusdt_gp}")
        print(f"")
