from functools import _lru_cache_wrapper
from utils import actions, checks, utils
import pytest
from brownie import Contract, chain, SpookyJoint, reverts, ProviderStrategy

def test_clone_joint(
    joint_to_use,
    hedge_type,
    providerA,
    providerB,
    router,
    gov,
    wftm,
    rewards,
    hedgilV2,
    masterchef,
    mc_pid,
    joint,
):
    checks.check_run_test("hedgilV2", hedge_type)
    # Clone the deployed joint
    if joint_to_use == SpookyJoint:
        cloned_joint = joint.cloneSpookyJoint(
            providerA,
            providerB,
            router,
            wftm,
            rewards,
            hedgilV2,
            masterchef,
            mc_pid,
            {"from": gov}
        ).return_value
        cloned_joint = SpookyJoint.at(cloned_joint)
    else:
        print("Joint type not included in test!")

    # Try to clone it again
    if joint_to_use == SpookyJoint:
        with reverts():
            cloned_joint.cloneSpookyJoint(
                providerA,
                providerB,
                router,
                wftm,
                rewards,
                hedgilV2,
                masterchef,
                mc_pid,
                {"from":cloned_joint, "gas_price":0}
            )
    else:
        print("Joint type not included in test!")
    
    # Try to initialize again
    if joint_to_use == SpookyJoint:
        with reverts():
            cloned_joint.initialize(
                providerA,
                providerB,
                router,
                wftm,
                rewards,
                hedgilV2,
                masterchef,
                mc_pid,
                {"from":providerA, "gas_price":0}
            )
    else:
        print("Joint type not included in test!")

def test_clone_provider_migrate(
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
    hedgilV2,
    tokenA_whale,
    tokenB_whale,
    chainlink_owner,
    deployer,
    tokenA_oracle,
    tokenB_oracle,
    router,
    dai,
    rewards,
    hedge_type
):
    checks.check_run_test("hedgilV2", hedge_type)
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

    balanceA_pre = tokenA.balanceOf(providerA)
    balanceB_pre = tokenB.balanceOf(providerB)

    new_providerA = providerA.clone(vaultA).return_value
    new_providerA = ProviderStrategy.at(new_providerA)
    vaultA.migrateStrategy(providerA, new_providerA, {"from":vaultA.governance()})
    new_providerA.setHealthCheck("0xf13Cd6887C62B5beC145e30c38c4938c5E627fe0", {"from": gov, "gas_price":0})
    new_providerA.setDoHealthCheck(False, {"from": gov, "gas_price":0})

    new_providerB = providerA.clone(vaultB).return_value
    new_providerB = ProviderStrategy.at(new_providerB)
    vaultB.migrateStrategy(providerB, new_providerB, {"from":vaultB.governance()})
    new_providerB.setHealthCheck("0xf13Cd6887C62B5beC145e30c38c4938c5E627fe0", {"from": gov, "gas_price":0})
    new_providerB.setDoHealthCheck(False, {"from": gov, "gas_price":0})

    # setup joint
    new_providerA.setJoint(joint, {"from": gov})
    new_providerB.setJoint(joint, {"from": gov})

    # Previous providers are empty
    assert tokenA.balanceOf(providerA) == 0
    assert tokenB.balanceOf(providerB) == 0

    # All balance should be in new providers
    assert tokenA.balanceOf(new_providerA) == balanceA_pre
    assert tokenB.balanceOf(new_providerB) == balanceB_pre

    # Joint is interacting with new providers
    assert joint.providerA() == new_providerA
    assert joint.providerB() == new_providerB

    with reverts():
        actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)
    
    actions.gov_end_epoch(gov, new_providerA, new_providerB, joint, vaultA, vaultB)

    assert providerA.estimatedTotalAssets() == 0
    assert new_providerA.estimatedTotalAssets() == 0
    assert providerB.estimatedTotalAssets() == 0
    assert new_providerB.estimatedTotalAssets() == 0

    assert vaultA.strategies(providerA).dict()["totalLoss"] == 0
    assert vaultB.strategies(providerB).dict()["totalLoss"] == 0
    assert vaultA.strategies(new_providerA).dict()["totalLoss"] > 0
    assert vaultB.strategies(new_providerB).dict()["totalLoss"] > 0

def test_migrate_joint_and_unwind(
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
    hedgilV2,
    tokenA_whale,
    tokenB_whale,
    chainlink_owner,
    deployer,
    tokenA_oracle,
    tokenB_oracle,
    router,
    joint_to_use,
    dai,
    wftm,
    masterchef,
    mc_pid,
    rewards,
    hedge_type
):
    checks.check_run_test("hedgilV2", hedge_type)
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

    # Get the hedgil open position
    hedgil_id = joint.activeHedgeID()
    # Get position details
    hedgil_position = hedgilV2.getHedgilByID(hedgil_id)

    # Joint has assets
    assert joint.estimatedTotalAssetsAfterBalance()[0] > 0
    assert joint.estimatedTotalAssetsAfterBalance()[1] > 0

    # Deploy new joint
    if joint_to_use == SpookyJoint:
        cloned_joint = joint.cloneSpookyJoint(
            providerA,
            providerB,
            router,
            wftm,
            rewards,
            hedgilV2,
            masterchef,
            mc_pid,
        ).return_value
        cloned_joint = SpookyJoint.at(cloned_joint)
    else:
        print("Joint type not included in test!")
    
    # New joint does not have assets
    assert cloned_joint.estimatedTotalAssetsAfterBalance()[0] == 0
    assert cloned_joint.estimatedTotalAssetsAfterBalance()[1] == 0

    # Set providers to new joint
    providerA.setJoint(cloned_joint, {"from": gov})
    providerB.setJoint(cloned_joint, {"from": gov})

    # Unwind old joint position
    joint.claimRewardManually()
    joint.withdrawLPManually(joint.balanceOfStake())
    joint.removeLiquidityManually(lp_token.balanceOf(joint), 0, 0)
    joint.returnLooseToProvidersManually()
    joint.closeHedgeManually()
    joint.sweep(rewards, {"from": gov})

    # Old joint should be empty
    assert joint.estimatedTotalAssetsAfterBalance()[0] == 0
    assert joint.estimatedTotalAssetsAfterBalance()[1] == 0
    assert joint.activeHedgeID() == 0

    # All balance should be now in providers
    assert pytest.approx(providerA.estimatedTotalAssets(), rel = 1e-3) == amountA
    assert pytest.approx(providerB.estimatedTotalAssets() + hedgil_position["cost"], rel = 1e-3) == amountB

    