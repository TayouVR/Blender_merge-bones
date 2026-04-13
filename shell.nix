{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  packages = with pkgs; [
    blender
    python3
  ];

  shellHook = ''
    echo "Blender development environment activated"
    echo "Blender version: $(blender --version)"
  '';
}
