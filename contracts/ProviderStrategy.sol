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
import {BaseStrategy} from "@yearnvaults/contracts/BaseStrategy.sol";

interface IERC20Extended {
    function decimals() external view returns (uint8);

    function name() external view returns (string memory);

    function symbol() external view returns (string memory);
}

contract ProviderStrategy is BaseStrategy {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    address public joint;
    bool public takeProfit;
    bool public investWant;

    constructor(address _vault, address _joint) public BaseStrategy(_vault) {
        _initializeStrat(_joint);
    }

    function initialize(
        address _vault,
        address _strategist,
        address _rewards,
        address _keeper,
        address _joint
    ) external {
        _initialize(_vault, _strategist, _rewards, _keeper);
        _initializeStrat(_joint);
    }

    function _initializeStrat(address _joint) internal {
        require(
            address(joint) == address(0),
            "ProviderStrategy already initialized"
        );
        joint = _joint;
        investWant = true;
        takeProfit = false;
    }

    event Cloned(address indexed clone);

    function cloneProviderStrategy(
        address _vault,
        address _strategist,
        address _rewards,
        address _keeper,
        address _joint
    ) external returns (address newStrategy) {
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
            newStrategy := create(0, clone_code, 0x37)
        }

        ProviderStrategy(newStrategy).initialize(
            _vault,
            _strategist,
            _rewards,
            _keeper,
            _joint
        );

        emit Cloned(newStrategy);
    }

    function name() external view override returns (string memory) {
        return
            string(
                abi.encodePacked(
                    "ProviderOf",
                    IERC20Extended(address(want)).symbol()
                )
            );
    }

    function estimatedTotalAssets() public view override returns (uint256) {
        return want.balanceOf(address(this));
    }

    function prepareReturn(uint256 _debtOutstanding)
        internal
        override
        returns (
            uint256 _profit,
            uint256 _loss,
            uint256 _debtPayment
        )
    {
        // if we are not taking profit, there is nothing to do
        if (!takeProfit) {
            return (0, 0, 0);
        }

        // If we reach this point, it means that we are winding down
        // and we will take profit / losses or pay back debt

        uint256 debt = vault.strategies(address(this)).totalDebt;
        uint256 wantBalance = balanceOfWant();

        // Set profit or loss based on the initial debt
        if (debt <= wantBalance) {
            _profit = wantBalance - debt;
        } else {
            _loss = debt - wantBalance;
        }

        // Repay debt. Amount will depend if we had profit or loss
        if (_debtOutstanding > 0) {
            if (_profit >= 0) {
                _debtPayment = Math.min(
                    _debtOutstanding,
                    wantBalance.sub(_profit)
                );
            } else {
                _debtPayment = Math.min(
                    _debtOutstanding,
                    wantBalance.sub(_loss)
                );
            }
        }
    }

    function adjustPosition(uint256 _debtOutstanding) internal override {
        if (emergencyExit) {
            return;
        }

        // If we shouldn't invest, don't do it :D
        if (!investWant) {
            return;
        }

        uint256 wantBalance = balanceOfWant();
        if (wantBalance > 0) {
            want.transfer(joint, wantBalance);
        }
    }

    function liquidatePosition(uint256 _amountNeeded)
        internal
        override
        returns (uint256 _liquidatedAmount, uint256 _loss)
    {
        uint256 totalAssets = want.balanceOf(address(this));
        if (_amountNeeded > totalAssets) {
            _liquidatedAmount = totalAssets;
            _loss = _amountNeeded.sub(totalAssets);
        } else {
            _liquidatedAmount = _amountNeeded;
        }
    }

    function prepareMigration(address _newStrategy) internal override {
        // Want is sent to the new strategy in the base class
        // nothing to do here
    }

    function protectedTokens()
        internal
        view
        override
        returns (address[] memory)
    {}

    function balanceOfWant() public view returns (uint256) {
        return IERC20(want).balanceOf(address(this));
    }

    function setJoint(address _joint) external onlyAuthorized {
        joint = _joint;
    }

    function setTakeProfit(bool _takeProfit) external onlyAuthorized {
        takeProfit = _takeProfit;
    }

    function setInvestWant(bool _investWant) external onlyAuthorized {
        investWant = _investWant;
    }
}
