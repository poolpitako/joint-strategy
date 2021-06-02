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
import "../interfaces/IMiniChefV2.sol";

interface IERC20Extended {
    function decimals() external view returns (uint8);

    function name() external view returns (string memory);

    function symbol() external view returns (string memory);
}

contract MiniChefJoint {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    address public tokenA;
    address public providerA;
    address public tokenB;
    address public providerB;

    address public governance;
    address public pendingGovernance;
    address public strategist;
    address public WETH;
    address public reward;
    address public router;
    uint256 public pid;
    IMiniChefV2 public minichef;

    modifier onlyGov {
        require(msg.sender == governance);
        _;
    }

    modifier onlyGovOrStrategist {
        require(msg.sender == governance || msg.sender == strategist);
        _;
    }

    constructor(
        address _governance,
        address _strategist,
        address _tokenA,
        address _tokenB,
        address _router,
        uint256 _pid
    ) public {
        _initialize(_governance, _strategist, _tokenA, _tokenB, _router, _pid);
    }

    function _initialize(
        address _governance,
        address _strategist,
        address _tokenA,
        address _tokenB,
        address _router,
        uint256 _pid
    ) internal {
        require(address(tokenA) == address(0), "Joint already initialized");

        governance = _governance;
        strategist = _strategist;
        tokenA = _tokenA;
        tokenB = _tokenB;
        router = _router;
        pid = _pid;

        minichef = IMiniChefV2(
            address(0x0769fd68dFb93167989C6f7254cd0D766Fb2841F)
        );

        reward = address(0x0b3F868E0BE5597D5DB7fEB59E1CADBb0fdDa50a);
        WETH = address(0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270);

        IERC20(getPair()).approve(address(minichef), type(uint256).max);
        IERC20(tokenA).approve(address(router), type(uint256).max);
        IERC20(tokenB).approve(address(router), type(uint256).max);
        IERC20(reward).approve(address(router), type(uint256).max);
        IERC20(getPair()).approve(address(router), type(uint256).max);
    }

    function name() external view returns (string memory) {
        string memory ab =
            string(
                abi.encodePacked(
                    IERC20Extended(address(tokenA)).symbol(),
                    "/",
                    IERC20Extended(address(tokenB)).symbol(),
                    "=>",
                    IERC20Extended(address(reward)).symbol()
                )
            );

        return string(abi.encodePacked("SushiMiniChefJointOf", ab));
    }

    function createLP() internal {
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

    function depositLP() internal {
        if (balanceOfPair() > 0)
            minichef.deposit(pid, balanceOfPair(), address(this));
    }

    function getReward() external onlyGovOrStrategist {
        minichef.harvest(pid, address(this));
    }

    function invest() external onlyGovOrStrategist {
        createLP();
        depositLP();
    }

    // If there is a lot of impermanent loss, some capital will need to be sold
    // To make both sides even
    function sellCapital(
        address _tokenFrom,
        address _tokenTo,
        uint256 _amount
    ) external onlyGovOrStrategist {
        IUniswapV2Router02(router)
            .swapExactTokensForTokensSupportingFeeOnTransferTokens(
            _amount,
            0,
            getTokenOutPath(_tokenFrom, _tokenTo),
            address(this),
            now
        );
    }

    function liquidatePosition() external onlyGovOrStrategist {
        minichef.withdrawAndHarvest(pid, balanceOfStake(), address(this));
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

    function distributeProfit() external onlyGovOrStrategist {
        uint256 balanceA = balanceOfA();
        if (balanceA > 0) {
            IERC20(tokenA).transfer(providerA, balanceA);
        }

        uint256 balanceB = balanceOfB();
        if (balanceB > 0) {
            IERC20(tokenB).transfer(providerB, balanceB);
        }
    }

    function setMiniChef(address _minichef) external onlyGov {
        minichef = IMiniChefV2(_minichef);
        IERC20(getPair()).approve(_minichef, type(uint256).max);
    }

    function setPid(uint256 _newPid) external onlyGov {
        pid = _newPid;
    }

    function setWETH(address _weth) external onlyGov {
        WETH = _weth;
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

    function getPair() public view returns (address) {
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
        return minichef.userInfo(pid, address(this)).amount;
    }

    function pendingReward()
        public
        view
        returns (
            uint256 _reward,
            IERC20[] memory _extraRewardTokens,
            uint256[] memory _extraRewardAmounts
        )
    {
        _reward = minichef.pendingSushi(pid, address(this));
        (_extraRewardTokens, _extraRewardAmounts) = minichef
            .rewarder(pid)
            .pendingTokens(pid, address(this), _reward);
    }

    function setProviderA(address _providerA) external onlyGov {
        providerA = _providerA;
    }

    function setProviderB(address _providerB) external onlyGov {
        providerB = _providerB;
    }

    function setReward(address _reward) external onlyGov {
        reward = _reward;
    }

    function setStrategist(address _strategist) external onlyGov {
        strategist = _strategist;
    }

    function setPendingGovernance(address _pendingGovernance) external onlyGov {
        pendingGovernance = _pendingGovernance;
    }

    function acceptGovernor() external {
        require(msg.sender == pendingGovernance);
        governance = pendingGovernance;
        pendingGovernance = address(0);
    }
}
