{
  description = "Scratch — packages the bits of this repo worth installing";

  # Pinned to the same channel as nixos-configs, so the consuming flake can
  # `follows` this away and only one nixpkgs is ever evaluated.
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

  outputs =
    { self
    , nixpkgs
    ,
    }:
    let
      systems = [ "aarch64-darwin" "x86_64-linux" "aarch64-linux" ];
      forAllSystems = f:
        nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      packages = forAllSystems (pkgs: rec {
        musiclib = pkgs.callPackage ./musiclib/package.nix { };
        default = musiclib;
      });
    };
}
