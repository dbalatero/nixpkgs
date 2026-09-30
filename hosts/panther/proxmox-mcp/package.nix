{lib, buildNpmPackage, fetchFromGitHub, nodejs}: buildNpmPackage {
  pname = "proxmox-mcp-readonly";
  version = "1.0.0-6186c71";
  inherit nodejs;

  src = fetchFromGitHub {
    owner = "gilby125";
    repo = "mcp-proxmox";
    rev = "6186c715b5ff393adc9fdf597a791c35bc2f90c7";
    hash = "sha256-23JHHHhszwDXehA20Kuz732fQwzCn/equlWEgyD2m/A=";
  };

  postPatch = ''
    cp ${./package-lock.json} package-lock.json
  '';

  npmDepsHash = "sha256-OMccQ+KRbhMauIpQFBr8stqsAzQKnZSlQ7qoqC2xeLw=";
  npmFlags = ["--ignore-scripts"];
  dontNpmBuild = true;
  doCheck = true;
  checkPhase = ''
    runHook preCheck
    for test in test/*.test.js; do
      node "$test"
    done
    runHook postCheck
  '';

  installPhase = ''
    runHook preInstall
    mkdir -p "$out/lib/proxmox-mcp"
    cp -r index.js package.json node_modules LICENSE "$out/lib/proxmox-mcp/"
    # Upstream looks here for .env; keep it empty and immutable.
    touch "$out/lib/.env"
    runHook postInstall
  '';

  meta = {
    description = "Pinned upstream Proxmox MCP server";
    homepage = "https://github.com/gilby125/mcp-proxmox";
    license = lib.licenses.mit;
    platforms = ["x86_64-linux"];
  };
}
