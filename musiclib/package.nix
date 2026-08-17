{ lib
, python3
,
}:

python3.pkgs.buildPythonApplication {
  pname = "musiclib";
  version = "0.1.0";
  pyproject = true;

  src = ./.;

  build-system = [ python3.pkgs.hatchling ];

  dependencies = with python3.pkgs; [
    mutagen
    pillow
    requests
    rich
    ruamel-yaml
    typer
  ];

  nativeCheckInputs = with python3.pkgs; [
    mediafile
    pytestCheckHook
  ];

  # VINYL_ROOT and BEETS_CONFIG_DIR are derived from Path.home() as the modules
  # import, and the build sandbox has no home directory of its own.
  preCheck = ''
    export HOME=$(mktemp -d)
  '';

  pythonImportsCheck = [ "musiclib.cli" ];

  meta = {
    description = "Takes a vinyl rip from Audacity export to a verified beets import";
    homepage = "https://github.com/jdheyburn/scratch/tree/main/musiclib";
    license = lib.licenses.asl20;
    mainProgram = "musiclib";
  };
}
