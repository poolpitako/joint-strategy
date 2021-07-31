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

import {
    StrategyParams,
    VaultAPI
} from "@yearnvaults/contracts/BaseStrategy.sol";

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
        address _router
    ) public {
        _initialize(_providerA, _providerB, _router);
    }

    function initialize(
        address _providerA,
        address _providerB,
        address _router
    ) external {
        _initialize(_providerA, _providerB, _router);
    }

    function _initialize(
        address _providerA,
        address _providerB,
        address _router
    ) internal {
        require(address(providerA) == address(0), "Joint already initialized");
        providerA = ProviderStrategy(_providerA);
        providerB = ProviderStrategy(_providerB);

        tokenA = providerA.want();
        tokenB = providerB.want();
        router = _router;
        reinvest = true;

        masterchef = IMasterchef(
            address(0xc2EdaD668740f1aA35E4D8f227fB8E17dcA888Cd)
        );
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
        address _router
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

        Joint(newJoint).initialize(_providerA, _providerB, _router);

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

    function estimatedTotalAssetsInToken(address token)
        external
        view
        returns (uint256)
    {
        require(token == tokenA || token == tokenB);

        uint256 balanceOfToken = token == tokenA ? balanceOfA() : balanceOfB();

        (uint256 reserve0, uint256 reserve1, ) = pair.getReserves();

        return 0; //balanceOfToken.add(reserve);
    }

    function prepareReturn() external onlyProviders {
        // IF tokenA or tokenB are rewards, we would be swapping all of it
        // Let's save the previous balance before claiming
        uint256 previousBalanceOfReward = balanceOfReward();

        // Gets the reward from the masterchef contract
        if (balanceOfStake() != 0) {
            getReward();
        }
        uint256 rewardProfit = balanceOfReward().sub(previousBalanceOfReward);

        address rewardSwappedTo;
        uint256 rewardSwapAmount;
        if (rewardProfit != 0) {
            (rewardSwappedTo, rewardSwapAmount) = swapReward(rewardProfit);
        }

        uint256 _investedA = investedA;
        uint256 _investedB = investedB;
        (uint256 aLiquidated, uint256 bLiquidated) = liquidatePosition();
        investedA = investedB = 0;

        if (!reinvest) {
            (address sellToken, uint256 sellAmount) =
                calculateSellToBalance(
                    aLiquidated.add(
                        rewardSwappedTo == tokenA ? rewardSwapAmount : 0
                    ),
                    bLiquidated.add(
                        rewardSwappedTo == tokenB ? rewardSwapAmount : 0
                    ),
                    investedA,
                    investedB
                );
            if (sellToken != address(0) && sellAmount != 0) {
                sellCapital(
                    sellToken,
                    sellToken == tokenA ? tokenB : tokenA,
                    sellAmount
                );
            }

            distributeProfit();
        }
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

    function calculateSellToBalance(
        uint256 currentA,
        uint256 currentB,
        uint256 startingA,
        uint256 startingB
    ) internal view returns (address _sellToken, uint256 _sellAmount) {
        if (startingA == 0 || startingB == 0) return (address(0), 0);

        uint256 percentReturnA = currentA.mul(1e4).div(startingA);
        uint256 percentReturnB = currentB.mul(1e4).div(startingB);

        if (percentReturnA == percentReturnB) return (address(0), 0);

        (uint256 _AForB, uint256 _BForA) = getSpotExchangeRates();

        uint256 numerator;
        uint256 denominator;
        if (percentReturnA > percentReturnB) {
            _sellToken = tokenA;
            numerator = currentA.sub(startingA.mul(currentB).div(startingB));
            denominator = 1 + startingA.mul(_BForA).div(startingB);
        } else {
            _sellToken = tokenB;
            numerator = currentB.sub(startingB.mul(currentA).div(startingA));
            denominator = 1 + startingB.mul(_AForB).div(startingA);
        }
        _sellAmount = numerator.div(denominator);
    }

    function getSpotExchangeRates()
        internal
        view
        returns (uint256 _AForB, uint256 _BForA)
    {
        (uint256 reserve0, uint256 reserve1, ) = pair.getReserves();
        uint256 _0For1 =
            reserve0.mul(10**IERC20Extended(pair.token1()).decimals()).div(
                reserve1
            );
        uint256 _1For0 =
            reserve1.mul(10**IERC20Extended(pair.token0()).decimals()).div(
                reserve0
            );
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

    function setWETH(address _weth) external onlyGovernance {
        WETH = _weth;
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
        uint256 _amount
    ) internal {
        IUniswapV2Router02(router).swapExactTokensForTokens(
            _amount,
            0,
            getTokenOutPath(_tokenFrom, _tokenTo),
            address(this),
            now
        );
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

    function setProviderA(address _providerA) external onlyGovernance {
        providerA = ProviderStrategy(_providerA);
        require(providerA.want() == tokenA);
    }

    function setProviderB(address _providerB) external onlyGovernance {
        providerB = ProviderStrategy(_providerB);
        require(providerB.want() == tokenB);
    }

    function setReward(address _reward) external onlyGovernance {
        reward = _reward;
    }
}
