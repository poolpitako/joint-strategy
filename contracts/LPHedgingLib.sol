pragma solidity 0.6.12;

import {
    SafeERC20,
    SafeMath,
    IERC20,
    Address
} from "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";
import "@openzeppelin/contracts/math/Math.sol";
import "../interfaces/uni/IUniswapV2Pair.sol";

interface IHegicPool {
    /**
     * @param holder The option buyer address
     * @param period The option period
     * @param amount The option size
     * @param strike The option strike
     **/
    function sellOption(
        address holder,
        uint256 period,
        uint256 amount,
        uint256 strike
    ) external returns (uint256 id);

    function profitOf(uint256 id) external view returns (uint256);

    function exercise(uint256 id) external;
}

interface IERC20Extended is IERC20 {
    function decimals() external view returns (uint8);

    function name() external view returns (string memory);

    function symbol() external view returns (string memory);
}

library LPHedgingLib {
    using SafeMath for uint256;
    using SafeERC20 for IERC20; 
    using Address for address;

    IHegicPool public constant hegicCallOptionsPool = IHegicPool(0xb9ed94c6d594b2517c4296e24A8c517FF133fb6d); 
    IHegicPool public constant hegicPutOptionsPool = IHegicPool(0x790e96E7452c3c2200bbCAA58a468256d482DD8b);
    address public constant hegicOptionsManager = 0x1BA4b447d0dF64DA64024e5Ec47dA94458C1e97f; 

    address public constant asset1 = 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2;

    uint256 private constant MAX_BPS = 10_000;

    function hedgeLPToken(address lpToken, uint256 amount, uint256 h, uint256 period) external returns (uint256 callID, uint256 putID) {
        // TODO: check if this require makes sense
        require(IUniswapV2Pair(lpToken).balanceOf(address(this)) == amount);

        address token0 = IUniswapV2Pair(lpToken).token0();
        address token1 = IUniswapV2Pair(lpToken).token1();

        uint256 token0Amount;
        uint256 token1Amount;
        { // to avoid stack too deep
            uint256 balance0 = IERC20(token0).balanceOf(address(this));
            uint256 balance1 = IERC20(token1).balanceOf(address(this));
            uint256 totalSupply = IUniswapV2Pair(lpToken).totalSupply();

            token0Amount = amount.mul(balance0) / totalSupply;
            token1Amount = amount.mul(balance1) / totalSupply;
        }

        uint256 q;
        uint256 decimals; 
        if(asset1 == token0) {
            q = token0Amount;
            decimals = uint256(10)**uint256(IERC20Extended(token0).decimals());
        } else if (asset1 == token1) {
            q = token1Amount;
            decimals = uint256(10)**uint256(IERC20Extended(token1).decimals());
        } else {
            revert("LPtoken not supported");
        }

        (uint256 putAmount, uint256 callAmount) = getOptionsAmount(q, h, decimals);
        callID = buyOptionFrom(hegicCallOptionsPool, callAmount, period);
        putID = buyOptionFrom(hegicPutOptionsPool, putAmount, period);
    }

    function closeHedge(uint256 callID, uint256 putID) external returns (uint256 payoutToken0, uint256 payoutToken1) {
        uint256 callProfit = hegicCallOptionsPool.profitOf(callID);
        uint256 putProfit = hegicPutOptionsPool.profitOf(putID);

        if(callProfit > 0) {
            // call option is ITM
            hegicCallOptionsPool.exercise(callID);
            // TODO: sell in secondary market
        } else {
            // TODO: sell in secondary market
        }

        if(putProfit > 0) {
            // put option is ITM
            hegicPutOptionsPool.exercise(putID);
            // TODO: sell in secondary market
        } else {
            // TODO: sell in secondary market
        }
        // TODO: return payout per token from exercise
    }

    function getOptionsAmount(uint256 q, uint256 h, uint256 decimals) internal returns (uint256 putAmount, uint256 callAmount) {
        uint256 one = MAX_BPS;
        uint256 two = one.mul(uint256(2));
        callAmount = one.add(two.div(h).mul(one.sub(sqrt(one.add(h))))).mul(decimals).div(MAX_BPS); // 1 + 2 / h * (1 - sqrt(1 + h))
        putAmount = one.sub(two.div(h).mul(one.sub(sqrt(one.sub(h))))).mul(decimals).div(MAX_BPS); // 1 - 2 / h * (1 - sqrt(1 - h));
    }

    function buyOptionFrom(IHegicPool pool, uint256 period, uint256 amount) internal returns (uint256) {
        return pool.sellOption(address(this), period, amount, 0);
    }

    function sqrt(uint256 x) internal pure returns (uint256 result) {
        result = x;
        uint256 k = (x >> 1) + 1;
        while (k < result) (result, k) = (k, (x / k + k) >> 1);
    }
}