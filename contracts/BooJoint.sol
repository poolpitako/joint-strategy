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
import "../interfaces/IMasterChef.sol";

interface IERC20Extended {
    function decimals() external view returns (uint8);

    function name() external view returns (string memory);

    function symbol() external view returns (string memory);
}

contract BooJoint {
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
    IMasterchef public masterchef;

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
        address _router
    ) public {
        _initialize(_governance, _strategist, _tokenA, _tokenB, _router);
    }

    function _initialize(
        address _governance,
        address _strategist,
        address _tokenA,
        address _tokenB,
        address _router
    ) internal {
        require(address(tokenA) == address(0), "Joint already initialized");

        governance = _governance;
        strategist = _strategist;
        tokenA = _tokenA;
        tokenB = _tokenB;
        router = _router;
        pid = 1;

        masterchef = IMasterchef(
            address(0x2b2929E785374c651a81A63878Ab22742656DcDd)
        );
        reward = address(0x841FAD6EAe12c286d1Fd18d1d525DFfA75C7EFFE);
        WETH = address(0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83);

        IERC20(getPair()).approve(address(masterchef), type(uint256).max);
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
                    IERC20Extended(address(tokenB)).symbol()
                )
            );

        return string(abi.encodePacked("BooJointOf", ab));
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
        if (balanceOfPair() > 0) masterchef.deposit(pid, balanceOfPair());
    }

    function getReward() external onlyGovOrStrategist {
        masterchef.deposit(pid, 0);
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
        masterchef.withdraw(pid, balanceOfStake());
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

    function setMasterChef(address _masterchef) external onlyGov {
        masterchef = IMasterchef(_masterchef);
        IERC20(getPair()).approve(_masterchef, type(uint256).max);
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
        return masterchef.userInfo(pid, address(this)).amount;
    }

    function pendingReward() public view returns (uint256) {
        return masterchef.pendingBOO(pid, address(this));
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
