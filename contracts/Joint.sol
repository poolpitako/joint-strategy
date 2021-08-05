// SPDX-License-Identifier: AGPL-3.0
pragma solidity 0.6.12;
pragma experimental ABIEncoderV2;

import {
    SafeERC20,
    SafeMath,
    IERC20,
    Address
} from "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";
import "@openzeppelin/contracts/math/Math.sol";

import "../interfaces/uni/IUniswapV2Router02.sol";
import "../interfaces/uni/IUniswapV2Factory.sol";
import "../interfaces/uni/IUniswapV2Pair.sol";
import "../interfaces/IMasterChef.sol";

import {VaultAPI} from "@yearnvaults/contracts/BaseStrategy.sol";

interface IERC20Extended {
    function decimals() external view returns (uint8);

    function name() external view returns (string memory);

    function symbol() external view returns (string memory);
}

interface ProviderStrategy {
    function vault() external view returns (VaultAPI);

    function strategist() external view returns (address);

    function keeper() external view returns (address);

    function want() external view returns (address);
}

contract Joint {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    ProviderStrategy public providerA;
    ProviderStrategy public providerB;

    address public tokenA;
    address public tokenB;

    bool public reinvest;

    address public WETH;
    address public reward;
    address public router;

    uint256 public pid;

    IMasterchef public masterchef;

    IUniswapV2Pair public pair;

    uint256 private investedA;
    uint256 private investedB;

    modifier onlyGovernance {
        require(
            msg.sender == providerA.vault().governance() ||
                msg.sender == providerB.vault().governance()
        );
        _;
    }

    modifier onlyAuthorized {
        require(
            msg.sender == providerA.vault().governance() ||
                msg.sender == providerB.vault().governance() ||
                msg.sender == providerA.strategist() ||
                msg.sender == providerB.strategist()
        );
        _;
    }

    modifier onlyKeepers {
        require(
            msg.sender == providerA.vault().governance() ||
                msg.sender == providerB.vault().governance() ||
                msg.sender == providerA.strategist() ||
                msg.sender == providerB.strategist() ||
                msg.sender == providerA.keeper() ||
                msg.sender == providerB.keeper()
        );
        _;
    }

    modifier onlyProviders {
        require(
            msg.sender == address(providerA) || msg.sender == address(providerB)
        );
        _;
    }

    constructor(
        address _providerA,
        address _providerB,
        address _router,
        address _weth,
        address _masterchef,
        address _reward,
        uint256 _pid
    ) public {
        _initialize(
            _providerA,
            _providerB,
            _router,
            _weth,
            _masterchef,
            _reward,
            _pid
        );
    }

    function initialize(
        address _providerA,
        address _providerB,
        address _router,
        address _weth,
        address _masterchef,
        address _reward,
        uint256 _pid
    ) external {
        _initialize(
            _providerA,
            _providerB,
            _router,
            _weth,
            _masterchef,
            _reward,
            _pid
        );
    }

    function _initialize(
        address _providerA,
        address _providerB,
        address _router,
        address _weth,
        address _masterchef,
        address _reward,
        uint256 _pid
    ) internal {
        require(address(providerA) == address(0), "Joint already initialized");
        providerA = ProviderStrategy(_providerA);
        providerB = ProviderStrategy(_providerB);
        router = _router;
        WETH = _weth;
        masterchef = IMasterchef(_masterchef);
        reward = _reward;
        pid = _pid;

        tokenA = providerA.want();
        tokenB = providerB.want();
        reinvest = true;

        reward = address(0x6B3595068778DD592e39A122f4f5a5cF09C90fE2);
        WETH = address(0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2);

        pair = IUniswapV2Pair(getPair());

        IERC20(address(pair)).approve(address(masterchef), type(uint256).max);
        IERC20(tokenA).approve(address(router), type(uint256).max);
        IERC20(tokenB).approve(address(router), type(uint256).max);
        IERC20(reward).approve(address(router), type(uint256).max);
        IERC20(address(pair)).approve(address(router), type(uint256).max);
    }

    event Cloned(address indexed clone);

    function cloneJoint(
        address _providerA,
        address _providerB,
        address _router,
        address _weth,
        address _masterchef,
        address _reward,
        uint256 _pid
    ) external returns (address newJoint) {
        bytes20 addressBytes = bytes20(address(this));

        assembly {
            // EIP-1167 bytecode
            let clone_code := mload(0x40)
            mstore(
                clone_code,
                0x3d602d80600a3d3981f3363d3d373d3d3d363d73000000000000000000000000
            )
            mstore(add(clone_code, 0x14), addressBytes)
            mstore(
                add(clone_code, 0x28),
                0x5af43d82803e903d91602b57fd5bf30000000000000000000000000000000000
            )
            newJoint := create(0, clone_code, 0x37)
        }

        Joint(newJoint).initialize(
            _providerA,
            _providerB,
            _router,
            _masterchef,
            _weth,
            _reward,
            _pid
        );

        emit Cloned(newJoint);
    }

    function name() external view returns (string memory) {
        string memory ab =
            string(
                abi.encodePacked(
                    IERC20Extended(address(tokenA)).symbol(),
                    IERC20Extended(address(tokenB)).symbol()
                )
            );

        return string(abi.encodePacked("JointOf", ab));
    }

        function prepareReturn() external onlyProviders {
        // Gets the reward from the masterchef contract
        if (balanceOfStake() != 0) {
            getReward();
        }

        (address rewardSwappedTo, uint256 rewardSwapAmount) =
            swapReward(balanceOfReward());

        uint256 _investedA = investedA;
        uint256 _investedB = investedB;
        (uint256 aLiquidated, uint256 bLiquidated) = liquidatePosition();
        investedA = investedB = 0;

        if (reinvest) return; // Don't distributeProfit
        
        if (_investedA != 0 && _investedB != 0) {
            uint256 currentA =
                aLiquidated.add(
                    rewardSwappedTo == tokenA ? rewardSwapAmount : 0
                );
            uint256 currentB =
                bLiquidated.add(
                    rewardSwappedTo == tokenB ? rewardSwapAmount : 0
                );

            (uint256 ratioA, uint256 ratioB) =
                getRatios(currentA, currentB, _investedA, _investedB);

            emit Ratios(ratioA, ratioB, "before balance");

            (address sellToken, uint256 sellAmount) =
                calculateSellToBalance(
                    currentA,
                    currentB,
                    _investedA,
                    _investedB
                );
            if (sellToken != address(0) && sellAmount != 0) {
                uint256 buyAmount =
                    sellCapital(
                        sellToken,
                        sellToken == tokenA ? tokenB : tokenA,
                        sellAmount
                    );
                emit SellToBalance(sellToken, sellAmount, buyAmount);

                if (sellToken == tokenA) {
                    currentA = currentA.sub(sellAmount);
                    currentB = currentB.add(buyAmount);
                } else {
                    currentB = currentB.sub(sellAmount);
                    currentA = currentA.add(buyAmount);
                }

                (ratioA, ratioB) = getRatios(
                    currentA,
                    currentB,
                    _investedA,
                    _investedB
                );
                emit Ratios(ratioA, ratioB, "after balance");
            }
        }

        distributeProfit();
    }

    function adjustPosition() external onlyProviders {
        // No capital, nothing to do
        if (balanceOfA() == 0 || balanceOfB() == 0) {
            return;
        }

        if (reinvest) {
            (investedA, investedB, ) = createLP();
            depositLP();
        }
    }

    function estimatedTotalAssetsInToken(address token)
        external
        view
        returns (uint256)
    {
        require(token == tokenA || token == tokenB);

        uint256 rewardsPending = pendingReward();

        uint256 aBalance;
        uint256 bBalance;

        if (reward == tokenA) {
            aBalance = aBalance.add(rewardsPending);
        } else if (reward == tokenB) {
            bBalance = bBalance.add(rewardsPending);
        } else if (rewardsPending != 0) {
            address swapTo = findSwapTo(reward);
            uint256[] memory outAmounts =
                IUniswapV2Router02(router).getAmountsOut(
                    rewardsPending,
                    getTokenOutPath(reward, swapTo)
                );
            if (swapTo == tokenA) {
                aBalance = aBalance.add(outAmounts[outAmounts.length - 1]);
            } else if (swapTo == tokenB) {
                bBalance = bBalance.add(outAmounts[outAmounts.length - 1]);
            }
        }

        uint256 reserveA;
        uint256 reserveB;
        if (tokenA == pair.token0()) {
            (reserveA, reserveB, ) = pair.getReserves();
        } else {
            (reserveB, reserveA, ) = pair.getReserves();
        }
        uint256 lpBal = balanceOfStake().add(balanceOfPair());
        uint256 percentTotal =
            lpBal.mul(pair.decimals()).div(pair.totalSupply());
        aBalance = aBalance.add(
            reserveA.mul(percentTotal).div(pair.decimals())
        );
        bBalance = bBalance.add(
            reserveB.mul(percentTotal).div(pair.decimals())
        );

        (address sellToken, uint256 sellAmount) =
            calculateSellToBalance(aBalance, bBalance, investedA, investedB);

        if (sellToken == tokenA) {
            uint256 buyAmount =
                IUniswapV2Router02(router).getAmountOut(
                    sellAmount,
                    reserveA,
                    reserveB
                );
            aBalance = aBalance.sub(sellAmount);
            bBalance = bBalance.add(buyAmount);
        } else if (sellToken == tokenB) {
            uint256 buyAmount =
                IUniswapV2Router02(router).getAmountOut(
                    sellAmount,
                    reserveB,
                    reserveA
                );
            bBalance = bBalance.sub(sellAmount);
            aBalance = aBalance.add(buyAmount);
        }

        if (token == tokenA) {
            return aBalance.add(balanceOfA());
        } else if (token == tokenB) {
            return bBalance.add(balanceOfB());
        }
    }

    event Ratios(uint256 tokenA, uint256 tokenB, string description);
    event SellToBalance(
        address sellToken,
        uint256 sellAmount,
        uint256 buyAmount
    );

    function calculateSellToBalance(
        uint256 currentA,
        uint256 currentB,
        uint256 startingA,
        uint256 startingB
    ) internal view returns (address _sellToken, uint256 _sellAmount) {
        if (startingA == 0 || startingB == 0) return (address(0), 0);

        (uint256 ratioA, uint256 ratioB) =
            getRatios(currentA, currentB, startingA, startingB);

        if (ratioA == ratioB) return (address(0), 0);

        (uint256 _AForB, uint256 _BForA) = getSpotExchangeRates();

        uint256 numerator;
        uint256 denominator;
        if (ratioA > ratioB) {
            _sellToken = tokenA;
            numerator = currentA.sub(startingA.mul(currentB).div(startingB));
            denominator = 1e18 + startingA.mul(_BForA).div(startingB);
        } else {
            _sellToken = tokenB;
            numerator = currentB.sub(startingB.mul(currentA).div(startingA));
            denominator = 1e18 + startingB.mul(_AForB).div(startingA);
        }
        _sellAmount = numerator.mul(1e18).div(denominator);
    }

    function getRatios(
        uint256 currentA,
        uint256 currentB,
        uint256 startingA,
        uint256 startingB
    ) internal pure returns (uint256 _a, uint256 _b) {
        _a = currentA.mul(1e4).div(startingA);
        _b = currentB.mul(1e4).div(startingB);
    }

    function getSpotExchangeRates()
        public
        view
        returns (uint256 _AForB, uint256 _BForA)
    {
        (uint256 reserve0, uint256 reserve1, ) = pair.getReserves();
        uint256 _0For1 = (reserve0.mul(1e18).div(reserve1)).mul(997).div(1000);
        uint256 _1For0 = (reserve1.mul(1e18).div(reserve0)).mul(997).div(1000);
        if (pair.token0() == tokenA) {
            _AForB = _0For1;
            _BForA = _1For0;
        } else {
            _BForA = _0For1;
            _AForB = _1For0;
        }
    }

    function createLP()
        internal
        returns (
            uint256,
            uint256,
            uint256
        )
    {
        return
            IUniswapV2Router02(router).addLiquidity(
                tokenA,
                tokenB,
                balanceOfA(),
                balanceOfB(),
                0,
                0,
                address(this),
                now
            );
    }

    function setMasterChef(address _masterchef) external onlyGovernance {
        masterchef = IMasterchef(_masterchef);
        IERC20(getPair()).approve(_masterchef, type(uint256).max);
    }

    function setPid(uint256 _newPid) external onlyGovernance {
        pid = _newPid;
    }

    function findSwapTo(address token) internal view returns (address) {
        if (tokenA == token) {
            return tokenB;
        } else if (tokenB == token) {
            return tokenA;
        } else if (reward == token) {
            if (tokenA == WETH || tokenB == WETH) {
                return WETH;
            }
            return tokenA;
        } else {
            revert("!swapTo");
        }
    }

    function getTokenOutPath(address _token_in, address _token_out)
        internal
        view
        returns (address[] memory _path)
    {
        bool is_weth =
            _token_in == address(WETH) || _token_out == address(WETH);
        _path = new address[](is_weth ? 2 : 3);
        _path[0] = _token_in;
        if (is_weth) {
            _path[1] = _token_out;
        } else {
            _path[1] = address(WETH);
            _path[2] = _token_out;
        }
    }

    function getReward() internal {
        masterchef.deposit(pid, 0);
    }

    function depositLP() internal {
        if (balanceOfPair() > 0) masterchef.deposit(pid, balanceOfPair());
    }

    function swapReward(uint256 _rewardBal)
        internal
        returns (address _swapTo, uint256 _receivedAmount)
    {
        if (reward == tokenA || reward == tokenB || _rewardBal == 0) {
            return (address(0), 0);
        }

        _swapTo = findSwapTo(reward);
        //Call swap to get more of the of the swapTo token
        uint256[] memory amounts =
            IUniswapV2Router02(router).swapExactTokensForTokens(
                _rewardBal,
                0,
                getTokenOutPath(reward, _swapTo),
                address(this),
                now
            );
        _receivedAmount = amounts[amounts.length - 1];
    }

    // If there is a lot of impermanent loss, some capital will need to be sold
    // To make both sides even
    function sellCapital(
        address _tokenFrom,
        address _tokenTo,
        uint256 _amountIn
    ) internal returns (uint256 _amountOut) {
        uint256[] memory amounts =
            IUniswapV2Router02(router).swapExactTokensForTokens(
                _amountIn,
                0,
                getTokenOutPath(_tokenFrom, _tokenTo),
                address(this),
                now
            );
        _amountOut = amounts[amounts.length - 1];
    }

    function liquidatePosition() internal returns (uint256, uint256) {
        if (balanceOfStake() != 0) {
            masterchef.withdraw(pid, balanceOfStake());
        }
        if (balanceOfPair() == 0) {
            return (0, 0);
        }
        return
            IUniswapV2Router02(router).removeLiquidity(
                tokenA,
                tokenB,
                balanceOfPair(),
                0,
                0,
                address(this),
                now
            );
    }

    function distributeProfit() internal {
        uint256 balanceA = balanceOfA();
        if (balanceA > 0) {
            IERC20(tokenA).transfer(address(providerA), balanceA);
        }

        uint256 balanceB = balanceOfB();
        if (balanceB > 0) {
            IERC20(tokenB).transfer(address(providerB), balanceB);
        }
    }

    function getPair() internal view returns (address) {
        address factory = IUniswapV2Router02(router).factory();
        return IUniswapV2Factory(factory).getPair(tokenA, tokenB);
    }

    function balanceOfPair() public view returns (uint256) {
        return IERC20(getPair()).balanceOf(address(this));
    }

    function balanceOfA() public view returns (uint256) {
        return IERC20(tokenA).balanceOf(address(this));
    }

    function balanceOfB() public view returns (uint256) {
        return IERC20(tokenB).balanceOf(address(this));
    }

    function balanceOfReward() public view returns (uint256) {
        return IERC20(reward).balanceOf(address(this));
    }

    function balanceOfStake() public view returns (uint256) {
        return masterchef.userInfo(pid, address(this)).amount;
    }

    function pendingReward() public view returns (uint256) {
        return masterchef.pendingSushi(pid, address(this));
    }

    function setReinvest(bool _reinvest) external onlyAuthorized {
        reinvest = _reinvest;
    }
}
