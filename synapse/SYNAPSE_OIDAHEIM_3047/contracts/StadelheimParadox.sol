// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract StadelheimParadox is ERC721, Ownable {
    uint256 public nextOidaId;
    
    // Oidaheim 3047: VIP-Grid Access
    mapping(uint256 => string) public trackMatrix;

    constructor() ERC721("Stadelheim Paradox (089)", "OIDA") Ownable(msg.sender) {}

    // Mint VIP Access for the Oidaheim 3047 Cyber Grid
    function mintVipAccess(address to, string memory quantumMode) public onlyOwner {
        _safeMint(to, nextOidaId);
        trackMatrix[nextOidaId] = quantumMode;
        nextOidaId++;
    }
}
