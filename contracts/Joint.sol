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

interface ProviderStrategy {
    function governance() external view returns (address);

    function strategist() external view returns (address);

    function keeper() external view returns (address);

    function want() external view returns (address);
}

contract Joint {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    ProviderStrategy public providerA;
    address public tokenA;
    ProviderStrategy public providerB;
    address public tokenB;

    bool public reinvest;

    address public WETH;
    address public reward;
    address public router;

    uint256 public pid;
    uint256 public ratio = 500;
    uint256 public constant MAX_RATIO = 1000;

    IMasterchef public masterchef;

    modifier onlyGovernance {
        require(
            msg.sender == providerA.governance() ||
                msg.sender == providerB.governance()
        );
        _;
    }

    modifier onlyAuthorized {
        require(
            msg.sender == providerA.governance() ||
                msg.sender == providerB.governance() ||
                msg.sender == providerA.strategist() ||
                msg.sender == providerB.strategist()
        );
        _;
    }

    modifier onlyKeepers {
        require(
            msg.sender == providerA.governance() ||
                msg.sender == providerB.governance() ||
                msg.sender == providerA.strategist() ||
                msg.sender == providerB.strategist() ||
                msg.sender == providerA.keeper() ||
                msg.sender == providerB.keeper()
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
        require(address(tokenA) == address(0), "Joint already initialized");

        providerA = ProviderStrategy(_providerA);
        providerB = ProviderStrategy(_providerB);

        tokenA = providerA.want();
        tokenB = providerB.want();
        router = _router;
        pid = 1;
        reinvest = true;

        masterchef = IMasterchef(
            address(0x05200cB2Cee4B6144B2B2984E246B52bB1afcBD0)
        );
        reward = address(0xf16e81dce15B08F326220742020379B855B87DF9);
        WETH = address(0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83);

        IERC20(getPair()).approve(address(masterchef), type(uint256).max);
        IERC20(tokenA).approve(address(router), type(uint256).max);
        IERC20(tokenB).approve(address(router), type(uint256).max);
        IERC20(getPair()).approve(address(router), type(uint256).max);
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

    function harvest() external onlyKeepers {
        // IF tokenA or tokenB are rewards, we would be swapping all of it
        // Let's save the previous balance before claiming
        uint256 previousBalanceOfReward = balanceOfReward();

        // Gets the reward from the masterchef contract
        getReward();
        uint256 rewardProfit = balanceOfReward().sub(previousBalanceOfReward);
        if (rewardProfit > 0) {
            swapReward(rewardProfit);
        }

        // No capital, nothing to do
        if (balanceOfA() == 0 && balanceOfB() == 0) {
            return;
        }

        if (reinvest) {
            createLP();
            depositLP();
        } else {
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

    function swapReward(uint256 _rewardBal) internal {
        // We don't want to sell reward
        if (ratio == 0) {
            return;
        }

        address swapTo = findSwapTo(reward);
        //Call swap to get more of the of the swapTo token
        IUniswapV2Router02(router)
            .swapExactTokensForTokensSupportingFeeOnTransferTokens(
            _rewardBal.mul(ratio).div(MAX_RATIO),
            0,
            getTokenOutPath(reward, swapTo),
            address(this),
            now
        );
    }

    // If there is a lot of impermanent loss, some capital will need to be sold
    // To make both sides even
    function sellCapital(
        address _tokenFrom,
        address _tokenTo,
        uint256 _amount
    ) public onlyAuthorized {
        IUniswapV2Router02(router)
            .swapExactTokensForTokensSupportingFeeOnTransferTokens(
            _amount,
            0,
            getTokenOutPath(_tokenFrom, _tokenTo),
            address(this),
            now
        );
    }

    function liquidatePosition() public onlyKeepers {
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
        return masterchef.pendingSushi(pid, address(this));
    }

    function setRatio(uint256 _ratio) external onlyAuthorized {
        require(_ratio <= MAX_RATIO);
        ratio = _ratio;
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
