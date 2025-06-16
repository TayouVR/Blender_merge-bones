{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  packages = with pkgs; [
    blender
  ];

  shellHook = ''
    echo "Blender development environment activated"
    echo "Blender version: $(blender --version)"
  '';
}
