from utils import actions, checks, utils
import pytest
from brownie import Contract, chain
import eth_utils
from eth_abi.packed import encode_abi_packed

def test_setup_positions(
    chain,
    tokenA,
    tokenB,
    vaultA,
    vaultB,
    providerA,
    providerB,
    joint,
    user,
    amountA,
    amountB,
    RELATIVE_APPROX,
    gov,
    tokenA_whale,
    tokenB_whale,
    hedge_type
):
    checks.check_run_test("nohedge", hedge_type)
    solid_token = Contract(joint.SOLID_SEX())
    sex_token = Contract(joint.SEX())
    # Deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)

    actions.gov_start_epoch(
        gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB
    )

    total_assets_tokenA = providerA.estimatedTotalAssets()
    total_assets_tokenB = providerB.estimatedTotalAssets()

    assert pytest.approx(total_assets_tokenA, rel=1e-5) == amountA
    assert pytest.approx(total_assets_tokenB, rel=1e-5) == amountB

    # No lp tokens should remain in the joint
    assert joint.balanceOfPair() == 0
    # As they should be staked
    assert joint.balanceOfStake() > 0

    # Get invested balances
    (balA, balB) = joint.balanceOfTokensInLP()
    # Get lp_token
    lp_token = Contract(joint.pair())

    # Check that total tokens still are accounted for:
    # TokenA (other token) are either in lp pool or provider A
    assert pytest.approx(balA + tokenA.balanceOf(providerA), rel=1e-5) == amountA
    # TokenAB(quote token) are either in lp pool or provider B as there is no hedge cost
    assert pytest.approx(balB + tokenB.balanceOf(providerB), rel=1e-5) == amountB

    # Check ratios
    (reserveA, reserveB) = joint.getReserves()
    # Check ratios between position and reserves are constant
    assert pytest.approx(balA / reserveA, rel=1e-5) == balB / reserveB


def test_open_position_price_change_tokenA(
    chain,
    accounts,
    tokenA,
    tokenB,
    vaultA,
    vaultB,
    providerA,
    providerB,
    joint,
    user,
    strategist,
    amountA,
    amountB,
    RELATIVE_APPROX,
    gov,
    tokenA_whale,
    tokenB_whale,
    chainlink_owner,
    deployer,
    tokenA_oracle,
    tokenB_oracle,
    router,
    dai,
    rewards,
    hedge_type,
    stable,
):
    checks.check_run_test("nohedge", hedge_type)
    # Deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    lp_token = Contract(joint.pair())
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle, tokenA_oracle)
    actions.gov_start_epoch(
        gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB
    )
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle, tokenA_oracle)
    (initial_amount_A, initial_amount_B) = joint.balanceOfTokensInLP()

    utils.print_joint_status(joint, tokenA, tokenB, lp_token, rewards)

    # Let's move prices, 2% of tokenA reserves
    tokenA_dump = (
        lp_token.getReserves()[0] / 50
        if lp_token.token0() == tokenA
        else lp_token.getReserves()[1] / 50
    )
    print(
        f"Dumping some {tokenA.symbol()}. Selling {tokenA_dump / (10 ** tokenA.decimals())} {tokenA.symbol()}"
    )
    actions.dump_token_bool_pair(tokenA_whale, tokenA, tokenB, router, tokenA_dump, stable)
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle, tokenA_oracle)

    utils.print_joint_status(joint, tokenA, tokenB, lp_token, rewards)

    (current_amount_A, current_amount_B) = joint.balanceOfTokensInLP()

    # As we have dumped some A tokens, there should be more liquidity and hence our position should have
    # more tokenA than initial and less tokenB than initial
    assert current_amount_A > initial_amount_A
    assert current_amount_B < initial_amount_B

    tokenA_excess = current_amount_A - initial_amount_A
    tokenA_excess_to_tokenB = utils.swap_tokens_value_bool_pair(
        router, tokenA, tokenB, tokenA_excess, stable
    )
    
    # TokenB checksum: initial amount = current amount + tokenA excess in token B
    total_B_value_now = (
        current_amount_B
        + tokenA_excess_to_tokenB
    )
    assert pytest.approx(total_B_value_now, rel=1e-3) == initial_amount_B
    # Ensure that initial amounts are still intact taking all current data into account
    # A tokens are either in the provider strat or excess
    assert (
        pytest.approx(
            tokenA.balanceOf(providerA) + current_amount_A - tokenA_excess, rel=1e-3
        )
        == amountA
    )
    # B tokens are either in provider strat, received from A excess
    assert (
        pytest.approx(
            tokenB.balanceOf(providerB) + total_B_value_now,
            rel=1e-3,
        )
        == amountB
    )

    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle, tokenA_oracle)
    tokenA_loss = vaultA.strategies(providerA)["totalLoss"]
    tokenB_loss = vaultB.strategies(providerB)["totalLoss"]

    assert tokenA_loss > 0
    assert tokenB_loss > 0

    # Loss should be evenly distributed
    assert pytest.approx(tokenA_loss / initial_amount_A, rel=1e-2) == tokenB_loss / initial_amount_B

