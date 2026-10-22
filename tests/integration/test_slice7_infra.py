"""Tests for Slice 7 infrastructure (Dockerfile, docker-compose.yml, CI/CD, Terraform)."""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_dockerfile_structure() -> None:
    dockerfile_path = REPO_ROOT / "Dockerfile"
    assert dockerfile_path.is_file(), "Dockerfile must exist at repository root"
    content = dockerfile_path.read_text(encoding="utf-8")

    # Multi-stage validation: Frontend builder stage
    assert "FROM node:" in content, "Dockerfile must have a Node.js builder stage"
    assert "AS frontend-builder" in content, "Frontend stage should be named frontend-builder"
    assert "npm run build" in content, "Frontend stage must build Next.js static export"

    # Multi-stage validation: Python runtime stage
    assert "FROM python:3.11-slim" in content, "Runtime stage must use python:3.11-slim"
    assert "playwright install" in content, "Runtime stage must install Playwright chromium"
    assert "typst" in content, "Runtime stage must bundle Typst binary"

    # Artifacts & Frontend copied
    assert "COPY --from=frontend-builder" in content, "Must copy compiled frontend from builder"
    assert "EXPOSE 8000" in content, "Must expose unified port 8000"
    assert "job-butler" in content or "uvicorn" in content, "Must define entrypoint"


def test_docker_compose_configuration() -> None:
    compose_path = REPO_ROOT / "docker-compose.yml"
    assert compose_path.is_file(), "docker-compose.yml must exist at repository root"
    data = yaml.safe_load(compose_path.read_text(encoding="utf-8"))

    assert "services" in data, "docker-compose.yml must define services"
    services = data["services"]
    assert "job-butler" in services, "Service must be named job-butler"

    svc = services["job-butler"]
    # Check port binding
    ports = svc.get("ports", [])
    assert any("8000:8000" in str(p) for p in ports), "Must bind port 8000:8000"

    # Check volumes
    volumes = svc.get("volumes", [])
    vol_strs = [str(v) for v in volumes]
    assert any("./data:" in v or "data" in v for v in vol_strs), (
        "Must mount persistent data volume"
    )
    assert any("./artifacts:" in v or "artifacts" in v for v in vol_strs), (
        "Must mount artifacts volume"
    )


def test_terraform_structure() -> None:
    tf_dir = REPO_ROOT / "terraform"
    assert tf_dir.is_dir(), "terraform/ directory must exist"

    # Root files
    assert (tf_dir / "main.tf").is_file()
    assert (tf_dir / "variables.tf").is_file()
    assert (tf_dir / "outputs.tf").is_file()

    # Modules
    for mod in ("ec2", "ebs", "cloudwatch", "ssm"):
        mod_dir = tf_dir / "modules" / mod
        assert mod_dir.is_dir(), f"Module {mod} directory must exist"
        assert (mod_dir / "main.tf").is_file()
        assert (mod_dir / "variables.tf").is_file()
        assert (mod_dir / "outputs.tf").is_file()

    main_content = (tf_dir / "main.tf").read_text(encoding="utf-8")
    assert 'provider "aws"' in main_content
    for mod in ("ec2", "ebs", "cloudwatch", "ssm"):
        assert f'module "{mod}"' in main_content

    # Check CloudWatch module has log group and error alarm
    cw_content = (tf_dir / "modules" / "cloudwatch" / "main.tf").read_text(encoding="utf-8")
    assert "aws_cloudwatch_log_group" in cw_content
    assert "aws_cloudwatch_metric_alarm" in cw_content

