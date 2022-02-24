// SPDX-License-Identifier: AGPL-3.0
pragma solidity 0.6.12;
pragma experimental ABIEncoderV2;

import "./NoHedgeJoint.sol";

interface ISolidex {
    struct Amounts {
        uint256 solid;
        uint256 sex;
    }

    function deposit(address _pair, uint256 _amount) external; 
    function withdraw(address _pair, uint256 _amount) external; 
    function getReward(address[] calldata _pairs) external; 
    function pendingRewards(address _account, address[] calldata pairs) external view returns (Amounts[] memory);
    function userBalances(address _account, address _pair) external view returns (uint256);
}

contract SolidexJoint is NoHedgeJoint {
    ISolidex public solidex;
    bool public dontWithdraw;

    bool public isOriginal = true;

    constructor(
        address _providerA,
        address _providerB,
        address _router,
        address _weth,
        address _reward,
        address _solidex
    )
        public
        NoHedgeJoint(
            _providerA,
            _providerB,
            _router,
            _weth,
            _reward
        )
    {
        _initalizeSolidexJoint(_solidex);
    }

    function initialize(
        address _providerA,
        address _providerB,
        address _router,
        address _weth,
        address _reward,
        address _solidex
    ) external {
        _initialize(_providerA, _providerB, _router, _weth, _reward);
        _initalizeSolidexJoint(_solidex);
    }

    function _initalizeSolidexJoint(address _solidex) internal {
        solidex = ISolidex(_solidex);

        IERC20(address(pair)).approve(_solidex, type(uint256).max);
    }

    event Cloned(address indexed clone);

    function cloneSolidexJoint(
        address _providerA,
        address _providerB,
        address _router,
        address _weth,
        address _reward,
        address _solidex
    ) external returns (address newJoint) {
        require(isOriginal, "!original");
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

        SolidexJoint(newJoint).initialize(
            _providerA,
            _providerB,
            _router,
            _weth,
            _reward,
            _solidex
        );

        emit Cloned(newJoint);
    }

    function name() external view override returns (string memory) {
        string memory ab =
            string(
                abi.encodePacked(
                    IERC20Extended(address(tokenA)).symbol(),
                    "-",
                    IERC20Extended(address(tokenB)).symbol()
                )
            );

        return string(abi.encodePacked("NoHedgeSolidexJoint(", ab, ")"));
    }

    function balanceOfStake() public view override returns (uint256) {
        return solidex.userBalances(address(this), address(pair));
    }

    function pendingReward() public view override returns (uint256) {
        address[] memory pairs = new address[](1);
        pairs[0] = address(pair);
        ISolidex.Amounts[] memory pendings = solidex.pendingRewards(address(this), pairs);
        
        uint256 pendingSEX = pendings[0].sex;
        uint256 pendingSOLID = pendings[0].solid;

        // TODO: convert SEX to SOLID and sum to pendingSOLID

        return pendingSOLID;
    }

    function getReward() internal override {
        address[] memory pairs = new address[](1);
        pairs[0] = address(pair);
        solidex.getReward(pairs);
        // TODO: sell SEX for SOLID
    }

    function setDontWithdraw(bool _dontWithdraw) external onlyVaultManagers {
        dontWithdraw = _dontWithdraw;
    }

    function depositLP() internal override {
        if (balanceOfPair() > 0) {
            solidex.deposit(address(pair), balanceOfPair());
        }
    }

    function withdrawLP() internal override {
        uint256 stakeBalance = balanceOfStake();
        if (stakeBalance > 0 && !dontWithdraw) {
            solidex.withdraw(address(pair), stakeBalance);
        }
    }

    function withdrawLPManually(uint256 amount) external onlyVaultManagers {
        solidex.withdraw(address(pair), amount);
    }
}
