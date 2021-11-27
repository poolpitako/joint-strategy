import time
from brownie import Contract, accounts, Wei, interface, chain
from datetime import datetime
from brownie import ZERO_ADDRESS

def main():
	
	list_of_joints = [
		Contract("0x997F3E5cae4455cFD225B5E43d2382C7f6B7c6E4"), #HegicSushiJoint(WETH-USDC)
		
	]
	#oracles:
	oracle = Contract("0x83d95e0D5f402511dB06817Aff3f9eA88224B030")
	
	#fixed epoch for non hedgil joints:
	fixed_epoch_days = 7

	while True:
		now = datetime.now()
		now_UNIX = int(now.strftime("%s"))

		print(f"\n{now.ctime()} - ETH Joints Status:")

		for i in list_of_joints:
			joint = i
			name = joint.name()
			providerA = Contract(joint.providerA())
			providerB = Contract(joint.providerB())
			vaultA = Contract(providerA.vault())
			vaultB = Contract(providerB.vault())
			tokenA = Contract(vaultA.token())
			tokenB = Contract(vaultB.token())
			tokenA_decimals = Contract(vaultA.token()).decimals()
			tokenB_decimals = Contract(vaultB.token()).decimals()
			tokenA_price = oracle.getNormalizedValueUsdc(tokenA, (10 ** tokenA_decimals))/(10 ** 6)
			tokenB_price = oracle.getNormalizedValueUsdc(tokenB, (10 ** tokenB_decimals))/(10 ** 6)
			reward = Contract(joint.reward())
			reward_decimals = reward.decimals()
			reward_price = oracle.getNormalizedValueUsdc(reward, (10 ** reward_decimals))/(10 ** 6)
			providerA_initial_capital = vaultA.strategies(providerA).dict()['totalDebt']
			providerB_initial_capital = vaultB.strategies(providerB).dict()['totalDebt']
			if providerA_initial_capital == 0 or providerB_initial_capital == 0:
				print(f"\n{name}: Inactive Joint")
			else:
				providerA_profit = joint.estimatedTotalAssetsAfterBalance()[0] + providerA.balanceOfWant() - providerA_initial_capital
				providerA_profit_usd = (providerA_profit/(10 ** tokenA.decimals())) * tokenA_price
				providerA_margin = providerA_profit / providerA_initial_capital
				providerB_profit = joint.estimatedTotalAssetsAfterBalance()[1] + providerB.balanceOfWant() - providerB_initial_capital
				providerB_profit_usd = (providerB_profit/(10 ** tokenB.decimals())) * tokenB_price
				providerB_margin = providerB_profit / providerB_initial_capital
				pending_reward = joint.pendingReward()
				pending_reward_usd = (pending_reward/(10 ** Contract(joint.reward()).decimals())) * reward_price
				last_harvest_UNIX = vaultA.strategies(providerA).dict()['lastReport']
				days_from_harvest = int((now_UNIX - last_harvest_UNIX)/86400)
				hours_from_harvest = int((now_UNIX - last_harvest_UNIX - (days_from_harvest*86400))/3600)
				providerA_APR = providerA_profit*(365/((now_UNIX - last_harvest_UNIX)/86400))*100/providerA_initial_capital
				providerB_APR = providerB_profit*(365/((now_UNIX - last_harvest_UNIX)/86400))*100/providerB_initial_capital 
				exchange_rate_init = (vaultB.strategies(providerB).dict()['maxDebtPerHarvest']/(10 ** tokenB.decimals())) / (vaultA.strategies(providerA).dict()['maxDebtPerHarvest'] /(10 ** tokenA.decimals()))
				exchange_rate_actual = tokenA_price / tokenB_price
				if exchange_rate_init > exchange_rate_actual:
					price_movement = ((exchange_rate_init - exchange_rate_actual) / exchange_rate_init)*100
				elif exchange_rate_actual > exchange_rate_init:
					price_movement = ((exchange_rate_actual - exchange_rate_init) / exchange_rate_init)*100

				print(f"\n{name}:")
				print(f"Last Harvest: {days_from_harvest}d, {hours_from_harvest}h ago")
				print(f"\n=== Debt ===")
				print(f"{tokenA.symbol()}: {providerA_initial_capital/(10 ** tokenA.decimals()):,.2f}")
				print(f"{tokenB.symbol()}: {providerB_initial_capital/(10 ** tokenB.decimals()):,.2f}")
				print(f"\n=== Invested ===")
				print(f"{tokenA.symbol()}: {joint.investedA()/(10 ** tokenA.decimals()):,.2f} ({joint.investedA()/providerA_initial_capital*100:,.2f}%)")
				print(f"{tokenB.symbol()}: {joint.investedB()/(10 ** tokenB.decimals()):,.2f} ({joint.investedB()/providerB_initial_capital*100:,.2f}%)")
				print(f"\n=== Reward ===")
				print(f"{reward.symbol()} ({reward_price:,.2f}): {pending_reward/(10 ** reward.decimals()):,.2f}")
				print(f"{tokenB.symbol()}/{reward.symbol()}: {pending_reward_usd:,.2f}")
				print(f"\n=== Yield ===")
				print(f"{tokenA.symbol()}: {providerA_profit/(10 ** tokenA.decimals()):,.4f} ({providerA_margin*100:.4f}%)")
				print(f"{tokenB.symbol()}: {providerB_profit/(10 ** tokenB.decimals()):,.4f} ({providerB_margin*100:.4f}%)")
				print(f"\n=== APR ===")
				print(f"{tokenA.symbol()}: {providerA_APR:,.2f}%")
				print(f"{tokenB.symbol()}: {providerB_APR:,.2f}%")
				
				if not hasattr(joint, "isHedgingEnabled"):
					if providerA_margin < 0 or providerB_margin < 0:
						print(f"Exchange rate {tokenA.symbol()}:{tokenB.symbol()} init ({exchange_rate_init:,.2f}:1) | actual ({exchange_rate_actual:,.2f}:1) | price movement: {price_movement:,.2f}%")
						print(f"Is everything ok? No, IL is bigger than rewards")
					elif providerA_margin >= 0 or providerB_margin >= 0:
						if days_from_harvest > fixed_epoch_days:
							print(f"Is everything ok? Yes, it's time to HARVEST")
						else: print(f"Is everything ok? Yes")
				else:
					print(f"\n=== Hedge Status ===")
					callID = joint.activeCallID()
					putID = joint.activePutID()
					if callID == 0 or putID == 0:						
						print(f"Hedged Position is off or has expired")
						if providerA_margin < 0 or providerB_margin < 0:
							print(f"Exchange rate {tokenA.symbol()}:{tokenB.symbol()} init ({exchange_rate_init:,.2f}:1) | actual ({exchange_rate_actual:,.2f}:1) | price movement: {price_movement:,.2f}%")
							print(f"Is everything ok? No, IL is bigger than rewards")
						elif providerA_margin >= 0 or providerB_margin >= 0:
							if days_from_harvest > fixed_epoch_days:
								print(f"Is everything ok? Yes, it's time to HARVEST")
						else: print(f"\nIs everything ok? Yes")
					else:
						callProvider = Contract(joint.hegicCallOptionsPool())
						putProvider = Contract(joint.hegicPutOptionsPool())
						callInfo = callProvider.options(callID)
						putInfo = putProvider.options(putID)
						expiration_days = int(joint.getTimeToMaturity()/86400)
						expiration_hours = joint.getTimeToMaturity()/3600
						minimum_price = (callInfo[1] / 10 ** 8) - ((callInfo[1] / 10 ** 8)*(joint.protectionRange()/10000))
						maximum_price = (callInfo[1] / 10 ** 8) + ((callInfo[1] / 10 ** 8)*(joint.protectionRange()/10000))
						if callInfo[1] / 10 ** 8 > exchange_rate_actual:
							price_change = (((callInfo[1] / 10 ** 8) - exchange_rate_actual) / (callInfo[1] / 10 ** 8))*100
						elif exchange_rate_actual > callInfo[1] / 10 ** 8:
							price_change = ((exchange_rate_actual - (callInfo[1] / 10 ** 8)) / (callInfo[1] / 10 ** 8))*100
						hedgil_payout = joint.getHedgeProfit()
						costCall = (callInfo[5]+callInfo[6])/0.8
						costPut = (putInfo[5]+putInfo[6])/0.8
						print(f"Protection Range: {joint.protectionRange()/100}%")
						print(f"Strike: {(callInfo[1] / 10 ** 8):,.2f} {tokenB.symbol()}/{tokenA.symbol()}")
						print(f"Min: {minimum_price:,.2f} | Max: {maximum_price:,.2f}")
						print(f"Current: {exchange_rate_actual:,.2f} ({price_change:,.2f}%)")
						print(f"Expires in {expiration_days}d, {(expiration_days*-24) + expiration_hours:.0f}h")

						print(f"\nCALL #{callID}")
						print(f"Cost: {costCall/(10 ** tokenA.decimals()):,.4f} {tokenA.symbol()}")
						print(f"Payoff: {hedgil_payout[0]/(10 ** tokenA.decimals()):,.4f} {tokenA.symbol()}")
						print(f"PUT #{putID}")
						print(f"Cost: {costPut/(10 ** tokenB.decimals()):,.4f} {tokenB.symbol()}")
						print(f"Payoff: {hedgil_payout[1]/(10 ** tokenB.decimals()):,.4f} {tokenB.symbol()}")
						
						print(f"\nHarvestTriggerA: {providerA.harvestTrigger(100)}")
						print(f"HarvestTriggerB: {providerB.harvestTrigger(100)}")
						if price_change*100 < joint.protectionRange() and expiration_hours > 2:
							print(f"\nIs everything ok? Yes")
						elif price_change*100 > joint.protectionRange():
							print(f"\nIs everything ok? No, the price change is greater than our option")
						elif expiration_hours > 0 and expiration_hours < 2:
							print(f"\nIs everything ok? Yes, in less than 2 hours hedgil will be expired")
		
		time.sleep(1200)
