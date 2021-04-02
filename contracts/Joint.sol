// SPDX-License-Identifier: AGPL-3.0
pragma solidity 0.6.12;
pragma experimental ABIEncoderV2;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/math/SafeMath.sol";
import "@openzeppelin/contracts/math/Math.sol";
import "@openzeppelin/contracts/utils/Address.sol";
import "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";

import "../interfaces/uni/IUniswapV2Router02.sol";
import "../interfaces/uni/IUniswapV2Factory.sol";

interface IERC20Extended {
    function decimals() external view returns (uint8);

    function name() external view returns (string memory);

    function symbol() external view returns (string memory);
}

contract Joint {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    address public tokenA;
    address public providerA;

    address public tokenB;
    address public providerB;
    address public router;

    bool public reinvest;

    address public gov;
    address public pendingGov;
    address public keeper;
    address public strategist;

    constructor(
        address _gov,
        address _keeper,
        address _strategist,
        address _tokenA,
        address _tokenB,
        address _router
    ) public {
        _initialize(_gov, _keeper, _strategist, _tokenA, _tokenB, _router);
    }

    function initialize(
        address _gov,
        address _keeper,
        address _strategist,
        address _tokenA,
        address _tokenB,
        address _router
    ) external {
        _initialize(_gov, _keeper, _strategist, _tokenA, _tokenB, _router);
    }

    function _initialize(
        address _gov,
        address _keeper,
        address _strategist,
        address _tokenA,
        address _tokenB,
        address _router
    ) internal {
        require(address(tokenA) == address(0), "Joint already initialized");

        gov = _gov;
        keeper = _keeper;
        strategist = _strategist;
        tokenA = _tokenA;
        tokenB = _tokenB;
        router = _router;

        reinvest = true;

        IERC20(tokenA).approve(address(router), type(uint256).max);
        IERC20(tokenB).approve(address(router), type(uint256).max);
        IERC20(getPair()).approve(address(router), type(uint256).max);
    }

    event Cloned(address indexed clone);

    function cloneJoint(
        address _gov,
        address _keeper,
        address _strategist,
        address _tokenA,
        address _tokenB,
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

        Joint(newJoint).initialize(
            _gov,
            _keeper,
            _strategist,
            _tokenA,
            _tokenB,
            _router
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

    function harvest() external {
        require(
            msg.sender == strategist ||
                msg.sender == keeper ||
                msg.sender == gov
        );

        // TODO get reward
        swapReward();

        if (reinvest) {
            createLP();
            // TODO invest the lp
        } else {
            liquidatePosition();
            distributeProfit();
        }
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

    function swapReward() internal {
        // TODO: do the uni magic to convert reward into tokenA and tokenB
    }

    function liquidatePosition() internal {
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
            IERC20(tokenA).transfer(providerA, balanceA);
        }

        uint256 balanceB = balanceOfB();
        if (balanceB > 0) {
            IERC20(tokenB).transfer(providerB, balanceB);
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

    function setReinvest(bool _reinvest) external {
        require(msg.sender == strategist || msg.sender == gov);
        reinvest = _reinvest;
    }

    function setProviderA(address _providerA) external {
        require(msg.sender == gov);
        providerA = _providerA;
    }

    function setProviderB(address _providerB) external {
        require(msg.sender == gov);
        providerB = _providerB;
    }

    function setStrategist(address _strategist) external {
        require(msg.sender == gov);
        strategist = _strategist;
    }

    function setKeeper(address _keeper) external {
        require(msg.sender == gov);
        keeper = _keeper;
    }

    function setPendingGovernor(address _pendingGov) external {
        require(msg.sender == gov);
        pendingGov = _pendingGov;
    }

    function acceptGovernor() external {
        require(msg.sender == pendingGov);
        gov = pendingGov;
        pendingGov = address(0);
    }
}
