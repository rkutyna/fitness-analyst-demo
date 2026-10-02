"""Structural checks on the deployment files. They parse the YAML as text (PyYAML
is not a dependency) and exist to catch the mistakes that would be expensive
to find on first run: publishing from a pull request, widening a token's
permissions, putting an id in a file, or making the deploy fail before Azure
is set up."""
import re
import subprocess
from pathlib import Path

import pytest

from .conftest import ROOT

CI = (ROOT / ".github/workflows/ci.yml").read_text()
DEPLOY = (ROOT / ".github/workflows/deploy.yml").read_text()
BICEP = (ROOT / "infra/main.bicep").read_text()


def jobs(text: str) -> dict[str, str]:
    """Split a workflow into {job name: its text} using the two-space job keys."""
    body = text.split("\njobs:\n", 1)[1]
    parts = re.split(r"(?m)^  ([A-Za-z0-9_-]+):\s*$", body)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts), 2)}


def header(text: str) -> str:
    return text.split("\njobs:\n", 1)[0]


def test_ci_publishes_only_from_the_publish_job_on_main_pushes():
    publish = jobs(CI)["publish"]
    assert re.search(r"(?m)^    needs: \[test, image\]$", publish)
    cond = re.search(r"(?m)^    if: (.+)$", publish).group(1)
    assert "github.event_name == 'push'" in cond
    assert "github.ref == 'refs/heads/main'" in cond
    assert "ghcr.io/rkutyna/fitness-analyst-demo" in publish
    assert "platforms: linux/amd64" in publish
    assert "steps.push.outputs.digest" in publish
    assert "type=raw,value=latest" in publish and "type=sha" in publish
    assert "org.opencontainers.image.source" in publish
    assert "org.opencontainers.image.revision" in publish
    # The workflow publishes nowhere else.
    for name, text in jobs(CI).items():
        if name != "publish":
            assert "push: true" not in text and "login-action" not in text, name


def test_only_the_publish_job_can_write_packages():
    assert CI.count("packages: write") == 1
    assert "packages: write" in jobs(CI)["publish"]
    assert re.search(r"(?m)^permissions:\n  contents: read\n(?!  )", header(CI))
    assert "packages: write" not in header(CI)


def test_actions_are_pinned_to_a_major_version():
    for text in (CI, DEPLOY):
        for ref in re.findall(r"(?m)^\s*-?\s*uses: (\S+)", text):
            if ref.startswith("./"):
                continue
            assert re.search(r"@v\d+$", ref), ref


def test_ci_deploy_job_calls_the_reusable_workflow_with_the_published_digest():
    deploy = jobs(CI)["deploy"]
    assert "needs: publish" in deploy
    assert "uses: ./.github/workflows/deploy.yml" in deploy
    assert "needs.publish.outputs.digest" in deploy
    assert "vars.AZURE_CLIENT_ID != ''" in deploy
    assert deploy.count("id-token: write") == 1
    assert "id-token: write" not in header(CI)


def test_deploy_uses_oidc_with_variables_not_secrets():
    assert re.search(r"(?m)^permissions:\n  id-token: write\n  contents: read\n(?!  )", header(DEPLOY))
    assert "azure/login@v2" in DEPLOY
    for name in ("AZURE_CLIENT_ID", "AZURE_TENANT_ID", "AZURE_SUBSCRIPTION_ID"):
        assert f"vars.{name}" in DEPLOY
        assert f"secrets.{name}" not in DEPLOY
    assert "vars.AZURE_RESOURCE_GROUP" in DEPLOY
    assert "workflow_dispatch" in DEPLOY and "workflow_call" in DEPLOY
    assert "environment: production" in DEPLOY
    assert "packages: write" not in DEPLOY
    # No client secret is ever used.
    assert "creds:" not in DEPLOY and "client-secret" not in DEPLOY


def test_deploy_is_skipped_until_azure_is_bootstrapped_and_checks_health():
    job = jobs(DEPLOY)["deploy"]
    assert re.search(r"(?m)^    if: \$\{\{ vars\.AZURE_CLIENT_ID != '' \}\}$", job)
    assert "az deployment group create" in job
    assert "infra/main.bicep" in job
    assert "/healthz" in job and "seq 1" in job and "exit 1" in job


def test_bicep_has_the_documented_parameters_and_outputs():
    for param in ("location", "appName", "image", "minReplicas", "maxReplicas",
                  "budgetContactEmail", "budgetAmount", "customDomain", "managedCertificateName"):
        assert re.search(rf"(?m)^param {param} ", BICEP), param
    assert "allowInsecure: false" in BICEP
    assert "targetPort: 8080" in BICEP
    assert "activeRevisionsMode: 'Single'" in BICEP
    assert not re.search(r"(?m)^\s*(registries|secrets):", BICEP)
    for out in ("fqdn", "customDomainVerificationId", "environmentName"):
        assert re.search(rf"(?m)^output {out} ", BICEP), out


SCANNED = [".github", "infra", "scripts", "docs"]
GUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def scanned_files():
    out = subprocess.run(["git", "ls-files", *SCANNED], cwd=ROOT, capture_output=True, text=True)
    tracked = [ROOT / line for line in out.stdout.splitlines()]
    # Untracked-but-present files count too: scan the directories directly.
    found = {p for d in SCANNED for p in (ROOT / d).rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    return sorted(set(tracked) | found)


@pytest.mark.parametrize("path", scanned_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_deployment_files_carry_no_ids_emails_or_home_paths(path):
    text = path.read_text(errors="replace")
    assert not GUID.search(text), "a GUID-shaped string"
    assert not EMAIL.search(text), "an email address"
    assert "/Users/" not in text