def test_open_position_price_change_tokenB(
    chain,
    accounts,
    tokenA,
    tokenB,
    vaultA,
    vaultB,
    providerA,
    providerB,
    joint,
    user,
    strategist,
    amountA,
    amountB,
    RELATIVE_APPROX,
    gov,
    tokenA_whale,
    tokenB_whale,
    chainlink_owner,
    deployer,
    tokenA_oracle,
    tokenB_oracle,
    router,
    dai,
    rewards,
    hedge_type,
    stable,
):
    checks.check_run_test("nohedge", hedge_type)
    # Deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    lp_token = Contract(joint.pair())
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle, tokenA_oracle)
    actions.gov_start_epoch(
        gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB
    )
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle, tokenA_oracle)
    (initial_amount_A, initial_amount_B) = joint.balanceOfTokensInLP()

    utils.print_joint_status(joint, tokenA, tokenB, lp_token, rewards)

    # Let's move prices, 2% of tokenA reserves
    tokenB_dump = (
        lp_token.getReserves()[0] / 50
        if lp_token.token0() == tokenB
        else lp_token.getReserves()[1] / 50
    )
    print(
        f"Dumping some {tokenB.symbol()}. Selling {tokenB_dump / (10 ** tokenB.decimals())} {tokenB.symbol()}"
    )
    actions.dump_token_bool_pair(tokenB_whale, tokenB, tokenA, router, tokenB_dump, stable)
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle, tokenA_oracle)

    utils.print_joint_status(joint, tokenA, tokenB, lp_token, rewards)

    (current_amount_A, current_amount_B) = joint.balanceOfTokensInLP()

    # As we have dumped some B tokens, there should be more liquidity and hence our position should have
    # more tokenB than initial and less tokenA than initial
    assert current_amount_A < initial_amount_A
    assert current_amount_B > initial_amount_B

    tokenB_excess = current_amount_B - initial_amount_B
    tokenB_excess_to_tokenA = utils.swap_tokens_value_bool_pair(
        router, tokenB, tokenA, tokenB_excess, stable
    )
    
    # TokenA checksum: initial amount = current amount + tokenB excess in token A
    total_A_value_now = (
        current_amount_A
        + tokenB_excess_to_tokenA
    )
    assert pytest.approx(total_A_value_now, rel=1e-3) == initial_amount_A
    # Ensure that initial amounts are still intact taking all current data into account
    # A tokens are either in the provider strat or excess
    assert (
        pytest.approx(
            tokenA.balanceOf(providerA) + total_A_value_now, rel=1e-3
        )
        == amountA
    )
    # B tokens are either in provider strat, received from A excess
    assert (
        pytest.approx(
            tokenB.balanceOf(providerB) + current_amount_B - tokenB_excess,
            rel=1e-3,
        )
        == amountB
    )

    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle, tokenA_oracle)
    tokenA_loss = vaultA.strategies(providerA)["totalLoss"]
    tokenB_loss = vaultB.strategies(providerB)["totalLoss"]

    assert tokenA_loss > 0
    assert tokenB_loss > 0
    
    # Loss should be evenly distributed
    assert pytest.approx(tokenA_loss / initial_amount_A, rel=1e-2) == tokenB_loss / initial_amount_B
