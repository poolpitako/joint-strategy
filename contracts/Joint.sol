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
import "../interfaces/IMasterchef.sol";

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
    address public reward;

    address public tokenB;
    address public providerB;
    address public router;

    bool public reinvest;

    address public gov;
    address public pendingGov;
    address public keeper;
    address public strategist;
    address public WETH;

    uint256 public _pid = 1;

    IMasterchef public masterchef;

    modifier onlyGov {
        require(msg.sender == gov);
        _;
    }

    modifier onlyGovOrStrategist {
        require(msg.sender == gov || msg.sender == strategist);
        _;
    }

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

        getReward();
        swapReward();

        if (reinvest) {
            createLP();
            depositLP();
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

    function setMasterChef(address _masterchef) external onlyGov {
        masterchef = IMasterchef(_masterchef);
        IERC20(getPair()).approve(_masterchef, type(uint256).max);
    }

    function setPid(uint256 _newPid) external onlyGov {
        _pid = _newPid;
    }

    function setWETH(address _weth) external onlyGov {
        WETH = _weth;
    }

    function findSwapTo(address token) internal view returns (address) {
        if (tokenA == token) {
            return tokenB;
        } else if (tokenB == token) {
            return tokenA;
        } else {
            return address(0);
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
        masterchef.deposit(_pid, 0);
    }

    function depositLP() internal {
        if (balanceOfPair() > 0) masterchef.deposit(_pid, balanceOfPair());
    }

    function swapReward() internal {
        bool shouldSwapOnlyOne = tokenA != reward && tokenB != reward;
        uint256 rewardBal = IERC20(reward).balanceOf(address(this));
        //Both tokens arent the reward we are getting,so swap reward to 50/50 ratio of rewards
        if (!shouldSwapOnlyOne) {
            IUniswapV2Router02(router)
                .swapExactTokensForTokensSupportingFeeOnTransferTokens(
                rewardBal / 2,
                0,
                getTokenOutPath(reward, tokenA),
                address(this),
                block.timestamp
            );
            IUniswapV2Router02(router)
                .swapExactTokensForTokensSupportingFeeOnTransferTokens(
                rewardBal / 2,
                0,
                getTokenOutPath(reward, tokenB),
                address(this),
                block.timestamp
            );
        } else {
            address swapTo = findSwapTo(reward);
            require(swapTo != address(0), "!SwapTo");
            //Call swap to get more of the of the swapTo token
            IUniswapV2Router02(router)
                .swapExactTokensForTokensSupportingFeeOnTransferTokens(
                rewardBal / 2,
                0,
                getTokenOutPath(reward, swapTo),
                address(this),
                block.timestamp
            );
        }
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

    function setReinvest(bool _reinvest) external onlyGovOrStrategist {
        reinvest = _reinvest;
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

    function setKeeper(address _keeper) external onlyGovOrStrategist {
        keeper = _keeper;
    }

    function setPendingGovernor(address _pendingGov) external onlyGov {
        pendingGov = _pendingGov;
    }

    function acceptGovernor() external {
        require(msg.sender == pendingGov);
        gov = pendingGov;
        pendingGov = address(0);
    }
}
